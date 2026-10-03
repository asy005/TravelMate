from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
INPUT = BASE_DIR / "user_destination_candidates.csv"
OUTPUT = BASE_DIR / "ml_training_features.csv"


def parse_season_range(value):
    if pd.isna(value):
        return set()

    value = str(value).strip().lower()

    if "all year" in value or value == "year":
        return set(range(1, 13))

    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    parts = [p.strip() for p in value.replace("/", "-").split("-")]

    if len(parts) != 2:
        return set()

    start = month_map.get(parts[0][:3])
    end = month_map.get(parts[1][:3])

    if start is None or end is None:
        return set()

    if start <= end:
        return set(range(start, end + 1))

    return set(range(start, 13)) | set(range(1, end + 1))


def season_match(user_season, destination_season):
    user_months = parse_season_range(user_season)
    destination_months = parse_season_range(destination_season)

    if not user_months or not destination_months:
        return 0

    return int(bool(user_months & destination_months))


df = pd.read_csv(
    INPUT,
    dtype={
        "user_id": str,
        "destination_id": str,
    },
)

df["interaction_target"] = df["interaction_observed"].astype(int)

df["category_match"] = (
    df["preferred_category"].fillna("").str.lower()
    == df["category"].fillna("").str.lower()
).astype(int)

budget_map = {
    "Low": 1,
    "Medium": 2,
    "High": 3,
}

df["user_budget_level"] = df["budget"].map(budget_map)

df["destination_budget_level"] = pd.cut(
    df["average_budget"],
    bins=[-np.inf, 15000, 40000, np.inf],
    labels=[1, 2, 3],
).astype(float)

df["budget_difference"] = (
    df["user_budget_level"]
    - df["destination_budget_level"]
).abs()

df["season_match"] = [
    season_match(user_season, destination_season)
    for user_season, destination_season
    in zip(df["preferred_season"], df["best_season"])
]

df["hotel_price_to_budget"] = (
    df["avg_hotel_price"]
    / df["average_budget"].replace(0, np.nan)
)

df["hotel_rating_available"] = (
    df["avg_hotel_rating"].notna().astype(int)
)

numeric_features = [
    "age",
    "average_budget",
    "ideal_duration",
    "num_hotels",
    "avg_hotel_price",
    "min_hotel_price",
    "max_hotel_price",
    "avg_hotel_rating",
    "num_hotel_types",
    "num_attractions",
    "avg_attraction_rating",
    "num_attraction_categories",
    "num_activities",
    "avg_activity_price",
    "avg_activity_duration",
    "num_activity_categories",
    "has_adventure_activities",
    "num_restaurants",
    "num_cuisine_types",
    "avg_restaurant_rating",
    "avg_restaurant_price_level",
    "num_packages",
    "avg_package_price",
    "avg_package_days",
    "avg_package_nights",
    "num_package_partners",
    "has_hotel_data",
    "has_attraction_data",
    "has_activity_data",
    "has_restaurant_data",
    "has_package_data",
    "has_weather_data",
    "category_match",
    "budget_difference",
    "season_match",
    "hotel_price_to_budget",
    "hotel_rating_available",
]

categorical_features = [
    "travel_style",
    "budget",
    "preferred_category",
    "preferred_season",
    "category",
    "state",
]

columns = (
    [
        "user_id",
        "destination_id",
        "interaction_target",
    ]
    + categorical_features
    + numeric_features
)

features = df[columns].copy()

for col in numeric_features:
    features[col] = pd.to_numeric(
        features[col],
        errors="coerce",
    )

for col in categorical_features:
    features[col] = (
        features[col]
        .fillna("Unknown")
        .astype(str)
    )

assert len(features) == len(df)
assert features["user_id"].notna().all()
assert features["destination_id"].notna().all()
assert set(features["interaction_target"].unique()) <= {0, 1}
assert set(features["season_match"].unique()) <= {0, 1}

features.to_csv(
    OUTPUT,
    index=False,
)

print("=" * 60)
print("ML FEATURE DATASET")
print("=" * 60)
print(f"Shape: {features.shape}")
print(
    f"Positive samples: "
    f"{(features['interaction_target'] == 1).sum()}"
)
print(
    f"Unobserved samples: "
    f"{(features['interaction_target'] == 0).sum()}"
)
print(f"Unique users: {features['user_id'].nunique()}")
print(
    f"Unique destinations: "
    f"{features['destination_id'].nunique()}"
)
print(f"Numeric features: {len(numeric_features)}")
print(f"Categorical features: {len(categorical_features)}")
print(f"Season matches: {features['season_match'].sum()}")
print(f"Saved to: {OUTPUT}")