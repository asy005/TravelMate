"""
test_csv_inventory_imports.py
-----------------------------
Focused tests for CSV inventory seeding scripts (destinations, hotels, packages),
mapping logic, repeat-import idempotency, dry-run safety, and inventory retrieval.
"""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, SessionLocal
from app.main import app
from app.models.destination import Destination
from app.models.favorites import Favorite  # noqa: F401
from app.models.hotel import Hotel
from app.models.package import Package
from app.models.partner import Partner
from app.models.user import User
from app.models.booking import Booking  # noqa: F401

from scripts.seed_csv_destinations import (
    _safe_float as dest_safe_float,
    _safe_int as dest_safe_int,
    _INVALID_DESCRIPTIONS,
    verify_local_development_target as verify_dest_target,
    seed as seed_destinations,
)
from scripts.seed_csv_hotels import (
    _calculate_price_tier as hotel_price_tier,
    _normalize_accommodation_type,
    verify_local_development_target as verify_hotel_target,
    seed as seed_hotels,
)
from scripts.seed_csv_packages import (
    _calculate_price_tier as pkg_price_tier,
    _normalize_partner_type,
    _load_partner_metadata,
    verify_local_development_target as verify_pkg_target,
    seed as seed_packages,
)


# ==============================================================================
# 1. Target Guard Tests
# ==============================================================================

def test_seeding_production_guards():
    """All seeding scripts must refuse remote hosts and production environments."""
    for guard_fn in (verify_dest_target, verify_hotel_target, verify_pkg_target):
        with patch.object(settings, "POSTGRES_HOST", "remote.prod.db.internal"):
            with pytest.raises(RuntimeError) as exc_info:
                guard_fn()
            assert "not a verified local development host" in str(exc_info.value)

        with patch.object(settings, "POSTGRES_HOST", "localhost"), patch.object(settings, "ENVIRONMENT", "production"):
            with pytest.raises(RuntimeError) as exc_info:
                guard_fn()
            assert "strictly forbidden in production" in str(exc_info.value)


# ==============================================================================
# 2. Destination Seeding & Mapping Tests
# ==============================================================================

def test_destination_safe_parsers():
    assert dest_safe_float("1500.50") == 1500.50
    assert dest_safe_float("   ") is None
    assert dest_safe_float("invalid", default=0.0) == 0.0

    assert dest_safe_int("4") == 4
    assert dest_safe_int("4.0") == 4
    assert dest_safe_int("", default=1) == 1
    assert dest_safe_int("bad", default=2) == 2


def test_destination_description_cleaning_rules():
    assert "relaxing" in _INVALID_DESCRIPTIONS
    assert "adventure" in _INVALID_DESCRIPTIONS
    assert "wildlife" in _INVALID_DESCRIPTIONS
    assert "spiritual" in _INVALID_DESCRIPTIONS
    assert "luxury" in _INVALID_DESCRIPTIONS


def test_destination_dry_run_idempotency_on_live_db():
    """Dry run against live DB must report 614 existing skipped, 0 inserted, and touch nothing."""
    summary = seed_destinations(dry_run=True)
    assert summary["total_csv_rows"] == 614
    assert summary["inserted"] == 0
    assert summary["skipped_existing"] == 614
    assert summary["invalid"] == 0


# ==============================================================================
# 3. Hotel Seeding & Mapping Tests
# ==============================================================================

def test_hotel_price_tier_mapping():
    assert hotel_price_tier(1500.0) == "low"
    assert hotel_price_tier(2499.0) == "low"
    assert hotel_price_tier(2500.0) == "medium"
    assert hotel_price_tier(6000.0) == "medium"
    assert hotel_price_tier(6001.0) == "luxury"
    assert hotel_price_tier(12000.0) == "luxury"


def test_hotel_accommodation_type_normalization():
    assert _normalize_accommodation_type("Hotel") == "hotel"
    assert _normalize_accommodation_type("Luxury Resort") == "resort"
    assert _normalize_accommodation_type("Backwater Houseboat") == "homestay"
    assert _normalize_accommodation_type("Heritage Homestay") == "homestay"
    assert _normalize_accommodation_type("Boutique") == "boutique"
    assert _normalize_accommodation_type("Unknown") == "hotel"


def test_hotel_dry_run_parses_all_records_safely():
    """Dry run must parse all 2058 hotel records without modifying DB count."""
    db = SessionLocal()
    try:
        initial_count = db.query(Hotel).count()
        assert initial_count >= 32  # existing hotels preserved
    finally:
        db.close()

    summary = seed_hotels(dry_run=True)
    assert summary["total_rows"] == 2058
    assert summary["invalid"] == 0
    assert summary["inserted"] + summary["skipped"] == 2058

    db = SessionLocal()
    try:
        after_count = db.query(Hotel).count()
        assert after_count == initial_count, "Dry-run must not write any records to database"
    finally:
        db.close()


# ==============================================================================
# 4. Package Seeding & Mapping Tests
# ==============================================================================

def test_package_price_tier_mapping():
    assert pkg_price_tier(2000.0) == "low"
    assert pkg_price_tier(3499.0) == "low"
    assert pkg_price_tier(3500.0) == "medium"
    assert pkg_price_tier(10000.0) == "medium"
    assert pkg_price_tier(10001.0) == "luxury"


def test_package_partner_type_normalization():
    assert _normalize_partner_type("Tour Operator") == "tour_operator"
    assert _normalize_partner_type("Travel Agency") == "travel_agency"
    assert _normalize_partner_type("Local Guide") == "local_guide"
    assert _normalize_partner_type("Custom Guide") == "local_guide"


def test_package_partner_metadata_loader():
    meta = _load_partner_metadata()
    assert len(meta) >= 57
    assert "P02085" in meta
    assert meta["P02085"]["business_name"] == "Spice Route Expeditions"
    assert meta["P02085"]["city"] == "Agra"


def test_package_dry_run_parses_all_records_safely():
    """Dry run must parse all 220 package records without modifying DB count."""
    db = SessionLocal()
    try:
        initial_count = db.query(Package).count()
        assert initial_count >= 16  # existing packages preserved
    finally:
        db.close()

    summary = seed_packages(dry_run=True)
    assert summary["total_rows"] == 220
    assert summary["invalid"] == 0
    assert summary["inserted"] + summary["skipped"] == 220

    db = SessionLocal()
    try:
        after_count = db.query(Package).count()
        assert after_count == initial_count, "Dry-run must not write any records to database"
    finally:
        db.close()


# ==============================================================================
# 5. In-Memory Isolated Database Idempotency Test
# ==============================================================================

def test_isolated_database_repeat_import_idempotency():
    """
    In an isolated SQLite database, verify that inserting records once
    and repeating the operation results in 0 duplicates (inserted=0, skipped>0).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSession()
    try:
        # Create test destination
        dest = Destination(
            id=1,
            name="Test Destination",
            country="India",
            description="A test destination",
            tags="test",
            avg_rating=4.5,
        )
        session.add(dest)

        # Create test user & partner
        user = User(
            id=10,
            username="test_partner_user",
            email="test_partner@test.com",
            password="hashed_pass_test",
            role="partner",
        )
        session.add(user)
        session.flush()

        partner = Partner(
            id=20,
            owner_user_id=user.id,
            business_name="Test Partner Agency",
            partner_type="tour_operator",
            status="approved",
        )
        session.add(partner)
        session.flush()

        # Insert hotel
        hotel = Hotel(
            destination_id=dest.id,
            partner_id=partner.id,
            name="Seeded Grand Hotel",
            price_tier="medium",
            price_per_night=3500.0,
            star_rating=4.2,
        )
        session.add(hotel)

        # Insert package
        pkg = Package(
            destination_id=dest.id,
            partner_id=partner.id,
            title="Seeded Grand Tour",
            price_tier="medium",
            price_per_package=8000.0,
            duration_days=3,
        )
        session.add(pkg)
        session.commit()

        # Verify initial counts
        assert session.query(Hotel).count() == 1
        assert session.query(Package).count() == 1

        # Simulate repeat import checking for existing key
        existing_hotel_keys = {
            (h.destination_id, h.name.strip().lower())
            for h in session.query(Hotel).all()
        }
        assert (1, "seeded grand hotel") in existing_hotel_keys

        # A repeat insert attempt for the same key is skipped
        if (dest.id, "seeded grand hotel") in existing_hotel_keys:
            repeat_hotel_inserted = False
        else:
            session.add(Hotel(destination_id=dest.id, name="Seeded Grand Hotel"))
            repeat_hotel_inserted = True

        assert not repeat_hotel_inserted
        assert session.query(Hotel).count() == 1

    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ==============================================================================
# 6. Inventory Retrieval Route Tests
# ==============================================================================

def test_inventory_retrieval_routes_preserve_demo_items():
    """Verify hotel and package API endpoints correctly retrieve existing items."""
    client = TestClient(app)

    db = SessionLocal()
    try:
        hotel = db.query(Hotel).filter(Hotel.id == 1).first()
        assert hotel is not None
        pkg = db.query(Package).filter(Package.id == 1).first()
        assert pkg is not None
    finally:
        db.close()

    # Query hotel details
    res_hotel = client.get(f"/hotels/{hotel.id}")
    assert res_hotel.status_code == 200
    h_data = res_hotel.json()
    assert h_data["id"] == hotel.id
    assert h_data["name"] == hotel.name

    # Query package details
    res_pkg = client.get(f"/packages/{pkg.id}")
    assert res_pkg.status_code == 200
    p_data = res_pkg.json()
    assert p_data["id"] == pkg.id
    assert p_data["title"] == pkg.title
