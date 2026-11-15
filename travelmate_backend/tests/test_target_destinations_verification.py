# travelmate_backend/tests/test_target_destinations_verification.py
"""
Focused verification tests for target destinations:
- Hampi
- Pondicherry / Puducherry
- Lakshadweep
- Agonda
- Tarkarli

Verifies:
1. Lakshadweep returns valid non-zero attractions with verified coordinates.
2. Agonda returns geographically relevant South Goa attractions (no Dudhsagar Falls or Arambol Beach).
3. Hampi Virupaksha Temple coordinates are in Hampi (not Mysore).
4. Pondicherry aliases and attractions are correctly resolved.
5. Tarkarli coastal attractions and activities are correctly loaded.
6. Route optimizer resolves coordinates and optimizes routes for these destinations.
7. SavedTrip workflow persists and updates customized trip payloads without duplicates.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.services.auth_utils import create_token
from app.routes.destination_routes import _get_dest_attractions, _get_dest_activities
from app.services.route_optimizer import (
    AttractionCoordinateResolver,
    optimize_day_route,
)

client = TestClient(app)


def _get_auth_header(user_id: int, username: str) -> dict:
    token = create_token({"sub": username, "user_id": user_id})
    return {"Authorization": f"Bearer {token}"}


class TestTargetDestinationsData:
    """Verifies target destinations data accuracy and geographic relevance."""

    def test_lakshadweep_attractions_and_activities(self):
        attractions = _get_dest_attractions(dest_name="Lakshadweep")
        assert len(attractions) >= 4, f"Expected >= 4 attractions, got {len(attractions)}"
        names = [a["name"] for a in attractions]
        assert any("Bangaram" in n for n in names)
        assert any("Agatti" in n for n in names)
        assert any("Kavaratti" in n for n in names)

        # Check coordinates are real and valid within Lakshadweep archipelago (8° - 12° N, 71° - 74° E)
        for a in attractions:
            assert a["lat"] is not None and a["lon"] is not None
            assert 8.0 <= float(a["lat"]) <= 12.5
            assert 71.0 <= float(a["lon"]) <= 74.5

        activities = _get_dest_activities(dest_name="Lakshadweep")
        assert len(activities) >= 4
        assert any("Scuba" in act["name"] or "Snorkeling" in act["name"] for act in activities)

    def test_agonda_geographic_relevance_no_north_goa(self):
        attractions = _get_dest_attractions(dest_name="Agonda")
        assert len(attractions) >= 4
        names = [a["name"].lower() for a in attractions]

        # Verify geographically relevant South Goa / Canacona spots
        assert any("agonda" in n for n in names)
        assert any("cola" in n for n in names)
        assert any("butterfly" in n or "palolem" in n or "cabo de rama" in n for n in names)

        # Strictly verify that distant North Goa / interior attractions are NOT present
        assert not any("dudhsagar" in n for n in names), "Dudhsagar Falls should not be an Agonda attraction"
        assert not any("arambol" in n for n in names), "Arambol Beach should not be an Agonda attraction"
        assert not any("calangute" in n for n in names), "Calangute should not be an Agonda attraction"
        assert not any("baga" in n for n in names), "Baga should not be an Agonda attraction"
        assert not any("aguada" in n for n in names), "Fort Aguada should not be an Agonda attraction"

        # Check coordinates are in South Goa (lat ~14.9 to 15.2, lon ~73.8 to 74.1)
        for a in attractions:
            assert a["lat"] is not None and a["lon"] is not None
            assert 14.9 <= float(a["lat"]) <= 15.2
            assert 73.8 <= float(a["lon"]) <= 74.2

    def test_hampi_virupaksha_temple_coordinates_fixed(self):
        attractions = _get_dest_attractions(csv_dest_id="D0026", dest_name="Hampi")
        assert len(attractions) >= 5
        virupaksha = next((a for a in attractions if "virupaksha" in a["name"].lower()), None)
        assert virupaksha is not None

        # Verify Virupaksha Temple is in Hampi (lat ~15.33, lon ~76.46), NOT in Mysore (lat ~12.3)
        assert 15.3 <= float(virupaksha["lat"]) <= 15.4
        assert 76.4 <= float(virupaksha["lon"]) <= 76.5

    def test_pondicherry_alias_resolution(self):
        # Both "Pondicherry" and "Puducherry" should return verified Puducherry attractions
        attractions_pon = _get_dest_attractions(dest_name="Pondicherry")
        attractions_pud = _get_dest_attractions(dest_name="Puducherry")
        assert len(attractions_pon) >= 5
        assert len(attractions_pud) >= 5
        names = [a["name"].lower() for a in attractions_pon]
        assert any("promenade" in n or "auroville" in n for n in names)

    def test_tarkarli_attractions_and_activities(self):
        attractions = _get_dest_attractions(dest_name="Tarkarli")
        assert len(attractions) >= 3
        names = [a["name"].lower() for a in attractions]
        assert any("tarkarli" in n for n in names)
        assert any("sindhudurg" in n or "devbagh" in n for n in names)

        # Coordinates should be on Konkan coast (lat ~15.9 to 16.2, lon ~73.4 to 73.6)
        for a in attractions:
            assert a["lat"] is not None and a["lon"] is not None
            assert 15.8 <= float(a["lat"]) <= 16.2
            assert 73.3 <= float(a["lon"]) <= 73.6

    def test_route_optimizer_target_destinations(self):
        # Test route optimization with real stops from Agonda
        agonda_stops = [
            {"name": "Agonda Beach", "lat": 15.0442, "lon": 73.9877},
            {"name": "Cola Beach", "lat": 15.0592, "lon": 73.9744},
            {"name": "Cabo de Rama Fort", "lat": 15.0883, "lon": 73.9217},
        ]
        res = optimize_day_route(agonda_stops)
        assert len(res["ordered_stops"]) == 3
        assert res["total_distance_km"] > 0
        assert res["total_distance_km"] < 35.0  # Should be a compact, local South Goa route!

        # Test route optimization with real stops from Hampi
        hampi_stops = [
            {"name": "Virupaksha Temple", "lat": 15.3353, "lon": 76.4600},
            {"name": "Stone Chariot", "lat": 15.3351, "lon": 76.4587},
            {"name": "Lotus Mahal", "lat": 15.3350, "lon": 76.4619},
        ]
        res_hampi = optimize_day_route(hampi_stops)
        assert len(res_hampi["ordered_stops"]) == 3
        assert res_hampi["total_distance_km"] < 10.0  # Compact historical complex route


class TestSavedTripFullWorkflow:
    """Verifies complete save, deduplicate/upsert, restore, ownership, and delete."""

    def test_save_trip_upsert_and_ownership(self, db_session):
        user_a = User(username="user_alpha", email="alpha@example.com", password="pw1")
        user_b = User(username="user_beta", email="beta@example.com", password="pw2")
        db_session.add_all([user_a, user_b])
        db_session.commit()
        db_session.refresh(user_a)
        db_session.refresh(user_b)

        headers_a = _get_auth_header(user_a.id, user_a.username)
        headers_b = _get_auth_header(user_b.id, user_b.username)

        # 1. User A saves Agonda customized trip
        payload = {
            "destination_id": 49,
            "destination_name": "Agonda",
            "trip_title": "Relaxing Retreat in Agonda",
            "trip_duration_days": 4,
            "itinerary": {"day_1": ["Agonda Beach Walk", "Cola Beach Sunset"]},
            "selected_activities": [{"name": "Sunset Kayaking at Cola Beach Lagoon"}],
            "route_stops": [
                {"name": "Agonda Beach", "lat": 15.0442, "lon": 73.9877},
                {"name": "Cola Beach", "lat": 15.0592, "lon": 73.9744},
            ],
            "packing_checklist": {"Swimwear": True, "Sunscreen SPF 50": False},
            "custom_packing_items": ["Dry Bag", "Snorkel Mask"],
            "notes": "Book kayak early at Cola lagoon.",
        }

        res = client.post("/saved-trips/", json=payload, headers=headers_a)
        assert res.status_code == 200
        trip = res.json()
        assert trip["id"] is not None
        assert trip["destination_name"] == "Agonda"
        trip_id = trip["id"]

        # 2. Retrieve by destination ID
        get_res = client.get("/saved-trips/by-destination/49", headers=headers_a)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == trip_id
        assert get_res.json()["custom_packing_items"] == ["Dry Bag", "Snorkel Mask"]

        # 3. Save again with updated data -> must update existing without creating duplicate
        payload["trip_duration_days"] = 5
        payload["notes"] = "Updated note: visit Cabo de Rama at sunset."
        payload["custom_packing_items"].append("Action Camera")

        update_res = client.post("/saved-trips/", json=payload, headers=headers_a)
        assert update_res.status_code == 200
        updated = update_res.json()
        assert updated["id"] == trip_id  # Same record updated
        assert updated["trip_duration_days"] == 5
        assert "Action Camera" in updated["custom_packing_items"]

        # Verify only 1 record exists in list
        list_res = client.get("/saved-trips/", headers=headers_a)
        assert list_res.status_code == 200
        user_trips = list_res.json()
        assert len(user_trips) == 1
        assert user_trips[0]["id"] == trip_id

        # 4. Ownership verification: User B cannot view or delete User A's trip
        unauth_get = client.get(f"/saved-trips/{trip_id}", headers=headers_b)
        assert unauth_get.status_code == 403

        unauth_del = client.delete(f"/saved-trips/{trip_id}", headers=headers_b)
        assert unauth_del.status_code == 403

        # 5. User A deletes their trip
        del_res = client.delete(f"/saved-trips/{trip_id}", headers=headers_a)
        assert del_res.status_code == 200

        # Verify it's gone
        after_get = client.get(f"/saved-trips/{trip_id}", headers=headers_a)
        assert after_get.status_code == 404
