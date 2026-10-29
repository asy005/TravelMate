# app/services/voice_service.py
"""
Voice Service for TravelMate (Phase 5).

Provides helper utilities for the Voice Assistant:
- Speech text cleanup: converts Markdown, bullet points, headers, URLs, and symbols
  into natural, conversational speech text suitable for Web Speech API synthesis.
- Speech transcript validation: validates voice recognition input before passing
  into the conversation engine.
- Speech summarization: creates concise speech snippets for lengthy assistant responses.
"""

import re
from typing import Dict, Any, Optional


def clean_speech_text(text: Optional[str]) -> str:
    """
    Strips markdown formatting, code blocks, URLs, bullet symbols,
    and special characters so that browser Text-to-Speech engines pronounce
    the message naturally and smoothly.
    """
    if not text or not isinstance(text, str):
        return ""

    cleaned = text

    # Remove code blocks
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

    # Remove markdown links [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)

    # Remove raw URLs
    cleaned = re.sub(r"https?://\S+", "", cleaned)

    # Remove Markdown headers (# Header)
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)

    # Remove bold/italic markers (* or _)
    cleaned = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", cleaned)
    cleaned = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", cleaned)

    # Replace markdown bullet points with a slight pause or comma
    cleaned = re.sub(r"^\s*[-*•]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)

    # Clean multiple dashes, asterisks, tildes
    cleaned = re.sub(r"[-—~=]{2,}", " ", cleaned)

    # Clean currency symbols for natural speech (e.g. ₹5000 -> 5000 rupees)
    cleaned = re.sub(r"₹\s*(\d[\d,]*)", r"\1 rupees", cleaned)
    cleaned = re.sub(r"rs\.?\s*(\d[\d,]*)", r"\1 rupees", cleaned, flags=re.IGNORECASE)

    # Clean up excess whitespace and newlines
    cleaned = re.sub(r"\n+", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    return cleaned.strip()


def validate_voice_transcript(transcript: Optional[str]) -> Dict[str, Any]:
    """
    Validates a recognized voice transcript before it enters the conversation pipeline.
    """
    if not transcript or not isinstance(transcript, str):
        return {
            "valid": False,
            "error": "empty_transcript",
            "message": "No speech detected. Please speak clearly into your microphone.",
            "clean_transcript": "",
        }

    clean = transcript.strip()

    if len(clean) == 0:
        return {
            "valid": False,
            "error": "empty_transcript",
            "message": "No speech detected. Please speak clearly into your microphone.",
            "clean_transcript": "",
        }

    # If transcript consists only of punctuation/symbols
    if not re.search(r"[a-zA-Z0-9]", clean):
        return {
            "valid": False,
            "error": "unintelligible",
            "message": "Could not understand speech. Please try speaking again.",
            "clean_transcript": clean,
        }

    return {
        "valid": True,
        "error": None,
        "clean_transcript": clean,
    }


def summarize_for_speech(text: Optional[str], max_words: int = 60) -> str:
    """
    Produces a concise, speech-friendly summary from a longer assistant response.
    """
    cleaned = clean_speech_text(text)
    words = cleaned.split()

    if len(words) <= max_words:
        return cleaned

    # Cut off at sentence boundary if possible
    truncated = " ".join(words[:max_words])
    last_period = truncated.rfind(".")
    last_exclamation = truncated.rfind("!")
    last_question = truncated.rfind("?")

    boundary = max(last_period, last_exclamation, last_question)
    if boundary > 20:
        return truncated[: boundary + 1]

    return truncated + "..."
