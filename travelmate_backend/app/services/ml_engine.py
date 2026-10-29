from pathlib import Path
import sys
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

SERVICE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SERVICE_DIR.parents[1]
PROJECT_DIR = BACKEND_DIR.parent

ML_DIR = PROJECT_DIR / "datasets" / "ml"

MODEL_PATH = ML_DIR / "travelmate_recommender_final.pkl"
FEATURES_PATH = ML_DIR / "destination_features.csv"

if not ML_DIR.joinpath("recommendation_features.py").is_file():
    raise FileNotFoundError(
        f"recommendation_features.py not found in {ML_DIR}"
    )

if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

class MLEngine:
    def __init__(self):
        self.model = None
        self.destinations = None
        self._feature_names = None

        ml_path = str(ML_DIR)
        if ml_path not in sys.path:
            sys.path.insert(0, ml_path)

        from recommendation_features import BUDGET_VALUES

        self.budget_values = BUDGET_VALUES

    def _load_artifacts(self):
        if self.model is not None and self.destinations is not None:
            return

        if not MODEL_PATH.is_file():
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

        if not FEATURES_PATH.is_file():
            raise FileNotFoundError(
                f"Destination features not found: {FEATURES_PATH}"
            )

        model = joblib.load(MODEL_PATH)
        destinations = pd.read_csv(
            FEATURES_PATH,
            dtype={"destination_id": str},
        )

        if destinations.empty:
            raise ValueError("The destination feature dataset is empty.")

        feature_names = getattr(model, "feature_names_in_", None)

        if feature_names is None and hasattr(model, "named_steps"):
            preprocessor = model.named_steps.get("preprocessing")
            if preprocessor is not None:
                feature_names = getattr(
                    preprocessor, "feature_names_in_", None
                )

        if feature_names is None and hasattr(model, "named_steps"):
            for step in model.named_steps.values():
                feature_names = getattr(step, "feature_names_in_", None)
                if feature_names is not None:
                    break

        self.model = model
        self.destinations = destinations
        self._feature_names = (
            list(feature_names) if feature_names is not None else None
        )

    @staticmethod
    def _season_months(season):
        season = str(season or "").strip().casefold()
        mapping = {
            "summer": {3, 4, 5},
            "monsoon": {6, 7, 8, 9},
            "winter": {11, 12, 1, 2},
            "spring": {2, 3, 4},
            "autumn": {9, 10, 11},
        }
        return mapping.get(season, set())

    @staticmethod
    def _parse_season_range(value):
        if pd.isna(value):
            return set()

        value = str(value).strip().casefold()
        if "all year" in value or value == "year":
            return set(range(1, 13))

        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        parts = [
            part.strip()
            for part in value.replace("/", "-").split("-")
        ]
        if len(parts) != 2:
            return set()

        start = month_map.get(parts[0][:3])
        end = month_map.get(parts[1][:3])
        if start is None or end is None:
            return set()

        if start <= end:
            return set(range(start, end + 1))
        return set(range(start, 13)) | set(range(1, end + 1))

    def _season_match(self, preferred_season, destination_season):
        user_months = self._season_months(preferred_season)
        if not user_months:
            user_months = self._parse_season_range(preferred_season)

        destination_months = self._parse_season_range(destination_season)
        if not user_months or not destination_months:
            return 0.0

        return len(user_months & destination_months) / len(user_months)

    @staticmethod
    def _destination_budget_level(value):
        if pd.isna(value):
            return np.nan
        if value <= 15000:
            return 1
        if value <= 40000:
            return 2
        return 3

    def _build_features(self, user_profile):
        df = self.destinations.copy()

        required_destination_columns = {
            "destination_id", "destination_name", "category",
            "average_budget", "best_season",
        }
        missing = required_destination_columns - set(df.columns)
        if missing:
            raise ValueError(
                f"Destination dataset is missing columns: {sorted(missing)}"
            )

        for field in (
            "age", "travel_style", "budget",
            "preferred_category", "preferred_season",
        ):
            df[field] = user_profile[field]

        df["category_match"] = (
            df["category"].fillna("").astype(str).str.casefold()
            == str(user_profile["preferred_category"]).strip().casefold()
        ).astype(int)

        budget_levels = {"Low": 1, "Medium": 2, "High": 3}
        user_level = budget_levels[user_profile["budget"]]
        df["budget_difference"] = (
            user_level
            - df["average_budget"].apply(self._destination_budget_level)
        ).abs()

        df["season_match"] = df["best_season"].apply(
            lambda season: self._season_match(
                user_profile["preferred_season"], season
            )
        )

        if "avg_hotel_price" not in df:
            df["avg_hotel_price"] = np.nan
        if "avg_hotel_rating" not in df:
            df["avg_hotel_rating"] = np.nan

        df["hotel_price_to_budget"] = (
            pd.to_numeric(df["avg_hotel_price"], errors="coerce")
            / pd.to_numeric(df["average_budget"], errors="coerce").replace(
                0, np.nan
            )
        )
        df["hotel_rating_available"] = (
            df["avg_hotel_rating"].notna().astype(int)
        )

        optional_numeric = [
            "ideal_duration", "num_hotels", "min_hotel_price",
            "max_hotel_price", "num_hotel_types", "num_attractions",
            "avg_attraction_rating", "num_attraction_categories",
            "num_activities", "avg_activity_price", "avg_activity_duration",
            "num_activity_categories", "has_adventure_activities",
            "num_restaurants", "num_cuisine_types",
            "avg_restaurant_rating", "avg_restaurant_price_level",
            "num_packages", "avg_package_price", "avg_package_days",
            "avg_package_nights", "num_package_partners",
            "has_hotel_data", "has_attraction_data", "has_activity_data",
            "has_restaurant_data", "has_package_data", "has_weather_data",
            "has_booking_data", "has_review_data", "total_bookings",
            "avg_booking_value", "confirmed_booking_rate", "total_reviews",
            "avg_review_rating", "pct_high_rating_reviews",
            "avg_annual_temperature", "temperature_volatility",
            "avg_annual_rainfall", "avg_humidity",
            "num_favorable_weather_months",
        ]
        for column in optional_numeric:
            if column not in df.columns:
                df[column] = np.nan

        if self._feature_names:
            absent = [c for c in self._feature_names if c not in df.columns]
            if absent:
                raise ValueError(
                    "The saved model expects feature columns that cannot "
                    f"be built from destination_features.csv: {absent}. "
                    "Check that the model and feature dataset are from "
                    "the same training run."
                )
            features = df[self._feature_names].copy()
        else:
            from recommendation_features import MODEL_FEATURES
            absent = [c for c in MODEL_FEATURES if c not in df.columns]
            if absent:
                raise ValueError(
                    f"Cannot build model features: {absent}"
                )
            features = df[MODEL_FEATURES].copy()

        return df, features

    def train(self, data=None):
        raise NotImplementedError(
            "Train the model offline; this engine only loads saved artifacts."
        )

    def recommend_profile(
        self,
        user_profile: Dict,
        top_k: int = 10,
        category_filter: Optional[str] = None,
    ) -> List[Dict]:
        required = [
            "age", "travel_style", "budget",
            "preferred_category", "preferred_season",
        ]
        missing = [
            field for field in required
            if field not in user_profile
            or user_profile[field] is None
            or str(user_profile[field]).strip() == ""
        ]
        if missing:
            raise ValueError(f"Missing required profile fields: {missing}")

        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20.")

        if user_profile["budget"] not in self.budget_values:
            raise ValueError("budget must be Low, Medium, or High.")
        self._load_artifacts()
        if callable(getattr(self, "build_features", None)):
            enriched, features = self.build_features(
                user_profile,
                self.destinations.copy(),
            )
        else:
            enriched, features = self._build_features(user_profile)

        probabilities = self.model.predict_proba(features)
        classes = list(getattr(self.model, "classes_", []))

        positive_index = classes.index(1) if 1 in classes else len(classes) - 1
        enriched["ml_score"] = probabilities[:, positive_index]

        budget_limit = self.budget_values[user_profile["budget"]]
        destination_budget = pd.to_numeric(
            enriched["average_budget"], errors="coerce"
        )
        enriched["budget_compatibility"] = (
            1 - (
                (destination_budget - budget_limit).clip(lower=0)
                / budget_limit
            )
        ).clip(0, 1).fillna(0.5)

        enriched["recommendation_score"] = enriched["ml_score"]

        effective_category = category_filter or user_profile.get("preferred_category")
        if effective_category:
            mask = (
                enriched["category"].fillna("").astype(str).str.strip()
                .str.casefold()
                == str(effective_category).strip().casefold()
            )
            filtered = enriched.loc[mask]
            if not filtered.empty:
                enriched = filtered

        # Budget hard constraint: for Low budget, prefer destinations within budget limit
        if user_profile.get("budget") == "Low":
            dest_b = pd.to_numeric(enriched["average_budget"], errors="coerce")
            within_budget = enriched.loc[dest_b.isna() | (dest_b <= budget_limit)]
            if not within_budget.empty:
                enriched = within_budget

        ranked = enriched.sort_values(
            "ml_score", ascending=False, kind="mergesort"
        ).head(top_k)

        output_columns = [
            "destination_id", "destination_name", "state", "city",
            "category", "average_budget", "ideal_duration", "ml_score",
            "category_match", "season_match", "budget_compatibility",
            "recommendation_score",
        ]
        output_columns = [
            col for col in output_columns if col in ranked.columns
        ]

        results = []
        for rank_idx, record in enumerate(ranked[output_columns].to_dict(orient="records")):
            clean = {}
            for key, value in record.items():
                if pd.isna(value):
                    clean[key] = None
                elif hasattr(value, "item"):
                    clean[key] = value.item()
                else:
                    clean[key] = value
            # Qualitative match label without fabricating fake percentage numbers
            if rank_idx == 0:
                clean["match_label"] = "Top Match"
            elif rank_idx == 1:
                clean["match_label"] = "Great Match"
            else:
                clean["match_label"] = "Recommended Match"
            results.append(clean)

        return results

ml_engine = MLEngine()