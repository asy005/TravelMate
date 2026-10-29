from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from app.services.route_optimizer import optimize_day_route

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
    distance_as_proxy: Optional[bool] = True
    algorithm: Optional[str] = None
    legs: Optional[List[Dict[str, Any]]] = None

@router.post("/", response_model=RouteResponse)
def optimize_route(data: RouteRequest):
    """
    Route optimizer using Haversine distance heuristic (Nearest-Neighbor + 2-opt).
    Maintains backward compatibility with RouteOptimizerBox frontend component.
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

    summary = (
        f"Route optimized for {len(ordered)} stop(s): approx. {total_km} km total distance "
        "(via Nearest-Neighbor + 2-opt heuristic; distance used as proxy)."
    )

    return {
        "summary": summary,
        "ordered_points": ordered,
        "total_distance_km": total_km,
        "distance_as_proxy": True,
        "algorithm": result["algorithm"],
        "legs": result.get("legs", []),
    }
