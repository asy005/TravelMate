# app/routes/nearby_routes.py
from fastapi import APIRouter, Query, HTTPException, status
import os
import requests

router = APIRouter(prefix="/nearby", tags=["nearby"])
OPENTRIP_KEY = os.getenv("OPENTRIPMAP_API_KEY")

@router.get("/")
def nearby(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = 10000,
    kinds: str = "interesting_places",
):
    api_key = os.getenv("OPENTRIPMAP_API_KEY") or OPENTRIP_KEY
    if not api_key:
        return {"error": "OPENTRIPMAP_API_KEY not set"}

    url = "https://api.opentripmap.com/0.1/en/places/radius"
    params = {
        "radius": radius,
        "lon": lon,
        "lat": lat,
        "kinds": kinds,
        "format": "json",
        "apikey": api_key,
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            return {"error": f"{r.status_code} {r.text}"}
        return r.json()
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="OpenTripMap service timed out. Please try again later.",
        )
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to OpenTripMap service. Please verify network connectivity.",
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenTripMap upstream service error: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Invalid response received from OpenTripMap: {str(e)}",
        )
