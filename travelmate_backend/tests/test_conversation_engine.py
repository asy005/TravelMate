from unittest.mock import patch

from app.services.conversation_engine import (
    merge_slots,
    missing_required_slots,
    is_ready_for_plan,
    process_message,
    EMPTY_SLOTS,
    extract_explicit_slots,
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


def test_extracts_budget_from_common_natural_language():
    assert extract_explicit_slots("My budget is 15000")["budget"] == "15000"
    assert extract_explicit_slots("Budget around 15k")["budget"] == "15000"
    assert extract_explicit_slots("I have a budget of ₹15,000")["budget"] == "15000"


def test_explicit_extraction_does_not_confuse_duration_with_budget():
    slots = extract_explicit_slots("2 people for 3 days, relaxing beach trip")
    assert "budget" not in slots
    assert slots["travelers"] == 2
    assert slots["duration_days"] == 3
    assert slots["travel_style"] == "relaxing"


def test_extracts_singular_beach_interest():
    slots = extract_explicit_slots(
        "I want a relaxing beach trip from Bangalore for 2 people, "
        "for 4 days, with a budget of ₹15,000. I prefer travelling by car "
        "and vegetarian food."
    )
    assert slots["origin"] == "Bangalore"
    assert slots["interests"] == "beaches"
    assert slots["travel_style"] == "relaxing"
    assert slots["budget"] == "15000"
    assert slots["duration_days"] == 4
    assert slots["travelers"] == 2
    assert slots["transport_pref"] == "car"
    assert slots["food_pref"] == "vegetarian"


def test_extracts_plural_beaches_interest():
    assert extract_explicit_slots("We want to visit beaches") ["interests"] == "beaches"

def test_tolerant_budget_extraction_examples():
    # Budget examples required by user:
    # "approximately 15000", "around ₹15,000", "15k", "under 20,000"
    assert extract_explicit_slots("approximately 15000")["budget"] == "15000"
    assert extract_explicit_slots("around ₹15,000")["budget"] == "15000"
    assert extract_explicit_slots("15k")["budget"] == "15000"
    assert extract_explicit_slots("under 20,000")["budget"] == "20000"


def test_tolerant_duration_extraction_examples():
    # Duration examples required by user:
    # "3 days", "three days", "about three days", "a long weekend"
    assert extract_explicit_slots("3 days")["duration_days"] == 3
    assert extract_explicit_slots("three days")["duration_days"] == 3
    assert extract_explicit_slots("about three days")["duration_days"] == 3
    assert extract_explicit_slots("a long weekend")["duration_days"] == 3


def test_tolerant_travelers_extraction_examples():
    # Travellers examples required by user:
    # "one person", "just me", "alone", "solo", "two people", "four of us"
    assert extract_explicit_slots("one person")["travelers"] == 1
    assert extract_explicit_slots("just me")["travelers"] == 1
    assert extract_explicit_slots("alone")["travelers"] == 1
    assert extract_explicit_slots("solo")["travelers"] == 1
    assert extract_explicit_slots("two people")["travelers"] == 2
    assert extract_explicit_slots("four of us")["travelers"] == 4


def test_contextual_slot_answering_preserves_preferences():
    # Assistant asks for budget, user gives a concise budget answer
    reply, updated, ready = process_message(
        prior_slots={"duration_days": 3, "travelers": 2, "travel_style": "relaxing"},
        conversation_history=[
            {"role": "assistant", "content": "What's your approximate budget for this trip?"}
        ],
        user_message="under 20,000",
    )
    assert updated["budget"] == "20000"
    assert updated["duration_days"] == 3
    assert updated["travelers"] == 2
    assert updated["travel_style"] == "relaxing"
    assert ready is True
