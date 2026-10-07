import numpy as np
import pandas as pd

SEASON_MONTHS = {
    "Summer": {3, 4, 5},
    "Monsoon": {6, 7, 8, 9},
    "Winter": {11, 12, 1, 2},
    "Spring": {2, 3, 4},
    "Autumn": {9, 10, 11},
}

BUDGET_LEVELS = {
    "Low": 1,
    "Medium": 2,
    "High": 3,
}

BUDGET_VALUES = {
    "Low": 2000,
    "Medium": 5000,
    "High": 10000,
}

MODEL_FEATURES = [
    "age",
    "travel_style",
    "budget",
    "preferred_category",
    "preferred_season",

    "category_match",
    "budget_difference",
    "season_match",

    "hotel_price_to_budget",
    "hotel_rating_available",

    "average_budget",
    "ideal_duration",

    "avg_hotel_price",
    "min_hotel_price",
    "max_hotel_price",
    "avg_hotel_rating",

    "avg_package_price",
    "avg_package_days",
    "avg_package_nights",

    "avg_restaurant_rating",
    "avg_restaurant_price_level",

    "avg_attraction_rating",

    "has_weather_data",
]

def parse_season_range(value):

    if pd.isna(value):
        return set()

    value = str(value).strip()

    if value in SEASON_MONTHS:
        return SEASON_MONTHS[value]

    parts = [
        part.strip()
        for part in value.replace("–", "-").split("-")
    ]

    months = set()

    for part in parts:
        if part in SEASON_MONTHS:
            months.update(
                SEASON_MONTHS[part]
            )

    return months

def calculate_season_match(
    user_season,
    destination_season
):

    user_months = parse_season_range(
        user_season
    )

    destination_months = parse_season_range(
        destination_season
    )

    if not user_months or not destination_months:
        return 0

    return int(
        bool(
            user_months.intersection(
                destination_months
            )
        )
    )

def destination_budget_level(average_budget):
    if pd.isna(average_budget):
        return np.nan

    if average_budget <= 15000:
        return 1

    if average_budget <= 40000:
        return 2

    return 3

def calculate_budget_difference(
    user_budget,
    destination_average_budget
):
    user_level = BUDGET_LEVELS.get(
        user_budget,
        BUDGET_LEVELS["Medium"]
    )

    destination_level_name = (
        destination_budget_level(
            destination_average_budget
        )
    )

    destination_level = BUDGET_LEVELS[
        destination_level_name
    ]

    return abs(
        user_level - destination_level
    )

def build_user_destination_features(
    user_profile,
    destinations
):

    df = destinations.copy()

    df["age"] = user_profile["age"]

    df["travel_style"] = user_profile["travel_style"]

    df["budget"] = user_profile["budget"]

    df["preferred_category"] = (
        user_profile["preferred_category"]
    )

    df["preferred_season"] = (
        user_profile["preferred_season"]
    )

    df["category_match"] = (
        df["category"].fillna("").str.lower()
        ==
        str(user_profile["preferred_category"]).lower()
    ).astype(int)

    # Match the exact budget logic used during ML training
    destination_budget_levels = (
        df["average_budget"]
        .apply(destination_budget_level)
    )

    user_budget_levels = df["budget"].map(BUDGET_LEVELS)

    df["budget_difference"] = (
        user_budget_levels
        - destination_budget_levels
    ).abs()

    df["season_match"] = df.apply(
        lambda row:
        calculate_season_match(
            user_profile["preferred_season"],
            row["best_season"]
        ),
        axis=1
    )

    # Match the exact feature definition used during ML training
    df["hotel_price_to_budget"] = (
        df["avg_hotel_price"]
        / df["average_budget"].replace(0, np.nan)
    )

    df["hotel_rating_available"] = (
        df["avg_hotel_rating"]
        .notna()
        .astype(int)
    )

    return df, df[MODEL_FEATURES].copy()