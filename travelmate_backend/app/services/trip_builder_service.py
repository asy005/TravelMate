# app/services/trip_builder_service.py
"""
AI Trip Builder — composition service.

This module is the flagship "single form -> full trip plan" feature. It does
NOT reimplement recommendation, weather, itinerary, packing, or nearby-places
logic. It reuses the exact functions already backing /recommend, /plan/generate,
/packing/generate, and /nearby so that:
  - behavior stays consistent across the standalone endpoints and the trip builder
  - bug fixes/improvements to those underlying modules automatically benefit
    the trip builder too
  - no existing route/module is modified to support this new feature
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.destination import Destination
from app.services.rag_engine import query_knowledge_base
from app.services.weather_service import cached_weather

# Reused from the existing recommendation module (unmodified)
from app.routes.recommend_routes import extract_mood, extract_budget, extract_best_time, fetch_latlon

# Reused from the existing itinerary module (unmodified)
from app.routes.itinerary_routes import simple_activity_from_snippets

# Reused from the existing packing module (unmodified)
from app.routes.packing_routes import (
    BASE_PACK,
    generate_by_weather,
    generate_by_activities,
)

# Reused from the existing nearby-attractions module (unmodified)
from app.routes.nearby_routes import nearby as nearby_lookup


TRAVEL_STYLE_BUDGET_SPLIT: Dict[str, Dict[str, float]] = {
    # Category weights must sum to 1.0. These are heuristic starting points —
    # they will be replaced by the real, pricing-data-driven Budget Optimizer
    # (roadmap milestone M10) once the hotel/package booking engine exists.
    "luxury": {"accommodation": 0.45, "transport": 0.20, "food": 0.15, "activities": 0.12, "misc": 0.08},
    "adventure": {"accommodation": 0.25, "transport": 0.20, "food": 0.20, "activities": 0.28, "misc": 0.07},
    "family": {"accommodation": 0.35, "transport": 0.20, "food": 0.22, "activities": 0.15, "misc": 0.08},
    "solo": {"accommodation": 0.30, "transport": 0.22, "food": 0.20, "activities": 0.20, "misc": 0.08},
    "cultural": {"accommodation": 0.30, "transport": 0.18, "food": 0.20, "activities": 0.24, "misc": 0.08},
    "relaxing": {"accommodation": 0.40, "transport": 0.18, "food": 0.18, "activities": 0.16, "misc": 0.08},
}
DEFAULT_BUDGET_SPLIT = TRAVEL_STYLE_BUDGET_SPLIT["family"]

HOTEL_TIERS = [
    {
        "tier": "Budget-Friendly",
        "share_of_accommodation_budget": 0.6,
        "description": "Clean, well-rated stays focused on value — guesthouses, budget hotels, or homestays.",
    },
    {
        "tier": "Comfort",
        "share_of_accommodation_budget": 1.0,
        "description": "3-star hotels with good amenities and central locations, balancing comfort and cost.",
    },
    {
        "tier": "Premium",
        "share_of_accommodation_budget": 1.6,
        "description": "4-5 star hotels or resorts for a more indulgent stay, if the budget stretches.",
    },
]


def _normalize_style(travel_style: str) -> str:
    return (travel_style or "").strip().lower()


def compute_budget_breakdown(total_budget: float, days: int, travelers: int, travel_style: str) -> Dict[str, Any]:
    """
    Heuristic budget allocator. This is intentionally simple (percentage
    split by travel style) rather than pricing-data-driven, since no live
    hotel/package inventory exists yet (that lands with the Hotel Booking
    Engine milestone). It gives users a genuinely useful planning number
    today and is designed to be swapped for the real Budget Optimizer later
    without changing the response shape.
    """
    split = TRAVEL_STYLE_BUDGET_SPLIT.get(_normalize_style(travel_style), DEFAULT_BUDGET_SPLIT)
    days = max(1, days)
    travelers = max(1, travelers)

    breakdown = {}
    for category, pct in split.items():
        amount = round(total_budget * pct, 2)
        breakdown[category] = {
            "amount": amount,
            "percent": round(pct * 100, 1),
            "per_day": round(amount / days, 2),
        }

    return {
        "total_budget": total_budget,
        "currency": "INR",
        "per_traveler": round(total_budget / travelers, 2),
        "per_day": round(total_budget / days, 2),
        "categories": breakdown,
    }


def recommend_hotel_tiers(budget_breakdown: Dict[str, Any], days: int) -> List[Dict[str, Any]]:
    """
    Heuristic hotel-tier suggestions derived from the accommodation slice of
    the budget breakdown. These are illustrative price bands, not live,
    bookable inventory — real hotel search/booking is a separate module
    (Hotel Booking Engine) that will supersede this with actual listings.
    """
    days = max(1, days)
    accommodation_total = budget_breakdown["categories"]["accommodation"]["amount"]
    per_night_baseline = accommodation_total / days if days else accommodation_total

    tiers = []
    for tier in HOTEL_TIERS:
        est_per_night = round(per_night_baseline * tier["share_of_accommodation_budget"], 2)
        tiers.append({
            "tier": tier["tier"],
            "description": tier["description"],
            "estimated_price_per_night": est_per_night,
            "estimated_total_for_stay": round(est_per_night * days, 2),
            "currency": "INR",
        })
    return tiers


def build_day_wise_itinerary(destination_name: str, days: int, interests: List[str]) -> Dict[str, List[str]]:
    """
    Reuses the same RAG-snippet-to-activity extraction used by
    /plan/generate, seeded with the destination + the user's interests so
    the itinerary reflects what they said they care about.
    """
    days = max(1, min(14, days))
    interest_str = ", ".join(interests) if interests else ""
    query = f"{destination_name} itinerary highlights {interest_str}".strip()

    rag = query_knowledge_base(query)
    activities = simple_activity_from_snippets(rag, limit=days * 2)

    if not activities:
        activities = [
            f"Explore local markets in {destination_name}",
            f"Visit top landmarks in {destination_name}",
            "Try local cuisine and cafes",
            "Relax at a scenic spot",
            "Light walking tour of the old town",
            "Souvenir shopping and rest",
        ]

    plan: Dict[str, List[str]] = {}
    per_day = max(1, len(activities) // days)
    idx = 0
    for d in range(1, days + 1):
        day_items = []
        for _ in range(per_day):
            if idx >= len(activities):
                break
            day_items.append(activities[idx])
            idx += 1
        if not day_items and idx < len(activities):
            day_items.append(activities[idx])
            idx += 1
        if not day_items:
            day_items = ["Free time / relax at your own pace"]
        plan[f"day_{d}"] = day_items

    return plan


def build_packing_list(destination_name: str, weather: Optional[Dict[str, Any]], days: int, interests: List[str], travel_style: str) -> List[str]:
    """
    Reuses the exact packing-generation building blocks from
    /packing/generate (BASE_PACK, generate_by_weather, generate_by_activities)
    instead of re-implementing packing logic.
    """
    weather_str = weather.get("description", "") if weather else ""
    activities_for_packing = list(interests) + [travel_style]

    items = BASE_PACK.copy()
    items += generate_by_weather(weather_str)
    items += generate_by_activities(activities_for_packing)

    clothing_count = min(7, max(1, days))
    items += [f"{clothing_count}x Shirts/Tops", f"{clothing_count}x Bottoms"]

    seen = set()
    final = []
    for it in items:
        if it not in seen:
            seen.add(it)
            final.append(it)
    return final


def get_nearby_attractions(lat: Optional[float], lon: Optional[float]) -> Any:
    """
    Reuses the existing /nearby route function directly rather than
    duplicating the OpenTripMap integration.
    """
    if not lat or not lon:
        return {"error": "No coordinates available for this destination"}
    return nearby_lookup(lat=lat, lon=lon)


def find_candidate_destinations(
    db: Session,
    query_text: str,
    interests: List[str],
    travel_style: str,
    max_results: int = 3,
):
    """
    Reuses the same RAG -> Destination-table lookup pattern already used by
    /recommend, extended with a tag-based fallback (same technique used in
    /travel/plan) so travel_style/interests can steer the match when the RAG
    fallback destination isn't in the DB yet.
    """
    rag = query_knowledge_base(query_text)
    fb = rag.get("fallback", {}) if isinstance(rag, dict) else {}
    context = rag.get("context", "") if isinstance(rag, dict) else ""

    rag_destination_name = fb.get("destination")
    mood = extract_mood(context)
    budget_label = extract_budget(context)
    best_time = extract_best_time(context)

    results = []
    if rag_destination_name:
        results = db.query(Destination).filter(
            Destination.name.ilike(f"%{rag_destination_name}%")
        ).all()

    if not results:
        # Tag-based fallback using travel style / interests (same technique
        # already used in plan_routes.py's mood->tags filtering)
        q = db.query(Destination)
        style = _normalize_style(travel_style)
        if style == "adventure" or "trekking" in interests or "adventure" in interests:
            q = q.filter(Destination.tags.ilike("%adventure%") | Destination.tags.ilike("%trek%"))
        elif style in ("relaxing", "luxury") or "beach" in interests:
            q = q.filter(Destination.tags.ilike("%beach%") | Destination.tags.ilike("%relax%"))
        elif style == "cultural" or "culture" in interests or "heritage" in interests:
            q = q.filter(Destination.tags.ilike("%culture%") | Destination.tags.ilike("%heritage%"))
        results = q.order_by(Destination.avg_rating.desc()).limit(max_results).all()

    results = results[:max_results]

    candidates = []
    for d in results:
        lat, lon = d.lat, d.lon
        if not lat or not lon:
            lat, lon = fetch_latlon(d.name)
        candidates.append({
            "id": d.id,
            "name": d.name,
            "country": d.country or "Unknown",
            "description": d.description,
            "lat": lat,
            "lon": lon,
            "tags": d.tags,
            "thumbnail_url": d.thumbnail_url or "",
            "avg_rating": d.avg_rating,
            "mood": mood,
            "budget_label": budget_label,
            "best_time": best_time,
        })

    if not candidates:
        # Same "virtual recommendation" fallback pattern used in /recommend
        # when nothing matches in the DB yet.
        fallback_name = rag_destination_name or fb.get("destination") or "Goa"
        lat, lon = fetch_latlon(fallback_name)
        candidates.append({
            "id": None,
            "name": fallback_name,
            "country": "Unknown",
            "description": fb.get("description", ""),
            "lat": lat,
            "lon": lon,
            "tags": None,
            "thumbnail_url": "",
            "avg_rating": None,
            "mood": mood,
            "budget_label": budget_label,
            "best_time": best_time,
        })

    return candidates


def build_trip_plan(db: Session, req) -> Dict[str, Any]:
    """
    Top-level orchestration for the AI Trip Builder. `req` is a
    TripBuilderRequest (see trip_builder_routes.py).
    """
    interests = req.interests or []
    query_text = (
        f"{req.travel_style} trip from {req.start_location} for {req.travelers} traveler(s), "
        f"interested in {', '.join(interests) if interests else 'general sightseeing'}, "
        f"budget around {req.budget}"
    )

    candidates = find_candidate_destinations(
        db=db,
        query_text=query_text,
        interests=[i.lower() for i in interests],
        travel_style=req.travel_style,
        max_results=3,
    )

    primary = candidates[0]

    # Weather (reused cached_weather from weather_service.py)
    weather = cached_weather(primary["lat"], primary["lon"]) if primary["lat"] and primary["lon"] else None
    if weather:
        weather["weather_short"] = weather.get("description", "").title()

    # Attach lightweight weather to each candidate for the shortlist view
    for c in candidates:
        if c is primary:
            c["weather"] = weather
        elif c["lat"] and c["lon"]:
            c["weather"] = cached_weather(c["lat"], c["lon"])
        else:
            c["weather"] = None

    itinerary = build_day_wise_itinerary(primary["name"], req.days, interests)
    budget_breakdown = compute_budget_breakdown(req.budget, req.days, req.travelers, req.travel_style)
    hotel_recommendations = recommend_hotel_tiers(budget_breakdown, req.days)
    nearby_attractions = get_nearby_attractions(primary["lat"], primary["lon"])
    packing_list = build_packing_list(primary["name"], weather, req.days, interests, req.travel_style)

    return {
        "trip_request": {
            "start_location": req.start_location,
            "budget": req.budget,
            "travelers": req.travelers,
            "days": req.days,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "travel_style": req.travel_style,
            "interests": interests,
            "transport_preference": req.transport_preference,
        },
        "recommended_destinations": candidates,
        "primary_destination": primary,
        "weather": weather,
        "itinerary": itinerary,
        "budget_breakdown": budget_breakdown,
        "hotel_recommendations": hotel_recommendations,
        "nearby_attractions": nearby_attractions,
        "packing_list": packing_list,
        "notes": (
            "Destination shortlist and itinerary are AI-generated from TravelMate's "
            "knowledge base. Hotel recommendations are estimated price tiers, not live "
            "bookable inventory — real-time hotel search and booking is a separate, "
            "upcoming module."
        ),
    }
