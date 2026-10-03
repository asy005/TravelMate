from unittest.mock import patch

from app.services.conversation_engine import (
    merge_slots,
    missing_required_slots,
    is_ready_for_plan,
    process_message,
    EMPTY_SLOTS,
)
from app.services.llm_gateway import LLMGatewayError


def test_merge_slots_fills_in_new_values():
    old = dict(EMPTY_SLOTS)
    new = {"budget": "medium", "travelers": 2}
    merged = merge_slots(old, new)
    assert merged["budget"] == "medium"
    assert merged["travelers"] == 2
    assert merged["duration_days"] is None


def test_merge_slots_never_erases_a_confirmed_value():
    old = dict(EMPTY_SLOTS)
    old["budget"] = "luxury"
    # A later extraction that doesn't mention budget must not wipe it out.
    merged = merge_slots(old, {"travelers": 3})
    assert merged["budget"] == "luxury"
    assert merged["travelers"] == 3


def test_missing_required_slots_and_readiness():
    slots = dict(EMPTY_SLOTS)
    assert missing_required_slots(slots) == ["budget", "duration_days", "travelers", "travel_style"]
    assert is_ready_for_plan(slots) is False

    slots.update({"budget": "medium", "duration_days": 5, "travelers": 2, "travel_style": "relaxing"})
    assert missing_required_slots(slots) == []
    assert is_ready_for_plan(slots) is True


def test_process_message_falls_back_gracefully_when_llm_unavailable():
    """
    If the LLM gateway is unavailable (no API key, network error, etc.),
    the assistant must still return a sensible next question rather than
    raising an error up to the API layer.
    """
    with patch(
        "app.services.conversation_engine.chat_completion",
        side_effect=LLMGatewayError("no key configured"),
    ):
        reply, updated_slots, ready = process_message(
            prior_slots=dict(EMPTY_SLOTS),
            conversation_history=[],
            user_message="I want to go on a trip",
        )

    assert isinstance(reply, str) and len(reply) > 0
    assert ready is False
    assert updated_slots == dict(EMPTY_SLOTS)


def test_process_message_merges_llm_extracted_slots():
    fake_response = (
        '{"slots": {"budget": "medium", "travelers": 2, "duration_days": 5, '
        '"travel_style": "relaxing"}, "reply": "Great, where are you starting from?", '
        '"ready_for_plan": true}'
    )
    with patch(
        "app.services.conversation_engine.chat_completion",
        return_value=fake_response,
    ):
        reply, updated_slots, ready = process_message(
            prior_slots=dict(EMPTY_SLOTS),
            conversation_history=[],
            user_message="Medium budget, 2 of us, 5 days, want to relax",
        )

    assert updated_slots["budget"] == "medium"
    assert updated_slots["travelers"] == 2
    assert ready is True
    assert "starting from" in reply
