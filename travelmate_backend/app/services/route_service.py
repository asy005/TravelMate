import requests
from math import radians, sin, cos, sqrt, atan2

OSRM_URL = "http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false&alternatives=false&annotations=duration,distance"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def get_route_osrm(source_lat, source_lon, dest_lat, dest_lon):
    url = OSRM_URL.format(lat1=source_lat, lon1=source_lon, lat2=dest_lat, lon2=dest_lon,
                          lon1_param=source_lon, lat1_param=source_lat, lon2_param=dest_lon, lat2_param=dest_lat)
    url = OSRM_URL.format(lon1=source_lon, lat1=source_lat, lon2=dest_lon, lat2=dest_lat)
    try:
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        j = r.json()
        if "routes" in j and len(j["routes"]) > 0:
            route = j["routes"][0]
            distance_m = route.get("distance")  # meters
            duration_s = route.get("duration")  # seconds
            return {
                "distance_km": round(distance_m/1000, 2),
                "eta_hours": round((duration_s/3600), 2),
                "raw": route
            }
    except Exception as e:
        print(f"[OSRM] error: {e}")
    d_km = round(haversine(source_lat, source_lon, dest_lat, dest_lon), 2)
    eta_hours = round(d_km / 50.0, 2)
    return {"distance_km": d_km, "eta_hours": eta_hours, "raw": None, "notes": "OSRM fallback used"}


def get_osrm_multi_stop_route(coords, timeout=6):
    if not coords or len(coords) < 2:
        return None

    pairs = []
    for pt in coords:
        if isinstance(pt, dict):
            lat, lon = pt.get("lat"), pt.get("lon")
        elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
            lat, lon = pt[0], pt[1]
        else:
            lat, lon = None, None
        if lat is not None and lon is not None:
            pairs.append((float(lat), float(lon)))

    if len(pairs) < 2:
        return None

    loc_str = ";".join(f"{lon},{lat}" for lat, lon in pairs)
    url = f"https://router.project-osrm.org/route/v1/driving/{loc_str}?overview=full&geometries=geojson"

    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        j = r.json()
        if j.get("code") == "Ok" and j.get("routes"):
            route = j["routes"][0]
            distance_m = route.get("distance", 0.0)
            duration_s = route.get("duration", 0.0)
            geojson_coords = route.get("geometry", {}).get("coordinates", [])
            leaflet_coords = [[pt[1], pt[0]] for pt in geojson_coords if len(pt) >= 2]
            return {
                "distance_km": round(distance_m / 1000.0, 2),
                "duration_min": round(duration_s / 60.0, 1),
                "geometry": leaflet_coords,
                "source": "OSRM OpenStreetMap Driving Router",
            }
    except Exception as exc:
        print(f"[OSRM] Multi-stop road routing notice: {exc}")

    return None
