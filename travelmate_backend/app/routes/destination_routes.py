from typing import List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.destination import Destination
from ..schemas.destination import DestinationOut
from ..services.weather_service import cached_weather
from ..utils.image_resolver import resolve_destination_image
import requests
import os

router = APIRouter(prefix="/destinations", tags=["destinations"])


# --------------------------
# GET ALL DESTINATIONS WITH WEATHER, SEARCH & FILTER
# Returns { items: [...], total: N } for pagination support.
# Still emits a bare list for backwards-compat when no pagination params given.
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
        # Use DB thumbnail_url if set; otherwise resolve from dataset images at runtime
        thumbnail = d.thumbnail_url
        if not thumbnail:
            thumbnail = resolve_destination_image(d.id, getattr(d, "csv_destination_id", None))

        obj = {
            "id": d.id,
            "name": d.name,
            "country": d.country,
            "description": d.description,
            "lat": d.lat,
            "lon": d.lon,
            "tags": d.tags,
            "thumbnail_url": thumbnail,
            "avg_rating": d.avg_rating,
            "state": getattr(d, "state", None),
            "category": getattr(d, "category", None),
            "average_budget": getattr(d, "average_budget", None),
            "best_season": getattr(d, "best_season", None),
            "ideal_duration": getattr(d, "ideal_duration", None),
        }

        if d.lat and d.lon:
            obj["weather"] = cached_weather(d.lat, d.lon)
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
# GET ONE DESTINATION WITH WEATHER
# --------------------------
@router.get("/{dest_id}", response_model=DestinationOut)
def get_destination(dest_id: int, db: Session = Depends(get_db)):
    d = db.query(Destination).filter(Destination.id == dest_id).first()

    if not d:
        raise HTTPException(status_code=404, detail="Destination not found")

    # Use DB thumbnail_url if set; otherwise resolve from dataset images at runtime
    thumbnail = d.thumbnail_url
    if not thumbnail:
        thumbnail = resolve_destination_image(d.id, getattr(d, "csv_destination_id", None))

    obj = {
        "id": d.id,
        "name": d.name,
        "country": d.country,
        "description": d.description,
        "lat": d.lat,
        "lon": d.lon,
        "tags": d.tags,
        "thumbnail_url": thumbnail,
        "avg_rating": d.avg_rating, "state": getattr(d, "state", None), "category": getattr(d, "category", None), "average_budget": getattr(d, "average_budget", None),
    }

    if d.lat and d.lon:
        obj["weather"] = cached_weather(d.lat, d.lon)
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
