# travelmate_backend/tests/test_saved_trips.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.services.auth_utils import create_token

client = TestClient(app)


def _get_auth_header(user_id: int, username: str) -> dict:
    token = create_token({"sub": username, "user_id": user_id})
    return {"Authorization": f"Bearer {token}"}


class TestSavedTrips:
    """Tests CRUD, authorization, deduplication, and persistence for SavedTrips."""

    def test_save_and_retrieve_trip(self, db_session):
        user = User(
            username="traveler_one",
            email="traveler_one@example.com",
            password="dummy_hashed_password_1",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        headers = _get_auth_header(user.id, user.username)

        payload = {
            "destination_id": 26,
            "destination_name": "Hampi",
            "trip_title": "Heritage Trip to Hampi",
            "trip_duration_days": 4,
            "travel_dates": "Nov 20 - Nov 24, 2026",
            "destination_data": {"state": "Karnataka", "country": "India"},
            "itinerary": {"day_1": ["Virupaksha Temple", "Stone Chariot"]},
            "selected_attractions": ["Virupaksha Temple", "Stone Chariot"],
            "selected_activities": ["Vijayanagara Empire Heritage Walking Tour"],
            "route_stops": [{"name": "Hampi"}, {"name": "Virupaksha Temple"}],
            "packing_checklist": {"Sun hat": True, "Comfortable Walking Shoes": False},
            "custom_packing_items": ["DSLR Camera", "Wide brim hat"],
            "trip_preferences": {"budget": "Medium", "travel_style": "Cultural"},
            "notes": "Remember to hire a local guide at the temple complex.",
        }

        # 1. Save trip
        post_res = client.post("/saved-trips/", json=payload, headers=headers)
        assert post_res.status_code == 200, post_res.text
        created = post_res.json()
        assert created["id"] is not None
        assert created["destination_name"] == "Hampi"
        assert created["trip_duration_days"] == 4
        trip_id = created["id"]

        # 2. Get all saved trips for user
        list_res = client.get("/saved-trips/", headers=headers)
        assert list_res.status_code == 200
        trips = list_res.json()
        assert len(trips) >= 1
        assert any(t["id"] == trip_id for t in trips)

        # 3. Get trip by destination ID
        by_dest_res = client.get("/saved-trips/by-destination/26", headers=headers)
        assert by_dest_res.status_code == 200
        by_dest = by_dest_res.json()
        assert by_dest is not None
        assert by_dest["id"] == trip_id
        assert by_dest["custom_packing_items"] == ["DSLR Camera", "Wide brim hat"]

        # 4. Update trip (prevents duplicates by updating existing for same destination)
        payload["trip_duration_days"] = 5
        payload["notes"] = "Updated note: also visit Sanapur Lake."
        post_res2 = client.post("/saved-trips/", json=payload, headers=headers)
        assert post_res2.status_code == 200
        updated = post_res2.json()
        assert updated["id"] == trip_id  # same record updated, no duplicate created!
        assert updated["trip_duration_days"] == 5
        assert updated["notes"] == "Updated note: also visit Sanapur Lake."

        # 5. Ownership check: another user cannot access or delete this trip
        user2 = User(
            username="traveler_two",
            email="traveler_two@example.com",
            password="dummy_hashed_password_2",
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)
        headers2 = _get_auth_header(user2.id, user2.username)

        unauth_get = client.get(f"/saved-trips/{trip_id}", headers=headers2)
        assert unauth_get.status_code == 403

        unauth_del = client.delete(f"/saved-trips/{trip_id}", headers=headers2)
        assert unauth_del.status_code == 403

        # 6. Delete trip by owner
        del_res = client.delete(f"/saved-trips/{trip_id}", headers=headers)
        assert del_res.status_code == 200

        # Verify it is deleted
        get_after = client.get(f"/saved-trips/{trip_id}", headers=headers)
        assert get_after.status_code == 404
