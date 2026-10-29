# app/routes/voice_routes.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.voice_service import clean_speech_text, validate_voice_transcript, summarize_for_speech

router = APIRouter(prefix="/voice", tags=["voice"])


class CleanSpeechRequest(BaseModel):
    text: str
    max_words: Optional[int] = 80


class CleanSpeechResponse(BaseModel):
    original_length: int
    clean_text: str
    speech_summary: str
    word_count: int


class ValidateTranscriptRequest(BaseModel):
    transcript: str


class ValidateTranscriptResponse(BaseModel):
    valid: bool
    clean_transcript: str
    error: Optional[str] = None
    message: Optional[str] = None


@router.get("/status")
def voice_status():
    """
    Returns the supported client-side voice assistant integration details.
    Uses browser native Web Speech API (zero paid APIs, zero external keys).
    """
    return {
        "status": "ready",
        "provider": "Web Speech API (Browser Native)",
        "features": {
            "speech_recognition": "window.SpeechRecognition / window.webkitSpeechRecognition",
            "speech_synthesis": "window.speechSynthesis",
            "paid_apis": False,
            "offline_friendly": False,
        },
        "supported_browsers": [
            "Chrome (Desktop/Android)",
            "Edge (Desktop/Android)",
            "Safari (macOS/iOS, SpeechSynthesis and webkitSpeechRecognition)",
        ],
    }


@router.post("/clean-text", response_model=CleanSpeechResponse)
def format_speech_text(payload: CleanSpeechRequest):
    """
    Cleans markdown, URLs, symbols, and formatting from an assistant response
    so it can be spoken smoothly by client-side Web Speech API Text-to-Speech.
    """
    cleaned = clean_speech_text(payload.text)
    summary = summarize_for_speech(payload.text, max_words=payload.max_words or 80)
    return {
        "original_length": len(payload.text or ""),
        "clean_text": cleaned,
        "speech_summary": summary,
        "word_count": len(cleaned.split()),
    }


@router.post("/validate-transcript", response_model=ValidateTranscriptResponse)
def validate_transcript_endpoint(payload: ValidateTranscriptRequest):
    """
    Validates a recognized transcript before sending into conversational slot filling.
    """
    result = validate_voice_transcript(payload.transcript)
    return {
        "valid": result["valid"],
        "clean_transcript": result.get("clean_transcript", ""),
        "error": result.get("error"),
        "message": result.get("message"),
    }
