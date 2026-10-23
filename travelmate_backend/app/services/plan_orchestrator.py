from app.services.ml_engine import ml_engine
from typing import Dict, Any, List, Optional
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
from app.services.package_recommender import (
    recommend_packages,
    should_recommend_packages,
)
from app.services.budget_optimizer import allocate_budget

def _climate_hint_from_tags(tags: str) -> str:
    tags = (tags or "").lower()

    if any(word in tags for word in ("tropical", "beach")):
        return "tropical"
    if any(word in tags for word in ("cold", "snow", "mountain")):
        return "cold"

    return "temperate"

def _ml_profile_from_slots(slots: Dict[str, Any]) -> Dict[str, Any]:
    from datetime import date, datetime

    style = str(slots.get("travel_style") or "relaxing").strip().lower()
    interests = str(slots.get("interests") or "").strip().lower()

    category_map = {
        "beach": "Beach",
        "beaches": "Beach",
        "hill": "Hill Station",
        "hills": "Hill Station",
        "mountain": "Hill Station",
        "mountains": "Hill Station",
        "heritage": "Heritage",
        "historical": "Heritage",
        "history": "Heritage",
        "forest": "Forest",
        "wildlife": "Forest",
        "desert": "Desert",
        "adventure": "Adventure",
        "city": "Urban",
        "cities": "Urban",
        "urban": "Urban",
    }

    preferred_category = next(
        (
            category
            for keyword, category in category_map.items()
            if keyword in interests
        ),
        "Urban",
    )

    raw_budget = str(slots.get("budget") or "").strip().lower()
    digits = raw_budget.replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").strip()
    if digits.endswith("k"):
        try:
            digits = str(float(digits[:-1]) * 1000)
        except ValueError:
            pass

    try:
        amount = float(digits)
        budget = "Low" if amount <= 15000 else "Medium" if amount <= 40000 else "High"
    except (TypeError, ValueError):
        budget_map = {
            "low": "Low",
            "budget": "Low",
            "cheap": "Low",
            "medium": "Medium",
            "moderate": "Medium",
            "high": "High",
            "luxury": "High",
        }
        budget = budget_map.get(raw_budget, "Medium")

    raw_date = slots.get("start_date")
    month = None
    try:
        if isinstance(raw_date, (date, datetime)):
            month = raw_date.month
        elif raw_date:
            month = datetime.fromisoformat(
                str(raw_date).replace("Z", "+00:00")
            ).month
    except (TypeError, ValueError):
        pass

    if month in (3, 4, 5):
        season = "Summer"
    elif month in (6, 7, 8, 9):
        season = "Monsoon"
    elif month == 10:
        season = "Autumn"
    elif month in (11, 12, 1, 2):
        season = "Winter"
    else:
        season = "Spring"

    return {
        "age": 30,
        "travel_style": style.title(),
        "budget": budget,
        "preferred_category": preferred_category,
        "preferred_season": season,
    }

def _find_ml_candidate_destinations(
    db: Session,
    slots: Dict[str, Any],
    max_results: int = 3,
) -> List[Destination]:
    requested_destination = str(slots.get("destination") or "").strip()

    if requested_destination:
        exact = (
            db.query(Destination)
            .filter(Destination.name.ilike(requested_destination))
            .first()
        )
        if exact:
            return [exact]

    profile = _ml_profile_from_slots(slots)

    category = profile["preferred_category"]
    category_requested = any(
        term in str(slots.get("interests") or "").lower()
        for term in (
            "beach", "hill", "mountain", "heritage",
            "historical", "history", "forest", "wildlife",
            "desert", "adventure", "city", "urban",
        )
    )

    recommendations = ml_engine.recommend_profile(
        profile,
        top_k=20,
        category_filter=category if category_requested else None,
    )

    results = []
    seen_ids = set()

    for item in recommendations:
        name = str(item.get("destination_name") or "").strip()
        if not name:
            continue

        destination = (
            db.query(Destination)
            .filter(Destination.name.ilike(name))
            .first()
        )

        if destination and destination.id not in seen_ids:
            results.append(destination)
            seen_ids.add(destination.id)

        if len(results) >= max_results:
            break

    return results

def _find_candidate_destinations(
    db: Session,
    slots: Dict[str, Any],
    max_results: int = 3,
) -> List[Destination]:
    interests = (slots.get("interests") or "").strip().lower()
    style = (slots.get("travel_style") or "").strip().lower()
    requested_destination = (slots.get("destination") or "").strip()

    query = db.query(Destination)

    if requested_destination:
        exact = query.filter(
            Destination.name.ilike(requested_destination)
        ).first()

        if exact:
            return [exact]

    terms = [
        term
        for term in (interests + " " + style).split()
        if len(term) > 2
    ]

    if terms:
        from sqlalchemy import or_

        conditions = []
        for term in terms:
            pattern = f"%{term}%"
            conditions.extend([
                Destination.tags.ilike(pattern),
                Destination.description.ilike(pattern),
                Destination.name.ilike(pattern),
            ])

        results = (
            query.filter(or_(*conditions))
            .order_by(Destination.avg_rating.desc())
            .limit(max_results)
            .all()
        )

        if results:
            return results

    return (
        db.query(Destination)
        .order_by(Destination.avg_rating.desc())
        .limit(max_results)
        .all()
    )

def _llm_explanation(
    destination: Destination,
    slots: Dict[str, Any],
) -> str:
    desc_hint = f" Known details: {destination.description}." if destination.description else ""
    tags_hint = f" Highlights/tags: {destination.tags}." if destination.tags else ""
    prompt = (
        f"In two short sentences, explain why {destination.name}, "
        f"{destination.country or 'India'}, fits a traveler whose style is "
        f"'{slots.get('travel_style') or 'unspecified'}', interests are "
        f"'{slots.get('interests') or 'unspecified'}', and budget is "
        f"'{slots.get('budget') or 'unspecified'}'.{desc_hint}{tags_hint} "
        "Use the destination's known characteristics and avoid inventing facts."
    )

    try:
        result = chat_completion(
            [{"role": "user", "content": prompt}],
            json_mode=False,
            temperature=0.3,
            max_tokens=150,
        )
        return result.strip() or (
            f"{destination.name} suits your {slots.get('travel_style', 'travel')} preferences."
        )
    except (LLMGatewayError, Exception):
        desc = (destination.description or "").strip()
        tags = (destination.tags or "").strip()
        style = slots.get("travel_style") or "preferred"
        if desc:
            return f"{destination.name} offers {desc.rstrip('.')}. It is a great match for a {style} trip."
        elif tags:
            return f"{destination.name} is celebrated for its {tags}, making it well-suited for a {style} experience."
        return f"{destination.name} in {destination.country or 'India'} offers distinctive cultural and outdoor attractions suited for a {style} journey."

def _llm_travel_tips(
    destination_names: List[str],
    slots: Dict[str, Any],
) -> List[str]:
    prompt = (
        "Give four short, practical travel tips for "
        f"{', '.join(destination_names)}. Consider accessibility: "
        f"{slots.get('accessibility') or 'no special requirements'}; food: "
        f"{slots.get('food_pref') or 'no preference'}; transport: "
        f"{slots.get('transport_pref') or 'no preference'}. "
        "Return one tip per line."
    )

    try:
        response = chat_completion(
            [{"role": "user", "content": prompt}],
            json_mode=False,
            temperature=0.3,
            max_tokens=250,
        )

        tips = [
            line.strip("-• \t").strip()
            for line in response.splitlines()
            if line.strip()
        ]

        return tips[:5] or [
            "Check local weather before departure.",
            "Keep travel documents and booking details accessible.",
            "Confirm transport and attraction timings before visiting.",
        ]

    except Exception:
        return [
            "Check local weather before departure.",
            "Keep travel documents and booking details accessible.",
            "Confirm transport and attraction timings before visiting.",
        ]

import re
from typing import List, Optional

def _filter_foreign_destination_highlights(
    destination_name: str,
    highlights: Optional[List[str]],
    known_destinations: Optional[List[str]] = None,
) -> List[str]:
    if not destination_name or not destination_name.strip():
        return []

    destination = destination_name.strip()
    destination_key = destination.casefold()
    known_destinations = known_destinations or []

    foreign_destinations = [
        name.strip()
        for name in known_destinations
        if isinstance(name, str)
        and name.strip()
        and name.strip().casefold() != destination_key
    ]

    common_foreign_places = [
        "Tiruchirappalli",
        "Tiruchirapalli",
        "Trichy",
        "Rock Fort",
        "Railway Museum",
        "New Delhi",
        "Bangalore",
        "Bengaluru",
        "Jaipur",
        "Gokarna",
        "Ganpatipule",
        "Pondicherry",
        "Puducherry",
        "Goa",
    ]

    foreign_destinations.extend(
        place for place in common_foreign_places
        if place.casefold() != destination_key
    )

    foreign_pattern = None
    if foreign_destinations:
        alternatives = sorted(
            {re.escape(place) for place in foreign_destinations},
            key=len,
            reverse=True,
        )
        foreign_pattern = re.compile(
            r"\b(?:" + "|".join(alternatives) + r")\b",
            re.IGNORECASE,
        )

    result = []
    seen = set()

    for item in highlights or []:
        if not isinstance(item, str):
            continue

        text = " ".join(item.split()).strip()
        if len(text) < 20:
            continue

        if foreign_pattern and foreign_pattern.search(text):
            continue

        normalized = text.casefold()
        if normalized not in seen:
            result.append(text)
            seen.add(normalized)

    return result

def _day_wise_itinerary(
    destination: Destination,
    duration_days: int,
    highlights: List[str],
) -> List[Dict[str, Any]]:
    duration_days = max(1, min(int(duration_days or 3), 30))
    destination_name = str(
        getattr(destination, "name", "") or "your destination"
    ).strip()
    destination_key = destination_name.casefold()

    unrelated_place_markers = (
        "tiruchirappalli", "tiruchirapalli", "trichy", "rock fort",
        "railway museum", "new delhi", "bangalore", "bengaluru",
        "jaipur", "gokarna", "pondicherry", "puducherry", "goa",
    )

    clean_highlights = _filter_foreign_destination_highlights(
    destination_name,
    highlights,
    [],
)
    curated_itineraries = {
        "bangalore": [
            (
                "Start with a morning walk through Lalbagh Botanical Garden, visit the historic "
                "Bangalore Palace, and explore local South Indian specialties around Basavanagudi."
            ),
            (
                "Stroll through Cubbon Park, view the grand architecture of Vidhana Soudha, and "
                "spend the afternoon visiting the Visvesvaraya Industrial and Technological Museum."
            ),
            (
                "Plan an adventure excursion to Bannerghatta Biological Park safari or head towards "
                "Nandi Hills for trekking trails and panoramic valley views."
            ),
            (
                "Discover Bangalore's thriving cafe and craft brewing scene in Indiranagar or Koramangala, "
                "browsing local boutique shops and art galleries."
            ),
        ],
        "bengaluru": [
            (
                "Start with a morning walk through Lalbagh Botanical Garden, visit the historic "
                "Bangalore Palace, and explore local South Indian specialties around Basavanagudi."
            ),
            (
                "Stroll through Cubbon Park, view the grand architecture of Vidhana Soudha, and "
                "spend the afternoon visiting the Visvesvaraya Industrial and Technological Museum."
            ),
            (
                "Plan an adventure excursion to Bannerghatta Biological Park safari or head towards "
                "Nandi Hills for trekking trails and panoramic valley views."
            ),
            (
                "Discover Bangalore's thriving cafe and craft brewing scene in Indiranagar or Koramangala, "
                "browsing local boutique shops and art galleries."
            ),
        ],
        "shimla": [
            (
                "Stroll along Mall Road and Scandal Point, admire the colonial-era architecture "
                "of Christ Church, and browse local handicrafts at Lakkar Bazaar."
            ),
            (
                "Visit The Ridge for panoramic Himalayan views, then walk or take the ropeway "
                "up to Jakhoo Temple on Jakhoo Hill."
            ),
            (
                "Take a scenic day excursion to Kufri to explore cedar-lined nature trails, valley viewpoints, "
                "and surrounding alpine landscapes."
            ),
            (
                "Visit the peaceful surroundings of Chadwick Falls or enjoy a relaxed walk around "
                "the historic open greenery of Annandale."
            ),
            (
                "Take a quiet morning visit to Tara Devi Temple with sweeping mountain views, "
                "leaving time for local cafes and your return journey."
            ),
        ],
        "solang valley": [
            (
                "Explore Solang Valley and enjoy the mountain scenery. "
                "If operating, consider the Solang ropeway after checking "
                "current weather, ticket prices and opening times."
            ),
            (
                "Plan an adventure day around activities such as paragliding "
                "or zorbing, choosing only activities currently operating "
                "with a reputable provider. Confirm prices, weather limits "
                "and safety requirements before booking."
            ),
            (
                "Spend the morning enjoying the valley views and, if "
                "conditions permit, choose a suitable guided outdoor activity. "
                "Keep time for a relaxed meal and your onward journey."
            ),
            (
                "Use an extra day for another locally available outdoor "
                "experience or a scenic excursion nearby. Verify road access, "
                "weather and return transport before setting out."
            ),
        ],
        "ganpatipule": [
            (
                "Visit Shri Swayambhu Ganpati Temple, then walk along "
                "Ganpatipule Beach. Check temple timings and sea conditions."
            ),
            (
                "Explore Prachin Konkan Museum and learn about the region's "
                "traditional coastal life. Confirm opening times."
            ),
            (
                "Take a scenic drive towards Aare-Ware Beach for coastal "
                "views. Check road and sea conditions before visiting."
            ),
            (
                "If time permits, visit Jaigad Fort or the Keshavsut Memorial "
                "in nearby Malgund, allowing time for the return journey."
            ),
        ],
        "pondicherry": [
            (
                "Explore White Town's heritage streets and visit the "
                "Promenade during the cooler evening hours."
            ),
            (
                "Visit Sri Aurobindo Ashram respectfully, then explore nearby "
                "heritage streets and cafés. Check visitor rules."
            ),
            (
                "Visit Paradise Beach if access and ferry services are "
                "available. Confirm sea conditions before travelling."
            ),
            (
                "Visit Manakula Vinayagar Temple and browse local boutiques "
                "before departure."
            ),
        ],
        "gokarna": [
            (
                "Visit Mahabaleshwar Temple and explore Gokarna's town lanes, "
                "then walk along Main Beach near sunset."
            ),
            (
                "Visit Kudle Beach and enjoy the coastal scenery. Use marked "
                "paths and check sea conditions."
            ),
            (
                "Explore Om Beach and nearby viewpoints during daylight, "
                "arranging local transport if needed."
            ),
            (
                "Keep the final morning for a short town or beach visit, "
                "leaving enough time for your onward journey."
            ),
        ],
    }

    destination_itinerary = curated_itineraries.get(destination_key)

    fallback_activities = [
        (
            f"Explore {destination_name} and select a locally verified "
            "attraction that matches your interests. Check access and timings."
        ),
        (
            f"Choose a verified nature area, landmark or activity near "
            f"{destination_name}, checking travel time before leaving."
        ),
        (
            f"Explore another suitable local attraction around "
            f"{destination_name}, allowing time for meals and rest."
        ),
        (
            f"Keep time for a final local visit near {destination_name} "
            "and your onward journey."
        ),
    ]

    candidates: List[str] = []
    seen_normalized = set()

    def add_candidate(text: str):
        if not text or not isinstance(text, str):
            return
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return
        norm = cleaned.casefold()
        if norm not in seen_normalized:
            seen_normalized.add(norm)
            candidates.append(cleaned)

    # 1. Curated destination itinerary if available
    if destination_itinerary:
        for act in destination_itinerary:
            add_candidate(act)

    # 2. Destination-grounded clean highlights
    for h in clean_highlights:
        add_candidate(h)

    # 3. Structured attractions from geo lookup / curated fallback places
    try:
        lat = getattr(destination, "lat", None)
        lon = getattr(destination, "lon", None)
        if lat is None or lon is None:
            guessed = guess_coordinates(destination_name)
            if guessed:
                lat, lon = guessed
        if lat is not None and lon is not None:
            attractions = get_nearby_attractions(lat, lon)
            for attr in attractions:
                name = attr.get("name") if isinstance(attr, dict) else None
                if name and not any(name.casefold() in c.casefold() for c in candidates):
                    add_candidate(
                        f"Visit {name} and take time to explore the surrounding area at a relaxed pace."
                    )
    except Exception:
        pass

    # 4. Verified fallback activities
    for fb in fallback_activities:
        add_candidate(fb)

    days: List[Dict[str, Any]] = []

    for index in range(duration_days):
        if index < len(candidates):
            activity = candidates[index]
        elif candidates:
            base = candidates[index % len(candidates)]
            activity = f"Enjoy additional leisure and exploration: {base}"
        else:
            activity = f"Explore {destination_name} at your own pace."

        days.append({
            "day": index + 1,
            "summary": f"Day {index + 1} in {destination_name}: {activity}",
        })

    return days

def itinerary_with_package(
    destination_name: str,
    duration_days: int,
    package: Dict[str, Any],
) -> List[Dict[str, Any]]:
    package_days = max(
        1,
        min(int(package.get("duration_days") or duration_days or 3), 30),
    )
    inclusions = package.get("amenities") or []
    days = []

    for day_num in range(1, package_days + 1):
        if day_num == 1:
            summary = (
                f"Begin '{package.get('title', 'your travel package')}' "
                f"with {package.get('partner_name') or 'your tour partner'}."
            )
        elif inclusions:
            inclusion = inclusions[(day_num - 2) % len(inclusions)]
            summary = (
                f"Day {day_num} of '{package.get('title', 'your travel package')}' "
                f"— includes {str(inclusion).strip()}."
            )
        else:
            summary = f"Explore {destination_name} on day {day_num}."

        days.append({"day": day_num, "summary": summary})

    return days

def refresh_hotel_and_package_recommendations(
    db: Session,
    destination_id: int,
    slots: Dict[str, Any],
):
    hotels = recommend_hotels(db, destination_id, slots)
    packages = recommend_packages(db, destination_id, slots)

    if not should_recommend_packages(slots, packages):
        packages = []

    return hotels, packages

def regenerate_itinerary(
    db: Session,
    destination_id: int,
    duration_days: int,
    slots: Dict[str, Any],
) -> List[Dict[str, Any]]:
    destination = (
        db.query(Destination)
        .filter(Destination.id == destination_id)
        .first()
    )

    if not destination:
        return []

    query = " ".join([
        destination.name,
        slots.get("travel_style") or "",
        slots.get("interests") or "",
    ]).strip()

    try:
        rag = query_knowledge_base(query, destination_name=destination.name)
    except Exception:
        rag = {}

    highlights = top_highlights_from_rag(
        rag,
        max_items=min(max(1, duration_days), 5),
        destination_name=destination.name,
    )
    highlights = _filter_foreign_destination_highlights(
        destination.name,
        highlights,
        [],
    )

    return _day_wise_itinerary(destination, duration_days, highlights)

def generate_plan(
    db: Session,
    slots: Dict[str, Any],
    source_coords: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    duration_days = max(1, min(int(slots.get("duration_days") or 3), 30))
    travelers = max(1, int(slots.get("travelers") or 1))

    destinations = _find_ml_candidate_destinations(db, slots)
    primary = destinations[0] if destinations else None

    query_parts = [
        primary.name if primary else "",
        slots.get("travel_style") or "",
        slots.get("interests") or "",
    ]
    rag_query = " ".join(part for part in query_parts if part).strip() or "travel"

    try:
        rag = query_knowledge_base(rag_query, destination_name=primary.name if primary else None)
    except Exception:
        rag = {}

    highlights = []

    if primary:
        highlights = top_highlights_from_rag(
            rag,
            max_items=min(duration_days, 5),
            destination_name=primary.name,
        )
        highlights = _filter_foreign_destination_highlights(
            primary.name,
            highlights,
            [d.name for d in destinations],
        )

    destination_blocks = []

    for destination in destinations:
        lat = destination.lat
        lon = destination.lon

        if lat is None or lon is None:
            try:
                guessed = guess_coordinates(destination.name)
                if guessed:
                    lat, lon = guessed
            except Exception:
                lat, lon = None, None

        try:
            weather = (
                cached_weather(lat, lon)
                if lat is not None and lon is not None
                else None
            )
        except Exception:
            weather = None

        candidate_packages = recommend_packages(db, destination.id, slots)
        recommended_packages = (
            candidate_packages
            if should_recommend_packages(slots, candidate_packages)
            else []
        )

        destination_blocks.append({
            "id": destination.id,
            "name": destination.name,
            "country": destination.country,
            "description": destination.description,
            "thumbnail_url": destination.thumbnail_url,
            "avg_rating": destination.avg_rating,
            "explanation": _llm_explanation(destination, slots),
            "weather": weather,
            "recommended_hotels": recommend_hotels(db, destination.id, slots),
            "recommended_packages": recommended_packages,
        })

    itinerary = (
        _day_wise_itinerary(primary, duration_days, highlights)
        if primary else []
    )

    nearby_attractions = []
    if primary:
        guessed = guess_coordinates(primary.name)

        if guessed:
            p_lat, p_lon = guessed
        else:
            p_lat, p_lon = primary.lat, primary.lon

        if p_lat is not None and p_lon is not None:
            try:
                nearby_attractions = get_nearby_attractions(p_lat, p_lon) or []
            except Exception as exc:
                print(f"[Attractions] Lookup failed: {exc}")
                nearby_attractions = []

    route = None
    if primary and source_coords:
        source_lat = source_coords.get("lat")
        source_lon = source_coords.get("lon")

        dest_lat = primary.lat
        dest_lon = primary.lon

        if dest_lat is None or dest_lon is None:
            try:
                guessed = guess_coordinates(primary.name)
                if guessed:
                    dest_lat, dest_lon = guessed
            except Exception:
                dest_lat, dest_lon = None, None

        if (
            source_lat is not None
            and source_lon is not None
            and dest_lat is not None
            and dest_lon is not None
        ):
            try:
                route = get_route_osrm(
                    source_lat,
                    source_lon,
                    dest_lat,
                    dest_lon,
                )
            except Exception:
                route = None

    climate_hint = (
        _climate_hint_from_tags(primary.tags)
        if primary else "temperate"
    )
    activities = [
        item.strip()
        for item in (slots.get("interests") or "").split(",")
        if item.strip()
    ]
    packing_list = generate_packing(
        climate_hint,
        duration_days,
        activities,
    )

    budget = allocate_budget(
        db,
        slots,
        duration_days,
        travelers,
        destination_id=primary.id if primary else None,
        selected_hotel=None,
    )

    tips = _llm_travel_tips(
        [item["name"] for item in destination_blocks] or ["your destination"],
        slots,
    )
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