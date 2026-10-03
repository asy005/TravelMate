from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import os, re, requests

from app.services.rag_engine import query_knowledge_base, ensure_initialized
from app.services.weather_service import cached_weather
from app.database import get_db
from app.models.destination import Destination

router = APIRouter(prefix="/recommend", tags=["recommend"])
ensure_initialized()

OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")


def fetch_latlon(city: str):
    """Auto-fetch city coordinates for weather."""
    if not OPENWEATHER_KEY:
        return None, None
    try:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_KEY}"
        res = requests.get(url).json()
        if isinstance(res, list) and res:
            return res[0]["lat"], res[0]["lon"]
    except:
        pass
    return None, None


def dedupe(destinations):
    seen = set()
    final = []
    for d in destinations:
        key = (d["name"].lower(), d["country"].lower() if d["country"] else "")
        if key not in seen:
            seen.add(key)
            final.append(d)
    return final


# -----------------------
# Extractors from context
# -----------------------
def extract_mood(context: str):
    mood_keywords = ["Relaxing", "Adventure", "Romantic", "Cultural", "Spiritual"]
    for word in mood_keywords:
        if re.search(rf"\b{word}\b", context, re.IGNORECASE):
            return word
    return "Relaxing"

def extract_budget(context: str):
    budget_keywords = ["Low", "Medium", "Luxury", "Affordable", "Expensive"]
    for word in budget_keywords:
        if re.search(rf"\b{word}\b", context, re.IGNORECASE):
            if word.lower() == "affordable":
                return "Low"
            elif word.lower() == "expensive":
                return "Luxury"
            return word
    return "Medium"

def extract_best_time(context: str):
    matches = re.findall(r"(January|February|March|April|May|June|July|August|September|October|November|December)", context, re.IGNORECASE)
    months = list(dict.fromkeys(matches))  # Remove duplicates but keep order
    if months:
        return " to ".join([months[0], months[-1]])
    return "October to March"


@router.get("/")
def recommend(query: str, db: Session = Depends(get_db)):
    print("🔍 Received user query:", query)
    rag = query_knowledge_base(query)
    print("📚 RAG raw output:", rag)

    if "error" in rag:
        fb = rag["fallback"]
        print("⚠️ Using fallback due to RAG error")
        return {
            "destination": fb["destination"],
            "mood": fb["mood"],
            "budget": fb["budget"],
            "best_time": fb["best_time"],
            "description": fb["description"],
            "type": fb["type"],
            "destinations": [],
        }

    fb = rag["fallback"]
    context = rag.get("context", "")
    print("📄 Extracting fields from context snippet...")

    destination = fb["destination"]
    mood = extract_mood(context)
    budget = extract_budget(context)
    best_time = extract_best_time(context)
    description = fb["description"]
    dtype = fb["type"]

    print("✅ Extracted:", {
        "destination": destination,
        "mood": mood,
        "budget": budget,
        "best_time": best_time
    })

    results = db.query(Destination).filter(Destination.name.ilike(f"%{destination}%")).all()
    enriched = []

    for d in results:
        lat, lon = d.lat, d.lon
        if not lat or not lon:
            lat, lon = fetch_latlon(d.name)

        enriched.append({
            "id": d.id,
            "name": d.name,
            "country": d.country or "Unknown",
            "type": dtype,
            "description": d.description,
            "lat": lat,
            "lon": lon,
            "thumbnail_url": d.thumbnail_url or "",
            "mood": mood,
            "budget": budget,
            "best_time": best_time,
            "weather": cached_weather(lat, lon) if lat and lon else None,
        })

    if not enriched:
        print("⚠️ No DB result. Generating virtual recommendation...")
        lat, lon = fetch_latlon(destination)
        enriched.append({
            "id": 0,
            "name": destination,
            "country": "Unknown",
            "type": dtype,
            "description": description,
            "lat": lat,
            "lon": lon,
            "thumbnail_url": "",
            "mood": mood,
            "budget": budget,
            "best_time": best_time,
            "weather": cached_weather(lat, lon) if lat and lon else None,
        })

    enriched = dedupe(enriched)
    print(f"✅ Final deduplicated destinations: {len(enriched)}")

    return {
        "destination": destination,
        "mood": mood,
        "budget": budget,
        "best_time": best_time,
        "description": description,
        "type": dtype,
        "destinations": enriched,
    }
