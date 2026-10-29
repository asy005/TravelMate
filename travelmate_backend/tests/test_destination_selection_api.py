"""
Regression tests for destination selection through the assistant API.

Verifies that:
1. When a user clicks a destination card ("I want to plan my trip to Darjeeling"),
   the /assistant/message endpoint re-generates the plan with Darjeeling as the
   primary destination, preserving budget, duration, travelers, and travel_style.
2. The returned plan's trip_overview.primary_destination matches the selected
   destination.
3. The user's prior preferences (budget, duration, travelers, travel_style) are
   NOT erased by the destination selection.
"""
from unittest.mock import patch, MagicMock
import json
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.conversation import ConversationSession
from app.models.destination import Destination
from app.services.conversation_engine import EMPTY_SLOTS


# ---------------------------------------------------------------------------
# In-memory DB fixture
# ---------------------------------------------------------------------------
@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(db_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def _seed_ready_session(db, session_id: str = "test-dest-sel"):
    """
    Seed a ConversationSession that is in 'ready' state with a completed plan
    and the 4 required slots filled in.  This replicates the state the app
    reaches after the user answers all required questions.
    """
    darjeeling = Destination(
        name="Darjeeling",
        country="India",
        description="The queen of hills",
        lat=27.0360,
        lon=88.2627,
        category="Hill Station",
    )
    goa = Destination(
        name="Goa",
        country="India",
        description="Beach paradise",
        lat=15.2993,
        lon=74.1240,
        category="Beach",
    )
    db.add_all([darjeeling, goa])
    db.flush()

    # A minimal "ready" plan referencing Goa as the initial choice
    existing_plan = {
        "trip_overview": {
            "primary_destination": "Goa",
            "duration_days": 5,
            "travelers": 2,
            "budget": "30000",
            "travel_style": "relaxing",
        },
        "destinations": [{"id": goa.id, "name": "Goa"}],
        "budget": {},
        "day_wise_itinerary": [],
    }
    existing_slots = {
        **dict(EMPTY_SLOTS),
        "budget": "30000",
        "duration_days": 5,
        "travelers": 2,
        "travel_style": "relaxing",
        "destination": "Goa",
    }
    session = ConversationSession(
        session_id=session_id,
        messages=[],
        slots=existing_slots,
        status="ready",
        generated_plan=existing_plan,
    )
    db.add(session)
    db.commit()
    db.refresh(darjeeling)
    db.refresh(goa)
    db.refresh(session)
    return darjeeling, goa, session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDestinationSelection:
    def test_destination_selection_updates_plan_primary_destination(self, client, db):
        """
        Selecting Darjeeling from recommendations must update the plan so that
        trip_overview.primary_destination == 'Darjeeling'.
        """
        darjeeling, _goa, sess = _seed_ready_session(db)

        # Mock generate_plan to avoid side effects (LLM, weather, etc.) while
        # still verifying that the correct destination was requested.
        darjeeling_plan = {
            "trip_overview": {
                "primary_destination": "Darjeeling",
                "duration_days": 5,
                "travelers": 2,
                "budget": "30000",
                "travel_style": "relaxing",
            },
            "destinations": [{"id": darjeeling.id, "name": "Darjeeling"}],
            "budget": {"total": 30000},
            "day_wise_itinerary": [],
            "slots_used": {
                "budget": "30000",
                "duration_days": 5,
                "travelers": 2,
                "travel_style": "relaxing",
                "destination": "Darjeeling",
            },
        }

        with patch(
            "app.services.refinement_engine.generate_plan",
            return_value=darjeeling_plan,
        ) as mock_gen:
            res = client.post("/assistant/message", json={
                "session_id": sess.session_id,
                "message": "I want to plan my trip to Darjeeling.",
            })

        assert res.status_code == 200, res.text
        data = res.json()

        # The plan must be returned and contain Darjeeling
        assert data["ready_for_plan"] is True
        assert data["plan"] is not None
        assert data["plan"]["trip_overview"]["primary_destination"] == "Darjeeling"

        # generate_plan must have been called (not skipped)
        mock_gen.assert_called_once()

        # The slots passed to generate_plan must include destination=Darjeeling
        call_slots = mock_gen.call_args[0][1]  # positional arg: slots
        assert call_slots.get("destination", "").lower() == "darjeeling", (
            f"Expected destination='Darjeeling' in slots, got: {call_slots.get('destination')}"
        )

    def test_destination_selection_preserves_budget_duration_travelers_style(self, client, db):
        """
        After selecting a destination, the user's prior budget, duration,
        travelers count, and travel_style must survive in updated_slots.
        """
        _darjeeling, _goa, sess = _seed_ready_session(db)

        captured = {}

        def fake_generate(db_session, slots, **kwargs):
            captured["slots"] = dict(slots)
            return {
                "trip_overview": {
                    "primary_destination": "Darjeeling",
                    "duration_days": slots.get("duration_days"),
                    "travelers": slots.get("travelers"),
                },
                "destinations": [{"id": 1, "name": "Darjeeling"}],
                "budget": {},
                "day_wise_itinerary": [],
                "slots_used": slots,
            }

        with patch("app.services.refinement_engine.generate_plan", side_effect=fake_generate):
            res = client.post("/assistant/message", json={
                "session_id": sess.session_id,
                "message": "I want to plan my trip to Darjeeling.",
            })

        assert res.status_code == 200, res.text
        s = captured["slots"]
        assert s.get("budget") == "30000", f"Budget was lost: {s.get('budget')}"
        assert s.get("duration_days") == 5, f"duration_days was lost: {s.get('duration_days')}"
        assert s.get("travelers") == 2, f"travelers was lost: {s.get('travelers')}"
        assert s.get("travel_style") == "relaxing", f"travel_style was lost: {s.get('travel_style')}"

    def test_destination_selection_uses_keyword_fallback_when_llm_unavailable(self, client, db):
        """
        When the LLM gateway is down, the keyword fallback must still correctly
        detect change_type='destination' and extract the destination name.
        """
        _darjeeling, _goa, sess = _seed_ready_session(db)

        stub_plan = {
            "trip_overview": {"primary_destination": "Darjeeling", "duration_days": 5, "travelers": 2},
            "destinations": [{"id": 1, "name": "Darjeeling"}],
            "budget": {},
            "day_wise_itinerary": [],
            "slots_used": {"destination": "Darjeeling", "budget": "30000", "duration_days": 5},
        }

        from app.services.llm_gateway import LLMGatewayError

        with patch("app.services.refinement_engine.chat_completion", side_effect=LLMGatewayError("no key")):
            with patch("app.services.refinement_engine.generate_plan", return_value=stub_plan) as mock_gen:
                res = client.post("/assistant/message", json={
                    "session_id": sess.session_id,
                    "message": "I want to plan my trip to Darjeeling.",
                })

        assert res.status_code == 200, res.text
        assert res.json()["plan"]["trip_overview"]["primary_destination"] == "Darjeeling"
        call_slots = mock_gen.call_args[0][1]
        assert call_slots.get("destination", "").lower() == "darjeeling"
