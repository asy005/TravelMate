# app/services/geo_lookup.py

def guess_coordinates(name: str):
    """
    Returns (lat, lon) for known destination names.
    Falls back to Tokyo if no match.
    """

    mapping = {
        "hiroshima": (34.3853, 132.4553),
        "japan": (35.6762, 139.6503),
        "tokyo": (35.6895, 139.6917),
        "kyoto": (35.0116, 135.7681),

        "paris": (48.8566, 2.3522),
        "france": (46.2276, 2.2137),

        "goa": (15.2993, 74.1240),
        "india": (20.5937, 78.9629),
        "kerala": (10.8505, 76.2711),
        "wayanad": (11.6854, 76.1320),

        "dubai": (25.276987, 55.296249),
        "uae": (23.4241, 53.8478),

        "germany": (52.5200, 13.4050),
        "berlin": (52.5200, 13.4050),

        "bali": (8.3405, 115.0920),
        "maldives": (3.2028, 73.2207),
    }

    name_low = name.lower()
    for key, coords in mapping.items():
        if key in name_low:
            return coords

    # Default fallback → Tokyo (global safe default)
    return (35.6895, 139.6917)


def get_nearby_attractions(lat: float, lon: float, max_results: int = 6):
    """
    Shared OpenTripMap lookup used by both the hotel details page and the
    AI-generated plan/dashboard, so this logic lives in exactly one place.
    """
    import os
    import requests

    api_key = os.getenv("OPENTRIPMAP_API_KEY")
    if not api_key or not lat or not lon:
        return []

    try:
        url = "https://api.opentripmap.com/0.1/en/places/radius"
        params = {
            "radius": 5000, "lon": lon, "lat": lat,
            "kinds": "interesting_places", "format": "json",
            "apikey": api_key, "limit": max_results,
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        return [
            {"name": p.get("name"), "distance_m": p.get("dist")}
            for p in data if p.get("name")
        ][:max_results]
    except requests.exceptions.RequestException:
        return []
