"""
seed_csv_packages.py
--------------------
Imports package listings from datasets/packages.csv into PostgreSQL.

Safe / Idempotent Behaviour
---------------------------
- Existing packages (matched by destination_id + lower-cased title) are
  never duplicated or deleted.
- Existing bookings and partner records are strictly preserved.
- Existing demo packages (IDs 1-16) and demo partner (ID 1) are left untouched.
- Accompanying partner profiles from datasets/partners.csv are resolved or
  created idempotently with valid owner_user_id relationships.
- Dry-run capability (--dry-run) simulates the entire import without touching the database.
- Verifies local development target before execution.

Usage
-----
    cd travelmate_backend
    python scripts/seed_csv_packages.py [--dry-run] [--update-existing]
"""
import sys
from pathlib import Path

# Configure utf-8 stdout on Windows to prevent UnicodeEncodeError
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
from app.models.package import Package
from app.models.partner import Partner
from app.models.user import User
from app.models.booking import Booking  # noqa: F401
from app.services.auth_utils import hash_password

PACKAGES_CSV_PATH = BACKEND_DIR.parent / "datasets" / "packages.csv"
PARTNERS_CSV_PATH = BACKEND_DIR.parent / "datasets" / "partners.csv"


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


def _safe_int(value: str, *, default=None):
    v = (value or "").strip()
    if not v:
        return default
    try:
        return int(float(v))
    except ValueError:
        return default


def _calculate_price_tier(price: float) -> str:
    if price < 3500:
        return "low"
    elif price <= 10000:
        return "medium"
    return "luxury"


def _normalize_partner_type(raw_type: str) -> str:
    t = (raw_type or "").strip().lower().replace(" ", "_")
    valid_types = {"tour_operator", "travel_agency", "local_guide", "hotel", "homestay", "resort"}
    if t in valid_types:
        return t
    if "guide" in t:
        return "local_guide"
    if "operator" in t:
        return "tour_operator"
    if "agency" in t:
        return "travel_agency"
    return "tour_operator"


def _load_partner_metadata():
    """Load partner profiles keyed by partner_id from partners.csv."""
    partners_meta = {}
    if PARTNERS_CSV_PATH.exists():
        with PARTNERS_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                pid = (row.get("partner_id") or "").strip().upper()
                if pid:
                    partners_meta[pid] = row
    return partners_meta


def seed(dry_run: bool = False, update_existing: bool = False) -> dict:
    """
    Import packages from CSV into PostgreSQL idempotently.

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

    if not PACKAGES_CSV_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {PACKAGES_CSV_PATH}")

    partners_metadata = _load_partner_metadata()

    db = SessionLocal()
    inserted = 0
    updated = 0
    skipped = 0
    invalid_rows = 0
    total_rows = 0

    try:
        # Build destination lookup table:
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

        # Map existing partners in DB by business name (lower) and email (lower)
        existing_partners_by_name = {}
        for p in db.query(Partner).all():
            if p.business_name:
                existing_partners_by_name[p.business_name.strip().lower()] = p

        # Map existing users by username
        existing_users_by_uname = {u.username: u for u in db.query(User).all()}

        # Cache created or resolved partners by CSV partner_id
        csv_partner_cache = {}

        # Map existing packages in DB by (destination_id, lower(title))
        existing_packages = {}
        for pkg in db.query(Package).all():
            key = (pkg.destination_id, pkg.title.strip().lower())
            existing_packages[key] = pkg

        with PACKAGES_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                total_rows += 1

                pkg_name = (row.get("package_name") or "").strip()
                if not pkg_name:
                    invalid_rows += 1
                    continue

                raw_dest_id = (row.get("destination_id") or "").strip().upper()
                raw_partner_id = (row.get("partner_id") or "").strip().upper()

                # Resolve destination
                dest = dest_by_code.get(raw_dest_id)
                if not dest and raw_dest_id.startswith("D"):
                    try:
                        numeric_id = int(raw_dest_id[1:])
                        dest = dest_by_id.get(numeric_id)
                    except ValueError:
                        dest = None

                if not dest:
                    invalid_rows += 1
                    continue

                # Resolve or simulate partner
                partner = None
                p_meta = partners_metadata.get(raw_partner_id, {})
                biz_name = (p_meta.get("business_name") or f"Partner {raw_partner_id}").strip()
                biz_type = _normalize_partner_type(p_meta.get("partner_type") or "tour_operator")
                p_email = (p_meta.get("email") or f"{raw_partner_id.lower()}@travelmate.local").strip()
                p_phone = (p_meta.get("phone") or "+910000000000").strip()
                p_address = (p_meta.get("address") or "").strip()
                p_city = (p_meta.get("city") or "").strip()
                p_state = (p_meta.get("state") or "").strip()
                p_rating = _safe_float(p_meta.get("rating"), default=4.5)

                if raw_partner_id in csv_partner_cache:
                    partner = csv_partner_cache[raw_partner_id]
                elif biz_name.lower() in existing_partners_by_name:
                    partner = existing_partners_by_name[biz_name.lower()]
                    csv_partner_cache[raw_partner_id] = partner
                elif not dry_run:
                    # Create User + Partner idempotently
                    uname = f"partner_{raw_partner_id.lower()}"
                    user = existing_users_by_uname.get(uname)
                    if not user:
                        user = User(
                            username=uname,
                            email=p_email,
                            password=hash_password("PartnerPassword123!"),
                            role="partner",
                            full_name=biz_name,
                        )
                        db.add(user)
                        db.flush()
                        existing_users_by_uname[uname] = user

                    partner = Partner(
                        owner_user_id=user.id,
                        business_name=biz_name,
                        partner_type=biz_type,
                        contact_email=p_email,
                        contact_phone=p_phone,
                        description=f"Curated packages and travel services by {biz_name}.",
                        address=p_address,
                        city=p_city,
                        state=p_state,
                        status="approved",
                    )
                    db.add(partner)
                    db.flush()
                    existing_partners_by_name[biz_name.lower()] = partner
                    csv_partner_cache[raw_partner_id] = partner

                pkg_key = (dest.id, pkg_name.lower())
                price = _safe_float(row.get("price"), default=5000.0)
                tier = _calculate_price_tier(price)
                duration_days = _safe_int(row.get("days"), default=3)
                description = (row.get("description") or f"{pkg_name} in {dest.name}.").strip()

                # Build amenities from booleans
                inclusions = []
                if str(row.get("includes_hotel")).strip().lower() in ("true", "1"):
                    inclusions.append("Hotel Stay")
                if str(row.get("includes_transport")).strip().lower() in ("true", "1"):
                    inclusions.append("Local Transport")
                if str(row.get("meals_included")).strip().lower() in ("true", "1"):
                    inclusions.append("Meals")
                if str(row.get("guide_included")).strip().lower() in ("true", "1"):
                    inclusions.append("Local Guide")
                amenities = ", ".join(inclusions) if inclusions else "Sightseeing"

                if pkg_key in existing_packages:
                    existing_p = existing_packages[pkg_key]
                    if update_existing:
                        modified = False
                        if existing_p.price_per_package is None and price is not None:
                            existing_p.price_per_package = price
                            existing_p.price_tier = tier
                            modified = True
                        if existing_p.duration_days is None and duration_days is not None:
                            existing_p.duration_days = duration_days
                            modified = True
                        if not existing_p.amenities and amenities:
                            existing_p.amenities = amenities
                            modified = True

                        if modified:
                            if dry_run:
                                print(f"[DRY-RUN] Would update package {pkg_name!r}")
                            updated += 1
                        else:
                            skipped += 1
                    else:
                        skipped += 1
                    continue

                if dry_run:
                    print(f"[DRY-RUN] Would insert package {pkg_name!r} (dest: {dest.name}, partner: {biz_name})")
                    existing_packages[pkg_key] = None
                    inserted += 1
                    continue

                new_pkg = Package(
                    destination_id=dest.id,
                    partner_id=partner.id,
                    title=pkg_name,
                    category=biz_type,
                    price_tier=tier,
                    price_per_package=price,
                    duration_days=duration_days,
                    capacity=6,
                    rating=p_rating,
                    amenities=amenities,
                    thumbnail_url="",
                    description=description,
                    photos=[],
                )
                db.add(new_pkg)
                existing_packages[pkg_key] = new_pkg
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
    print(f"{tag}Packages inserted: {inserted}")
    print(f"{tag}Packages updated: {updated}")
    print(f"{tag}Packages skipped (already in DB): {skipped}")
    print(f"{tag}Packages invalid/unresolvable: {invalid_rows}")
    print(f"{tag}Total CSV rows read: {total_rows}")
    if not dry_run:
        db = SessionLocal()
        try:
            total_in_db = db.query(Package).count()
            print(f"Total packages in database: {total_in_db}")
        finally:
            db.close()
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import packages from CSV")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing to the database.",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update missing fields on existing packages.",
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run, update_existing=args.update_existing)
