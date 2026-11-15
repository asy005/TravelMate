# app/routes/packing_routes.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/packing", tags=["packing"])

class PackingRequest(BaseModel):
    destination: str
    weather: Optional[str] = None  # "cold", "hot", "rain", "moderate"
    days: int = 3
    activities: List[str] = []  # optional: ["hiking", "swimming", "temple"]

# High-utility base travel essentials (generic personal garments like underwear omitted)
BASE_PACK = [
    "Government ID / Passport & Travel Tickets",
    "Smartphone & Multi-Port Fast Charger",
    "High-Capacity Power Bank",
    "Personal Toiletries Kit",
    "First Aid Essentials & Personal Medications",
]

def generate_by_weather(weather: Optional[str]):
    w = (weather or "").lower()
    items = []
    if any(k in w for k in ["cold", "snow", "chill", "freeze", "frost"]):
        items += [
            "Insulated Warm Jacket",
            "Thermal Base Layers",
            "Fleece Beanie & Neck Warmer",
            "Insulated Gloves",
            "Warm Woolen Socks",
        ]
    if any(k in w for k in ["hot", "sun", "humid", "warm", "summer"]):
        items += [
            "Breathable Cotton / Linen Tops",
            "Broad-Spectrum Sunscreen (SPF 50+)",
            "UV Polarized Sunglasses",
            "Wide-Brim Sun Hat",
            "Electrolyte Hydration Packets",
        ]
    if any(k in w for k in ["rain", "wet", "shower", "storm", "drizzle", "monsoon"]):
        items += [
            "Waterproof Rain Jacket",
            "Compact Travel Umbrella",
            "Waterproof Dry Bag / Electronics Pouch",
            "Quick-Dry Clothing",
        ]
    if any(k in w for k in ["moderate", "pleasant"]) or not w:
        items += [
            "Light Layering Jacket or Cardigan",
            "Comfortable All-Day Walking Shoes",
        ]
    return items

def generate_by_activities(acts: List[str]):
    items = []
    if not acts:
        return items
    acts_low = [a.lower() for a in acts]
    if any("hik" in a or "trek" in a for a in acts_low):
        items += [
            "Sturdy Hiking Shoes / Trail Footwear",
            "Ergonomic Lightweight Daypack",
            "Reusable Insulated Water Bottle",
            "Blister Protection Bandages",
        ]
    if any(k in a for a in acts_low for k in ["swim", "beach", "water", "scuba", "snorkel", "kayak"]):
        items += [
            "UV Swimwear",
            "Quick-Dry Beach Towel",
            "Waterproof Phone Pouch",
            "Reef-Safe Sunscreen",
        ]
    if any(k in a for a in acts_low for k in ["formal", "dinner", "party", "club", "fine dining"]):
        items += ["Evening / Formal Outfit", "Dress Shoes"]
    if any(k in a for a in acts_low for k in ["temple", "spiritual", "heritage", "culture", "monument"]):
        items += [
            "Modest Shoulder & Knee-Covering Apparel",
            "Slip-On Walking Shoes (Convenient for Temple Entry)",
        ]
    if any(k in a for a in acts_low for k in ["camp", "wildlife", "safari", "nature", "bird"]):
        items += [
            "Insect / Mosquito Repellent Spray",
            "Compact LED Flashlight / Headlamp",
            "Compact Travel Binoculars",
        ]
    return items

@router.post("/generate")
def generate_packing(req: PackingRequest):
    days = max(1, min(30, int(req.days or 3)))
    items = BASE_PACK.copy()

    # Weather-specific items
    items += generate_by_weather(req.weather)

    # Activity-specific gear
    items += generate_by_activities(req.activities)

    # Duration-based clothing estimate
    clothing_count = min(7, max(1, days))
    items += [
        f"{clothing_count}x Everyday Tops / Shirts",
        f"{min(4, clothing_count)}x Travel Bottoms / Pants",
    ]

    # Deduplicate while strictly preserving order
    seen = set()
    final = []
    for it in items:
        if it not in seen:
            seen.add(it)
            final.append(it)

    return {"destination": req.destination, "days": days, "packing_list": final}
