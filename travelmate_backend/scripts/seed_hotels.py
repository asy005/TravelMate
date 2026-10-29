# scripts/seed_hotels.py
import os
import sys

sys.path.append(os.path.abspath("."))

from app.config import settings
from app.database import SessionLocal
from app.models.destination import Destination
from app.models.favorites import Favorite  # noqa: F401 - ensures SQLAlchemy mapper registry resolves
from app.models.hotel import Hotel
from app.models.package import Package
from app.models.partner import Partner
from app.models.user import User
from app.services.auth_utils import hash_password


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
            f"Refusing to seed: environment is '{env}'. Seeding demo inventory is strictly forbidden in production."
        )


HOTEL_TEMPLATES = [
    {
        "suffix": "Budget Inn",
        "tier": "low",
        "type": "hotel",
        "price": 1800,
        "rating": 3.8,
        "amenities": "WiFi,Breakfast",
    },
    {
        "suffix": "Comfort Stay",
        "tier": "medium",
        "type": "hotel",
        "price": 4500,
        "rating": 4.2,
        "amenities": "WiFi,Breakfast,Pool",
    },
    {
        "suffix": "Homestay Retreat",
        "tier": "medium",
        "type": "homestay",
        "price": 3800,
        "rating": 4.5,
        "amenities": "WiFi,Home-cooked meals,Local host",
    },
    {
        "suffix": "Grand Resort",
        "tier": "luxury",
        "type": "resort",
        "price": 11000,
        "rating": 4.8,
        "amenities": "WiFi,Pool,Spa,Fine dining",
    },
]

PACKAGE_TEMPLATES = [
    {
        "title_suffix": "Explorer Tour",
        "category": "tour_operator",
        "tier": "medium",
        "price": 8500.0,
        "duration_days": 3,
        "capacity": 8,
        "rating": 4.6,
        "amenities": "Guided tours,Local transport,Sightseeing pass,Breakfast",
        "description_tpl": "A 3-day guided explorer package in {dest} covering top cultural landmarks and natural attractions.",
    },
    {
        "title_suffix": "Weekend Getaway",
        "category": "travel_agency",
        "tier": "low",
        "price": 4200.0,
        "duration_days": 2,
        "capacity": 4,
        "rating": 4.3,
        "amenities": "Sightseeing,Local guide,Snack kit",
        "description_tpl": "A relaxed 2-day weekend package to explore {dest} with local guidance and curated spot visits.",
    },
]

TARGET_DESTINATIONS = [
    "Goa",
    "Manali",
    "Leh-Ladakh",
    "Shimla",
    "Ooty",
    "Munnar",
    "Jaipur",
    "Udaipur",
]


def _get_or_create_demo_partner(db) -> Partner:
    """
    Safely and idempotently retrieves or creates a demo partner and owner user
    with valid foreign key relationships.
    """
    demo_user = db.query(User).filter(User.username == "demo_partner").first()
    if not demo_user:
        demo_user = User(
            username="demo_partner",
            email="demo_partner@travelmate.local",
            password=hash_password("DemoPartnerPass123!"),
            role="partner",
            full_name="TravelMate Demo Partner",
        )
        db.add(demo_user)
        db.flush()

    partner = db.query(Partner).filter(Partner.owner_user_id == demo_user.id).first()
    if not partner:
        partner = Partner(
            owner_user_id=demo_user.id,
            business_name="[Demo] TravelMate Adventures",
            partner_type="tour_operator",
            contact_email="demo_partner@travelmate.local",
            contact_phone="+910000000000",
            description="Verified demo partner providing curated travel experiences.",
            status="approved",
        )
        db.add(partner)
        db.flush()

    return partner


def seed_hotels(db, destinations):
    """
    Seeds a small set of clearly labelled demo hotels linked to existing destinations.
    Safe and idempotent: skips any hotel that already exists, never deletes or overwrites.
    """
    added_hotels = 0
    skipped_hotels = 0

    for dest in destinations:
        for tpl in HOTEL_TEMPLATES:
            hotel_name = f"[Demo] {dest.name} {tpl['suffix']}"

            existing = (
                db.query(Hotel)
                .filter(Hotel.destination_id == dest.id, Hotel.name == hotel_name)
                .first()
            )
            if existing:
                skipped_hotels += 1
                continue

            hotel = Hotel(
                destination_id=dest.id,
                partner_id=None,  # platform-seeded inventory
                name=hotel_name,
                partner_name=f"[Demo] {tpl['suffix']} Group",
                accommodation_type=tpl["type"],
                price_tier=tpl["tier"],
                price_per_night=float(tpl["price"]),
                star_rating=float(tpl["rating"]),
                amenities=tpl["amenities"],
                thumbnail_url="",
                description=(
                    f"{hotel_name} is a demo {tpl['type']} in {dest.name} offering "
                    f"{tpl['amenities'].replace(',', ', ')}. Clearly labelled for local testing."
                ),
                photos=[],
                lat=dest.lat,
                lon=dest.lon,
            )
            db.add(hotel)
            added_hotels += 1

    return added_hotels, skipped_hotels


def seed_packages(db, destinations, partner: Partner):
    """
    Seeds clearly labelled demo packages linked to existing destinations and a valid partner.
    Safe and idempotent: skips any package that already exists, never deletes or overwrites.
    """
    added_packages = 0
    skipped_packages = 0

    for dest in destinations:
        for tpl in PACKAGE_TEMPLATES:
            pkg_title = f"[Demo] {dest.name} {tpl['title_suffix']}"

            existing = (
                db.query(Package)
                .filter(Package.destination_id == dest.id, Package.title == pkg_title)
                .first()
            )
            if existing:
                skipped_packages += 1
                continue

            pkg = Package(
                destination_id=dest.id,
                partner_id=partner.id,
                title=pkg_title,
                category=tpl["category"],
                price_tier=tpl["tier"],
                price_per_package=tpl["price"],
                duration_days=tpl["duration_days"],
                capacity=tpl["capacity"],
                rating=tpl["rating"],
                amenities=tpl["amenities"],
                thumbnail_url="",
                description=tpl["description_tpl"].format(dest=dest.name),
                photos=[],
            )
            db.add(pkg)
            added_packages += 1

    return added_packages, skipped_packages


def seed():
    verify_local_development_target()

    db = SessionLocal()
    try:
        # Fetch target destinations from verified existing database records
        destinations = (
            db.query(Destination)
            .filter(Destination.name.in_(TARGET_DESTINATIONS))
            .all()
        )

        if not destinations:
            # Fallback to any existing destinations up to 8
            destinations = db.query(Destination).limit(8).all()

        if not destinations:
            print("No destinations found in local database. Run destination seeding first.")
            return

        print(f"Targeting {len(destinations)} verified local destinations for demo inventory.")

        # 1. Seed demo hotels
        added_h, skipped_h = seed_hotels(db, destinations)

        # 2. Seed demo packages
        partner = _get_or_create_demo_partner(db)
        added_p, skipped_p = seed_packages(db, destinations, partner)

        db.commit()

        print(
            f"Hotel seeding complete: {added_h} created, {skipped_h} already existed."
        )
        print(
            f"Package seeding complete: {added_p} created, {skipped_p} already existed."
        )
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
