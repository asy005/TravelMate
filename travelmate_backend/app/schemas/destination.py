from pydantic import BaseModel
from typing import Optional

class DestinationOut(BaseModel):
    id: int
    name: str
    country: Optional[str]
    description: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    tags: Optional[str]
    thumbnail_url: Optional[str]
    avg_rating: Optional[float]

    class Config:
        orm_mode = True
