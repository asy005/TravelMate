# app/routes/highlight_routes.py
from fastapi import APIRouter, Depends
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.highlights_service import get_destination_highlights

router = APIRouter(prefix="/highlights", tags=["highlights"])

@router.get("/")
def get_highlights(
    query: str,
    top: int = 4,
    destination: Optional[str] = None,
    destination_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    target_dest = destination or query
    highlights = get_destination_highlights(
        destination_name=target_dest,
        destination_id=destination_id,
        max_items=top,
        db=db,
    )
    return {"query": query, "destination": target_dest, "highlights": highlights}
