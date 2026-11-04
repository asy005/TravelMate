from pydantic import BaseModel
from typing import Optional, List, Any, Dict

class DestinationOut(BaseModel):
    id: int
    name: str
    country: Optional[str] = None
    description: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    tags: Optional[str] = None
    thumbnail_url: Optional[str] = None
    avg_rating: Optional[float] = None
    state: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    average_budget: Optional[float] = None
    best_season: Optional[str] = None
    ideal_duration: Optional[int] = None
    weather: Optional[Any] = None
    attractions: Optional[List[Dict[str, Any]]] = None
    activities: Optional[List[Dict[str, Any]]] = None
    restaurants: Optional[List[Dict[str, Any]]] = None

    class Config:
        orm_mode = True
        from_attributes = True
