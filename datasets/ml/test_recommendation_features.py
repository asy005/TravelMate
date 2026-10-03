import pandas as pd
from recommendation_features import (
    build_user_destination_features,
    MODEL_FEATURES,
)

DESTINATION_FILE = "destination_features.csv"

destinations = pd.read_csv(
    DESTINATION_FILE
)

user = {
    "age": 22,
    "travel_style": "Solo",
    "budget": "Medium",
    "preferred_category": "Hill Station",
    "preferred_season": "Winter",
}

enriched, features = (
    build_user_destination_features(
        user,
        destinations
    )
)

print("====================================")
print("FEATURE ENGINEERING TEST")
print("====================================")

print(
    "Destination rows:",
    len(enriched)
)

print(
    "ML feature rows:",
    len(features)
)

print(
    "ML feature columns:",
    len(features.columns)
)

print(
    "Expected feature columns:",
    len(MODEL_FEATURES)
)

print("\nFirst destination:")
print(
    features.iloc[0].to_dict()
)

print("\nValidation:")

if len(enriched) == 614:
    print("PASS: All 614 destinations processed.")
else:
    print(
        "FAIL: Expected 614 destinations."
    )

if len(features.columns) == 23:
    print("PASS: 23 ML features generated.")
else:
    print(
        "FAIL: Expected 23 ML features."
    )

if list(features.columns) == MODEL_FEATURES:
    print(
        "PASS: Feature order matches model."
    )
else:
    print(
        "FAIL: Feature order mismatch."
    )