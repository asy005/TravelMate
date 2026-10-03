from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.destination import Destination
from ..schemas.destination import DestinationOut
from ..services.weather_service import cached_weather
from fastapi import Query

router = APIRouter(prefix="/destinations", tags=["destinations"])


# --------------------------
# GET ALL DESTINATIONS WITH WEATHER
# --------------------------
@router.get("/", response_model=List[DestinationOut])
def list_destinations(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    destinations = db.query(Destination).offset(skip).limit(limit).all()

    enriched = []
    for d in destinations:
        obj = {
            "id": d.id,
            "name": d.name,
            "country": d.country,
            "description": d.description,
            "lat": d.lat,
            "lon": d.lon,
            "tags": d.tags,
            "thumbnail_url": d.thumbnail_url,
            "avg_rating": d.avg_rating,
        }

        if d.lat and d.lon:
            obj["weather"] = cached_weather(d.lat, d.lon)
        else:
            obj["weather"] = None

        enriched.append(obj)

    return enriched


# --------------------------
# GET ONE DESTINATION WITH WEATHER
# --------------------------
@router.get("/{dest_id}", response_model=DestinationOut)
def get_destination(dest_id: int, db: Session = Depends(get_db)):
    d = db.query(Destination).filter(Destination.id == dest_id).first()

    if not d:
        raise HTTPException(status_code=404, detail="Destination not found")

    obj = {
        "id": d.id,
        "name": d.name,
        "country": d.country,
        "description": d.description,
        "lat": d.lat,
        "lon": d.lon,
        "tags": d.tags,
        "thumbnail_url": d.thumbnail_url,
        "avg_rating": d.avg_rating,
    }

    if d.lat and d.lon:
        obj["weather"] = cached_weather(d.lat, d.lon)
    else:
        obj["weather"] = None

    return obj
import requests
import os

OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")

def fetch_latlon(city: str):
    try:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_KEY}"
        res = requests.get(url).json()
        if res and len(res) > 0:
            return res[0]["lat"], res[0]["lon"]
    except:
        return None, None
    return None, None


@router.get("/packing")
def generate_packing_list(
    days: int = Query(..., ge=1),
    activities: str = "",
    weather: str = ""
):
    base_items = ["Passport", "Travel tickets", "Phone charger", "Sunscreen"]

    activity_items = {
        "hiking": ["Hiking shoes", "Backpack"],
        "swim": ["Swimsuit", "Towel"],
        "dinner": ["Formal wear", "Shoes"]
    }

    weather_items = {
        "hot": ["Sunglasses", "Hat"],
        "cold": ["Jacket", "Gloves"],
        "rain": ["Umbrella", "Raincoat"]
    }

    packing = base_items.copy()

    # Add based on weather
    for key, items in weather_items.items():
        if key in weather.lower():
            packing.extend(items)

    # Add based on activities
    for key, items in activity_items.items():
        if key in activities.lower():
            packing.extend(items)

    # Add generic per-day items
    packing.extend(["Outfit", "Toiletries"] * days)

    return {"list": packing}
