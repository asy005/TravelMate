"""
seed_csv_destinations.py
------------------------
Imports destination records from datasets/destinations.csv into PostgreSQL.

Safe / idempotent behaviour
---------------------------
- Existing rows (matched by lower-cased destination_name) are NOT deleted or
  overwritten by default. Only brand-new names are inserted.
- When --update-existing is passed and the destination model supports extended
  columns, missing/null fields on existing records are backfilled safely
  without overwriting custom descriptions or ratings.
- New columns added to the Destination model (state, city, category,
  best_season, average_budget, ideal_duration, csv_destination_id) are
  dynamically populated only if the model and table support them.
- Rows whose destination_name is blank or already present in the database are
  skipped and counted in the summary.
- Verifies local development target before execution to prevent accidental
  execution against production environments.

Usage
-----
    cd travelmate_backend
    python scripts/seed_csv_destinations.py [--dry-run] [--update-existing]

Options
-------
    --dry-run          Print what would be inserted/updated without writing to the database.
    --update-existing  Backfill empty fields on existing destinations from CSV.
"""
import sys
from pathlib import Path

# Configure utf-8 stdout on Windows to prevent UnicodeEncodeError with special characters
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import csv
import argparse
from app.config import settings
from app.database import SessionLocal
from app.models.destination import Destination
from app.models.favorites import Favorite  # noqa: F401
from app.models.hotel import Hotel  # noqa: F401
from app.models.package import Package  # noqa: F401
from app.models.partner import Partner  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.booking import Booking  # noqa: F401

CSV_PATH = BACKEND_DIR.parent / "datasets" / "destinations.csv"

# Mood/travel-style labels that were sometimes stored as the description
# field in the CSV — they are not real descriptions.
_INVALID_DESCRIPTIONS = {
    "relaxing", "adventure", "adventurous",
    "cultural", "romantic", "family",
    "wildlife", "spiritual", "luxury",
    "beach", "nature", "heritage",
}


def verify_local_development_target():
    """
    Safety guard: refuse to seed if the database target is not verified local development.
    Never run against remote hosts or production environments.
    """
    host = (settings.POSTGRES_HOST or "").strip().lower()
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if host not in local_hosts:
        raise RuntimeError(
            f"Refusing to seed: target database host '{host}' is not a verified local development host {local_hosts}."
        )

    env = (getattr(settings, "ENVIRONMENT", "") or "development").strip().lower()
    if env in ("production", "prod"):
        raise RuntimeError(
            f"Refusing to seed: environment is '{env}'. Seeding inventory is strictly forbidden in production."
        )


def _safe_float(value: str, *, default=None):
    """Parse a string to float; return ``default`` on empty or invalid input."""
    v = (value or "").strip()
    if not v:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _safe_int(value: str, *, default=None):
    """Parse a string to int; return ``default`` on empty or invalid input."""
    v = (value or "").strip()
    if not v:
        return default
    try:
        return int(float(v))  # handles "3.0" as well as "3"
    except ValueError:
        return default


def seed(dry_run: bool = False, update_existing: bool = False) -> dict:
    """
    Import destinations from CSV.

    Returns a summary dict:
        {
            "inserted": <int>,
            "updated": <int>,
            "skipped_existing": <int>,
            "skipped_blank_name": <int>,
            "invalid": <int>,
            "total_csv_rows": <int>,
        }
    """
    verify_local_development_target()

    db = SessionLocal()
    inserted = 0
    updated = 0
    skipped_existing = 0
    skipped_blank = 0
    invalid_rows = 0
    total_rows = 0

    try:
        if not CSV_PATH.exists():
            raise FileNotFoundError(f"Dataset not found: {CSV_PATH}")

        # Check which columns exist on Destination model/table
        supported_columns = {c.key for c in Destination.__table__.columns}

        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
            rows = csv.DictReader(file)

            # Map existing records by lower-cased name
            existing_dests = {}
            for dest in db.query(Destination).all():
                if dest.name:
                    existing_dests[dest.name.strip().lower()] = dest

            for row in rows:
                total_rows += 1

                # ── identity ────────────────────────────────────────────────
                name = (row.get("destination_name") or "").strip()
                if not name:
                    skipped_blank += 1
                    continue

                csv_id = (row.get("destination_id") or "").strip()  # e.g. "D0001"
                state = (row.get("state") or "").strip()
                city = (row.get("city") or "").strip()
                category = (row.get("category") or "").strip()
                best_season = (row.get("best_season") or "").strip()

                average_budget = _safe_float(row.get("average_budget"))
                ideal_duration = _safe_int(row.get("ideal_duration"))

                # ── description cleanup ──────────────────────────────────────
                description = (row.get("description") or "").strip()
                if description.lower() in _INVALID_DESCRIPTIONS:
                    description = ""

                if not description:
                    description = (
                        f"{name} is a destination in {state or 'India'} "
                        f"known for its {category.lower() if category else 'travel experiences'}."
                    )

                # ── tags ─────────────────────────────────────────────────────
                tags = ",".join(x for x in [category, state, city] if x)

                if name.lower() in existing_dests:
                    existing_dest = existing_dests[name.lower()]
                    if update_existing:
                        fields_to_update = {}
                        if "csv_destination_id" in supported_columns and not getattr(existing_dest, "csv_destination_id", None):
                            fields_to_update["csv_destination_id"] = csv_id or None
                        if "state" in supported_columns and not getattr(existing_dest, "state", None):
                            fields_to_update["state"] = state or None
                        if "city" in supported_columns and not getattr(existing_dest, "city", None):
                            fields_to_update["city"] = city or None
                        if "category" in supported_columns and not getattr(existing_dest, "category", None):
                            fields_to_update["category"] = category or None
                        if "best_season" in supported_columns and not getattr(existing_dest, "best_season", None):
                            fields_to_update["best_season"] = best_season or None
                        if "average_budget" in supported_columns and getattr(existing_dest, "average_budget", None) is None:
                            fields_to_update["average_budget"] = average_budget
                        if "ideal_duration" in supported_columns and getattr(existing_dest, "ideal_duration", None) is None:
                            fields_to_update["ideal_duration"] = ideal_duration

                        if fields_to_update:
                            if dry_run:
                                print(f"[DRY-RUN] Would update {name!r}: {list(fields_to_update.keys())}")
                            else:
                                for k, v in fields_to_update.items():
                                    setattr(existing_dest, k, v)
                            updated += 1
                        else:
                            skipped_existing += 1
                    else:
                        skipped_existing += 1
                    continue

                # Prepare new record attributes
                dest_kwargs = {
                    "name": name,
                    "country": "India",
                    "description": description,
                    "tags": tags,
                    "avg_rating": 4.0,
                }
                if "csv_destination_id" in supported_columns:
                    dest_kwargs["csv_destination_id"] = csv_id or None
                if "state" in supported_columns:
                    dest_kwargs["state"] = state or None
                if "city" in supported_columns:
                    dest_kwargs["city"] = city or None
                if "category" in supported_columns:
                    dest_kwargs["category"] = category or None
                if "best_season" in supported_columns:
                    dest_kwargs["best_season"] = best_season or None
                if "average_budget" in supported_columns:
                    dest_kwargs["average_budget"] = average_budget
                if "ideal_duration" in supported_columns:
                    dest_kwargs["ideal_duration"] = ideal_duration

                if dry_run:
                    print(f"[DRY-RUN] Would insert: {name!r} ({csv_id})")
                    existing_dests[name.lower()] = None
                    inserted += 1
                    continue

                new_dest = Destination(**dest_kwargs)
                db.add(new_dest)
                existing_dests[name.lower()] = new_dest
                inserted += 1

            if not dry_run:
                db.commit()

    except Exception:
        if not dry_run:
            db.rollback()
        raise
    finally:
        db.close()

    summary = {
        "inserted": inserted,
        "updated": updated,
        "skipped_existing": skipped_existing,
        "skipped_blank_name": skipped_blank,
        "invalid": invalid_rows,
        "total_csv_rows": total_rows,
    }
    tag = "[DRY-RUN] " if dry_run else ""
    print(f"{tag}Destinations inserted: {inserted}")
    print(f"{tag}Destinations updated: {updated}")
    print(f"{tag}Skipped (already in DB): {skipped_existing}")
    print(f"{tag}Skipped (blank name): {skipped_blank}")
    print(f"{tag}Invalid rows: {invalid_rows}")
    print(f"{tag}Total CSV rows read: {total_rows}")
    if not dry_run:
        db = SessionLocal()
        try:
            total_in_db = db.query(Destination).count()
            print(f"Total destinations in database: {total_in_db}")
        finally:
            db.close()
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed destinations from CSV")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing to the database.",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update missing fields on existing destinations.",
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run, update_existing=args.update_existing)
