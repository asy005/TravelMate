"""
seed_csv_reviews.py
-------------------
Imports review records from datasets/reviews.csv into PostgreSQL.

Safe / Idempotent Behaviour
---------------------------
- Uses csv_review_id (e.g. "REV00001") as the deduplication key.
  A row is skipped if a Review with the same csv_review_id already exists.
- Never deletes or modifies existing reviews (including user-submitted ones).
- Ratings outside [1.0, 5.0] are rejected and counted as validation errors.
- Hotel/package identifiers are resolved by matching:
    hotels:   datasets/hotels.csv  hotel_id -> hotel_name -> DB Hotel.name
    packages: datasets/packages.csv package_id -> package_name -> DB Package.title
  If the entity cannot be resolved, the row is skipped and logged.
- Sentiment is computed for every imported review.
- Verifies local development target before execution.

Usage
-----
    cd travelmate_backend
    python scripts/seed_csv_reviews.py [--dry-run] [--verbose]

Options
-------
    --dry-run   Print what would happen without writing to the database.
    --verbose   Log each row's outcome regardless of status.
"""
import sys
from pathlib import Path

# Configure utf-8 stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import csv
import argparse
from datetime import date

from app.config import settings
from app.database import SessionLocal
from app.models.hotel import Hotel
from app.models.package import Package
from app.models.review import Review
# Ensure all models are imported so FK relationships are resolved at engine level
from app.models.user import User  # noqa: F401
from app.models.favorites import Favorite  # noqa: F401
from app.models.destination import Destination  # noqa: F401
from app.models.partner import Partner  # noqa: F401
from app.models.booking import Booking  # noqa: F401
from app.services.sentiment_analyser import classify_review

CSV_REVIEWS_PATH = BACKEND_DIR.parent / "datasets" / "reviews.csv"
CSV_HOTELS_PATH  = BACKEND_DIR.parent / "datasets" / "hotels.csv"
CSV_PACKAGES_PATH = BACKEND_DIR.parent / "datasets" / "packages.csv"


# ---------------------------------------------------------------------------
# Safety guard
# ---------------------------------------------------------------------------

def verify_local_development_target():
    """Refuse to run against remote / production environments."""
    host = (settings.POSTGRES_HOST or "").strip().lower()
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if host not in local_hosts:
        raise RuntimeError(
            f"Refusing to seed: target database host '{host}' is not a verified "
            f"local development host {local_hosts}."
        )
    env = (getattr(settings, "ENVIRONMENT", "") or "development").strip().lower()
    if env in ("production", "prod"):
        raise RuntimeError(
            f"Refusing to seed: environment is '{env}'. "
            "Seeding is forbidden in production."
        )


# ---------------------------------------------------------------------------
# CSV lookup helpers
# ---------------------------------------------------------------------------

def _load_hotel_name_map() -> dict[str, str]:
    """Return {hotel_id -> hotel_name} from datasets/hotels.csv."""
    mapping: dict[str, str] = {}
    with open(CSV_HOTELS_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            hid = (row.get("hotel_id") or "").strip()
            name = (row.get("hotel_name") or "").strip()
            if hid and name:
                mapping[hid] = name
    return mapping


def _load_package_title_map() -> dict[str, str]:
    """Return {package_id -> package_name} from datasets/packages.csv."""
    mapping: dict[str, str] = {}
    with open(CSV_PACKAGES_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            pid = (row.get("package_id") or "").strip()
            name = (row.get("package_name") or "").strip()
            if pid and name:
                mapping[pid] = name
    return mapping


def _safe_float(value: str, *, default=None):
    v = (value or "").strip()
    if not v:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _parse_date(value: str) -> date | None:
    """Parse DD-MM-YYYY dates from the CSV; return None on failure."""
    v = (value or "").strip()
    if not v:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

def seed(dry_run: bool = False, verbose: bool = False) -> dict:
    """
    Import reviews from CSV.  Returns a summary dict.

    Parameters
    ----------
    dry_run:  When True, no database writes are performed.
    verbose:  When True, log every row's outcome.
    """
    verify_local_development_target()

    hotel_name_map = _load_hotel_name_map()    # csv_hotel_id -> hotel_name
    package_title_map = _load_package_title_map()  # csv_pkg_id  -> package_name

    rows = []
    with open(CSV_REVIEWS_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    counters = {
        "total": len(rows),
        "inserted": 0,
        "skipped_duplicate": 0,
        "skipped_no_entity": 0,
        "skipped_validation": 0,
        "skipped_hotel_not_in_db": 0,
        "skipped_package_not_in_db": 0,
    }

    if not rows:
        print("[seed_csv_reviews] No rows found in CSV.")
        return counters

    db = SessionLocal() if not dry_run else None

    try:
        # Pre-fetch existing csv_review_ids to skip in O(1)
        existing_ids: set[str] = set()
        if not dry_run:
            for (rid,) in db.query(Review.csv_review_id).filter(Review.csv_review_id != None).all():
                if rid:
                    existing_ids.add(rid)

        # Build DB name lookup caches (case-insensitive)
        hotel_name_to_id: dict[str, int] = {}
        package_title_to_id: dict[str, int] = {}
        if not dry_run:
            for (h_id, h_name) in db.query(Hotel.id, Hotel.name).all():
                if h_name:
                    hotel_name_to_id[h_name.strip().lower()] = h_id
            for (p_id, p_title) in db.query(Package.id, Package.title).all():
                if p_title:
                    package_title_to_id[p_title.strip().lower()] = p_id

        for row in rows:
            csv_review_id = (row.get("review_id") or "").strip()
            csv_hotel_id  = (row.get("hotel_id")  or "").strip()
            csv_pkg_id    = (row.get("package_id") or "").strip()
            csv_user_id   = (row.get("user_id")   or "").strip()
            rating_raw    = (row.get("rating")     or "").strip()
            review_text   = (row.get("review_text") or "").strip()
            date_raw      = (row.get("date")       or "").strip()
            images        = (row.get("images")     or "").strip()

            # --- Validate rating ---
            rating = _safe_float(rating_raw)
            if rating is None or not (1.0 <= rating <= 5.0):
                if verbose:
                    print(f"  [SKIP-VALIDATION] {csv_review_id}: invalid rating '{rating_raw}'")
                counters["skipped_validation"] += 1
                continue

            # --- Deduplicate on csv_review_id ---
            if csv_review_id and csv_review_id in existing_ids:
                if verbose:
                    print(f"  [SKIP-DUPLICATE] {csv_review_id}: already in DB")
                counters["skipped_duplicate"] += 1
                continue

            # --- Resolve entity ---
            hotel_db_id: int | None = None
            package_db_id: int | None = None

            if csv_hotel_id:
                hotel_name = hotel_name_map.get(csv_hotel_id, "")
                if not hotel_name:
                    if verbose:
                        print(f"  [SKIP-NO-ENTITY] {csv_review_id}: hotel_id '{csv_hotel_id}' not in hotels.csv")
                    counters["skipped_no_entity"] += 1
                    continue
                if not dry_run:
                    hotel_db_id = hotel_name_to_id.get(hotel_name.strip().lower())
                    if hotel_db_id is None:
                        if verbose:
                            print(f"  [SKIP-NO-DB-HOTEL] {csv_review_id}: '{hotel_name}' not found in DB")
                        counters["skipped_hotel_not_in_db"] += 1
                        continue
                else:
                    hotel_db_id = -1  # dry-run placeholder

            elif csv_pkg_id:
                pkg_title = package_title_map.get(csv_pkg_id, "")
                if not pkg_title:
                    if verbose:
                        print(f"  [SKIP-NO-ENTITY] {csv_review_id}: package_id '{csv_pkg_id}' not in packages.csv")
                    counters["skipped_no_entity"] += 1
                    continue
                if not dry_run:
                    package_db_id = package_title_to_id.get(pkg_title.strip().lower())
                    if package_db_id is None:
                        if verbose:
                            print(f"  [SKIP-NO-DB-PKG] {csv_review_id}: '{pkg_title}' not found in DB")
                        counters["skipped_package_not_in_db"] += 1
                        continue
                else:
                    package_db_id = -1  # dry-run placeholder

            else:
                if verbose:
                    print(f"  [SKIP-NO-ENTITY] {csv_review_id}: no hotel_id or package_id")
                counters["skipped_no_entity"] += 1
                continue

            # --- Sentiment ---
            sentiment = classify_review(review_text, rating)

            # --- Parse date ---
            review_date = _parse_date(date_raw)

            if verbose:
                entity = f"hotel={hotel_db_id}" if hotel_db_id else f"package={package_db_id}"
                print(
                    f"  [{'DRY-RUN' if dry_run else 'INSERT'}] "
                    f"{csv_review_id} | {entity} | rating={rating} | "
                    f"sentiment={sentiment.label}({sentiment.score})"
                )

            if not dry_run:
                review = Review(
                    csv_review_id=csv_review_id or None,
                    csv_user_id=csv_user_id or None,
                    user_id=None,  # CSV reviews are not linked to auth users
                    hotel_id=hotel_db_id,
                    package_id=package_db_id,
                    rating=rating,
                    review_text=review_text,
                    review_date=review_date,
                    images=images or None,
                    sentiment_label=sentiment.label,
                    sentiment_score=sentiment.score,
                )
                db.add(review)
                existing_ids.add(csv_review_id)  # prevent intra-batch duplication

            counters["inserted"] += 1

        if not dry_run:
            db.commit()
            print(f"[seed_csv_reviews] Committed {counters['inserted']} new reviews.")

    except Exception:
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()

    return counters


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed reviews from datasets/reviews.csv")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without DB writes")
    parser.add_argument("--verbose", action="store_true", help="Log every row's outcome")
    args = parser.parse_args()

    print(f"[seed_csv_reviews] Starting{'  (DRY RUN)' if args.dry_run else ''}...")
    result = seed(dry_run=args.dry_run, verbose=args.verbose)

    print("\n=== Import Summary ===")
    for key, val in result.items():
        print(f"  {key:35s}: {val}")


if __name__ == "__main__":
    main()
