# app/routes/highlight_routes.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from sqlalchemy.orm import Session
from app.services.rag_engine import query_knowledge_base, ensure_initialized
from app.services.highlights_service import top_highlights_from_rag

router = APIRouter(prefix="/highlights", tags=["highlights"])
ensure_initialized()

@router.get("/")
def get_highlights(query: str, top: int = 3, destination: Optional[str] = None):
    target_dest = destination or query
    rag = query_knowledge_base(query, destination_name=target_dest)
    if "error" in rag:
        rag = {"fallback": rag.get("fallback", {}), "snippets": rag.get("snippets", []), "context": rag.get("context", "")}
    highlights = top_highlights_from_rag(rag, max_items=top, destination_name=target_dest)
    return {"query": query, "highlights": highlights}
