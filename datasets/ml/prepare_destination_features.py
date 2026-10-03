"""
prepare_destination_features.py
--------------------------------
TravelMate ML Pipeline - Step 1: Destination Feature Engineering

Built against the CONFIRMED, EXACT column schemas for each source CSV. No
column is assumed beyond what was explicitly listed. Two columns whose
*values* (not names) were not specified up front -- restaurants.price_range
and bookings.status -- are inspected at runtime before any numeric
conversion is applied. This script does NOT train any model.

CONFIRMED SCHEMAS (exact column names, nothing added)
------------------------------------------------------
destinations.csv : destination_id, destination_name, state, city, category,
                    description, best_season, average_budget, ideal_duration
hotels.csv       : hotel_id, destination_id, hotel_name, city_hotel,
                    state_hotel, hotel_type, address, price_per_night,
                    rating, amenities, latitude, longitude
attractions.csv  : attraction_id, destination_id, attraction_name, city,
                    state, category, entry_fee, rating, latitude, longitude
activities.csv   : activity_id, destination_id, activity_name, category,
                    price, duration, best_season
restaurants.csv  : restaurant_id, destination_id, restaurant_name, city,
                    cuisine, price_range, rating, address, latitude,
                    longitude
packages.csv     : package_id, partner_id, destination_id, package_name,
                    days, nights, includes_hotel, includes_transport,
                    meals_included, guide_included, price, description
partners.csv     : partner_id, business_name, partner_type, address, phone,
                    email, gst_number, city, state, rating
users.csv        : user_id, age, gender, travel_style, budget,
                    preferred_category, preferred_season
reviews.csv      : review_id, user_id, hotel_id, package_id, rating,
                    review_text, date, images
bookings.csv     : booking_id, user_id, hotel_id, package_id, booking_type,
                    travel_date, amount, status
weather.csv      : destination_id, month, average_temperature, rainfall,
                    humidity, weather_type

CONFIRMED FACTS THIS SCRIPT RELIES ON
---------------------------------------
- Exactly 614 destinations.
- destination_id is a STRING (e.g. "D0001") -- never cast to int, anywhere.
- Every hotel/attraction/activity/restaurant/package has a valid
  destination_id (so no dropna is needed on those direct joins).
- bookings.csv / reviews.csv each have EITHER hotel_id OR package_id
  populated per row (never both, never neither) -- resolved to a
  destination via hotels.destination_id / packages.destination_id.
- hotels.csv has NO partner_id -- hotel-partner linkage is not available
  and no such feature is fabricated.
- packages.csv DOES have partner_id -- used for num_package_partners.
- partners.csv has NO status column -- no "verified partner" feature is
  fabricated from it. It is loaded (per the load requirement) but not
  aggregated into any destination feature.
- bookings.csv has NO num_travelers column -- no traveler-count feature is
  created.
- packages.csv has NO category column -- no package-category feature is
  created.
- users.csv is intentionally NOT aggregated (reserved for the later
  user-destination recommendation training step).

WHY LEFT JOINS + explicit 0 vs. NaN handling
----------------------------------------------
Every source table is aggregated independently, then LEFT-joined onto the
full 614-row destinations table. Count-type features (num_hotels, etc.) are
filled with 0 when a destination has no matching rows, because "zero
hotels" is a known fact. Average/rating/price features are left as NaN in
that case, because we do not know what the average would have been --
filling with 0 or a global mean would fabricate data.

DATA-AVAILABILITY FLAGS (added after the aggregate features)
---------------------------------------------------------------
Eight binary columns -- has_hotel_data, has_attraction_data,
has_activity_data, has_restaurant_data, has_package_data, has_booking_data,
has_review_data, has_weather_data -- record whether a destination has AT
LEAST ONE matching record in that source table, independent of what the
aggregate feature values happen to be. These are computed directly from
the raw source tables (via the same destination-resolution logic used for
bookings/reviews), not derived from the count columns, so they remain
correct even if a count column's fill logic ever changes. They are always
exactly 0 or 1 -- never NaN -- since "does at least one record exist" is
always a knowable fact, unlike an average.
"""

import os
import sys
import re
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "destination_features.csv")

EXPECTED_DESTINATION_COUNT = 614
DEST_ID = "destination_id"


# ---------------------------------------------------------------------------
# LOADING
# destination_id (wherever it appears) is forced to string dtype at load
# time so it can never be silently cast to int downstream by pandas.
# ---------------------------------------------------------------------------

def load_csv(filename: str, string_id_cols=None) -> pd.DataFrame:
    path = os.path.join(DATASETS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Required dataset not found: {path}\n"
            f"Expected all source CSVs in: {DATASETS_DIR}"
        )
    dtype = {col: str for col in (string_id_cols or [])}
    return pd.read_csv(path, dtype=dtype)


def load_all_datasets() -> dict:
    data = {
        "destinations": load_csv("destinations.csv", [DEST_ID]),
        "hotels": load_csv("hotels.csv", [DEST_ID]),
        "attractions": load_csv("attractions.csv", [DEST_ID]),
        "activities": load_csv("activities.csv", [DEST_ID]),
        "restaurants": load_csv("restaurants.csv", [DEST_ID]),
        "packages": load_csv("packages.csv", [DEST_ID]),
        "partners": load_csv("partners.csv"),
        "users": load_csv("users.csv"),
        "reviews": load_csv("reviews.csv"),
        "bookings": load_csv("bookings.csv"),
        "weather": load_csv("weather.csv", [DEST_ID]),
    }
    print("Loaded datasets (source files are only ever read, never written to):")
    for name, df in data.items():
        print(f"  - {name:<12} {len(df):>6} rows, {len(df.columns):>2} columns")
    return data


# ---------------------------------------------------------------------------
# ID MAPPING: bookings/reviews reference a hotel OR a package, never a
# destination directly. Resolve via whichever FK is populated.
# ---------------------------------------------------------------------------

def map_to_destination(df: pd.DataFrame, hotels: pd.DataFrame, packages: pd.DataFrame) -> pd.Series:
    hotel_to_dest = hotels.set_index("hotel_id")[DEST_ID]
    package_to_dest = packages.set_index("package_id")[DEST_ID]

    via_hotel = df["hotel_id"].map(hotel_to_dest)
    via_package = df["package_id"].map(package_to_dest)

    # Exactly one of hotel_id/package_id is populated per confirmed facts,
    # so exactly one of these two lookups will produce a non-null value.
    resolved = via_hotel.fillna(via_package)
    return resolved


# ---------------------------------------------------------------------------
# "INSPECT REAL DATA FIRST" HELPERS
# Two columns' *values* were not specified in the confirmed schema:
# restaurants.price_range and bookings.status. Both are inspected at
# runtime and the chosen conversion is printed, rather than assuming a
# format (e.g. "$"/"$$"/"$$$") that may not match the real data.
# ---------------------------------------------------------------------------

def infer_price_range_mapping(price_range_series: pd.Series) -> dict:
    """
    Inspects the actual unique values of restaurants.price_range and
    decides how to convert them to a numeric price level:
      1. If values are already numeric (or numeric-looking strings) -> use as-is.
      2. Elif values are repeated-symbol strings (e.g. '$', '$$', '$$$') ->
         map by symbol count.
      3. Elif values are recognizable ordinal words (budget/moderate/
         expensive, low/medium/high, etc.) -> map via a small ordinal
         dictionary, ONLY for words we can confidently order.
      4. Otherwise -> no numeric mapping is invented; the feature is left
         as NaN for all rows and this is printed clearly, rather than
         guessing at an order that isn't actually in the data.
    """
    uniques = sorted(price_range_series.dropna().unique().tolist(), key=str)
    print(f"\n[price_range inspection] Unique values found: {uniques}")

    # Case 1: already numeric
    try:
        pd.to_numeric(pd.Series(uniques))
        print("[price_range inspection] Values are numeric -> using as-is.")
        return {v: float(v) for v in uniques}
    except (ValueError, TypeError):
        pass

    # Case 2: repeated-symbol strings, e.g. '$', '$$', '$$$'
    symbol_pattern = re.compile(r"^(.)\1*$")
    if all(isinstance(v, str) and symbol_pattern.match(v) for v in uniques):
        mapping = {v: len(v) for v in uniques}
        print(f"[price_range inspection] Detected repeated-symbol pattern -> mapping by length: {mapping}")
        return mapping

    # Case 3: recognizable ordinal words
    ordinal_vocab = {
        "budget": 1, "low": 1, "cheap": 1, "inexpensive": 1,
        "moderate": 2, "medium": 2, "mid": 2, "mid-range": 2, "average": 2,
        "expensive": 3, "high": 3, "premium": 3, "luxury": 3,
    }
    normalized = {v: ordinal_vocab.get(str(v).strip().lower()) for v in uniques}
    if all(val is not None for val in normalized.values()):
        print(f"[price_range inspection] Detected ordinal words -> mapping: {normalized}")
        return normalized

    print(
        "[price_range inspection] Could not confidently determine an order for "
        f"these values: {uniques}. avg_restaurant_price_level will be left as "
        "NaN for all rows rather than inventing an ordering."
    )
    return {}


def infer_success_statuses(status_series: pd.Series) -> set:
    """
    Inspects the actual unique values of bookings.status and identifies
    which ones represent a "successful" booking, via case-insensitive
    substring matching against common success-related keywords. Values that
    don't match anything are reported but NOT guessed at.
    """
    uniques = sorted(status_series.dropna().unique().tolist(), key=str)
    print(f"\n[booking status inspection] Unique values found: {uniques}")

    success_keywords = ("confirm", "complet", "success", "paid")
    success_values = {
        v for v in uniques
        if any(kw in str(v).lower() for kw in success_keywords)
    }

    unclassified = set(uniques) - success_values
    print(f"[booking status inspection] Classified as SUCCESS: {sorted(success_values, key=str)}")
    print(f"[booking status inspection] Not classified as success (treated as not-successful): {sorted(unclassified, key=str)}")

    return success_values


# ---------------------------------------------------------------------------
# PER-SOURCE FEATURE BUILDERS
# ---------------------------------------------------------------------------

def build_hotel_features(hotels: pd.DataFrame) -> pd.DataFrame:
    grouped = hotels.groupby(DEST_ID)
    return pd.DataFrame({
        "num_hotels": grouped.size(),
        "avg_hotel_price": grouped["price_per_night"].mean(),
        "min_hotel_price": grouped["price_per_night"].min(),
        "max_hotel_price": grouped["price_per_night"].max(),
        "avg_hotel_rating": grouped["rating"].mean(),
        "num_hotel_types": grouped["hotel_type"].nunique(),
    })


def build_attraction_features(attractions: pd.DataFrame) -> pd.DataFrame:
    grouped = attractions.groupby(DEST_ID)
    return pd.DataFrame({
        "num_attractions": grouped.size(),
        "avg_attraction_rating": grouped["rating"].mean(),
        "num_attraction_categories": grouped["category"].nunique(),
    })


def build_activity_features(activities: pd.DataFrame) -> pd.DataFrame:
    grouped = activities.groupby(DEST_ID)
    features = pd.DataFrame({
        "num_activities": grouped.size(),
        "avg_activity_price": grouped["price"].mean(),
        "avg_activity_duration": grouped["duration"].mean(),
        "num_activity_categories": grouped["category"].nunique(),
    })

    # has_adventure_activities: binary flag, 1 if any activity at this
    # destination has a category containing an adventure-related keyword.
    adventure_keywords = ("adventure", "trek", "hike", "climb", "raft", "safari")
    category_lower = activities["category"].astype(str).str.lower()
    is_adventure = category_lower.str.contains("|".join(adventure_keywords), na=False)
    features["has_adventure_activities"] = (
        is_adventure.groupby(activities[DEST_ID]).max().astype(int)
    )
    return features


def build_restaurant_features(restaurants: pd.DataFrame, price_mapping: dict) -> pd.DataFrame:
    grouped = restaurants.groupby(DEST_ID)
    features = pd.DataFrame({
        "num_restaurants": grouped.size(),
        "num_cuisine_types": grouped["cuisine"].nunique(),
        "avg_restaurant_rating": grouped["rating"].mean(),
    })

    if price_mapping:
        numeric_price_level = restaurants["price_range"].map(price_mapping)
        features["avg_restaurant_price_level"] = (
            numeric_price_level.groupby(restaurants[DEST_ID]).mean()
        )
    else:
        features["avg_restaurant_price_level"] = np.nan

    return features


def build_package_features(packages: pd.DataFrame) -> pd.DataFrame:
    grouped = packages.groupby(DEST_ID)
    return pd.DataFrame({
        "num_packages": grouped.size(),
        "avg_package_price": grouped["price"].mean(),
        "avg_package_days": grouped["days"].mean(),
        "avg_package_nights": grouped["nights"].mean(),
        "num_package_partners": grouped["partner_id"].nunique(),
    })


def build_booking_features(
    bookings: pd.DataFrame, hotels: pd.DataFrame, packages: pd.DataFrame, success_statuses: set
) -> pd.DataFrame:
    resolved = bookings.copy()
    resolved[DEST_ID] = map_to_destination(bookings, hotels, packages)

    unmapped = resolved[DEST_ID].isna().sum()
    if unmapped:
        print(f"WARNING: {unmapped} booking(s) could not be mapped to a destination "
              f"(expected 0 per confirmed facts) -- these rows are excluded from booking features.")
    resolved = resolved.dropna(subset=[DEST_ID])

    grouped = resolved.groupby(DEST_ID)
    features = pd.DataFrame({
        "total_bookings": grouped.size(),
        "avg_booking_value": grouped["amount"].mean(),
    })

    is_success = resolved["status"].isin(success_statuses).astype(int)
    features["confirmed_booking_rate"] = is_success.groupby(resolved[DEST_ID]).mean()

    return features


def build_review_features(reviews: pd.DataFrame, hotels: pd.DataFrame, packages: pd.DataFrame) -> pd.DataFrame:
    resolved = reviews.copy()
    resolved[DEST_ID] = map_to_destination(reviews, hotels, packages)

    unmapped = resolved[DEST_ID].isna().sum()
    if unmapped:
        print(f"WARNING: {unmapped} review(s) could not be mapped to a destination "
              f"(expected 0 per confirmed facts) -- these rows are excluded from review features.")
    resolved = resolved.dropna(subset=[DEST_ID])

    grouped = resolved.groupby(DEST_ID)
    features = pd.DataFrame({
        "total_reviews": grouped.size(),
        "avg_review_rating": grouped["rating"].mean(),
    })

    is_high = (resolved["rating"] >= 4.0).astype(int)
    features["pct_high_rating_reviews"] = is_high.groupby(resolved[DEST_ID]).mean()

    return features


def build_weather_features(weather: pd.DataFrame) -> pd.DataFrame:
    """
    num_favorable_weather_months is a HEURISTIC, not ground truth: a month
    is counted as favorable if average_temperature falls in a comfortable
    band (15-30 C) AND rainfall is low (<= 100 mm). weather_type is loaded
    but NOT used in this heuristic, since its actual category values were
    not part of the confirmed schema detail.
    """
    grouped = weather.groupby(DEST_ID)
    features = pd.DataFrame({
        "avg_annual_temperature": grouped["average_temperature"].mean(),
        "temperature_volatility": grouped["average_temperature"].std(),
        "avg_annual_rainfall": grouped["rainfall"].mean(),
        "avg_humidity": grouped["humidity"].mean(),
    })

    comfortable_temp_min, comfortable_temp_max = 15, 30
    low_rainfall_max_mm = 100
    is_favorable = (
        weather["average_temperature"].between(comfortable_temp_min, comfortable_temp_max)
        & (weather["rainfall"] <= low_rainfall_max_mm)
    ).astype(int)
    features["num_favorable_weather_months"] = (
        is_favorable.groupby(weather[DEST_ID]).sum()
    )

    return features


# ---------------------------------------------------------------------------
# DATA-AVAILABILITY FLAGS
# Computed directly from the raw source tables (independent of the
# aggregate feature values above), so they stay correct even if the
# aggregate columns' fill logic ever changes.
# ---------------------------------------------------------------------------

FLAG_COLUMNS = [
    "has_hotel_data", "has_attraction_data", "has_activity_data",
    "has_restaurant_data", "has_package_data", "has_booking_data",
    "has_review_data", "has_weather_data",
]


def build_availability_flags(
    destination_ids: pd.Index, data: dict, mapped_booking_dest_ids: pd.Series, mapped_review_dest_ids: pd.Series
) -> pd.DataFrame:
    flags = pd.DataFrame(index=destination_ids)

    flags["has_hotel_data"] = destination_ids.isin(data["hotels"][DEST_ID].unique())
    flags["has_attraction_data"] = destination_ids.isin(data["attractions"][DEST_ID].unique())
    flags["has_activity_data"] = destination_ids.isin(data["activities"][DEST_ID].unique())
    flags["has_restaurant_data"] = destination_ids.isin(data["restaurants"][DEST_ID].unique())
    flags["has_package_data"] = destination_ids.isin(data["packages"][DEST_ID].unique())
    flags["has_booking_data"] = destination_ids.isin(mapped_booking_dest_ids.dropna().unique())
    flags["has_review_data"] = destination_ids.isin(mapped_review_dest_ids.dropna().unique())
    flags["has_weather_data"] = destination_ids.isin(data["weather"][DEST_ID].unique())

    for col in FLAG_COLUMNS:
        flags[col] = flags[col].astype(int)

    return flags


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

# Count-type columns where "no matching rows" legitimately means 0.
COUNT_COLUMNS = {
    "num_hotels", "num_hotel_types",
    "num_attractions", "num_attraction_categories",
    "num_activities", "num_activity_categories", "has_adventure_activities",
    "num_restaurants", "num_cuisine_types",
    "num_packages", "num_package_partners",
    "total_bookings", "total_reviews",
    "num_favorable_weather_months",
}


def build_feature_table(data: dict, price_mapping: dict, success_statuses: set) -> pd.DataFrame:
    destinations = data["destinations"]

    base_cols = [
        "destination_id", "destination_name", "state", "city", "category",
        "description", "best_season", "average_budget", "ideal_duration",
    ]
    features = destinations[base_cols].copy().set_index(DEST_ID)

    # Resolved once here, then reused for both the booking/review aggregate
    # features AND the has_booking_data / has_review_data flags below, so
    # the mapping logic is never duplicated.
    mapped_booking_dest_ids = map_to_destination(data["bookings"], data["hotels"], data["packages"])
    mapped_review_dest_ids = map_to_destination(data["reviews"], data["hotels"], data["packages"])

    blocks = {
        "hotels": build_hotel_features(data["hotels"]),
        "attractions": build_attraction_features(data["attractions"]),
        "activities": build_activity_features(data["activities"]),
        "restaurants": build_restaurant_features(data["restaurants"], price_mapping),
        "packages": build_package_features(data["packages"]),
        "bookings": build_booking_features(data["bookings"], data["hotels"], data["packages"], success_statuses),
        "reviews": build_review_features(data["reviews"], data["hotels"], data["packages"]),
        "weather": build_weather_features(data["weather"]),
    }

    for block in blocks.values():
        features = features.join(block, how="left")

    for col in features.columns:
        if col in COUNT_COLUMNS:
            features[col] = features[col].fillna(0)
        # All other columns (averages/ratings/prices/weather stats) are
        # intentionally left as NaN when there's no underlying data --
        # unaffected by the flags added below.

    # Availability flags are appended LAST, after every existing aggregate
    # feature column, per the requirement that they go at the end of the
    # table. They are always 0/1, never NaN.
    flags = build_availability_flags(features.index, data, mapped_booking_dest_ids, mapped_review_dest_ids)
    features = features.join(flags, how="left")

    return features.reset_index()


def validate_feature_table(features: pd.DataFrame, destinations: pd.DataFrame) -> None:
    n_rows = len(features)
    n_unique = features[DEST_ID].nunique()

    assert n_rows == EXPECTED_DESTINATION_COUNT, (
        f"Expected exactly {EXPECTED_DESTINATION_COUNT} destinations, found {n_rows}."
    )
    assert n_unique == EXPECTED_DESTINATION_COUNT, (
        f"destination_id is not unique: {n_rows} rows but only {n_unique} unique IDs."
    )

    original_ids = set(destinations[DEST_ID])
    feature_ids = set(features[DEST_ID])
    missing = original_ids - feature_ids
    assert not missing, f"{len(missing)} original destination(s) were lost: {sorted(missing)[:10]}"

    assert features[DEST_ID].map(lambda x: isinstance(x, str)).all(), (
        "destination_id must remain a string throughout -- found a non-string value."
    )

    for col in FLAG_COLUMNS:
        valid_values = set(features[col].unique().tolist())
        assert valid_values <= {0, 1}, (
            f"{col} must contain only 0 or 1 -- found: {valid_values}"
        )

    print("\nValidation passed:")
    print(f"  - Exactly {n_rows} destinations present")
    print(f"  - All destination_id values unique")
    print(f"  - No original destination lost")
    print(f"  - destination_id preserved as string dtype throughout")
    print(f"  - All 8 availability flags contain only 0/1 values")


def print_summary(features: pd.DataFrame) -> None:
    numeric_cols = features.select_dtypes(include=[np.number]).columns.tolist()
    missing_counts = features[numeric_cols].isna().sum()
    missing_report = missing_counts[missing_counts > 0]

    print("\n" + "=" * 60)
    print("DESTINATION FEATURE TABLE SUMMARY")
    print("=" * 60)
    print(f"Shape: {features.shape[0]} rows x {features.shape[1]} columns")
    print(f"\nColumns ({len(features.columns)}):")
    for col in features.columns:
        print(f"  - {col}")

    print(f"\nNumeric feature columns: {len(numeric_cols)}")
    if len(missing_report) > 0:
        print("\nColumns with missing values (legitimately unknown, not fabricated):")
        for col, count in missing_report.items():
            pct = 100 * count / len(features)
            print(f"  - {col:<30} {count:>4} missing ({pct:.1f}%)")
    else:
        print("\nNo missing values in numeric columns.")

    print("\nData availability across destinations:")
    for col in FLAG_COLUMNS:
        count_with_data = int(features[col].sum())
        pct = 100 * count_with_data / len(features)
        source_label = col.replace("has_", "").replace("_data", "")
        print(f"  - Destinations with {source_label:<12}: {count_with_data:>4} / {len(features)} ({pct:.1f}%)")
    print("=" * 60 + "\n")


def main():
    print(f"Reading source datasets from: {DATASETS_DIR}")
    print("(These files are opened read-only -- this script never writes back to them.)\n")
    data = load_all_datasets()

    price_mapping = infer_price_range_mapping(data["restaurants"]["price_range"])
    success_statuses = infer_success_statuses(data["bookings"]["status"])

    print("\nBuilding destination-level feature table...")
    features = build_feature_table(data, price_mapping, success_statuses)

    print("\nValidating feature table...")
    validate_feature_table(features, data["destinations"])

    os.makedirs(SCRIPT_DIR, exist_ok=True)
    features.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved feature table to: {OUTPUT_PATH}")

    print_summary(features)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, AssertionError) as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)