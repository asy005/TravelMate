# travelmate_backend/tests/test_route_optimization.py
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.destination import Destination
from app.services.route_optimizer import (
    haversine_distance,
    optimize_day_route,
    optimize_trip_builder_plan,
    AttractionCoordinateResolver,
)
from app.services.plan_orchestrator import _day_wise_itinerary, generate_plan
from app.services.trip_builder_service import build_day_wise_itinerary
from app.services.refinement_engine import apply_refinement


client = TestClient(app)


class TestDistanceCalculation:
    """Verifies Haversine distance calculation and boundary cases."""

    def test_haversine_known_coordinates(self):
        # New Delhi (28.6139, 77.2090) to Mumbai (19.0760, 72.8777)
        dist = haversine_distance((28.6139, 77.2090), (19.0760, 72.8777))
        assert dist is not None
        # Reference great-circle distance is ~1148 km
        assert 1140.0 <= dist <= 1160.0

    def test_haversine_same_coordinates_returns_zero(self):
        dist = haversine_distance((28.6129, 77.2295), (28.6129, 77.2295))
        assert dist == 0.0

    def test_haversine_missing_or_invalid_coordinates(self):
        assert haversine_distance((None, None), (28.6, 77.2)) is None
        assert haversine_distance(None, (28.6, 77.2)) is None
        assert haversine_distance((28.6, None), (28.6, 77.2)) is None
        assert haversine_distance(("invalid", "coord"), (28.6, 77.2)) is None


class TestRouteOrderingAndHeuristics:
    """Verifies Nearest-Neighbor + 2-opt ordering and distance improvements."""

    def test_route_ordering_reduces_crisscross_distance(self):
        # 4 stops in Delhi arranged in a deliberately zigzag sequence
        stops = [
            {"name": "Qutub Minar", "lat": 28.5245, "lon": 77.1855},
            {"name": "Red Fort", "lat": 28.6562, "lon": 77.2410},
            {"name": "Humayun's Tomb", "lat": 28.5933, "lon": 77.2507},
            {"name": "India Gate", "lat": 28.6129, "lon": 77.2295},
        ]

        # Calculate unoptimized distance
        unoptimized_dist = (
            haversine_distance((stops[0]["lat"], stops[0]["lon"]), (stops[1]["lat"], stops[1]["lon"]))
            + haversine_distance((stops[1]["lat"], stops[1]["lon"]), (stops[2]["lat"], stops[2]["lon"]))
            + haversine_distance((stops[2]["lat"], stops[2]["lon"]), (stops[3]["lat"], stops[3]["lon"]))
        )

        result = optimize_day_route(stops)
        optimized_dist = result["total_distance_km"]

        assert len(result["ordered_stops"]) == 4
        # Optimized distance should be shorter than zigzag distance
        assert optimized_dist < unoptimized_dist
        assert result["distance_as_proxy"] is True
        assert result["is_globally_optimal"] is False
        assert "Nearest-Neighbor with 2-opt" in result["algorithm"]

    def test_return_to_start_included_in_tour(self):
        stops = [
            {"name": "Hotel / Origin", "lat": 28.6139, "lon": 77.2090, "is_start": True},
            {"name": "India Gate", "lat": 28.6129, "lon": 77.2295},
            {"name": "Humayun's Tomb", "lat": 28.5933, "lon": 77.2507},
        ]
        result_open = optimize_day_route(stops, return_to_start=False)
        result_closed = optimize_day_route(stops, return_to_start=True)

        assert result_closed["return_to_start"] is True
        assert result_closed["total_distance_km"] > result_open["total_distance_km"]
        assert len(result_closed["legs"]) == len(stops)  # includes return leg


class TestMissingCoordinatesSafelyHandled:
    """Verifies that missing coordinates are never fabricated and activities are preserved."""

    def test_unmapped_stops_preserved_without_inventing_coordinates(self):
        stops = [
            {"name": "India Gate", "lat": 28.6129, "lon": 77.2295},
            {"name": "Leisure walk at local market", "lat": None, "lon": None},
            {"name": "Humayun's Tomb", "lat": 28.5933, "lon": 77.2507},
            {"name": "Dinner at unmapped eatery", "lat": None, "lon": None},
        ]

        result = optimize_day_route(stops)
        ordered = result["ordered_stops"]

        # All 4 activities must be preserved
        assert len(ordered) == 4
        names = [s["name"] for s in ordered]
        assert "India Gate" in names
        assert "Leisure walk at local market" in names
        assert "Humayun's Tomb" in names
        assert "Dinner at unmapped eatery" in names

        # Unmapped stops MUST NOT have invented coordinates
        for s in ordered:
            if "unmapped" in s["name"] or "Leisure" in s["name"]:
                assert s["lat"] is None
                assert s["lon"] is None
                assert s["has_coordinates"] is False

        assert result["unmapped_stops_count"] == 2


class TestSingleAndZeroStopRoutes:
    """Verifies edge cases for zero and single stops."""

    def test_zero_stops(self):
        result = optimize_day_route([])
        assert result["ordered_stops"] == []
        assert result["total_distance_km"] == 0.0
        assert result["unmapped_stops_count"] == 0

    def test_single_stop(self):
        stops = [{"name": "Only Stop", "lat": 28.6139, "lon": 77.2090}]
        result = optimize_day_route(stops)
        assert len(result["ordered_stops"]) == 1
        assert result["total_distance_km"] == 0.0
        assert result["ordered_stops"][0]["name"] == "Only Stop"


class TestFixedAppointmentsAndUserOrdering:
    """Verifies preservation of fixed slots and explicit ordering."""

    def test_fixed_slot_preserved_in_final_order(self):
        stops = [
            {"name": "Stop A", "lat": 28.6000, "lon": 77.2000},
            {"name": "Fixed Lunch Appointment", "lat": 28.7000, "lon": 77.3000, "fixed_slot": 1, "is_fixed": True},
            {"name": "Stop B", "lat": 28.6050, "lon": 77.2050},
        ]
        result = optimize_day_route(stops)
        ordered = result["ordered_stops"]
        assert len(ordered) == 3
        # The fixed appointment must remain at index 1
        assert ordered[1]["name"] == "Fixed Lunch Appointment"

    def test_explicit_user_ordering_preserved(self):
        stops = [
            {"name": "Stop 3", "lat": 28.6500, "lon": 77.2400, "order": 3},
            {"name": "Stop 1", "lat": 28.5200, "lon": 77.1800, "order": 1},
            {"name": "Stop 2", "lat": 28.6100, "lon": 77.2200, "order": 2},
        ]
        result = optimize_day_route(stops)
        ordered = result["ordered_stops"]
        assert [s["name"] for s in ordered] == ["Stop 1", "Stop 2", "Stop 3"]


class TestMultipleDaysAndDestinationIsolation:
    """Verifies multi-day isolation and destination boundaries."""

    def test_day_and_destination_isolation(self):
        dest_delhi = Destination(id=1, name="Delhi", country="India", lat=28.6139, lon=77.2090)
        itinerary = _day_wise_itinerary(dest_delhi, duration_days=3, highlights=[])

        assert len(itinerary) == 3
        for day in itinerary:
            assert "day" in day
            assert "summary" in day
            assert "activities" in day
            assert "route" in day
            assert isinstance(day["activities"], list)
            assert len(day["activities"]) >= 1

        # Check destination isolation: Delhi itinerary should never contain foreign landmarks
        full_text = " ".join(day["summary"].lower() for day in itinerary)
        assert "delhi" in full_text
        assert "jaipur" not in full_text
        assert "goa" not in full_text


class TestPipelineNonRegression:
    """Verifies that route optimization does not break packing, budget, duration or refinement."""

    def test_generate_plan_includes_route_metadata(self, db_session):
        dest = Destination(
            name="Goa",
            country="India",
            lat=15.2993,
            lon=74.1240,
            tags="beach, relaxing",
            avg_rating=4.5,
        )
        db_session.add(dest)
        db_session.commit()

        slots = {
            "origin": "Bangalore",
            "destination": "Goa",
            "duration_days": 3,
            "travelers": 2,
            "budget": "Medium",
            "travel_style": "relaxing",
            "interests": "beach",
        }
        plan = generate_plan(db_session, slots)
        assert plan is not None

        # Check itinerary contract
        itinerary = plan.get("day_wise_itinerary", [])
        assert len(itinerary) == 3
        for day in itinerary:
            assert "day" in day
            assert "summary" in day
            assert "route" in day
            assert day["route"]["distance_as_proxy"] is True

        # Check itinerary top-level summary
        assert "itinerary_route_summary" in plan
        assert plan["itinerary_route_summary"]["distance_as_proxy"] is True

        # Check packing and budget are not broken
        assert len(plan.get("packing_list", [])) > 0
        assert plan.get("budget") is not None
        assert "estimated_total" in plan["budget"]

    def test_refinement_preserves_route_optimized_itinerary(self, db_session):
        dest = Destination(
            name="Goa",
            country="India",
            lat=15.2993,
            lon=74.1240,
            tags="beach, relaxing",
            avg_rating=4.5,
        )
        db_session.add(dest)
        db_session.commit()

        slots = {
            "origin": "Bangalore",
            "destination": "Goa",
            "duration_days": 3,
            "travelers": 2,
            "budget": "Medium",
            "travel_style": "relaxing",
            "interests": "beach",
        }
        plan = generate_plan(db_session, slots)

        # Refine trip duration from 3 days to 4 days
        updated_plan, updated_slots = apply_refinement(
            db=db_session,
            current_slots=slots,
            plan=plan,
            change_type="duration",
            extracted_slots={"duration_days": 4},
            remove_package=False,
        )

        assert updated_slots["duration_days"] == 4
        new_itinerary = updated_plan.get("day_wise_itinerary", [])
        assert len(new_itinerary) == 4
        for day in new_itinerary:
            assert "route" in day
            assert "summary" in day


class TestRouteEndpointsAndTripBuilder:
    """Verifies FastAPI /routes/ endpoint and Trip Builder integration."""

    def test_routes_api_endpoint(self):
        payload = {
            "points": [
                {"name": "India Gate", "lat": 28.6129, "lon": 77.2295},
                {"name": "Humayun's Tomb", "lat": 28.5933, "lon": 77.2507},
            ],
            "return_to_start": False,
        }
        response = client.post("/routes/", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "ordered_points" in data
        assert len(data["ordered_points"]) == 2
        assert data["total_distance_km"] > 0
        assert data["distance_as_proxy"] is True

    def test_trip_builder_plan_optimization(self):
        plan = {
            "day_1": [
                "Visit Qutub Minar",
                "Explore Red Fort",
                "Stroll near India Gate",
            ],
            "day_2": [
                "Relax at scenic spot",
                "Souvenir shopping at local market",
            ],
        }
        optimized = optimize_trip_builder_plan("Delhi", plan)
        assert "day_1" in optimized
        assert "day_2" in optimized
        assert len(optimized["day_1"]) == 3
        assert len(optimized["day_2"]) == 2
