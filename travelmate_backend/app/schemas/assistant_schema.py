# app/schemas/assistant_schema.py
from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class AssistantMessageIn(BaseModel):
    session_id: Optional[str] = None
    message: str


class AssistantMessageOut(BaseModel):
    session_id: str
    reply: str
    slots: Dict[str, Any]
    missing_slots: List[str]
    ready_for_plan: bool
    plan: Optional[Dict[str, Any]] = None


class AssistantResetIn(BaseModel):
    session_id: str
