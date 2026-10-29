"""
Focused tests for hotel and package inventory, lookup routes, and safe idempotent seeding.
"""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.destination import Destination
from app.models.favorites import Favorite  # noqa: F401
from app.models.hotel import Hotel
from app.models.package import Package
from app.models.partner import Partner
from app.models.user import User
from scripts.seed_hotels import (
    verify_local_development_target,
    seed_hotels,
    seed_packages,
    _get_or_create_demo_partner,
    TARGET_DESTINATIONS,
    HOTEL_TEMPLATES,
    PACKAGE_TEMPLATES,
)


def test_verify_local_development_target_guards():
    """Confirms seeding strictly refuses non-local or production databases."""
    with patch.object(settings, "POSTGRES_HOST", "db.production.travelmate.com"):
        with pytest.raises(RuntimeError) as exc_info:
            verify_local_development_target()
        assert "not a verified local development host" in str(exc_info.value)

    with patch.object(settings, "POSTGRES_HOST", "localhost"), patch.object(settings, "ENVIRONMENT", "production"):
        with pytest.raises(RuntimeError) as exc_info:
            verify_local_development_target()
        assert "strictly forbidden in production" in str(exc_info.value)


def test_hotel_details_lookup_route():
    client = TestClient(app)
    db = SessionLocal()
    try:
        hotel = db.query(Hotel).first()
        assert hotel is not None, "At least one hotel should be seeded"
        hotel_id = hotel.id
    finally:
        db.close()

    res = client.get(f"/hotels/{hotel_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == hotel_id
    assert data["name"].startswith("[Demo]")
    assert "room_types" in data
    assert len(data["room_types"]) > 0
    assert "location" in data


def test_hotel_recommend_route():
    client = TestClient(app)
    db = SessionLocal()
    try:
        hotel = db.query(Hotel).first()
        dest_id = hotel.destination_id
    finally:
        db.close()

    res = client.post("/hotels/recommend", json={
        "destination_id": dest_id,
        "slots": {"budget": "medium"}
    })
    assert res.status_code == 200
    data = res.json()
    assert "hotels" in data
    assert len(data["hotels"]) > 0


def test_package_details_lookup_route():
    client = TestClient(app)
    db = SessionLocal()
    try:
        pkg = db.query(Package).first()
        assert pkg is not None, "At least one package should be seeded"
        pkg_id = pkg.id
    finally:
        db.close()

    res = client.get(f"/packages/{pkg_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == pkg_id
    assert data["title"].startswith("[Demo]")
    assert data["duration_days"] is not None
    assert data["price_per_package"] is not None
    assert data["partner_name"] is not None


def test_seeding_idempotency_does_not_duplicate():
    """Running seed operations again on already-seeded destinations must add 0 records."""
    db = SessionLocal()
    try:
        destinations = db.query(Destination).filter(Destination.name.in_(TARGET_DESTINATIONS)).all()
        assert len(destinations) > 0

        # Seed hotels again
        added_h, skipped_h = seed_hotels(db, destinations)
        assert added_h == 0
        assert skipped_h == len(destinations) * len(HOTEL_TEMPLATES)

        # Seed packages again
        partner = _get_or_create_demo_partner(db)
        added_p, skipped_p = seed_packages(db, destinations, partner)
        assert added_p == 0
        assert skipped_p == len(destinations) * len(PACKAGE_TEMPLATES)
    finally:
        db.rollback()
        db.close()
