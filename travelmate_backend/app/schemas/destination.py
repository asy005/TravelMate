from pydantic import BaseModel
from typing import Optional

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
    category: Optional[str] = None
    average_budget: Optional[float] = None
    best_season: Optional[str] = None
    ideal_duration: Optional[int] = None

    class Config:
        orm_mode = True
