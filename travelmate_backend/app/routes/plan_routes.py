# app/routes/plan_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from ..database import get_db
from ..models.destination import Destination
from ..services.rag_engine import query_knowledge_base, ensure_initialized
from ..services.weather_service import cached_weather
from ..services.route_service import get_route_osrm
from ..services.packing_service import generate_packing
from ..routes.mood_routes import classify_mood as fallback_classify_mood  # if mood_routes exists

router = APIRouter(prefix="/travel", tags=["travel_plan"])

def simple_classify(text: str) -> str:
    # fallback small classifier if mood_routes.classify_mood not present
    try:
        return fallback_classify_mood(text)
    except Exception:
        t = text.lower()
        if any(x in t for x in ["relax","beach","chill","spa"]):
            return "relax"
        if any(x in t for x in ["adventure","trek","hike","explore"]):
            return "adventurous"
        if any(x in t for x in ["romance","couple","honeymoon"]):
            return "romantic"
        if any(x in t for x in ["museum","history","culture"]):
            return "culture"
        return "relax"

@router.post("/plan")
def create_plan(payload: Dict, db: Session = Depends(get_db)):
    """
    payload example:
    {
      "query":"Plan me a 5-day relaxing trip to Goa from Bangalore",
      "source": {"lat": 12.9716, "lon":77.5946},
      "duration_days": 5,
      "max_results": 3
    }
    """
    ensure_initialized()  # ensure RAG is ready (no-op if already initialized)
    query = payload.get("query", "")
    source = payload.get("source", {})
    duration_days = int(payload.get("duration_days", 3))
    max_results = int(payload.get("max_results", 3))

    # 1) mood
    mood = simple_classify(query)

    # 2) RAG context
    rag = query_knowledge_base(query)
    rag_best = rag.get("best_destination") if isinstance(rag, dict) else None

    # 3) DB query: prefer RAG name if present, else mood-based filter on tags
    q = db.query(Destination)
    if rag_best:
        q = q.filter(Destination.name.ilike(f"%{rag_best}%") | Destination.description.ilike(f"%{rag_best}%"))
    else:
        # simple mood->tags preference (tags is a free-text/comma-separated column on Destination)
        if mood == "relax":
            q = q.filter(Destination.tags.ilike("%beach%") | Destination.tags.ilike("%relax%") | (Destination.tags == None))
        elif mood == "adventurous":
            q = q.filter(Destination.tags.ilike("%adventure%") | Destination.tags.ilike("%trek%"))

    results = q.order_by(Destination.avg_rating.desc()).limit(max_results).all()

    # 4) Build response objects (with weather + packing + route)
    destinations_output = []
    for dest in results:
        dest_obj = {
            "id": dest.id,
            "name": dest.name,
            "country": dest.country,
            "description": dest.description,
            "lat": dest.lat,
            "lon": dest.lon,
            "tags": dest.tags,
            "thumbnail_url": dest.thumbnail_url,
            "avg_rating": dest.avg_rating,
        }
        # weather (guard against missing lat/lon so `weather` is always defined)
        weather = None
        if dest.lat and dest.lon:
            weather = cached_weather(dest.lat, dest.lon)
            if weather:
                weather["weather_short"] = weather["description"].title()
        dest_obj["weather"] = weather
        destinations_output.append(dest_obj)

    # 5) packing list (basic heuristics)
    # keep simple: infer a climate hint from the first destination's tags
    first_tags = (destinations_output[0]["tags"] or "").lower() if destinations_output else ""
    if "tropical" in first_tags or "beach" in first_tags:
        climate_hint = "tropical"
    elif "cold" in first_tags or "snow" in first_tags or "mountain" in first_tags:
        climate_hint = "cold"
    else:
        climate_hint = "temperate"

    activities = ["beach"] if mood == "relax" else (["trekking"] if mood == "adventurous" else [])
    packing_list = generate_packing(climate_hint, duration_days, activities)

    # 6) route: compute OSRM route from source to first destination (if available)
    route_info = None
    if source and destinations_output:
        src_lat = source.get("lat"); src_lon = source.get("lon")
        dest_lat = destinations_output[0].get("lat"); dest_lon = destinations_output[0].get("lon")
        if src_lat and src_lon and dest_lat and dest_lon:
            route_info = get_route_osrm(src_lat, src_lon, dest_lat, dest_lon)

    # 7) final output
    return {
        "query": query,
        "mood": mood,
        "rag_best": rag_best,
        "destinations": destinations_output,
        "packing_list": packing_list,
        "route": route_info,
        "rag_snippets_count": len(rag.get("snippets", [])) if isinstance(rag, dict) else 0
    }
