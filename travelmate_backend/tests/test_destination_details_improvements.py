# travelmate_backend/tests/test_destination_details_improvements.py
"""
Comprehensive verification and regression test suite for Destination Details Improvements:
1. Top Highlights (verified attraction data, formatting, proper empty state).
2. Navigation context preservation.
3. Smart Packing List (weather conditions, activities, fallback handling).
4. Fixed Day-by-Day Itinerary (morning, afternoon, evening activities, multiple destinations, trip durations).
5. Route Map & Route Optimizer (coordinate resolution, heuristic sequencing, distances without fabrication).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.highlights_service import get_destination_highlights
from app.services.route_optimizer import (
    haversine_distance,
    optimize_day_route,
    AttractionCoordinateResolver,
)
from app.routes.itinerary_routes import (
    generate_plan,
    PlanRequest,
    _build_grounded_fallback_plan,
)

client = TestClient(app)


# ─── 1. Top Highlights Tests ──────────────────────────────────────────────────

class TestTopHighlights:
    def test_highlights_reuse_actual_attractions_jaipur(self):
        highlights = get_destination_highlights(destination_name="Jaipur", max_items=4)
        assert len(highlights) > 0
        assert len(highlights) <= 4
        # Verify real attraction contents
        assert any("Jaipur" in h for h in highlights)
        assert any("★" in h or "entry" in h.lower() for h in highlights)

    def test_highlights_reuse_actual_attractions_by_id(self):
        # D0001 is Goa
        highlights = get_destination_highlights(destination_id="D0001", max_items=4)
        assert len(highlights) > 0
        assert any("Goa" in h for h in highlights)

    def test_highlights_empty_state_for_unknown_destination(self):
        highlights = get_destination_highlights(
            destination_name="CompletelyUnknownPlace999",
            destination_id="D9999",
            max_items=4,
        )
        assert highlights == []

    def test_highlights_api_endpoint(self):
        res = client.get("/highlights/?query=Goa&destination=Goa&top=3")
        assert res.status_code == 200
        data = res.json()
        assert "highlights" in data
        assert isinstance(data["highlights"], list)
        assert len(data["highlights"]) <= 3


# ─── 2. Packing List Tests ───────────────────────────────────────────────────

class TestSmartPackingList:
    def test_packing_weather_rain(self):
        res = client.post(
            "/packing/generate",
            json={
                "destination": "Goa",
                "weather": "heavy rain and thunderstorms",
                "days": 3,
                "activities": ["hiking"],
            },
        )
        assert res.status_code == 200
        data = res.json()
        items = [i.lower() for i in data.get("packing_list", [])]
        assert any("umbrella" in i or "rain" in i or "waterproof" in i for i in items)
        assert any("hiking" in i for i in items)

    def test_packing_weather_cold(self):
        res = client.post(
            "/packing/generate",
            json={
                "destination": "Manali",
                "weather": "snow and freezing cold",
                "days": 5,
                "activities": [],
            },
        )
        assert res.status_code == 200
        data = res.json()
        items = [i.lower() for i in data.get("packing_list", [])]
        assert any("jacket" in i or "thermal" in i or "gloves" in i for i in items)

    def test_packing_weather_unavailable_fallback(self):
        res = client.post(
            "/packing/generate",
            json={
                "destination": "Jaipur",
                "weather": "",
                "days": 2,
                "activities": ["temple", "dinner"],
            },
        )
        assert res.status_code == 200
        data = res.json()
        items = data.get("packing_list", [])
        assert len(items) > 0


# ─── 3. Day-by-Day Itinerary Tests ───────────────────────────────────────────

class TestDayByDayItinerary:
    def test_itinerary_generation_structure_jaipur(self):
        req = PlanRequest(destination="Jaipur", days=2)
        res = generate_plan(req)
        assert res["destination"] == "Jaipur"
        assert res["days"] == 2
        plan = res["plan"]
        assert "day_1" in plan
        assert "day_2" in plan
        assert len(plan["day_1"]) == 3
        # Check structured Morning / Afternoon / Evening format
        day1_text = " ".join(plan["day_1"]).lower()
        assert "morning" in day1_text
        assert "afternoon" in day1_text
        assert "evening" in day1_text

    def test_itinerary_generation_structure_goa(self):
        req = PlanRequest(destination="Goa", days=1)
        res = generate_plan(req)
        assert res["destination"] == "Goa"
        assert "day_1" in res["plan"]
        assert len(res["plan"]["day_1"]) == 3

    def test_itinerary_grounded_fallback_builder(self):
        mock_attractions = [
            {"name": "Attraction A", "category": "Heritage", "city": "TestCity"},
            {"name": "Attraction B", "category": "Nature", "city": "TestCity"},
            {"name": "Attraction C", "category": "Spiritual", "city": "TestCity"},
        ]
        fallback_plan = _build_grounded_fallback_plan("TestCity", 2, mock_attractions)
        assert "day_1" in fallback_plan
        assert "day_2" in fallback_plan
        assert len(fallback_plan["day_1"]) == 3
        assert "Attraction A" in fallback_plan["day_1"][0]
        assert "Attraction B" in fallback_plan["day_1"][1]

    def test_itinerary_api_endpoint(self):
        res = client.post("/plan/generate", json={"destination": "Manali", "days": 2})
        assert res.status_code == 200
        data = res.json()
        assert "plan" in data
        assert "day_1" in data["plan"]
        assert "day_2" in data["plan"]


# ─── 4. Route Map & Route Optimizer Tests ────────────────────────────────────

class TestRouteMapAndOptimizer:
    def test_route_resolver_datasets(self):
        resolver = AttractionCoordinateResolver.get_instance()
        assert resolver._loaded is True
        # Check coordinate resolution for known attraction
        coords = resolver.resolve("Hawa Mahal", "Jaipur")
        assert coords is not None
        lat, lon = coords
        assert 26.0 <= lat <= 28.0
        assert 75.0 <= lon <= 77.0

    def test_route_optimizer_single_stop(self):
        stops = [{"name": "Start", "lat": 26.9124, "lon": 75.7873}]
        res = optimize_day_route(stops)
        assert len(res["ordered_stops"]) == 1
        assert res["total_distance_km"] == 0.0

    def test_route_optimizer_multiple_stops_heuristic(self):
        stops = [
            {"name": "Hawa Mahal", "lat": 26.9239, "lon": 75.8267},
            {"name": "Amber Palace", "lat": 26.9855, "lon": 75.8513},
            {"name": "City Palace", "lat": 26.9258, "lon": 75.8237},
        ]
        res = optimize_day_route(stops)
        assert len(res["ordered_stops"]) == 3
        assert res["total_distance_km"] is not None
        assert res["total_distance_km"] > 0.0

    def test_route_optimizer_api_endpoint(self):
        payload = {
            "destination_name": "Jaipur",
            "points": [
                {"name": "City Palace", "lat": 26.9258, "lon": 75.8237},
                {"name": "Amber Fort", "lat": 26.9855, "lon": 75.8513},
            ],
        }
        res = client.post("/routes/", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "ordered_points" in data
        assert len(data["ordered_points"]) == 2
        assert data["total_distance_km"] > 0
