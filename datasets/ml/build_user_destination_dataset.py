import os
import sys
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

DESTINATION_FEATURES_PATH = os.path.join(SCRIPT_DIR, "destination_features.csv")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "user_destination_training.csv")

DEST_ID = "destination_id"
USER_ID = "user_id"

def load_csv(path: str, string_id_cols=None) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required dataset not found: {path}")
    dtype = {col: str for col in (string_id_cols or [])}
    return pd.read_csv(path, dtype=dtype)


def load_all_datasets() -> dict:
    data = {
        "users": load_csv(os.path.join(DATASETS_DIR, "users.csv")),
        "bookings": load_csv(os.path.join(DATASETS_DIR, "bookings.csv")),
        "reviews": load_csv(os.path.join(DATASETS_DIR, "reviews.csv")),
        "hotels": load_csv(os.path.join(DATASETS_DIR, "hotels.csv"), [DEST_ID]),
        "packages": load_csv(os.path.join(DATASETS_DIR, "packages.csv"), [DEST_ID]),
        "destination_features": load_csv(DESTINATION_FEATURES_PATH, [DEST_ID]),
    }
    print("Loaded datasets (read-only -- source files are never modified):")
    for name, df in data.items():
        print(f"  - {name:<22} {len(df):>6} rows, {len(df.columns):>2} columns")
    return data

def map_to_destination(df: pd.DataFrame, hotels: pd.DataFrame, packages: pd.DataFrame) -> pd.Series:
    hotel_to_dest = hotels.set_index("hotel_id")[DEST_ID]
    package_to_dest = packages.set_index("package_id")[DEST_ID]

    via_hotel = df["hotel_id"].map(hotel_to_dest)
    via_package = df["package_id"].map(package_to_dest)
    return via_hotel.fillna(via_package)

def classify_booking_statuses(status_series: pd.Series) -> tuple:
    uniques = sorted(status_series.dropna().unique().tolist(), key=str)
    print(f"\n[booking status inspection] Unique values found: {uniques}")

    success_keywords = ("confirm", "complet", "success", "paid")
    cancel_keywords = ("cancel", "refund", "fail", "reject")

    success_statuses = {v for v in uniques if any(k in str(v).lower() for k in success_keywords)}
    cancelled_statuses = {v for v in uniques if any(k in str(v).lower() for k in cancel_keywords)}

    overlap = success_statuses & cancelled_statuses
    if overlap:
        print(f"WARNING: status value(s) matched BOTH success and cancel keywords: {overlap} "
              f"-- treated as success (cancel classification removed for these).")
        cancelled_statuses -= overlap

    other = set(uniques) - success_statuses - cancelled_statuses
    print(f"[booking status inspection] SUCCESS statuses: {sorted(success_statuses, key=str)}")
    print(f"[booking status inspection] CANCELLED statuses: {sorted(cancelled_statuses, key=str)}")
    print(f"[booking status inspection] Other (not successful, not cancelled): {sorted(other, key=str)}")

    return success_statuses, cancelled_statuses

def build_booking_interactions(bookings: pd.DataFrame, hotels: pd.DataFrame, packages: pd.DataFrame,
                                success_statuses: set, cancelled_statuses: set) -> pd.DataFrame:
    resolved = bookings.copy()
    resolved[DEST_ID] = map_to_destination(bookings, hotels, packages)

    unmapped = resolved[DEST_ID].isna().sum()
    if unmapped:
        print(f"WARNING: {unmapped} booking(s) could not be resolved to a destination "
              f"(missing/unknown hotel_id or package_id) -- excluded from interactions.")
    resolved = resolved.dropna(subset=[DEST_ID, USER_ID])

    resolved["_is_success"] = resolved["status"].isin(success_statuses).astype(int)
    resolved["_is_cancelled"] = resolved["status"].isin(cancelled_statuses).astype(int)

    grouped = resolved.groupby([USER_ID, DEST_ID])
    booking_interactions = pd.DataFrame({
        "booking_count": grouped.size(),
        "successful_booking_count": grouped["_is_success"].sum(),
        "cancelled_booking_count": grouped["_is_cancelled"].sum(),
    }).reset_index()

    booking_interactions["has_booking"] = (booking_interactions["booking_count"] > 0).astype(int)
    booking_interactions["has_successful_booking"] = (
        booking_interactions["successful_booking_count"] > 0
    ).astype(int)

    return booking_interactions

def build_review_interactions(reviews: pd.DataFrame, hotels: pd.DataFrame, packages: pd.DataFrame) -> pd.DataFrame:
    resolved = reviews.copy()
    resolved[DEST_ID] = map_to_destination(reviews, hotels, packages)

    unmapped = resolved[DEST_ID].isna().sum()
    if unmapped:
        print(f"WARNING: {unmapped} review(s) could not be resolved to a destination "
              f"(missing/unknown hotel_id or package_id) -- excluded from interactions.")
    resolved = resolved.dropna(subset=[DEST_ID, USER_ID])

    grouped = resolved.groupby([USER_ID, DEST_ID])
    review_interactions = pd.DataFrame({
        "review_count": grouped.size(),
        "user_review_rating": grouped["rating"].mean(),
        "average_user_review_rating": grouped["rating"].mean(),
    }).reset_index()

    review_interactions["has_review"] = (review_interactions["review_count"] > 0).astype(int)

    return review_interactions

def combine_interactions(booking_interactions: pd.DataFrame, review_interactions: pd.DataFrame) -> pd.DataFrame:
    combined = pd.merge(
        booking_interactions, review_interactions,
        on=[USER_ID, DEST_ID], how="outer",
    )
    zero_fill_cols = [
        "booking_count", "successful_booking_count", "cancelled_booking_count",
        "has_booking", "has_successful_booking", "review_count", "has_review",
    ]
    for col in zero_fill_cols:
        combined[col] = combined[col].fillna(0).astype(int)

    return combined

def assign_label_and_type(combined: pd.DataFrame) -> pd.DataFrame:
    has_success = combined["has_successful_booking"] == 1
    has_review = combined["has_review"] == 1
    has_booking_only_failed = (combined["has_booking"] == 1) & (~has_success)

    combined["interaction_label"] = np.select(
        [has_success | has_review, has_booking_only_failed],
        [1, 0],
        default=np.nan,
    )

    combined["interaction_type"] = np.select(
        [has_success, has_review, has_booking_only_failed],
        ["successful_booking", "review", "booking_not_successful"],
        default="none",
    )

    return combined

USER_FEATURE_COLS = [
    "age", "gender", "travel_style", "budget", "preferred_category", "preferred_season",
]


def join_user_features(combined: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    user_cols = [USER_ID] + [c for c in USER_FEATURE_COLS if c in users.columns]
    return combined.merge(users[user_cols], on=USER_ID, how="left")


def join_destination_features(combined: pd.DataFrame, destination_features: pd.DataFrame) -> pd.DataFrame:
    return combined.merge(destination_features, on=DEST_ID, how="left")

def validate_dataset(df: pd.DataFrame, users: pd.DataFrame, destination_features: pd.DataFrame) -> None:
    assert df[USER_ID].notna().all(), "Found row(s) with a missing user_id."
    assert df[DEST_ID].notna().all(), "Found row(s) with a missing destination_id."
    assert (df[DEST_ID].astype(str).str.len() > 0).all(), "Found row(s) with an empty destination_id."
    dup_count = df.duplicated(subset=[USER_ID, DEST_ID]).sum()
    assert dup_count == 0, f"Found {dup_count} duplicate (user_id, destination_id) pair(s)."
    known_destinations = set(destination_features[DEST_ID])
    unknown_destinations = set(df[DEST_ID]) - known_destinations
    assert not unknown_destinations, (
        f"{len(unknown_destinations)} destination_id(s) not found in destination_features.csv: "
        f"{sorted(unknown_destinations)[:10]}"
    )
    known_users = set(users[USER_ID])
    unknown_users = set(df[USER_ID]) - known_users
    assert not unknown_users, (
        f"{len(unknown_users)} user_id(s) not found in users.csv: {sorted(unknown_users)[:10]}"
    )
    label_values = set(df["interaction_label"].dropna().unique().tolist())
    assert label_values <= {0, 1}, f"interaction_label contains unexpected values: {label_values}"
    assert df[DEST_ID].map(lambda x: isinstance(x, str)).all(), (
        "destination_id must remain a string throughout -- found a non-string value."
    )

    print("\nValidation passed:")
    print(f"  - All user_id / destination_id values present and valid")
    print(f"  - No duplicate (user_id, destination_id) pairs")
    print(f"  - All destination_id values exist in destination_features.csv")
    print(f"  - All user_id values exist in users.csv")
    print(f"  - interaction_label contains only 0, 1, or NaN")
    print(f"  - destination_id preserved as string dtype throughout")

def print_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("USER-DESTINATION INTERACTION DATASET SUMMARY")
    print("=" * 60)
    print(f"Row count: {len(df)}")
    print(f"Unique users: {df[USER_ID].nunique()}")
    print(f"Unique destinations: {df[DEST_ID].nunique()}")

    print("\nInteraction type counts:")
    for itype, count in df["interaction_type"].value_counts().items():
        print(f"  - {itype:<22} {count}")

    print("\nInteraction label counts (NaN = no observed interaction; "
          "not produced by this script, see assign_label_and_type docstring):")
    label_counts = df["interaction_label"].value_counts(dropna=False)
    for label, count in label_counts.items():
        label_display = "NaN" if pd.isna(label) else int(label)
        print(f"  - {label_display}: {count}")

    print("\nMissing-value summary (non-zero columns only):")
    missing = df.isna().sum()
    missing = missing[missing > 0]
    if len(missing) > 0:
        for col, count in missing.items():
            pct = 100 * count / len(df)
            print(f"  - {col:<30} {count:>5} missing ({pct:.1f}%)")
    else:
        print("  (none)")
    print("=" * 60 + "\n")

def main():
    print(f"Reading source datasets from: {DATASETS_DIR}")
    print(f"Reading destination features from: {DESTINATION_FEATURES_PATH}")
    print("(All source files are opened read-only -- this script never writes back to them.)\n")

    data = load_all_datasets()

    success_statuses, cancelled_statuses = classify_booking_statuses(data["bookings"]["status"])

    print("\nBuilding booking-based interactions...")
    booking_interactions = build_booking_interactions(
        data["bookings"], data["hotels"], data["packages"], success_statuses, cancelled_statuses
    )

    print("Building review-based interactions...")
    review_interactions = build_review_interactions(data["reviews"], data["hotels"], data["packages"])

    print("Combining booking and review interactions into one row per (user, destination)...")
    combined = combine_interactions(booking_interactions, review_interactions)

    print("Assigning interaction_label and interaction_type...")
    combined = assign_label_and_type(combined)

    print("Joining user features...")
    combined = join_user_features(combined, data["users"])

    print("Joining destination features...")
    combined = join_destination_features(combined, data["destination_features"])

    print("\nValidating dataset...")
    validate_dataset(combined, data["users"], data["destination_features"])

    os.makedirs(SCRIPT_DIR, exist_ok=True)
    combined.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved user-destination interaction dataset to: {OUTPUT_PATH}")

    print_summary(combined)
if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, AssertionError) as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)