# app/services/highlights_service.py
from typing import List, Dict
import re

def extract_sentences(text: str, max_sentences: int = 3) -> List[str]:
    # naive sentence splitter
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    out = []
    for s in sentences:
        s = s.strip()
        if s and len(s) > 20:  # skip tiny fragments
            out.append(s)
        if len(out) >= max_sentences:
            break
    return out

def top_highlights_from_rag(rag_result: Dict, max_items: int = 3) -> List[str]:
    # Try snippets first
    snippets = rag_result.get("snippets") or []
    highlights = []

    # Take first informative lines from top snippets
    for s in snippets:
        text = s.get("text") if isinstance(s, dict) else getattr(s, "page_content", "")
        if not text:
            continue
        for sent in extract_sentences(text, max_sentences=2):
            if sent not in highlights:
                highlights.append(sent)
            if len(highlights) >= max_items:
                break
        if len(highlights) >= max_items:
            break

    # If not enough, fall back to fallback.description or context
    fb = rag_result.get("fallback", {})
    if len(highlights) < max_items and fb.get("description"):
        for sent in extract_sentences(fb["description"], max_sentences=max_items):
            if sent not in highlights:
                highlights.append(sent)
            if len(highlights) >= max_items:
                break

    # final fallback - context
    if len(highlights) < max_items and rag_result.get("context"):
        for sent in extract_sentences(rag_result["context"], max_sentences=max_items):
            if sent not in highlights:
                highlights.append(sent)
            if len(highlights) >= max_items:
                break

    return highlights[:max_items]
