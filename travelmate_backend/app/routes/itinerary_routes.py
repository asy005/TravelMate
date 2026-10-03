# app/routes/itinerary_routes.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict
from app.services.rag_engine import query_knowledge_base, ensure_initialized

router = APIRouter(prefix="/plan", tags=["plan"])
ensure_initialized()

class PlanRequest(BaseModel):
    destination: str
    days: int = 3
    preferences: Optional[List[str]] = []  # e.g., ["relax","culture","food"]

def simple_activity_from_snippets(rag_result, limit=6):
    snippets = rag_result.get("snippets", [])
    activities = []
    for s in snippets:
        text = s.get("text") if isinstance(s, dict) else getattr(s, "page_content", "")
        if not text:
            continue
        # pick lines that look like places
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for ln in lines:
            if len(activities) >= limit:
                break
            if len(ln) > 20 and len(ln) < 120:
                activities.append(ln)
        if len(activities) >= limit:
            break
    return activities

@router.post("/generate")
def generate_plan(req: PlanRequest):
    days = max(1, min(14, req.days))
    rag = query_knowledge_base(req.destination)
    activities = simple_activity_from_snippets(rag, limit=days*2)

    # fallback activities
    if not activities:
        activities = [
            f"Explore local markets in {req.destination}",
            f"Visit top landmarks in {req.destination}",
            "Try local cuisine and cafes",
            "Relax at a scenic spot",
            "Light hiking or walking tour",
            "Souvenir shopping and rest"
        ]

    # build daywise plan
    plan = {}
    per_day = max(1, len(activities)//days)
    idx = 0
    for d in range(1, days+1):
        day_items = []
        for _ in range(per_day):
            if idx >= len(activities):
                break
            day_items.append(activities[idx])
            idx += 1
        # ensure at least one item
        if not day_items and idx < len(activities):
            day_items.append(activities[idx]); idx += 1
        if not day_items:
            day_items = ["Free time / relax"]
        plan[f"day_{d}"] = day_items

    return {
        "destination": req.destination,
        "days": days,
        "plan": plan,
        "notes": "Automatically generated. Edit for personalization."
    }
