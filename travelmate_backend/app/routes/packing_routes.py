# app/routes/packing_routes.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/packing", tags=["packing"])

class PackingRequest(BaseModel):
    destination: str
    weather: str = None  # "cold", "hot", "rain", "moderate"
    days: int = 3
    activities: List[str] = []  # optional: ["hiking","swimming"]

# base items always
BASE_PACK = [
    "Passport / ID",
    "Phone charger",
    "Powerbank",
    "Toiletries",
    "Underwear",
]

def generate_by_weather(weather: str):
    w = (weather or "").lower()
    items = []
    if "cold" in w or "snow" in w or "chill" in w:
        items += ["Warm jacket", "Thermal wear", "Beanie", "Gloves"]
    if "hot" in w or "sun" in w or "humid" in w:
        items += ["Light shirts", "Sunscreen", "Hat", "Sunglasses"]
    if "rain" in w or "wet" in w:
        items += ["Rain Jacket", "Travel umbrella", "Waterproof bag"]
    if "moderate" in w or w == "":
        items += ["Light jacket", "Comfortable shoes"]
    return items

def generate_by_activities(acts):
    items = []
    if not acts:
        return items
    acts_low = [a.lower() for a in acts]
    if any("hike" in a or "trek" in a for a in acts_low):
        items += ["Hiking shoes", "Daypack", "Water bottle"]
    if any("swim" in a or "beach" in a for a in acts_low):
        items += ["Swimwear", "Beach towel"]
    if any("formal" in a or "dinner" in a for a in acts_low):
        items += ["Smart outfit", "Dress shoes"]
    return items

@router.post("/generate")
def generate_packing(req: PackingRequest):
    days = max(1, int(req.days))
    items = BASE_PACK.copy()

    # add weather-specific
    items += generate_by_weather(req.weather)

    # add activity items
    items += generate_by_activities(req.activities)

    # days-based clothing estimate
    clothing_count = min(7, max(1, days))
    items += [f"{clothing_count}x Shirts/Tops", f"{clothing_count}x Bottoms"]

    # dedupe preserving order
    seen = set()
    final = []
    for it in items:
        if it not in seen:
            seen.add(it)
            final.append(it)

    return {"destination": req.destination, "days": days, "packing_list": final}
