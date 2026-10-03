# app/schemas/packing_schema.py
from pydantic import BaseModel
from typing import List

class PackingIn(BaseModel):
    climate: str
    duration_days: int
    activities: List[str] = []

class PackingOut(BaseModel):
    packing_list: List[str]
