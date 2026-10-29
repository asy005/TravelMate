import pandas as pd
import joblib

from recommendation_features import (
    BUDGET_VALUES,
    build_user_destination_features,
)

DESTINATION_FILE = "destination_features.csv"
MODEL_FILE = "travelmate_recommender_final.pkl"
ML_WEIGHT = 0.55
CATEGORY_WEIGHT = 0.25
SEASON_WEIGHT = 0.15
BUDGET_WEIGHT = 0.05

model = joblib.load(MODEL_FILE)
destinations = pd.read_csv(
    DESTINATION_FILE,
    dtype={"destination_id": str},
)

def recommend(user_profile, top_k=5):
    required_fields = [
        "age",
        "travel_style",
        "budget",
        "preferred_category",
        "preferred_season",
    ]

    missing_fields = [
        field for field in required_fields
        if field not in user_profile
        or user_profile[field] is None
        or str(user_profile[field]).strip() == ""
    ]

    if missing_fields:
        raise ValueError(
            f"Missing required profile fields: {missing_fields}"
        )

    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    enriched_df, features = build_user_destination_features(
        user_profile,
        destinations,
    )

    enriched_df["ml_score"] = model.predict_proba(features)[:, 1]

    category_match = (
        enriched_df["category_match"]
        .fillna(0)
        .astype(float)
        .clip(0, 1)
    )

    season_match = (
        enriched_df["season_match"]
        .fillna(0)
        .astype(float)
        .clip(0, 1)
    )

    user_budget_limit = BUDGET_VALUES.get(
        user_profile["budget"],
        BUDGET_VALUES["Medium"],
    )

    destination_budgets = pd.to_numeric(
        enriched_df["average_budget"],
        errors="coerce",
    )

    budget_compatibility = (
        1
        - (
            (destination_budgets - user_budget_limit)
            .clip(lower=0)
            / user_budget_limit
        )
    ).clip(0, 1)

    budget_compatibility = budget_compatibility.fillna(0.5)

    enriched_df["budget_compatibility"] = budget_compatibility

    enriched_df["recommendation_score"] = (
        ML_WEIGHT * enriched_df["ml_score"]
        + CATEGORY_WEIGHT * category_match
        + SEASON_WEIGHT * season_match
        + BUDGET_WEIGHT * budget_compatibility
    )

    ranked = enriched_df.sort_values(
        by="recommendation_score",
        ascending=False,
        kind="mergesort",
    )

    return ranked.head(top_k)

if __name__ == "__main__":
    user_profile = {
        "age": 22,
        "travel_style": "Solo",
        "budget": "Medium",
        "preferred_category": "Hill Station",
        "preferred_season": "Winter",
    }

    recommendations = recommend(user_profile, top_k=10)

    print("\n" + "=" * 45)
    print("TRAVELMATE — PERSONALIZED RECOMMENDATIONS")
    print("=" * 45)

    columns = [
        "destination_id",
        "destination_name",
        "state",
        "city",
        "category",
        "average_budget",
        "ideal_duration",
        "ml_score",
        "category_match",
        "season_match",
        "budget_compatibility",
        "recommendation_score",
    ]

    print(
        recommendations[columns].to_string(
            index=False,
            float_format=lambda value: f"{value:.4f}",
        )
    )