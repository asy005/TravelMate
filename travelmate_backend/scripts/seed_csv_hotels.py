"""
seed_csv_hotels.py
------------------
Imports hotel inventory from datasets/hotels.csv into PostgreSQL.

Safe / Idempotent Behaviour
---------------------------
- Existing hotels (matched by destination_id + lower-cased hotel name) are
  never duplicated or deleted.
- Existing bookings and partner records are strictly preserved.
- Existing demo hotels (IDs 1-32) are left untouched.
- Dry-run capability (--dry-run) simulates the entire import without touching the database.
- Verifies local development target before execution.

Usage
-----
    cd travelmate_backend
    python scripts/seed_csv_hotels.py [--dry-run] [--update-existing]
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
from app.models.hotel import Hotel
from app.models.package import Package  # noqa: F401
from app.models.partner import Partner  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.booking import Booking  # noqa: F401

CSV_PATH = BACKEND_DIR.parent / "datasets" / "hotels.csv"


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
    v = (value or "").strip()
    if not v:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _calculate_price_tier(price: float) -> str:
    if price < 2500:
        return "low"
    elif price <= 6000:
        return "medium"
    return "luxury"


def _normalize_accommodation_type(raw_type: str) -> str:
    t = (raw_type or "").strip().lower()
    valid_types = {"hotel", "homestay", "resort", "boutique", "lodge", "villa", "guesthouse"}
    if t in valid_types:
        return t
    if "resort" in t:
        return "resort"
    if "homestay" in t or "boat" in t or "houseboat" in t:
        return "homestay"
    return "hotel"


def seed(dry_run: bool = False, update_existing: bool = False) -> dict:
    """
    Import hotels from CSV into PostgreSQL idempotently.

    Returns:
        {
            "inserted": int,
            "updated": int,
            "skipped": int,
            "invalid": int,
            "total_rows": int,
        }
    """
    verify_local_development_target()

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {CSV_PATH}")

    db = SessionLocal()
    inserted = 0
    updated = 0
    skipped = 0
    invalid_rows = 0
    total_rows = 0

    try:
        # Build destination lookup table:
        # Supports:
        # 1. destination code: "D0449" -> int 449
        # 2. csv_destination_id if column exists
        # 3. destination.id (int)
        # 4. lower-cased name
        destinations = db.query(Destination).all()
        dest_by_id = {d.id: d for d in destinations}
        dest_by_name = {d.name.strip().lower(): d for d in destinations if d.name}
        dest_by_code = {}

        has_csv_id_col = hasattr(Destination, "csv_destination_id")
        for d in destinations:
            if has_csv_id_col:
                csv_code = getattr(d, "csv_destination_id", None)
                if csv_code:
                    dest_by_code[csv_code.strip().upper()] = d

        # Build existing hotel map by (destination_id, lower(name))
        existing_hotels = {}
        for h in db.query(Hotel).all():
            key = (h.destination_id, h.name.strip().lower())
            existing_hotels[key] = h

        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                total_rows += 1

                hotel_name = (row.get("hotel_name") or "").strip()
                if not hotel_name:
                    invalid_rows += 1
                    continue

                raw_dest_id = (row.get("destination_id") or "").strip().upper()
                city_hotel = (row.get("city_hotel") or "").strip()
                state_hotel = (row.get("state_hotel") or "").strip()

                # Resolve destination
                dest = dest_by_code.get(raw_dest_id)
                if not dest and raw_dest_id.startswith("D"):
                    try:
                        numeric_id = int(raw_dest_id[1:])
                        dest = dest_by_id.get(numeric_id)
                    except ValueError:
                        dest = None

                if not dest and city_hotel:
                    dest = dest_by_name.get(city_hotel.lower())

                if not dest:
                    invalid_rows += 1
                    continue

                hotel_key = (dest.id, hotel_name.lower())
                price = _safe_float(row.get("price_per_night"), default=2500.0)
                tier = _calculate_price_tier(price)
                rating = _safe_float(row.get("rating"), default=4.0)
                accom_type = _normalize_accommodation_type(row.get("hotel_type"))
                address = (row.get("address") or "").strip()
                amenities = (row.get("amenities") or "").strip()[:512]
                lat = _safe_float(row.get("latitude"))
                lon = _safe_float(row.get("longitude"))

                description = (
                    f"{hotel_name} is located at {address}."
                    if address
                    else f"{hotel_name} in {city_hotel or dest.name}, {state_hotel}."
                )

                if hotel_key in existing_hotels:
                    existing_h = existing_hotels[hotel_key]
                    if update_existing:
                        # Safely update empty fields without overwriting user/partner data
                        modified = False
                        if existing_h.price_per_night is None and price is not None:
                            existing_h.price_per_night = price
                            existing_h.price_tier = tier
                            modified = True
                        if existing_h.star_rating is None and rating is not None:
                            existing_h.star_rating = rating
                            modified = True
                        if not existing_h.amenities and amenities:
                            existing_h.amenities = amenities
                            modified = True
                        if existing_h.lat is None and lat is not None:
                            existing_h.lat = lat
                            existing_h.lon = lon
                            modified = True

                        if modified:
                            if dry_run:
                                print(f"[DRY-RUN] Would update hotel {hotel_name!r} in dest {dest.id}")
                            updated += 1
                        else:
                            skipped += 1
                    else:
                        skipped += 1
                    continue

                if dry_run:
                    print(f"[DRY-RUN] Would insert hotel {hotel_name!r} (dest: {dest.name})")
                    existing_hotels[hotel_key] = None
                    inserted += 1
                    continue

                new_hotel = Hotel(
                    destination_id=dest.id,
                    partner_id=None,  # platform-seeded inventory
                    name=hotel_name,
                    partner_name=hotel_name,
                    accommodation_type=accom_type,
                    price_tier=tier,
                    price_per_night=price,
                    star_rating=rating,
                    amenities=amenities,
                    thumbnail_url="",
                    description=description,
                    photos=[],
                    lat=lat or dest.lat,
                    lon=lon or dest.lon,
                )
                db.add(new_hotel)
                existing_hotels[hotel_key] = new_hotel
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
        "skipped": skipped,
        "invalid": invalid_rows,
        "total_rows": total_rows,
    }
    tag = "[DRY-RUN] " if dry_run else ""
    print(f"{tag}Hotels inserted: {inserted}")
    print(f"{tag}Hotels updated: {updated}")
    print(f"{tag}Hotels skipped (already in DB): {skipped}")
    print(f"{tag}Hotels invalid/unresolvable: {invalid_rows}")
    print(f"{tag}Total CSV rows read: {total_rows}")
    if not dry_run:
        db = SessionLocal()
        try:
            total_in_db = db.query(Hotel).count()
            print(f"Total hotels in database: {total_in_db}")
        finally:
            db.close()
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import hotels from CSV")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing to the database.",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update missing fields on existing hotels.",
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run, update_existing=args.update_existing)
