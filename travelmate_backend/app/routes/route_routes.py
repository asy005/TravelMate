from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/routes", tags=["routes"])

# Input model
class RouteRequest(BaseModel):
    points: list  # [{name, lat, lon}]

# Output model
class RouteResponse(BaseModel):
    summary: str
    ordered_points: list

@router.post("/")
def optimize_route(data: RouteRequest):
    """
    Very simple route optimizer (placeholder).
    You can replace with real TSP later.
    """

    points = data.points

    if not points or len(points) == 0:
        raise HTTPException(status_code=400, detail="No points received")

    # For now, just return same order
    ordered = points

    summary = f"Route created for {len(points)} stops."

    return {
        "summary": summary,
        "ordered_points": ordered
    }
