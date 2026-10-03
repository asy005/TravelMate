from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent

users = pd.read_csv(DATA_DIR / "users.csv", dtype={"user_id": str})
destinations = pd.read_csv(BASE_DIR / "destination_features.csv", dtype={"destination_id": str})
observed = pd.read_csv(
    BASE_DIR / "user_destination_training.csv",
    dtype={"user_id": str, "destination_id": str},
)

observed["interaction_observed"] = 1

user_cols = [
    "user_id", "age", "gender", "travel_style", "budget",
    "preferred_category", "preferred_season"
]

interaction_cols = [
    "booking_count", "successful_booking_count", "cancelled_booking_count",
    "has_booking", "has_successful_booking", "review_count",
    "user_review_rating", "average_user_review_rating", "has_review",
    "interaction_label", "interaction_type"
]

dest_id = destinations["destination_id"].astype(str)
all_destinations = dest_id.tolist()

observed_by_user = observed.groupby("user_id")["destination_id"].apply(set).to_dict()
rng = np.random.default_rng(42)

unobserved_rows = []

for _, user in users.iterrows():
    user_id = str(user["user_id"])
    seen = observed_by_user.get(user_id, set())

    available = [d for d in all_destinations if d not in seen]

    observed_count = len(seen)
    sample_count = min(observed_count * 3, 30, len(available))

    if sample_count == 0:
        continue

    sampled = rng.choice(available, size=sample_count, replace=False)

    for destination_id in sampled:
        row = user[user_cols].to_dict()
        row["destination_id"] = str(destination_id)

        destination_row = destinations[
            destinations["destination_id"] == str(destination_id)
        ].iloc[0]

        for col in destinations.columns:
            if col != "destination_id":
                row[col] = destination_row[col]

        row.update({
            "booking_count": 0,
            "successful_booking_count": 0,
            "cancelled_booking_count": 0,
            "has_booking": 0,
            "has_successful_booking": 0,
            "review_count": 0,
            "user_review_rating": np.nan,
            "average_user_review_rating": np.nan,
            "has_review": 0,
            "interaction_label": np.nan,
            "interaction_type": "unobserved",
            "interaction_observed": 0,
        })

        unobserved_rows.append(row)

unobserved = pd.DataFrame(unobserved_rows)

for col in observed.columns:
    if col not in unobserved.columns:
        unobserved[col] = np.nan

for col in unobserved.columns:
    if col not in observed.columns:
        observed[col] = np.nan

unobserved = unobserved[observed.columns]

candidates = pd.concat([observed, unobserved], ignore_index=True)

candidates["user_id"] = candidates["user_id"].astype(str)
candidates["destination_id"] = candidates["destination_id"].astype(str)

candidates = candidates.drop_duplicates(
    subset=["user_id", "destination_id"],
    keep="first"
).reset_index(drop=True)

assert len(observed) == 597
assert candidates["user_id"].isin(users["user_id"].astype(str)).all()
assert candidates["destination_id"].isin(dest_id).all()
assert not candidates.duplicated(["user_id", "destination_id"]).any()
assert set(candidates["interaction_observed"].dropna().unique()).issubset({0, 1})

observed_pairs = set(
    zip(observed["user_id"], observed["destination_id"])
)
final_observed_pairs = set(
    zip(
        candidates.loc[candidates["interaction_observed"] == 1, "user_id"],
        candidates.loc[candidates["interaction_observed"] == 1, "destination_id"]
    )
)

assert observed_pairs == final_observed_pairs

output_path = BASE_DIR / "user_destination_candidates.csv"
candidates.to_csv(output_path, index=False)

print("=" * 60)
print("USER-DESTINATION CANDIDATE DATASET")
print("=" * 60)
print(f"Shape: {candidates.shape}")
print(f"Observed rows: {(candidates['interaction_observed'] == 1).sum()}")
print(f"Unobserved rows: {(candidates['interaction_observed'] == 0).sum()}")
print(f"Unique users: {candidates['user_id'].nunique()}")
print(f"Unique destinations: {candidates['destination_id'].nunique()}")

rows_per_user = candidates.groupby("user_id").size()
print(f"Rows/user - min: {rows_per_user.min()}")
print(f"Rows/user - median: {rows_per_user.median()}")
print(f"Rows/user - max: {rows_per_user.max()}")

print("\nValidation: PASSED")
print(f"Saved to: {output_path}")