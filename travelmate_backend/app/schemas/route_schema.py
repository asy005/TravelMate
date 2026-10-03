# app/schemas/route_schema.py
from pydantic import BaseModel

class RouteIn(BaseModel):
    source_lat: float
    source_lon: float
    dest_lat: float
    dest_lon: float

class RouteOut(BaseModel):
    distance_km: float
    eta_hours: float
    notes: str
