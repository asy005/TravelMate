from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from app.services.route_optimizer import optimize_day_route
from app.services.route_service import get_osrm_multi_stop_route

router = APIRouter(prefix="/routes", tags=["routes"])

# Input model
class RouteRequest(BaseModel):
    points: list  # [{name, lat, lon, ...}]
    return_to_start: Optional[bool] = False
    destination_name: Optional[str] = None

# Output model
class RouteResponse(BaseModel):
    summary: str
    ordered_points: list
    total_distance_km: Optional[float] = None
    road_distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    distance_as_proxy: Optional[bool] = True
    algorithm: Optional[str] = None
    legs: Optional[List[Dict[str, Any]]] = None
    route_geometry: Optional[List[List[float]]] = None
    routing_service: Optional[str] = None

@router.post("/", response_model=RouteResponse)
def optimize_route(data: RouteRequest):
    """
    Route optimizer using Haversine distance heuristic (Nearest-Neighbor + 2-opt)
    and OpenStreetMap/OSRM road-following geometry when valid coordinates are available.
    """
    points = data.points

    if not points or len(points) == 0:
        raise HTTPException(status_code=400, detail="No points received")

    result = optimize_day_route(
        stops=points,
        return_to_start=data.return_to_start or False,
        destination_name=data.destination_name,
    )

    ordered = result["ordered_stops"]
    total_km = result["total_distance_km"]

    # Attempt to retrieve real road-following geometry via OpenStreetMap OSRM
    valid_coords = [
        (s["lat"], s["lon"])
        for s in ordered
        if s.get("lat") is not None and s.get("lon") is not None
    ]

    osrm_data = None
    if len(valid_coords) >= 2:
        osrm_data = get_osrm_multi_stop_route(valid_coords)

    if osrm_data:
        road_km = osrm_data["distance_km"]
        dur_min = osrm_data["duration_min"]
        route_geom = osrm_data["geometry"]
        svc_name = osrm_data["source"]
        summary = (
            f"Route optimized for {len(ordered)} stop(s): {road_km} km driving distance along real roads "
            f"(approx. {dur_min} mins via OpenStreetMap)."
        )
        dist_as_proxy = False
    elif total_km is not None and total_km > 0:
        road_km = None
        dur_min = None
        route_geom = None
        svc_name = None
        summary = (
            f"Route optimized for {len(ordered)} stop(s): approx. {total_km} km straight-line distance "
            "(heuristic proxy; live road routing service offline)."
        )
        dist_as_proxy = True
    else:
        road_km = None
        dur_min = None
        route_geom = None
        svc_name = None
        summary = (
            f"Route sequenced for {len(ordered)} stop(s). Coordinates unavailable for full road calculation."
        )
        dist_as_proxy = True

    return {
        "summary": summary,
        "ordered_points": ordered,
        "total_distance_km": total_km,
        "road_distance_km": road_km,
        "duration_min": dur_min,
        "distance_as_proxy": dist_as_proxy,
        "algorithm": result["algorithm"],
        "legs": result.get("legs", []),
        "route_geometry": route_geom,
        "routing_service": svc_name,
    }
