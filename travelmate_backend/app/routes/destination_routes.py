from typing import List, Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.destination import Destination
from ..schemas.destination import DestinationOut
from ..services.weather_service import cached_weather
from ..services.geo_lookup import guess_coordinates
from ..utils.image_resolver import resolve_destination_image, resolve_attraction_image
import requests
import os
import re

router = APIRouter(prefix="/destinations", tags=["destinations"])


# --------------------------
# CURATED ENHANCED DESCRIPTIONS (STEP 3)
# --------------------------
CURATED_DESTINATION_DESCRIPTIONS = {
    "hampi": (
        "Hampi is a celebrated UNESCO World Heritage Site nestled along the banks of the Tungabhadra River in Karnataka. "
        "Renowned for the magnificent ruins of the 14th-century Vijayanagara Empire, its landscape is studded with grand sculpted temples like "
        "Virupaksha and the iconic Stone Chariot at Vijaya Vitthala Temple, surrounded by surreal boulder-strewn hills, royal enclosures, "
        "and timeless river sunsets. The best time to visit is from October to March."
    ),
    "pondicherry": (
        "Pondicherry (Puducherry) is an enchanting coastal union territory on the Coromandel Coast featuring a distinctive blend of "
        "French colonial heritage and vibrant Tamil culture. Known for the mustard-yellow villas and tree-lined boulevards of White Town, "
        "the scenic Promenade Beach along the Bay of Bengal, serene seaside cafes, coastal cycling, and the experimental township of Auroville. "
        "The best time to visit is from October to March."
    ),
    "puducherry": (
        "Pondicherry (Puducherry) is an enchanting coastal union territory on the Coromandel Coast featuring a distinctive blend of "
        "French colonial heritage and vibrant Tamil culture. Known for the mustard-yellow villas and tree-lined boulevards of White Town, "
        "the scenic Promenade Beach along the Bay of Bengal, serene seaside cafes, coastal cycling, and the experimental township of Auroville. "
        "The best time to visit is from October to March."
    ),
    "lakshadweep": (
        "Lakshadweep is a pristine archipelago of 36 palm-fringed coral atolls, sparkling turquoise lagoons, and untouched white-sand beaches "
        "in the Arabian Sea off Kerala's coast. An exceptional destination for marine eco-tourism, world-class scuba diving, lagoon snorkeling, "
        "kayaking, and secluded island getaways. The ideal season to visit is October to May when the waters are calm and clear."
    ),
    "tarkarli": (
        "Tarkarli is a scenic coastal haven in the Konkan region of Maharashtra, famed for its long white-sand beach where the Karli River meets "
        "the Arabian Sea. It is a premier destination for coastal water sports including scuba diving, snorkeling along the Sindhudurg Fort coral reef, "
        "parasailing, dolphin-spotting cruises, and tranquil backwater boat safaris. Best visited between October and March."
    ),
    "agonda": (
        "Agonda is a serene, picturesque coastal village in South Goa renowned for its wide, pristine crescent beach and relaxed atmosphere. "
        "A recognized olive ridley turtle nesting sanctuary, it is an idyllic retreat for travelers seeking tranquil shores, dolphin-watching boat trips, "
        "sunset kayaking at nearby Cola Beach lagoon, yoga retreats, and authentic coastal dining away from crowded tourist hubs. Best visited between November and February."
    ),
    "jaipur": (
        "Jaipur, the historic Pink City and capital of Rajasthan, is world-famous for its majestic royal forts, palaces, and vibrant Rajasthani culture. "
        "Highlights include the hilltop Amber Fort, the iconic honeycomb facade of Hawa Mahal, the grand City Palace, and Jantar Mantar observatory, "
        "complemented by bustling traditional bazaars rich in textiles, jewelry, and handicrafts. The best time to visit is from October to March."
    ),
    "goa": (
        "Goa is India's premier beach and coastal destination on the western Konkan coast, celebrated for its sun-drenched golden beaches, "
        "UNESCO-listed Portuguese colonial churches in Old Goa, scenic spice plantations, lively coastal shacks, and rich Indo-Portuguese culinary heritage. "
        "From tranquil South Goa bays to bustling North Goa shores, the best season extends from November to March."
    ),
}


def get_enhanced_description(d: Destination, raw_desc: Optional[str] = None) -> str:
    name_key = (d.name or "").strip().lower()
    for k, text in CURATED_DESTINATION_DESCRIPTIONS.items():
        if k == name_key or k in name_key:
            return text

    desc = (raw_desc or d.description or "").strip()
    words = desc.split()

    # If already a comprehensive sentence, keep it
    if len(words) > 12 and desc.lower() not in ("cultural", "luxury", "adventure", "relaxing", "beach", "heritage", "nature"):
        return desc

    # Construct clean, verified synthesis
    category = getattr(d, "category", None) or "scenic"
    state = getattr(d, "state", None) or ""
    loc_parts = [p for p in [d.city if d.city and d.city != d.name else None, state, d.country or "India"] if p]
    loc_text = f" in {', '.join(loc_parts)}" if loc_parts else ""
    season_text = f" The ideal time to explore is during {d.best_season}." if getattr(d, "best_season", None) else ""
    duration_text = f" A stay of {d.ideal_duration} days is recommended for a balanced visit." if getattr(d, "ideal_duration", None) else ""

    return (
        f"{d.name} is a captivating {category.lower()} destination{loc_text}. "
        f"It offers travelers a rich combination of regional culture, scenic landscapes, and memorable local experiences.{season_text}{duration_text}"
    )


# --------------------------
# GET ALL DESTINATIONS WITH WEATHER, SEARCH & FILTER
# --------------------------
@router.get("/", response_model=List[DestinationOut])
def list_destinations(
    skip: int = 0,
    limit: int = 20,
    q: str = "",
    category: str = "",
    budget: str = "",
    state: str = "",
    mood: str = "",
    season: str = "",
    paginated: bool = False,
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_
    query = db.query(Destination)
    if q:
        query = query.filter(
            or_(
                Destination.name.ilike(f"%{q}%"),
                Destination.state.ilike(f"%{q}%"),
                Destination.city.ilike(f"%{q}%"),
            )
        )
    if category and category.lower() not in ("all", ""):
        query = query.filter(Destination.category.ilike(f"%{category}%"))

    if state and state.lower() not in ("all", ""):
        query = query.filter(Destination.state.ilike(f"%{state}%"))

    if budget and budget.lower() not in ("all", ""):
        b_low = budget.lower()
        if b_low == "low":
            query = query.filter(Destination.average_budget <= 2000)
        elif b_low == "medium":
            query = query.filter(Destination.average_budget > 2000, Destination.average_budget <= 4000)
        elif b_low in ("high", "luxury"):
            query = query.filter(Destination.average_budget > 4000)

    if mood and mood.lower() not in ("all", ""):
        m_low = mood.lower()
        if "relax" in m_low:
            query = query.filter(
                or_(
                    Destination.category.in_(["Beach", "Forest"]),
                    Destination.tags.ilike("%relax%"),
                    Destination.tags.ilike("%peace%"),
                    Destination.description.ilike("%relax%"),
                )
            )
        elif "adventur" in m_low:
            query = query.filter(
                or_(
                    Destination.category.in_(["Hill Station", "Adventure", "Desert"]),
                    Destination.tags.ilike("%adventure%"),
                    Destination.tags.ilike("%trek%"),
                    Destination.description.ilike("%adventure%"),
                )
            )
        elif "cultur" in m_low or "heritage" in m_low:
            query = query.filter(
                or_(
                    Destination.category.in_(["Heritage", "Urban"]),
                    Destination.tags.ilike("%heritage%"),
                    Destination.tags.ilike("%temple%"),
                    Destination.tags.ilike("%culture%"),
                )
            )
        elif "nature" in m_low:
            query = query.filter(
                or_(
                    Destination.category.in_(["Forest", "Hill Station", "Beach"]),
                    Destination.tags.ilike("%nature%"),
                    Destination.tags.ilike("%wildlife%"),
                    Destination.description.ilike("%nature%"),
                )
            )

    if season and season.lower() not in ("all", ""):
        s_low = season.lower()
        if "winter" in s_low:
            query = query.filter(
                or_(
                    Destination.best_season.ilike("%Nov%"),
                    Destination.best_season.ilike("%Dec%"),
                    Destination.best_season.ilike("%Jan%"),
                    Destination.best_season.ilike("%Feb%"),
                    Destination.best_season.ilike("%All Year%"),
                )
            )
        elif "summer" in s_low:
            query = query.filter(
                or_(
                    Destination.best_season.ilike("%Mar%"),
                    Destination.best_season.ilike("%Apr%"),
                    Destination.best_season.ilike("%May%"),
                    Destination.best_season.ilike("%Jun%"),
                    Destination.best_season.ilike("%All Year%"),
                )
            )
        elif "monsoon" in s_low:
            query = query.filter(
                or_(
                    Destination.best_season.ilike("%Jul%"),
                    Destination.best_season.ilike("%Aug%"),
                    Destination.best_season.ilike("%Sep%"),
                    Destination.best_season.ilike("%All Year%"),
                )
            )
        else:
            query = query.filter(Destination.best_season.ilike(f"%{season}%"))

    total = query.count()
    destinations = query.offset(skip).limit(limit).all()

    enriched = []
    for d in destinations:
        thumbnail = d.thumbnail_url
        if not thumbnail:
            thumbnail = resolve_destination_image(d.id, getattr(d, "csv_destination_id", None))

        lat = d.lat
        lon = d.lon
        if lat is None or lon is None:
            coords = guess_coordinates(d.name)
            if coords:
                lat, lon = coords

        obj = {
            "id": d.id,
            "name": d.name,
            "country": d.country,
            "description": get_enhanced_description(d),
            "lat": lat,
            "lon": lon,
            "tags": d.tags,
            "thumbnail_url": thumbnail,
            "avg_rating": d.avg_rating,
            "state": getattr(d, "state", None),
            "category": getattr(d, "category", None),
            "average_budget": getattr(d, "average_budget", None),
            "best_season": getattr(d, "best_season", None),
            "ideal_duration": getattr(d, "ideal_duration", None),
        }

        if lat and lon:
            obj["weather"] = cached_weather(lat, lon)
        else:
            obj["weather"] = None

        enriched.append(obj)

    if paginated:
        from fastapi.responses import JSONResponse
        return JSONResponse(content={"items": enriched, "total": total})

    return enriched


@router.get("/states", response_model=List[str])
def list_states(db: Session = Depends(get_db)):
    states = (
        db.query(Destination.state)
        .filter(Destination.state.isnot(None), Destination.state != "")
        .distinct()
        .order_by(Destination.state)
        .all()
    )
    return [s[0] for s in states if s[0]]


# --------------------------
# ATTRACTIONS & ACTIVITIES RESOLUTION (STEPS 7 & 8)
# --------------------------
_attractions_by_dest = None
_attractions_by_city = None
_activities_by_dest = None

CITY_ALIASES = {
    "pondicherry": "puducherry",
    "puducherry": "puducherry",
    "bengaluru": "bangalore",
    "bangalore": "bangalore",
    "mumbai": "mumbai",
    "bombay": "mumbai",
    "kochi": "kochi",
    "cochin": "kochi",
    "panjim": "goa",
}

# Curated attractions for destinations where dataset records are absent or require strict regional isolation
CURATED_DESTINATION_ATTRACTIONS: Dict[str, List[Dict[str, Any]]] = {
    "lakshadweep": [
        {
            "id": "ATT_LAK_1",
            "name": "Bangaram Atoll & Lagoon",
            "city": "Lakshadweep",
            "state": "Lakshadweep",
            "category": "Beach & Marine",
            "entry_fee": 0.0,
            "rating": 4.9,
            "lat": 10.9419,
            "lon": 72.2922,
            "image": None,
        },
        {
            "id": "ATT_LAK_2",
            "name": "Agatti Island Beach & Lagoon",
            "city": "Lakshadweep",
            "state": "Lakshadweep",
            "category": "Beach & Marine",
            "entry_fee": 0.0,
            "rating": 4.8,
            "lat": 10.8533,
            "lon": 72.1931,
            "image": None,
        },
        {
            "id": "ATT_LAK_3",
            "name": "Kavaratti Marine Aquarium & Beach",
            "city": "Lakshadweep",
            "state": "Lakshadweep",
            "category": "Marine Life & Sightseeing",
            "entry_fee": 50.0,
            "rating": 4.7,
            "lat": 10.5667,
            "lon": 72.6417,
            "image": None,
        },
        {
            "id": "ATT_LAK_4",
            "name": "Kalpeni Island Lagoon & Coral Bank",
            "city": "Lakshadweep",
            "state": "Lakshadweep",
            "category": "Beach & Marine",
            "entry_fee": 0.0,
            "rating": 4.7,
            "lat": 10.0717,
            "lon": 73.6528,
            "image": None,
        },
        {
            "id": "ATT_LAK_5",
            "name": "Kadmat Island Coral Reef",
            "city": "Lakshadweep",
            "state": "Lakshadweep",
            "category": "Water Sports & Nature",
            "entry_fee": 0.0,
            "rating": 4.8,
            "lat": 11.2333,
            "lon": 72.7833,
            "image": None,
        },
    ],
    "agonda": [
        {
            "id": "ATT_AGO_1",
            "name": "Agonda Beach & Turtle Nesting Site",
            "city": "Agonda",
            "state": "Goa",
            "category": "Beach & Nature",
            "entry_fee": 0.0,
            "rating": 4.8,
            "lat": 15.0442,
            "lon": 73.9877,
            "image": None,
        },
        {
            "id": "ATT_AGO_2",
            "name": "Cola Beach & Freshwater Lagoon",
            "city": "Agonda",
            "state": "Goa",
            "category": "Beach & Lagoon",
            "entry_fee": 0.0,
            "rating": 4.7,
            "lat": 15.0592,
            "lon": 73.9744,
            "image": None,
        },
        {
            "id": "ATT_AGO_3",
            "name": "Butterfly Beach",
            "city": "Agonda",
            "state": "Goa",
            "category": "Nature & Cove",
            "entry_fee": 0.0,
            "rating": 4.6,
            "lat": 15.0217,
            "lon": 74.0042,
            "image": None,
        },
        {
            "id": "ATT_AGO_4",
            "name": "Cabo de Rama Fort",
            "city": "Agonda",
            "state": "Goa",
            "category": "Heritage & Fort",
            "entry_fee": 0.0,
            "rating": 4.6,
            "lat": 15.0883,
            "lon": 73.9217,
            "image": None,
        },
        {
            "id": "ATT_AGO_5",
            "name": "Palolem Beach",
            "city": "Agonda",
            "state": "Goa",
            "category": "Beach & Sunset",
            "entry_fee": 0.0,
            "rating": 4.7,
            "lat": 15.0100,
            "lon": 74.0231,
            "image": None,
        },
    ],
    "tarkarli": [
        {
            "id": "ATT_TAR_1",
            "name": "Tarkarli Beach",
            "city": "Tarkarli",
            "state": "Maharashtra",
            "category": "Beach & Water Sports",
            "entry_fee": 0.0,
            "rating": 4.6,
            "lat": 16.0137,
            "lon": 73.4898,
            "image": None,
        },
        {
            "id": "ATT_TAR_2",
            "name": "Sindhudurg Fort",
            "city": "Tarkarli",
            "state": "Maharashtra",
            "category": "Heritage & Fort",
            "entry_fee": 50.0,
            "rating": 4.7,
            "lat": 16.0422,
            "lon": 73.4631,
            "image": None,
        },
        {
            "id": "ATT_TAR_3",
            "name": "Devbagh Beach & Tsunami Island",
            "city": "Tarkarli",
            "state": "Maharashtra",
            "category": "Beach & Water Adventure",
            "entry_fee": 0.0,
            "rating": 4.7,
            "lat": 15.9861,
            "lon": 73.4981,
            "image": None,
        },
        {
            "id": "ATT_TAR_4",
            "name": "Karli River Backwaters",
            "city": "Tarkarli",
            "state": "Maharashtra",
            "category": "Nature & Boating",
            "entry_fee": 0.0,
            "rating": 4.5,
            "lat": 16.0028,
            "lon": 73.5042,
            "image": None,
        },
    ],
}


def _load_attractions_datasets():
    global _attractions_by_dest, _attractions_by_city
    if _attractions_by_dest is not None and _attractions_by_city is not None:
        return

    import csv
    from pathlib import Path
    by_dest = {}
    by_city = {}
    possible_paths = [
        Path(__file__).resolve().parents[3] / "datasets" / "attractions.csv",
        Path(os.getcwd()) / "datasets" / "attractions.csv",
        Path(os.getcwd()).parent / "datasets" / "attractions.csv",
    ]
    csv_path = None
    for p in possible_paths:
        if p.exists() and p.is_file():
            csv_path = p
            break

    if csv_path:
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    did = (r.get("destination_id") or "").strip().upper()
                    city = (r.get("city") or "").strip().lower()
                    att_id = (r.get("attraction_id") or "").strip()
                    img_path = resolve_attraction_image(att_id)
                    fee_str = (r.get("entry_fee") or "0").replace(",", "").strip()
                    fee = float(fee_str) if fee_str.replace(".", "", 1).isdigit() else 0.0
                    rating_str = (r.get("rating") or "4.5").replace(",", "").strip()
                    rating = float(rating_str) if rating_str.replace(".", "", 1).isdigit() else 4.5
                    lat_str = (r.get("latitude") or "").strip()
                    lon_str = (r.get("longitude") or "").strip()
                    lat_val = float(lat_str) if lat_str and lat_str.replace("-", "", 1).replace(".", "", 1).isdigit() else None
                    lon_val = float(lon_str) if lon_str and lon_str.replace("-", "", 1).replace(".", "", 1).isdigit() else None

                    entry = {
                        "id": att_id,
                        "name": r.get("attraction_name", ""),
                        "city": r.get("city", ""),
                        "state": r.get("state", ""),
                        "category": r.get("category", ""),
                        "entry_fee": fee,
                        "rating": rating,
                        "lat": lat_val,
                        "lon": lon_val,
                        "image": img_path,
                    }
                    if did:
                        by_dest.setdefault(did, []).append(entry)
                    if city:
                        by_city.setdefault(city, []).append(entry)

            for d in by_dest:
                by_dest[d].sort(key=lambda x: x.get("rating", 0), reverse=True)
            for c in by_city:
                by_city[c].sort(key=lambda x: x.get("rating", 0), reverse=True)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Failed to load attractions: %s", exc, exc_info=True)

    _attractions_by_dest = by_dest
    _attractions_by_city = by_city


def _get_dest_attractions(
    csv_dest_id: Optional[str] = None,
    dest_name: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> List[Dict[str, Any]]:
    # 0. Check curated attractions first for destinations where dataset records are absent or require strict regional isolation
    if dest_name:
        dest_norm = dest_name.strip().lower()
        if dest_norm in CURATED_DESTINATION_ATTRACTIONS:
            return [dict(att) for att in CURATED_DESTINATION_ATTRACTIONS[dest_norm]]

    _load_attractions_datasets()
    results: List[Dict[str, Any]] = []
    seen_names = set()

    # 1. Primary lookup by csv_dest_id
    if csv_dest_id and _attractions_by_dest:
        clean_id = csv_dest_id.strip().upper()
        for item in _attractions_by_dest.get(clean_id, []):
            item_copy = dict(item)
            # Coordinate sanity fix for Virupaksha Temple in Hampi (attractions.csv has erroneous Mysore lat 12.3)
            if item_copy.get("name", "").strip().lower() == "virupaksha temple" and item_copy.get("lat") and float(item_copy["lat"]) < 13.0:
                item_copy["lat"] = 15.3353
                item_copy["lon"] = 76.4600

            name_norm = item_copy.get("name", "").strip().lower()
            if name_norm and name_norm not in seen_names:
                seen_names.add(name_norm)
                results.append(item_copy)

    # 2. Lookup by city or destination name
    lookup_keys = []
    if dest_name:
        dest_norm = dest_name.strip().lower()
        lookup_keys.append(dest_norm)
        if dest_norm in CITY_ALIASES:
            lookup_keys.append(CITY_ALIASES[dest_norm])
    if city:
        city_norm = city.strip().lower()
        if city_norm not in lookup_keys:
            lookup_keys.append(city_norm)
        if city_norm in CITY_ALIASES and CITY_ALIASES[city_norm] not in lookup_keys:
            lookup_keys.append(CITY_ALIASES[city_norm])

    if _attractions_by_city:
        for k in lookup_keys:
            if k in _attractions_by_city:
                for item in _attractions_by_city[k]:
                    item_copy = dict(item)
                    # Coordinate sanity fix for Virupaksha Temple in Hampi
                    if item_copy.get("name", "").strip().lower() == "virupaksha temple" and item_copy.get("lat") and float(item_copy["lat"]) < 13.0:
                        item_copy["lat"] = 15.3353
                        item_copy["lon"] = 76.4600

                    name_norm = item_copy.get("name", "").strip().lower()
                    if name_norm and name_norm not in seen_names:
                        seen_names.add(name_norm)
                        results.append(item_copy)

    # 3. Supplemental lookup from AttractionCoordinateResolver for verified landmark coords
    if len(results) < 3 and dest_name:
        try:
            from app.services.route_optimizer import AttractionCoordinateResolver
            resolver = AttractionCoordinateResolver.get_instance()
            norm_target = dest_name.casefold()
            for (c, an), info in resolver._by_city_and_name.items():
                if c == norm_target or norm_target in c:
                    name_norm = info["name"].strip().lower()
                    if name_norm not in seen_names:
                        seen_names.add(name_norm)
                        results.append({
                            "id": f"ATT_RES_{len(results)+1}",
                            "name": info["name"],
                            "city": info.get("city", dest_name),
                            "state": info.get("state", state or ""),
                            "category": info.get("category", "Heritage"),
                            "entry_fee": 0.0,
                            "rating": float(info.get("rating", 4.5)),
                            "lat": info.get("lat"),
                            "lon": info.get("lon"),
                            "image": None,
                        })
        except Exception:
            pass

    # Sort attractions with rating priority
    results.sort(key=lambda x: (x.get("rating") is not None, x.get("rating") or 0.0), reverse=True)
    return results


CURATED_DESTINATION_ACTIVITIES = {
    "hampi": [
        {"id": "ACT_HMP_1", "name": "Vijayanagara Empire Heritage Walking Tour", "category": "Heritage & Culture", "price": 400.0, "duration": 3, "best_season": "Oct-Mar"},
        {"id": "ACT_HMP_2", "name": "Coracle Boat Ride on Tungabhadra River", "category": "Water Adventure", "price": 300.0, "duration": 1, "best_season": "Oct-Mar"},
        {"id": "ACT_HMP_3", "name": "Sunset Bouldering & Trek to Matanga Hill", "category": "Adventure & Nature", "price": 0.0, "duration": 2, "best_season": "Oct-Mar"},
        {"id": "ACT_HMP_4", "name": "Bicycle Exploration of Royal Enclosure & Vitthala Complex", "category": "Sightseeing", "price": 250.0, "duration": 4, "best_season": "Oct-Mar"},
    ],
    "pondicherry": [
        {"id": "ACT_PDY_1", "name": "French Quarter Heritage & Architecture Walk", "category": "Heritage & Culture", "price": 350.0, "duration": 2, "best_season": "Oct-Mar"},
        {"id": "ACT_PDY_2", "name": "Scuba Diving & Coral Reef Exploration", "category": "Water Sports", "price": 3500.0, "duration": 3, "best_season": "Oct-Mar"},
        {"id": "ACT_PDY_3", "name": "Surfing Session at Serenity Beach", "category": "Water Sports", "price": 1500.0, "duration": 2, "best_season": "Oct-Mar"},
        {"id": "ACT_PDY_4", "name": "Auroville Meditation & Township Tour", "category": "Cultural & Wellness", "price": 0.0, "duration": 3, "best_season": "Oct-Mar"},
        {"id": "ACT_PDY_5", "name": "Promenade Seaside Sunset Cycling", "category": "Leisure & Nature", "price": 150.0, "duration": 2, "best_season": "Oct-Mar"},
    ],
    "puducherry": [
        {"id": "ACT_PDY_1", "name": "French Quarter Heritage & Architecture Walk", "category": "Heritage & Culture", "price": 350.0, "duration": 2, "best_season": "Oct-Mar"},
        {"id": "ACT_PDY_2", "name": "Scuba Diving & Coral Reef Exploration", "category": "Water Sports", "price": 3500.0, "duration": 3, "best_season": "Oct-Mar"},
        {"id": "ACT_PDY_3", "name": "Surfing Session at Serenity Beach", "category": "Water Sports", "price": 1500.0, "duration": 2, "best_season": "Oct-Mar"},
        {"id": "ACT_PDY_4", "name": "Auroville Meditation & Township Tour", "category": "Cultural & Wellness", "price": 0.0, "duration": 3, "best_season": "Oct-Mar"},
        {"id": "ACT_PDY_5", "name": "Promenade Seaside Sunset Cycling", "category": "Leisure & Nature", "price": 150.0, "duration": 2, "best_season": "Oct-Mar"},
    ],
    "lakshadweep": [
        {"id": "ACT_LAK_1", "name": "Scuba Diving at Bangaram Coral Reef", "category": "Water Sports", "price": 3800.0, "duration": 3, "best_season": "Oct-May"},
        {"id": "ACT_LAK_2", "name": "Lagoon Snorkeling & Sea Turtle Safari", "category": "Water Sports", "price": 1200.0, "duration": 2, "best_season": "Oct-May"},
        {"id": "ACT_LAK_3", "name": "Kayaking in Crystal Turquoise Waters", "category": "Water Sports", "price": 500.0, "duration": 2, "best_season": "Oct-May"},
        {"id": "ACT_LAK_4", "name": "Glass-Bottom Boat Coral Viewing", "category": "Sightseeing", "price": 800.0, "duration": 1, "best_season": "Oct-May"},
        {"id": "ACT_LAK_5", "name": "Catamaran Island Hopping Excursion", "category": "Adventure & Nature", "price": 1500.0, "duration": 4, "best_season": "Oct-May"},
    ],
    "tarkarli": [
        {"id": "ACT_TAR_1", "name": "Scuba Diving with Certified Instructors", "category": "Water Sports", "price": 2500.0, "duration": 3, "best_season": "Oct-Mar"},
        {"id": "ACT_TAR_2", "name": "Snorkeling at Sindhudurg Fort Coral Reef", "category": "Water Sports", "price": 1200.0, "duration": 2, "best_season": "Oct-Mar"},
        {"id": "ACT_TAR_3", "name": "Parasailing & Jet Ski Water Sports Combo", "category": "Adventure", "price": 1800.0, "duration": 2, "best_season": "Oct-Mar"},
        {"id": "ACT_TAR_4", "name": "Karli River Backwater Houseboat Safari", "category": "Sightseeing", "price": 600.0, "duration": 2, "best_season": "Oct-Mar"},
        {"id": "ACT_TAR_5", "name": "Dolphin Watching Marine Cruise", "category": "Wildlife & Marine", "price": 500.0, "duration": 2, "best_season": "Oct-Mar"},
    ],
    "agonda": [
        {"id": "ACT_AGO_1", "name": "Dolphin Watching Boat Safari", "category": "Wildlife & Marine", "price": 800.0, "duration": 2, "best_season": "Nov-Feb"},
        {"id": "ACT_AGO_2", "name": "Sunset Kayaking at Cola Beach Lagoon", "category": "Water Sports", "price": 400.0, "duration": 2, "best_season": "Nov-Feb"},
        {"id": "ACT_AGO_3", "name": "Olive Ridley Turtle Nesting Conservation Walk", "category": "Nature & Eco-Tourism", "price": 0.0, "duration": 2, "best_season": "Nov-Feb"},
        {"id": "ACT_AGO_4", "name": "Sunset Yoga & Beach Meditation Session", "category": "Wellness", "price": 500.0, "duration": 1, "best_season": "Nov-Feb"},
    ],
    "jaipur": [
        {"id": "ACT_JAI_1", "name": "Amber Fort Guided Heritage Walk & Photo Tour", "category": "Heritage & Culture", "price": 500.0, "duration": 3, "best_season": "Oct-Mar"},
        {"id": "ACT_JAI_2", "name": "City Palace & Jantar Mantar Astronomy Exploration", "category": "Heritage & Culture", "price": 400.0, "duration": 3, "best_season": "Oct-Mar"},
        {"id": "ACT_JAI_3", "name": "Traditional Block Printing & Craft Workshop in Old City", "category": "Arts & Craft", "price": 600.0, "duration": 2, "best_season": "Oct-Mar"},
        {"id": "ACT_JAI_4", "name": "Hot Air Balloon Flight Over Pink City & Aravallis", "category": "Adventure", "price": 9500.0, "duration": 2, "best_season": "Oct-Mar"},
    ],
}


def _get_dest_activities(
    csv_dest_id: Optional[str] = None,
    dest_name: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    global _activities_by_dest
    if _activities_by_dest is None:
        import csv
        from pathlib import Path
        cache = {}
        possible_paths = [
            Path(__file__).resolve().parents[3] / "datasets" / "activities.csv",
            Path(os.getcwd()) / "datasets" / "activities.csv",
            Path(os.getcwd()).parent / "datasets" / "activities.csv",
        ]
        csv_path = None
        for p in possible_paths:
            if p.exists() and p.is_file():
                csv_path = p
                break

        if csv_path:
            try:
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        did = (r.get("destination_id") or "").strip().upper()
                        if not did:
                            continue
                        price_str = (r.get("price") or "0").replace(",", "").strip()
                        price = float(price_str) if price_str.replace(".", "", 1).isdigit() else 0.0
                        dur_str = (r.get("duration") or "2").strip()
                        duration = int(dur_str) if dur_str.isdigit() else 2

                        entry = {
                            "id": r.get("activity_id", ""),
                            "name": r.get("activity_name", ""),
                            "category": r.get("category", ""),
                            "price": price,
                            "duration": duration,
                            "best_season": r.get("best_season", ""),
                        }
                        cache.setdefault(did, []).append(entry)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error("Failed to load activities: %s", exc, exc_info=True)
        _activities_by_dest = cache

    # 1. Check curated activities first for high-quality coverage
    if dest_name:
        dest_norm = dest_name.strip().lower()
        if dest_norm in CURATED_DESTINATION_ACTIVITIES:
            return CURATED_DESTINATION_ACTIVITIES[dest_norm]

    # 2. Check activities from CSV
    if csv_dest_id and _activities_by_dest:
        clean_id = csv_dest_id.strip().upper()
        if clean_id in _activities_by_dest and len(_activities_by_dest[clean_id]) > 0:
            return _activities_by_dest[clean_id]

    # 3. Grounded fallback by destination category
    cat_norm = (category or "sightseeing").strip().lower()
    if "beach" in cat_norm or "coast" in cat_norm:
        return [
            {"id": "ACT_GEN_B1", "name": "Coastal Water Sports & Banana Ride", "category": "Water Sports", "price": 800.0, "duration": 2, "best_season": "Oct-Mar"},
            {"id": "ACT_GEN_B2", "name": "Beach Sunset Kayaking & Paddleboarding", "category": "Water Adventure", "price": 500.0, "duration": 2, "best_season": "Oct-Mar"},
            {"id": "ACT_GEN_B3", "name": "Scenic Coastal Boat Cruise", "category": "Sightseeing", "price": 400.0, "duration": 1, "best_season": "Oct-Mar"},
        ]
    elif "heritage" in cat_norm or "culture" in cat_norm or "temple" in cat_norm:
        return [
            {"id": "ACT_GEN_H1", "name": "Guided Historical Monument Walking Tour", "category": "Heritage & Culture", "price": 300.0, "duration": 2, "best_season": "All Year"},
            {"id": "ACT_GEN_H2", "name": "Temple Architecture & Photography Tour", "category": "Sightseeing", "price": 200.0, "duration": 3, "best_season": "Oct-Mar"},
            {"id": "ACT_GEN_H3", "name": "Traditional Arts & Crafts Bazaar Walk", "category": "Culture & Shopping", "price": 0.0, "duration": 2, "best_season": "All Year"},
        ]
    elif "hill" in cat_norm or "mountain" in cat_norm:
        return [
            {"id": "ACT_GEN_M1", "name": "Scenic Mountain Valley Trekking Trail", "category": "Trekking & Nature", "price": 400.0, "duration": 4, "best_season": "Mar-Jun, Sep-Nov"},
            {"id": "ACT_GEN_M2", "name": "Panoramic Viewpoint Sunrise Excursion", "category": "Sightseeing", "price": 250.0, "duration": 2, "best_season": "All Year"},
            {"id": "ACT_GEN_M3", "name": "Local Tea & Spice Plantation Walk", "category": "Agri-Tourism", "price": 200.0, "duration": 2, "best_season": "All Year"},
        ]
    else:
        return [
            {"id": "ACT_GEN_1", "name": f"Highlights & Landmarks Sightseeing Tour in {dest_name or 'City'}", "category": "Sightseeing", "price": 350.0, "duration": 3, "best_season": "Oct-Mar"},
            {"id": "ACT_GEN_2", "name": "Local Culinary & Food Tasting Walk", "category": "Culinary & Culture", "price": 500.0, "duration": 2, "best_season": "All Year"},
            {"id": "ACT_GEN_3", "name": "Evening Sunset Viewpoint Stroll", "category": "Leisure & Nature", "price": 0.0, "duration": 1, "best_season": "All Year"},
        ]


_restaurants_by_dest = None


def _get_dest_restaurants(csv_dest_id):
    global _restaurants_by_dest
    if _restaurants_by_dest is None:
        import csv
        from pathlib import Path
        cache = {}
        possible_paths = [
            Path(__file__).resolve().parents[3] / "datasets" / "restaurants.csv",
            Path(os.getcwd()) / "datasets" / "restaurants.csv",
            Path(os.getcwd()).parent / "datasets" / "restaurants.csv",
        ]
        csv_path = None
        for p in possible_paths:
            if p.exists() and p.is_file():
                csv_path = p
                break

        if csv_path:
            try:
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        did = (r.get("destination_id") or "").strip().upper()
                        if not did:
                            continue
                        rst_id = (r.get("restaurant_id") or "").strip()
                        rating_raw = (r.get("rating") or "").replace(",", "").strip()
                        rating = float(rating_raw) if rating_raw.replace(".", "", 1).isdigit() and 1.0 <= float(rating_raw) <= 5.0 else None
                        lat_str = (r.get("latitude") or "").strip()
                        lon_str = (r.get("longitude") or "").strip()
                        lat_val = float(lat_str) if lat_str and lat_str.replace("-", "", 1).replace(".", "", 1).isdigit() else None
                        lon_val = float(lon_str) if lon_str and lon_str.replace("-", "", 1).replace(".", "", 1).isdigit() else None

                        entry = {
                            "id": rst_id,
                            "name": r.get("restaurant_name", ""),
                            "city": r.get("city", ""),
                            "cuisine": r.get("cuisine", ""),
                            "price_range": r.get("price_range", ""),
                            "rating": rating,
                            "address": r.get("address", ""),
                            "lat": lat_val,
                            "lon": lon_val,
                        }
                        cache.setdefault(did, []).append(entry)
                for did in cache:
                    cache[did].sort(key=lambda x: (x.get("rating") is not None, x.get("rating") or 0), reverse=True)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error("Failed to load restaurants: %s", exc, exc_info=True)
        _restaurants_by_dest = cache

    if not csv_dest_id:
        return []
    return _restaurants_by_dest.get(csv_dest_id.strip().upper(), [])


# --------------------------
# GET ONE DESTINATION WITH WEATHER, ATTRACTIONS, ACTIVITIES & RESTAURANTS
# --------------------------
@router.get("/{dest_id}", response_model=DestinationOut)
def get_destination(dest_id: int, db: Session = Depends(get_db)):
    d = db.query(Destination).filter(Destination.id == dest_id).first()

    if not d:
        raise HTTPException(status_code=404, detail="Destination not found")

    # Step 2: Ensure coordinates exist; resolve via geocoding fallback and persist to DB if missing
    lat = d.lat
    lon = d.lon
    if lat is None or lon is None:
        coords = guess_coordinates(d.name)
        if coords:
            lat, lon = coords
            try:
                d.lat = lat
                d.lon = lon
                db.commit()
            except Exception:
                db.rollback()

    csv_id = getattr(d, "csv_destination_id", None)
    thumbnail = d.thumbnail_url
    if not thumbnail:
        thumbnail = resolve_destination_image(d.id, csv_id)

    # Step 7: Standardize attractions retrieval across all destinations
    attractions = _get_dest_attractions(
        csv_dest_id=csv_id,
        dest_name=d.name,
        city=getattr(d, "city", None),
        state=getattr(d, "state", None),
    )

    # Step 8: Standardize activities retrieval for every destination
    activities = _get_dest_activities(
        csv_dest_id=csv_id,
        dest_name=d.name,
        category=getattr(d, "category", None),
    )

    restaurants = _get_dest_restaurants(csv_id)

    # Step 3: Enhance destination overview / description
    enhanced_desc = get_enhanced_description(d)

    obj = {
        "id": d.id,
        "name": d.name,
        "country": d.country,
        "description": enhanced_desc,
        "lat": lat,
        "lon": lon,
        "tags": d.tags,
        "thumbnail_url": thumbnail,
        "avg_rating": d.avg_rating,
        "state": getattr(d, "state", None),
        "city": getattr(d, "city", None),
        "category": getattr(d, "category", None),
        "average_budget": getattr(d, "average_budget", None),
        "best_season": getattr(d, "best_season", None),
        "ideal_duration": getattr(d, "ideal_duration", None),
        "attractions": attractions,
        "activities": activities,
        "restaurants": restaurants,
    }

    if lat and lon:
        obj["weather"] = cached_weather(lat, lon)
    else:
        obj["weather"] = None

    return obj


OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")


def fetch_latlon(city: str):
    try:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_KEY}"
        res = requests.get(url).json()
        if res and len(res) > 0:
            return res[0]["lat"], res[0]["lon"]
    except Exception:
        return None, None
    return None, None


@router.get("/packing")
def generate_packing_list_legacy(
    days: int = Query(..., ge=1),
    activities: str = "",
    weather: str = ""
):
    from .packing_routes import BASE_PACK, generate_by_weather, generate_by_activities
    acts = [a.strip() for a in activities.split(",") if a.strip()]
    items = BASE_PACK.copy() + generate_by_weather(weather) + generate_by_activities(acts)
    seen = set()
    final = [x for x in items if not (x in seen or seen.add(x))]
    return {"list": final}
