# app/services/plan_orchestrator.py
"""
Assembles a complete travel plan once the conversation engine has gathered
enough slots. This is intentionally a *composition* layer -- every section
below is produced by an existing, already-working service. The only new
capability here is the LLM writing natural-language explanations/tips on top
of that existing data.

Known limitation (by design, flagged in the technical design): "hotel
recommendations" are a suggested accommodation type/budget tier drawn from
the RAG travel-guide content, not real bookable inventory -- the Hotel
Booking Engine (M5) doesn't exist yet.
"""
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from app.models.destination import Destination
from app.services.rag_engine import query_knowledge_base
from app.services.weather_service import cached_weather
from app.services.route_service import get_route_osrm
from app.services.packing_service import generate_packing
from app.services.highlights_service import top_highlights_from_rag
from app.services.geo_lookup import guess_coordinates, get_nearby_attractions
from app.services.llm_gateway import chat_completion, LLMGatewayError
from app.services.hotel_recommender import recommend_hotels
from app.services.package_recommender import recommend_packages, should_recommend_packages
from app.services.budget_optimizer import allocate_budget


def _climate_hint_from_tags(tags: str) -> str:
    tags = (tags or "").lower()
    if "tropical" in tags or "beach" in tags:
        return "tropical"
    if "cold" in tags or "snow" in tags or "mountain" in tags:
        return "cold"
    return "temperate"


def _find_candidate_destinations(db: Session, slots: Dict[str, Any], max_results: int = 3) -> List[Destination]:
    interests = (slots.get("interests") or "").lower()
    style = (slots.get("travel_style") or "").lower()
    search_terms = " ".join([t for t in [interests, style] if t]).strip()

    q = db.query(Destination)
    if search_terms:
        like = f"%{search_terms.split()[0]}%" if search_terms.split() else None
        if like:
            q = q.filter(
                Destination.tags.ilike(like)
                | Destination.description.ilike(like)
                | Destination.name.ilike(like)
            )

    results = q.order_by(Destination.avg_rating.desc()).limit(max_results).all()
    if not results:
        # No tag match -- fall back to top-rated destinations rather than an empty plan.
        results = db.query(Destination).order_by(Destination.avg_rating.desc()).limit(max_results).all()
    return results


def _llm_explanation(destination: Destination, slots: Dict[str, Any]) -> str:
    """
    Ask the LLM for a short, personalized explanation of why this
    destination fits the traveler's stated preferences. Falls back to a
    simple templated sentence if the LLM is unavailable.
    """
    prompt = (
        f"In 2 short sentences, explain why {destination.name}, {destination.country or ''} "
        f"is a good fit for a traveler whose style is '{slots.get('travel_style') or 'unspecified'}', "
        f"interests are '{slots.get('interests') or 'unspecified'}', and budget is "
        f"'{slots.get('budget') or 'unspecified'}'. Be specific and warm, not generic."
    )
    try:
        return chat_completion(
            [{"role": "user", "content": prompt}],
            json_mode=False,
            temperature=0.5,
            max_tokens=150,
        ).strip()
    except LLMGatewayError:
        return (
            f"{destination.name} is a strong match for a {slots.get('travel_style') or 'well-rounded'} "
            f"trip within a {slots.get('budget') or 'moderate'} budget."
        )


def _llm_travel_tips(destination_names: List[str], slots: Dict[str, Any]) -> List[str]:
    prompt = (
        f"Give 4 short, practical travel tips (one line each, no numbering) for a trip to "
        f"{', '.join(destination_names)} for a traveler with these preferences: "
        f"accessibility notes: {slots.get('accessibility') or 'none'}; "
        f"food preference: {slots.get('food_pref') or 'no preference'}; "
        f"transport preference: {slots.get('transport_pref') or 'no preference'}."
    )
    try:
        text = chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=250,
        )
        tips = [line.strip("-• ").strip() for line in text.splitlines() if line.strip()]
        return tips[:5] if tips else []
    except LLMGatewayError:
        return [
            "Carry a copy of your ID and travel documents at all times.",
            "Check local weather right before departure and pack accordingly.",
            "Keep some cash on hand in case cards aren't accepted everywhere.",
        ]


def _day_wise_itinerary(destination: Destination, duration_days: int, highlights: List[str]) -> List[Dict[str, Any]]:
    days = []
    duration_days = duration_days or 3
    for day_num in range(1, duration_days + 1):
        highlight = highlights[(day_num - 1) % len(highlights)] if highlights else f"Explore {destination.name}"
        days.append({
            "day": day_num,
            "summary": highlight,
        })
    return days


def itinerary_with_package(destination_name: str, duration_days: int, package: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Regenerates the day-wise itinerary once a package is selected -- the
    itinerary length follows the package's own duration (if set, since
    that's now the actual planned trip length for these days), and each day
    references what the package covers rather than generic highlights.
    """
    package_days = package.get("duration_days") or duration_days or 3
    inclusions = package.get("amenities") or []
    days = []
    for day_num in range(1, package_days + 1):
        if day_num == 1:
            summary = f"Begin \"{package['title']}\" with {package.get('partner_name') or 'your tour partner'}."
        elif inclusions:
            summary = f"Day {day_num} of \"{package['title']}\" — includes {inclusions[(day_num - 2) % len(inclusions)].strip()}."
        else:
            summary = f"Day {day_num} of \"{package['title']}\" in {destination_name}."
        days.append({"day": day_num, "summary": summary})
    return days


def refresh_hotel_and_package_recommendations(db: Session, destination_id: int, slots: Dict[str, Any]):
    """
    Recomputes just the recommendation lists for a destination -- reused by
    both initial plan generation and the conversational refinement engine so
    "show me cheaper hotels" or "show luxury hotels" doesn't require
    regenerating the whole plan.
    """
    hotels = recommend_hotels(db, destination_id, slots)
    packages = recommend_packages(db, destination_id, slots)
    packages = packages if should_recommend_packages(slots, packages) else []
    return hotels, packages


def regenerate_itinerary(db: Session, destination_id: int, duration_days: int, slots: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Regenerates the day-wise itinerary for an existing destination (e.g. the
    traveler shortened their trip, or changed interests) without touching
    anything else in the plan.
    """
    dest = db.query(Destination).filter(Destination.id == destination_id).first()
    if not dest:
        return []
    rag = query_knowledge_base(
        f"{slots.get('travel_style') or ''} {slots.get('interests') or ''}".strip() or "travel"
    )
    highlights = top_highlights_from_rag(rag, max_items=duration_days if duration_days <= 5 else 5)
    return _day_wise_itinerary(dest, duration_days, highlights)


def generate_plan(db: Session, slots: Dict[str, Any], source_coords: Dict[str, float] = None) -> Dict[str, Any]:
    duration_days = int(slots.get("duration_days") or 3)
    travelers = int(slots.get("travelers") or 1)

    rag = query_knowledge_base(f"{slots.get('travel_style') or ''} {slots.get('interests') or ''}".strip() or "travel")

    destinations = _find_candidate_destinations(db, slots)
    highlights = top_highlights_from_rag(rag, max_items=duration_days if duration_days <= 5 else 5)

    destination_blocks = []
    for dest in destinations:
        lat, lon = dest.lat, dest.lon
        if not lat or not lon:
            lat, lon = guess_coordinates(dest.name)

        weather = cached_weather(lat, lon) if lat and lon else None
        climate_hint = _climate_hint_from_tags(dest.tags)

        candidate_packages = recommend_packages(db, dest.id, slots)
        recommended_packages = candidate_packages if should_recommend_packages(slots, candidate_packages) else []

        destination_blocks.append({
            "id": dest.id,
            "name": dest.name,
            "country": dest.country,
            "description": dest.description,
            "thumbnail_url": dest.thumbnail_url,
            "avg_rating": dest.avg_rating,
            "explanation": _llm_explanation(dest, slots),
            "weather": weather,
            "recommended_hotels": recommend_hotels(db, dest.id, slots),
            "recommended_packages": recommended_packages,
        })

    primary = destinations[0] if destinations else None
    itinerary = _day_wise_itinerary(primary, duration_days, highlights) if primary else []

    nearby_attractions = []
    if primary:
        p_lat, p_lon = primary.lat, primary.lon
        if not p_lat or not p_lon:
            p_lat, p_lon = guess_coordinates(primary.name)
        nearby_attractions = get_nearby_attractions(p_lat, p_lon)

    route = None
    if source_coords and primary:
        dest_lat = primary.lat or guess_coordinates(primary.name)[0]
        dest_lon = primary.lon or guess_coordinates(primary.name)[1]
        if source_coords.get("lat") and source_coords.get("lon"):
            route = get_route_osrm(source_coords["lat"], source_coords["lon"], dest_lat, dest_lon)

    climate_hint = _climate_hint_from_tags(primary.tags) if primary else "temperate"
    activities = [a.strip() for a in (slots.get("interests") or "").split(",") if a.strip()]
    packing_list = generate_packing(climate_hint, duration_days, activities)

    budget = allocate_budget(
        db, slots, duration_days, travelers,
        destination_id=primary.id if primary else None,
        selected_hotel=None,
    )

    tips = _llm_travel_tips([d["name"] for d in destination_blocks] or ["your destination"], slots)

    return {
        "trip_overview": {
            "origin": slots.get("origin"),
            "budget": slots.get("budget"),
            "travelers": travelers,
            "duration_days": duration_days,
            "travel_style": slots.get("travel_style"),
            "interests": slots.get("interests"),
            "primary_destination": primary.name if primary else None,
        },
        "destinations": destination_blocks,
        "day_wise_itinerary": itinerary,
        "budget": budget,
        "packing_list": packing_list,
        "nearby_attractions": nearby_attractions,
        "route": route,
        "travel_tips": tips,
        "slots_used": slots,
    }
