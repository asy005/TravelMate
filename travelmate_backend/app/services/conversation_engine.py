# app/services/conversation_engine.py
"""
Slot-filling dialogue engine for the AI travel assistant.

This module owns the "conversation" concern only: what do we know so far,
what's still missing, and what should the assistant say next. It calls
llm_gateway for the actual language understanding/generation, but the merging
and readiness logic is deterministic Python so it's testable without needing
a live LLM.
"""
import json
from typing import Dict, Any, List, Tuple

from app.services.llm_gateway import chat_completion, LLMGatewayError

ALL_SLOTS = [
    "origin", "budget", "travelers", "start_date", "duration_days",
    "travel_style", "interests", "transport_pref", "food_pref",
    "accommodation_pref", "weather_pref", "accessibility", "additional_notes",
]

# The minimum set of slots needed before we attempt to generate a plan.
# Everything else in ALL_SLOTS enriches the plan but doesn't block it.
REQUIRED_SLOTS = ["budget", "duration_days", "travelers", "travel_style"]

EMPTY_SLOTS: Dict[str, Any] = {slot: None for slot in ALL_SLOTS}


def merge_slots(old_slots: Dict[str, Any], new_slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge newly-extracted slot values into the existing slot state.
    A previously-confirmed value is only overwritten if the new extraction
    provides a non-empty value -- the model should never silently erase
    something the user already told us.
    """
    merged = dict(old_slots or {})
    for key in ALL_SLOTS:
        new_val = (new_slots or {}).get(key)
        if new_val not in (None, "", [], {}):
            merged[key] = new_val
        elif key not in merged:
            merged[key] = None
    return merged


def missing_required_slots(slots: Dict[str, Any]) -> List[str]:
    return [s for s in REQUIRED_SLOTS if not slots.get(s)]


def is_ready_for_plan(slots: Dict[str, Any]) -> bool:
    return len(missing_required_slots(slots)) == 0


def _system_prompt() -> str:
    return (
        "You are TravelMate's AI travel consultant. You talk naturally, like a "
        "helpful human travel agent, never like a form. Your job across the "
        "conversation is to gather these details when relevant: origin city, "
        "budget, number of travelers, start date, trip duration in days, "
        "travel style (e.g. relaxing/adventurous/cultural/romantic), interests, "
        "transport preference, food preference, accommodation preference, "
        "weather preference, accessibility needs, and any additional requests. "
        "Never ask for more than one or two things at a time. If the user has "
        "already given something, don't ask again. Keep replies short and warm.\n\n"
        "You must respond ONLY with a JSON object of this exact shape:\n"
        '{"slots": {"origin": null or string, "budget": null or string, '
        '"travelers": null or number, "start_date": null or string, '
        '"duration_days": null or number, "travel_style": null or string, '
        '"interests": null or string, "transport_pref": null or string, '
        '"food_pref": null or string, "accommodation_pref": null or string, '
        '"weather_pref": null or string, "accessibility": null or string, '
        '"additional_notes": null or string}, '
        '"reply": "your natural-language reply or next question", '
        '"ready_for_plan": true or false}\n'
        "Only include a slot value if the user actually stated it in this "
        "message. Leave everything else null -- do not guess."
    )


def _fallback_next_question(slots: Dict[str, Any]) -> str:
    """
    Deterministic fallback used if the LLM gateway is unavailable, so the
    assistant never hard-fails (NFR: AI features must degrade gracefully).
    """
    missing = missing_required_slots(slots)
    prompts = {
        "budget": "What's your approximate budget for this trip?",
        "duration_days": "How many days are you planning to travel?",
        "travelers": "How many people will be traveling?",
        "travel_style": "What kind of trip are you in the mood for -- relaxing, adventurous, cultural, or something else?",
    }
    if missing:
        return prompts.get(missing[0], "Could you tell me a bit more about your trip?")
    return "I think I have enough to put together a plan for you -- one moment."


def process_message(
    prior_slots: Dict[str, Any],
    conversation_history: List[Dict[str, str]],
    user_message: str,
) -> Tuple[str, Dict[str, Any], bool]:
    """
    Returns (assistant_reply, updated_slots, ready_for_plan).
    """
    messages = [{"role": "system", "content": _system_prompt()}]
    messages.extend(conversation_history[-12:])  # keep recent context bounded
    messages.append({"role": "user", "content": user_message})

    try:
        raw = chat_completion(messages, json_mode=True, temperature=0.3)
        parsed = json.loads(raw)
        extracted_slots = parsed.get("slots", {}) or {}
        reply = parsed.get("reply") or "Got it -- tell me a bit more about your trip."
        updated_slots = merge_slots(prior_slots, extracted_slots)
        ready = bool(parsed.get("ready_for_plan")) or is_ready_for_plan(updated_slots)
        return reply, updated_slots, ready
    except (LLMGatewayError, json.JSONDecodeError, KeyError, TypeError):
        # Graceful degradation: no LLM available -> deterministic next question.
        updated_slots = merge_slots(prior_slots, {})
        reply = _fallback_next_question(updated_slots)
        ready = is_ready_for_plan(updated_slots)
        return reply, updated_slots, ready
