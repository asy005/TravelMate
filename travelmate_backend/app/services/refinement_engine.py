# app/services/refinement_engine.py
"""
Handles follow-up messages once a plan already exists, so the assistant
supports iterative refinement ("increase my budget", "remove the package",
"I only have 3 days") instead of only one-shot generation.

Design: classify what changed (LLM-driven, with a keyword-based fallback for
graceful degradation), then only touch the parts of the existing plan that
change_type says are affected -- reusing hotel_recommender, package_recommender,
budget_optimizer, and plan_orchestrator's regeneration helpers exactly as
initial generation does. Nothing here duplicates their logic.
"""
import json
import re
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.services.llm_gateway import chat_completion, LLMGatewayError
from app.services.conversation_engine import merge_slots
from app.services.plan_orchestrator import (
    generate_plan,
    refresh_hotel_and_package_recommendations,
    regenerate_itinerary,
    itinerary_with_package,
)
from app.services.budget_optimizer import allocate_budget

CHANGE_TYPES = ["budget", "hotel", "destination", "package", "duration", "preference", "none"]


def _system_prompt() -> str:
    return (
        "You are TravelMate's AI travel consultant, continuing an ongoing "
        "conversation about a trip that has ALREADY been planned. The "
        "traveler is now asking for a change. Determine what changed and "
        "respond ONLY with a JSON object of this exact shape:\n"
        '{"updated_slots": {<only the slot keys that changed, from: origin, '
        'budget, travelers, start_date, duration_days, travel_style, '
        'interests, transport_pref, food_pref, accommodation_pref, '
        'weather_pref, accessibility, additional_notes>}, '
        '"change_type": one of ["budget", "hotel", "destination", "package", '
        '"duration", "preference", "none"], '
        '"remove_package": true or false, '
        '"reply": "a short, warm confirmation of what you changed"}\n\n'
        "Guidance on change_type:\n"
        "- budget: any change to spending amount (e.g. \"increase my budget to 60000\")\n"
        "- hotel: wants a different hotel tier/style (\"find a cheaper hotel\", \"show luxury hotels\")\n"
        "- destination: wants a different place/vibe entirely (\"I want beaches instead\")\n"
        "- package: wants to add/remove/change a tour package (\"remove the package\")\n"
        "- duration: trip length changed (\"I only have 3 days\")\n"
        "- preference: transport/food/activity/accessibility preference changes that don't "
        "fit the above (\"travel by train instead\", \"I prefer vegetarian food\", "
        "\"add more adventure activities\", \"I don't want trekking\")\n"
        "- none: message isn't actually a change request\n"
        "Only set remove_package true if the traveler explicitly wants the package removed."
    )


def _keyword_fallback(user_message: str) -> Tuple[Dict[str, Any], str, bool, str]:
    """
    Deterministic fallback if the LLM gateway is unavailable -- keeps the
    assistant from hard-failing on a refinement request (NFR: AI features
    degrade gracefully). Coarser than the LLM path, but keeps things moving.
    """
    text = user_message.lower()
    updated_slots: Dict[str, Any] = {}
    remove_package = False

    if any(k in text for k in ["remove the package", "no package", "without the package"]):
        change_type = "package"
        remove_package = True
    elif "package" in text:
        change_type = "package"
    elif "hotel" in text:
        change_type = "hotel"
        if "luxury" in text:
            updated_slots["budget"] = "luxury"
        elif "cheap" in text or "budget" in text:
            updated_slots["budget"] = "low"
    elif any(k in text for k in ["budget", "rupees", "rs."]) or "\u20b9" in text:
        change_type = "budget"
        match = re.search(r"(\d[\d,]{2,})", text.replace(",", ""))
        if match:
            updated_slots["budget"] = match.group(1)
    elif any(k in text for k in ["day", "days", "duration"]):
        change_type = "duration"
        match = re.search(r"(\d+)\s*day", text)
        if match:
            updated_slots["duration_days"] = int(match.group(1))
    elif any(k in text for k in ["train", "flight", "fly", "car", "bus", "vegetarian", "vegan", "trek", "adventure"]):
        change_type = "preference"
        if any(k in text for k in ["train", "flight", "fly", "car", "bus"]):
            updated_slots["transport_pref"] = text
        if any(k in text for k in ["vegetarian", "vegan"]):
            updated_slots["food_pref"] = text
        if any(k in text for k in ["trek", "adventure"]):
            updated_slots["interests"] = text
    elif any(k in text for k in ["instead", "prefer somewhere", "different place", "beach", "mountain"]):
        change_type = "destination"
        updated_slots["interests"] = text
    else:
        change_type = "none"

    reply = "Got it -- updating your trip." if change_type != "none" else (
        "I'm not sure what you'd like to change -- could you tell me more specifically?"
    )
    return updated_slots, change_type, remove_package, reply


def classify_refinement(
    prior_slots: Dict[str, Any],
    user_message: str,
) -> Tuple[Dict[str, Any], str, bool, str]:
    """
    Returns (updated_slots, change_type, remove_package, reply).
    """
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": f"Current trip details so far: {json.dumps(prior_slots)}"},
        {"role": "user", "content": user_message},
    ]

    try:
        raw = chat_completion(messages, json_mode=True, temperature=0.2)
        parsed = json.loads(raw)
        extracted = parsed.get("updated_slots", {}) or {}
        change_type = parsed.get("change_type") if parsed.get("change_type") in CHANGE_TYPES else "none"
        remove_package = bool(parsed.get("remove_package"))
        reply = parsed.get("reply") or "Updating your trip now."
        return extracted, change_type, remove_package, reply
    except (LLMGatewayError, json.JSONDecodeError, KeyError, TypeError):
        return _keyword_fallback(user_message)


def apply_refinement(
    db: Session,
    current_slots: Dict[str, Any],
    plan: Dict[str, Any],
    change_type: str,
    extracted_slots: Dict[str, Any],
    remove_package: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Applies the minimal regeneration needed for `change_type`, mutating and
    returning (updated_plan, updated_slots). Reuses every existing
    recommendation/itinerary/budget module -- nothing is recomputed from
    scratch except when the destination itself changes.
    """
    updated_slots = merge_slots(current_slots, extracted_slots)
    destinations = plan.get("destinations", [])

    # Destination changes (or no existing destination to refine) -> the only
    # case that regenerates the full plan, since everything downstream
    # (weather, itinerary, recommendations) depends on the destination.
    if change_type == "destination" or not destinations:
        return generate_plan(db, updated_slots), updated_slots

    primary = destinations[0]
    dest_id = primary["id"]
    duration_days = int(updated_slots.get("duration_days") or 3)
    travelers = int(updated_slots.get("travelers") or 1)

    if change_type == "package" and remove_package:
        primary.pop("selected_package", None)
        plan["day_wise_itinerary"] = regenerate_itinerary(db, dest_id, duration_days, updated_slots)

    if change_type in ("hotel", "package", "budget", "duration"):
        hotels, packages = refresh_hotel_and_package_recommendations(db, dest_id, updated_slots)
        primary["recommended_hotels"] = hotels
        primary["recommended_packages"] = packages

    if change_type == "duration":
        selected_package = primary.get("selected_package")
        if selected_package:
            # A selected package drives its own itinerary length/structure.
            plan["day_wise_itinerary"] = itinerary_with_package(primary["name"], duration_days, selected_package)
        else:
            plan["day_wise_itinerary"] = regenerate_itinerary(db, dest_id, duration_days, updated_slots)

    # Budget is recomputed for every change type below "destination" -- it's
    # the cheapest, most universally-affected number (matches the required
    # budget/hotel/package/duration -> budget mapping).
    if change_type != "none":
        selected_hotel = primary.get("selected_hotel")
        selected_package = primary.get("selected_package")
        plan["budget"] = allocate_budget(
            db, updated_slots, duration_days, travelers,
            destination_id=dest_id,
            selected_hotel=selected_hotel,
            selected_package=selected_package,
        )

    destinations[0] = primary
    plan["destinations"] = destinations
    plan["slots_used"] = updated_slots
    return plan, updated_slots
