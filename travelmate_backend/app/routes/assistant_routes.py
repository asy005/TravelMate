# app/routes/assistant_routes.py
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.conversation import ConversationSession
from app.schemas.assistant_schema import AssistantMessageIn, AssistantMessageOut, AssistantResetIn
from app.services.conversation_engine import (
    process_message,
    missing_required_slots,
    EMPTY_SLOTS,
)
from app.services.plan_orchestrator import generate_plan
from app.services.refinement_engine import classify_refinement, apply_refinement

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _get_or_create_session(db: Session, session_id: str) -> ConversationSession:
    session = None
    if session_id:
        session = db.query(ConversationSession).filter(
            ConversationSession.session_id == session_id
        ).first()

    if not session:
        session = ConversationSession(
            session_id=session_id or str(uuid.uuid4()),
            messages=[],
            slots=dict(EMPTY_SLOTS),
            status="collecting",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    return session


@router.post("/message", response_model=AssistantMessageOut)
def send_message(payload: AssistantMessageIn, db: Session = Depends(get_db)):
    session = _get_or_create_session(db, payload.session_id)

    history = list(session.messages or [])
    now = datetime.now(timezone.utc).isoformat()

    if session.status == "ready" and session.generated_plan:
        # A plan already exists -- treat this message as a refinement
        # request rather than more slot-filling (Conversational Trip
        # Refinement). The existing conversation/slots/plan are kept and
        # only the affected sections are regenerated.
        extracted_slots, change_type, remove_package, reply = classify_refinement(
            prior_slots=session.slots or {},
            user_message=payload.message,
        )
        updated_plan, updated_slots = apply_refinement(
            db,
            current_slots=session.slots or {},
            plan=session.generated_plan,
            change_type=change_type,
            extracted_slots=extracted_slots,
            remove_package=remove_package,
        )
        plan = updated_plan
        ready = True
        session.generated_plan = plan
        session.status = "ready"
    else:
        reply, updated_slots, ready = process_message(
            prior_slots=session.slots or dict(EMPTY_SLOTS),
            conversation_history=history,
            user_message=payload.message,
        )
        plan = None
        if ready:
            plan = generate_plan(db, updated_slots)
            session.status = "ready"
            session.generated_plan = plan
        else:
            session.status = "collecting"

    history.append({"role": "user", "content": payload.message, "ts": now})
    history.append({"role": "assistant", "content": reply, "ts": now})

    session.messages = history
    session.slots = updated_slots
    db.add(session)
    db.commit()
    db.refresh(session)

    return AssistantMessageOut(
        session_id=session.session_id,
        reply=reply,
        slots=updated_slots,
        missing_slots=missing_required_slots(updated_slots),
        ready_for_plan=ready,
        plan=plan,
    )


@router.get("/session/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ConversationSession).filter(
        ConversationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "messages": session.messages,
        "slots": session.slots,
        "status": session.status,
        "plan": session.generated_plan,
    }


@router.post("/reset")
def reset_session(payload: AssistantResetIn, db: Session = Depends(get_db)):
    session = db.query(ConversationSession).filter(
        ConversationSession.session_id == payload.session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.messages = []
    session.slots = dict(EMPTY_SLOTS)
    session.status = "collecting"
    session.generated_plan = None
    db.add(session)
    db.commit()

    return {"msg": "Session reset", "session_id": session.session_id}
