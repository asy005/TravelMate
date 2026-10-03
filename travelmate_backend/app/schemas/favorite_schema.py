# app/schemas/favorite_schema.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FavoriteCreate(BaseModel):
    destination_id: str
    destination_name: Optional[str] = None
    destination_payload: Optional[str] = None

class FavoriteOut(BaseModel):
    id: int
    user_id: int
    destination_id: str
    destination_name: Optional[str]
    destination_payload: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True

