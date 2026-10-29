import os
import re
import requests
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.destination import Destination
from app.services.rag_engine import (
    query_knowledge_base,
    ensure_initialized,
)
from app.services.weather_service import cached_weather
from app.services.ml_engine import ml_engine

router = APIRouter(prefix="/recommend", tags=["recommend"])
ensure_initialized()

OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")

class MLRecommendationRequest(BaseModel):
    age: int = Field(..., ge=1, le=120)
    travel_style: str = Field(..., min_length=1)
    budget: Literal["Low", "Medium", "High"]
    preferred_category: str = Field(..., min_length=1)
    preferred_season: str = Field(..., min_length=1)
    top_k: int = Field(default=10, ge=1, le=20)

def fetch_latlon(city: str):
    if not OPENWEATHER_KEY:
        return None, None

    try:
        url = (
            "https://api.openweathermap.org/geo/1.0/direct"
            f"?q={city}&limit=1&appid={OPENWEATHER_KEY}"
        )

        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and data:
            return data[0]["lat"], data[0]["lon"]

    except requests.RequestException:
        pass
    except (ValueError, KeyError, TypeError):
        pass

    return None, None

def dedupe(destinations):
    seen = set()
    final = []

    for destination in destinations:
        dest_name = (destination.get("name") or "").strip()
        if not dest_name:
            continue
        key = (
            dest_name.lower(),
            (destination.get("country") or "").lower(),
        )

        if key not in seen:
            seen.add(key)
            final.append(destination)

    return final

def extract_mood(context: str):
    mood_keywords = [
        "Relaxing",
        "Adventure",
        "Romantic",
        "Cultural",
        "Spiritual",
    ]

    for word in mood_keywords:
        if re.search(rf"\b{word}\b", context, re.IGNORECASE):
            return word

    return "Relaxing"

def extract_budget(context: str):
    budget_keywords = [
        "Low",
        "Medium",
        "Luxury",
        "Affordable",
        "Expensive",
    ]

    for word in budget_keywords:
        if re.search(rf"\b{word}\b", context, re.IGNORECASE):
            if word.lower() == "affordable":
                return "Low"
            if word.lower() == "expensive":
                return "Luxury"

            return word

    return "Medium"

def extract_best_time(context: str):
    matches = re.findall(
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\b",
        context,
        re.IGNORECASE,
    )

    months = list(dict.fromkeys(month.title() for month in matches))

    if months:
        return " to ".join([months[0], months[-1]])

    return "October to March"

@router.post("/ml")
def recommend_ml(request: MLRecommendationRequest):
    profile = request.model_dump(exclude={"top_k"})

    try:
        recommendations = ml_engine.recommend_profile(
            user_profile=profile,
            top_k=request.top_k,
            category_filter=request.preferred_category,
        )

        return {
            "method": "machine_learning",
            "count": len(recommendations),
            "recommendations": recommendations,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="The recommendation model or dataset is unavailable.",
        ) from exc

    except Exception as exc:
        print(f"ML recommendation error: {exc}")

        raise HTTPException(
            status_code=500,
            detail="Unable to generate ML recommendations.",
        ) from exc

@router.get("/")
def recommend(query: str, db: Session = Depends(get_db)):
    print("Received user query:", query)

    rag = query_knowledge_base(query)

    if "error" in rag:
        fb = rag["fallback"]

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

    destination = fb.get("destination") or rag.get("best_destination")
    mood = extract_mood(context)
    budget = extract_budget(context)
    best_time = extract_best_time(context)
    description = fb["description"]
    destination_type = fb["type"]

    if destination:
        results = (
            db.query(Destination)
            .filter(Destination.name.ilike(f"%{destination}%"))
            .all()
        )
    else:
        results = (
            db.query(Destination)
            .filter(Destination.category.ilike(f"%{destination_type}%"))
            .limit(5)
            .all()
        )
        if not results:
            results = db.query(Destination).limit(3).all()
        if results:
            destination = results[0].name

    enriched = []

    for item in results:
        lat, lon = item.lat, item.lon

        if lat is None or lon is None:
            lat, lon = fetch_latlon(item.name)

        enriched.append({
            "id": item.id,
            "name": item.name,
            "country": item.country or "Unknown",
            "type": destination_type,
            "description": item.description,
            "lat": lat,
            "lon": lon,
            "thumbnail_url": item.thumbnail_url or "",
            "mood": mood,
            "budget": budget,
            "best_time": best_time,
            "weather": (
                cached_weather(lat, lon)
                if lat is not None and lon is not None
                else None
            ),
        })

    if not enriched:
        dest_fallback = destination or destination_type or "India"
        lat, lon = fetch_latlon(dest_fallback)

        enriched.append({
            "id": 0,
            "name": dest_fallback,
            "country": "India",
            "type": destination_type,
            "description": description,
            "lat": lat,
            "lon": lon,
            "thumbnail_url": "",
            "mood": mood,
            "budget": budget,
            "best_time": best_time,
            "weather": (
                cached_weather(lat, lon)
                if lat is not None and lon is not None
                else None
            ),
        })

    enriched = dedupe(enriched)

    return {
        "destination": destination,
        "mood": mood,
        "budget": budget,
        "best_time": best_time,
        "description": description,
        "type": destination_type,
        "destinations": enriched,
    }