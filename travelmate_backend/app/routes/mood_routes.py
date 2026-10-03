from fastapi import APIRouter, UploadFile, File
from fastapi import HTTPException

router = APIRouter(prefix="/mood", tags=["mood"])


@router.post("/classify")
def classify_mood(text: str):
    """
    Simple text-based mood classifier.
    Used as fallback when ML model is not available.
    """
    text = text.lower()

    if any(w in text for w in ["sad", "down", "tired", "depressed"]):
        mood = "Relaxing"
    elif any(w in text for w in ["excited", "thrill", "adventure", "explore"]):
        mood = "Adventure"
    elif any(w in text for w in ["love", "romantic", "couple"]):
        mood = "Romantic"
    else:
        mood = "Neutral"

    return {"mood": mood}
