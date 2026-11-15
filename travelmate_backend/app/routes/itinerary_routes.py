# app/routes/itinerary_routes.py
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.destination import Destination
from app.routes.destination_routes import _get_dest_attractions
from app.services.llm_gateway import chat_completion, LLMGatewayError
from app.services.rag_engine import query_knowledge_base, ensure_initialized
from app.services.route_optimizer import optimize_trip_builder_plan, AttractionCoordinateResolver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plan", tags=["plan"])
ensure_initialized()


class PlanRequest(BaseModel):
    destination: str
    days: int = 3
    preferences: Optional[List[str]] = []  # e.g., ["relax","culture","food"]
    destination_id: Optional[Any] = None


def _get_verified_attractions_for_dest(
    dest_name: str,
    dest_id: Optional[Any] = None,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Look up verified attractions for a destination from database and datasets."""
    csv_dest_id = None

    if dest_id:
        clean_id = str(dest_id).strip().upper()
        if clean_id.startswith("D") and len(clean_id) <= 6:
            csv_dest_id = clean_id

    if not csv_dest_id and db is not None and hasattr(db, "query"):
        try:
            dest_record = None
            if dest_id and str(dest_id).isdigit():
                dest_record = db.query(Destination).filter(Destination.id == int(dest_id)).first()
            if not dest_record and dest_name:
                dest_record = db.query(Destination).filter(Destination.name.ilike(f"%{dest_name}%")).first()
            if dest_record and dest_record.csv_destination_id:
                csv_dest_id = dest_record.csv_destination_id
        except Exception as exc:
            logger.warning("[Itinerary] DB lookup failed: %s", exc)

    if not csv_dest_id and dest_name:
        import csv
        from pathlib import Path
        for p in [
            Path(__file__).resolve().parents[3] / "datasets" / "destinations.csv",
            Path("datasets/destinations.csv"),
        ]:
            if p.exists() and p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for row in csv.DictReader(f):
                            dname = (row.get("destination_name") or "").strip().lower()
                            if dname == dest_name.lower() or dest_name.lower() in dname:
                                csv_dest_id = (row.get("destination_id") or "").strip().upper()
                                break
                except Exception:
                    pass
                if csv_dest_id:
                    break

    attractions = _get_dest_attractions(csv_dest_id) if csv_dest_id else []

    if not attractions and dest_name:
        resolver = AttractionCoordinateResolver.get_instance()
        norm_city = dest_name.casefold()
        city_attractions = [
            info for (c, _), info in resolver._by_city_and_name.items()
            if c == norm_city or norm_city in c
        ]
        if city_attractions:
            city_attractions.sort(key=lambda x: x.get("rating", 0.0), reverse=True)
            attractions = city_attractions

    return attractions


def simple_activity_from_snippets(rag_result, limit=6):
    snippets = rag_result.get("snippets", []) if isinstance(rag_result, dict) else []
    activities = []
    for s in snippets:
        text = s.get("text") if isinstance(s, dict) else getattr(s, "page_content", "")
        if not text:
            continue
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for ln in lines:
            if len(activities) >= limit:
                break
            if 20 < len(ln) < 120:
                activities.append(ln)
        if len(activities) >= limit:
            break
    return activities


def _parse_json_plan(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        cleaned = cleaned[first_brace : last_brace + 1]
    return json.loads(cleaned)


def _build_grounded_fallback_plan(
    destination: str,
    days: int,
    attractions: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """Builds a structured Morning, Afternoon, Evening itinerary grounded in verified attractions."""
    plan: Dict[str, List[str]] = {}
    valid_attractions = [a for a in attractions if a.get("name")]
    att_idx = 0
    total_att = len(valid_attractions)

    for d in range(1, days + 1):
        day_acts = []
        # Morning slot
        if total_att > 0:
            m_att = valid_attractions[att_idx % total_att]
            att_idx += 1
            cat = m_att.get("category", "Landmark")
            day_acts.append(
                f"Morning: Visit {m_att['name']} (~2.5 hrs) - explore {cat.lower()} highlights and architecture"
            )
        else:
            day_acts.append(
                f"Morning: Explore historic center of {destination} (~2.5 hrs) - scenic walking tour and local heritage"
            )

        # Afternoon slot
        if total_att > 0:
            a_att = valid_attractions[att_idx % total_att]
            att_idx += 1
            cat = a_att.get("category", "Cultural site")
            day_acts.append(
                f"Afternoon: Explore {a_att['name']} (~2 hrs) - discover local surroundings and authentic regional lunch nearby"
            )
        else:
            day_acts.append(
                f"Afternoon: Visit local markets and craft centers in {destination} (~2 hrs) - sample regional delicacies"
            )

        # Evening slot
        if total_att > 0 and att_idx < total_att:
            e_att = valid_attractions[att_idx % total_att]
            att_idx += 1
            day_acts.append(
                f"Evening: Enjoy {e_att['name']} (~1.5 hrs) - panoramic sunset views and relaxed evening dining"
            )
        else:
            day_acts.append(
                f"Evening: Sunset walk and dinner in {destination} (~1.5 hrs) - experience local night ambiance and regional cuisine"
            )

        plan[f"day_{d}"] = day_acts

    return plan


@router.post("/generate")
def generate_plan(req: PlanRequest, db: Session = Depends(get_db)):
    destination = (req.destination or "").strip()
    if not destination:
        raise HTTPException(status_code=400, detail="Destination name is required.")

    days = max(1, min(14, int(req.days or 3)))
    preferences = req.preferences or []

    # 1. Retrieve verified attractions for destination grounding
    verified_attractions = _get_verified_attractions_for_dest(
        dest_name=destination,
        dest_id=req.destination_id,
        db=db,
    )

    # 2. Query RAG knowledge base for contextual destination details
    rag_context = ""
    try:
        rag = query_knowledge_base(destination, destination_name=destination)
        snippets = rag.get("snippets", [])
        if snippets:
            rag_context = "\n".join(
                s.get("text", "")[:200] for s in snippets[:3] if isinstance(s, dict)
            )
    except Exception as exc:
        logger.warning("[Itinerary] RAG retrieval notice: %s", exc)

    # 3. Format attraction summaries for LLM prompt
    if verified_attractions:
        attraction_lines = [
            f"- {a['name']} ({a.get('category', 'Landmark')}, Rating: {a.get('rating', 4.5)}★, Entry: ₹{a.get('entry_fee', 0)}) in {a.get('city', destination)}"
            for a in verified_attractions[:25]
        ]
        attractions_text = "\n".join(attraction_lines)
    else:
        attractions_text = f"- Key cultural landmarks, historic quarters, viewpoints, and nature parks in {destination}."

    pref_text = f" Travel preferences: {', '.join(preferences)}." if preferences else ""

    system_prompt = (
        "You are an expert travel planner for TravelMate. Generate a realistic, destination-specific "
        f"day-by-day travel itinerary for {days} day(s) in {destination}.{pref_text}\n\n"
        "STRICT GROUNDING RULES:\n"
        "1. Ground all activities strictly in the verified attractions and real landmarks for this destination listed below:\n"
        f"{attractions_text}\n"
        "2. Do NOT mention or invent attractions located in other cities or states.\n"
        f"3. Organize EACH day (named 'day_1', 'day_2', ... 'day_{days}') into exactly 3 structured activity entries:\n"
        "   - Morning: Must include realistic visit duration (~2-3 hrs), attraction name, and a short practical tip.\n"
        "   - Afternoon: Must include realistic visit duration (~2 hrs), a nearby attraction or cultural point, and lunch recommendation.\n"
        "   - Evening: Must include realistic visit duration (~1.5-2 hrs), a scenic sunset point, cultural show, or local dining area.\n"
        "4. Sequence activities with sensible geographical proximity so travelers do not crisscross the area.\n"
        "5. Avoid repeating the same attraction on multiple days.\n"
        "6. Return ONLY a valid JSON object with the following schema:\n"
        "{\n"
        '  "day_1": [\n'
        '    "Morning: Visit <Attraction Name> (~2.5 hrs) - <practical note>",\n'
        '    "Afternoon: Explore <Attraction Name> (~2 hrs) - <practical note>",\n'
        '    "Evening: Enjoy <Sunset/Walk/Dining> (~1.5 hrs) - <practical note>"\n'
        "  ],\n"
        "  ...\n"
        "}"
    )

    # 4. Generate plan via LLM Gateway
    plan: Dict[str, List[str]] = {}
    is_fallback = False

    try:
        raw_response = chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Generate a {days}-day structured itinerary for {destination} as a valid JSON object.",
                },
            ],
            json_mode=True,
            temperature=0.3,
            max_tokens=1800,
        )
        plan_data = _parse_json_plan(raw_response)

        # Validate that the response contains the expected day keys
        for d in range(1, days + 1):
            key = f"day_{d}"
            day_acts = plan_data.get(key)
            if isinstance(day_acts, list) and len(day_acts) > 0:
                plan[key] = [str(a).strip() for a in day_acts if str(a).strip()]
            else:
                # Fallback to general keys if LLM used numeric or different format
                alt_acts = plan_data.get(str(d)) or plan_data.get(f"Day {d}")
                if isinstance(alt_acts, list) and len(alt_acts) > 0:
                    plan[key] = [str(a).strip() for a in alt_acts if str(a).strip()]
                else:
                    raise LLMGatewayError(f"Missing schedule for day {d} in AI response.")

    except Exception as exc:
        logger.warning(
            "[Itinerary] Primary LLM generation encountered issue (%s). Using verified attraction fallback.",
            exc,
        )
        plan = _build_grounded_fallback_plan(destination, days, verified_attractions)
        is_fallback = True

    # 5. Geographically sequence and sort by time of day
    try:
        plan = optimize_trip_builder_plan(destination, plan)
    except Exception as exc:
        logger.warning("[Itinerary] Route sequence optimization notice: %s", exc)

    # Ensure temporal sequence: Morning -> Afternoon -> Evening
    time_order = {"morning": 0, "afternoon": 1, "evening": 2, "night": 3}
    for day_key, acts in plan.items():
        if isinstance(acts, list):
            plan[day_key] = sorted(
                acts,
                key=lambda a: next((order for t, order in time_order.items() if t in str(a).lower()[:15]), 99),
            )

    notes = (
        f"Verified attraction-grounded {days}-day itinerary for {destination}."
        if is_fallback
        else f"AI-crafted {days}-day itinerary grounded in verified attractions for {destination}."
    )

    return {
        "destination": destination,
        "days": days,
        "plan": plan,
        "notes": notes,
    }
