# app/schemas/mood_schema.py
from pydantic import BaseModel
from typing import List

class MoodIn(BaseModel):
    text: str

class MoodOut(BaseModel):
    mood: str
    tags: List[str] = []
