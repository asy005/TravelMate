import pytest
from unittest.mock import MagicMock, patch

from app.services.rag_engine import fallback_recommendation, query_knowledge_base
from app.services.highlights_service import top_highlights_from_rag
from app.services.geo_lookup import get_nearby_attractions, guess_coordinates
from app.services.plan_orchestrator import (
    _day_wise_itinerary,
    _llm_explanation,
    regenerate_itinerary,
)
from app.models.destination import Destination


class TestRAGDestinationGrounding:
    def test_fallback_recommendation_uses_explicit_destination(self):
        """Destination passed explicitly must never be replaced by regex or defaults."""
        res = fallback_recommendation(
            "Adventurous trip for 4 days",
            "",
            destination_name="Bangalore",
        )
        assert res["destination"] == "Bangalore"
        assert res["destination"] != "Peaceful Nature Retreat"
        assert "Bangalore" in res["description"]

    def test_fallback_recommendation_never_returns_peaceful_nature_retreat(self):
        """Even with an unparseable query, fallback destination must never be 'Peaceful Nature Retreat'."""
        res = fallback_recommendation("adventurous solo trip with hiking", "")
        assert res["destination"] != "Peaceful Nature Retreat"

    def test_query_knowledge_base_grounds_best_destination(self):
        """query_knowledge_base must return the requested destination as best_destination."""
        res = query_knowledge_base(
            "adventurous trip to Bangalore",
            destination_name="Bangalore",
        )
        assert res["best_destination"] == "Bangalore"
        assert res["best_destination"] != "Peaceful Nature Retreat"


class TestHighlightsDestinationGrounding:
    def test_curated_highlights_for_bangalore(self):
        """Bangalore highlights must reference actual Bangalore attractions, not coastal content."""
        highlights = top_highlights_from_rag({}, max_items=4, destination_name="Bangalore")
        assert len(highlights) > 0
        joined = " ".join(highlights).lower()
        assert any(spot in joined for spot in ["cubbon", "lalbagh", "palace", "nandi hills"])
        assert "beach" not in joined
        assert "gokarna" not in joined

    def test_curated_highlights_for_bengaluru_alias(self):
        """Bengaluru alias must produce the same grounded highlights as Bangalore."""
        highlights = top_highlights_from_rag({}, max_items=4, destination_name="Bengaluru")
        assert len(highlights) > 0
        joined = " ".join(highlights).lower()
        assert "cubbon" in joined or "lalbagh" in joined
        assert "gokarna" not in joined

    def test_filters_out_gokarna_and_beach_snippets_for_bangalore(self):
        """RAG snippets from coastal places must be filtered out when the destination is Bangalore."""
        fake_rag = {
            "snippets": [
                {"text": "Relax on pristine Kudle Beach and enjoy sunset views over the Gokarna coast."},
                {"text": "Take a scenic walk through the lush green trees and historical gardens."},
            ]
        }
        highlights = top_highlights_from_rag(
            fake_rag,
            max_items=3,
            destination_name="Bangalore",
        )
        joined = " ".join(highlights).lower()
        assert "gokarna" not in joined
        assert "beach" not in joined


class TestDayWiseItineraryGrounding:
    def test_bangalore_curated_itinerary_contains_no_coastal_content(self):
        """Bangalore day-wise itinerary must describe Bangalore, not beaches or Gokarna."""
        dest = Destination(
            id=1,
            name="Bangalore",
            country="India",
            description="Known as the Garden City and Silicon Valley of India.",
            lat=12.9716,
            lon=77.5946,
            tags="gardens, tech, palaces, breweries",
        )
        itinerary = _day_wise_itinerary(dest, duration_days=3, highlights=[])
        assert len(itinerary) == 3
        full_text = " ".join(day["summary"].lower() for day in itinerary)
        assert "bangalore" in full_text
        assert "lalbagh" in full_text or "cubbon" in full_text or "vidhana soudha" in full_text
        assert "beach" not in full_text
        assert "gokarna" not in full_text

    def test_shimla_5_day_curated_itinerary_has_distinct_activities(self):
        """Regression test: 5-day Shimla itinerary must have 5 distinct days with no repeats on Days 3, 4, 5."""
        dest = Destination(
            id=6,
            name="Shimla",
            country="India",
            description="Capital of Himachal Pradesh, known for colonial architecture and Himalayan views.",
            lat=31.1048,
            lon=77.1734,
            tags="Hill Station,Relaxing,Himachal Pradesh",
        )
        itinerary = _day_wise_itinerary(dest, duration_days=5, highlights=[])
        assert len(itinerary) == 5

        summaries = [day["summary"] for day in itinerary]
        # Every day must have a distinct summary
        assert len(set(summaries)) == 5

        # Specifically verify Days 3, 4, 5 are distinct and do not repeat
        assert summaries[2] != summaries[3]
        assert summaries[3] != summaries[4]
        assert summaries[2] != summaries[4]

        # Destination-appropriate attractions must be present
        full_text = " ".join(summaries).lower()
        assert "shimla" in full_text
        assert any(k in full_text for k in ["mall road", "ridge", "kufri", "jakhoo", "lakkar", "chadwick", "tara devi"])
        assert "beach" not in full_text
        assert "gokarna" not in full_text

    def test_shimla_5_day_itinerary_with_legacy_highlights_no_repetition_on_days_3_4_5(self):
        """Regression test: passing legacy 3 highlights must not cause Days 3, 4, 5 to repeat the 3rd highlight."""
        dest = Destination(
            id=6,
            name="Shimla",
            country="India",
            description="Hill station in Himachal Pradesh.",
            lat=31.1048,
            lon=77.1734,
            tags="Hill Station,Relaxing",
        )
        legacy_highlights = [
            "Walk along Mall Road and explore local shops and cafes.",
            "Visit the Ridge and enjoy views of the surrounding hills.",
            "Explore nearby nature trails and scenic viewpoints.",
        ]
        itinerary = _day_wise_itinerary(dest, duration_days=5, highlights=legacy_highlights)
        assert len(itinerary) == 5

        summaries = [day["summary"] for day in itinerary]
        # All 5 days must have unique summaries
        assert len(set(summaries)) == 5

        # Confirm Days 3, 4, and 5 are distinct
        assert summaries[2] != summaries[3]
        assert summaries[3] != summaries[4]

        # The phrase 'Explore nearby nature trails and scenic viewpoints' must not repeat across days 3, 4, 5
        repeated_phrase = "Explore nearby nature trails and scenic viewpoints"
        count = sum(1 for s in summaries if repeated_phrase in s)
        assert count <= 1


class TestLLMExplanationFallback:
    def test_llm_explanation_fallback_uses_structured_metadata(self):
        """When LLM gateway fails, explanation fallback must not be the bare 'X is a destination in India.'"""
        dest = Destination(
            id=1,
            name="Bangalore",
            country="India",
            description="Known as the Garden City and Silicon Valley of India with pleasant climate.",
            tags="gardens, tech, palaces, breweries",
        )
        with patch("app.services.plan_orchestrator.chat_completion", side_effect=Exception("API unavailable")):
            explanation = _llm_explanation(dest, {"travel_style": "adventurous"})
            assert "Bangalore is a destination in India." != explanation
            assert "Bangalore" in explanation
            assert ("Garden City" in explanation or "gardens" in explanation)


class TestGeoLookupCuratedFallback:
    def test_bangalore_coordinates_guess(self):
        coords = guess_coordinates("Bangalore")
        assert coords is not None
        assert abs(coords[0] - 12.9716) < 0.01
        assert abs(coords[1] - 77.5946) < 0.01

    def test_bangalore_nearby_attractions_curated_fallback(self):
        """When OpenTripMap is unauthorized (HTTP 401) or offline, curated fallback returns Bangalore landmarks."""
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_get.return_value = mock_resp

            attractions = get_nearby_attractions(12.9716, 77.5946, max_results=4)
            assert len(attractions) > 0
            names = [a["name"].lower() for a in attractions]
            assert any("lalbagh" in n or "cubbon" in n or "palace" in n for n in names)
            assert all(a["source"] == "curated" for a in attractions)


class TestItineraryRegeneration:
    def test_regenerate_itinerary_preserves_bangalore_grounding(self, db_session):
        dest = Destination(
            name="Bangalore",
            country="India",
            description="Garden City of India.",
            lat=12.9716,
            lon=77.5946,
            tags="gardens, tech, parks",
        )
        db_session.add(dest)
        db_session.commit()

        slots = {"travel_style": "adventurous", "interests": "parks, trekking"}
        itinerary = regenerate_itinerary(db_session, dest.id, duration_days=3, slots=slots)
        assert len(itinerary) == 3
        full_text = " ".join(day["summary"].lower() for day in itinerary)
        assert "bangalore" in full_text
        assert "gokarna" not in full_text
        assert "beach" not in full_text


    def test_regenerate_itinerary_shimla_5_days_distinct(self, db_session):
        dest = Destination(
            name="Shimla",
            country="India",
            description="Capital of Himachal Pradesh.",
            lat=31.1048,
            lon=77.1734,
            tags="Hill Station,Relaxing",
        )
        db_session.add(dest)
        db_session.commit()

        slots = {"travel_style": "relaxing", "interests": "nature, scenic"}
        itinerary = regenerate_itinerary(db_session, dest.id, duration_days=5, slots=slots)
        assert len(itinerary) == 5
        summaries = [day["summary"] for day in itinerary]
        assert len(set(summaries)) == 5
        assert summaries[2] != summaries[3]
        assert summaries[3] != summaries[4]


class TestGeneratePlanShimlaRegression:
    def test_5_day_relaxing_trip_to_shimla_has_distinct_days(self, db_session):
        """End-to-end regression: generate_plan for 5-day relaxing Shimla trip must not repeat Days 3, 4, 5."""
        from app.services.plan_orchestrator import generate_plan

        dest = Destination(
            name="Shimla",
            country="India",
            description="Capital of Himachal Pradesh, hill station.",
            lat=31.1048,
            lon=77.1734,
            tags="Hill Station,Himachal Pradesh,Shimla,Relaxing",
            avg_rating=4.5,
        )
        db_session.add(dest)
        db_session.commit()

        slots = {
            "destination": "Shimla",
            "duration_days": 5,
            "travel_style": "relaxing",
            "budget": "medium",
        }
        plan = generate_plan(db_session, slots)
        assert plan is not None
        itinerary = plan.get("day_wise_itinerary", [])
        assert len(itinerary) == 5

        summaries = [day["summary"] for day in itinerary]
        assert len(set(summaries)) == 5
        assert summaries[2] != summaries[3]
        assert summaries[3] != summaries[4]

        repeated_phrase = "Explore nearby nature trails and scenic viewpoints"
        count = sum(1 for s in summaries if repeated_phrase in s)
        assert count <= 1
