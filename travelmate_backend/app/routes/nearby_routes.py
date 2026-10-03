# app/routes/nearby_routes.py
from fastapi import APIRouter, Query
import os, requests

router = APIRouter(prefix="/nearby", tags=["nearby"])
OPENTRIP_KEY = os.getenv("OPENTRIPMAP_API_KEY")

@router.get("/")
def nearby(lat: float = Query(...), lon: float = Query(...), radius:int = 10000, kinds:str = "interesting_places"):
    if not OPENTRIP_KEY:
        return {"error": "OPENTRIPMAP_API_KEY not set"}
    url = "https://api.opentripmap.com/0.1/en/places/radius"
    params = {"radius": radius, "lon": lon, "lat": lat, "kinds": kinds, "format":"json", "apikey": OPENTRIP_KEY}
    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        return {"error": f"{r.status_code} {r.text}"}
    return r.json()
