# app/routes/photo_routes.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import requests
import tempfile
from PIL import Image
import io
import base64
import json

router = APIRouter(prefix="/photo", tags=["photo"])
HF = os.getenv("HUGGINGFACEHUB_API_TOKEN")

# simple mapping from common labels -> mood
LABEL_TO_MOOD = {
    "beach": "Relaxing",
    "ocean": "Relaxing",
    "mountain": "Adventure",
    "forest": "Adventure",
    "couple": "Romantic",
    "sunset": "Romantic",
    # add more mapping as you like
}


@router.post("/mood")
def photo_mood(file: UploadFile = File(...)):
    content = file.file.read()
    if HF:
        url = "https://api-inference.huggingface.co/models/google/vit-base-patch16-224"
        headers = {"Authorization": f"Bearer {HF}"}
        # HuggingFace image inference accepts binary input
        r = requests.post(url, headers=headers, data=content, timeout=30)
        if r.status_code == 200:
            data = r.json()
            # data often a list of labels with scores
            if isinstance(data, list) and len(data):
                top_label = data[0].get("label", "").lower()
                for k, mood in LABEL_TO_MOOD.items():
                    if k in top_label:
                        return {"mood": mood, "label": top_label}
                return {"mood": "Relaxing", "label": top_label}  # default fallback
            return {"error": "Cannot parse model output", "raw": data}
        else:
            return {"error": f"HF {r.status_code}", "body": r.text}

    # fallback if token not provided: return neutral result
    return {"mood": "Relaxing", "label": "placeholder_fallback"}


# ── Landmark detection via CLIP ─────────────────────────────────────────────

def _clip_available() -> bool:
    """Check whether torch + transformers are importable (cached after first call)."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


@router.post("/landmark")
def detect_landmark_endpoint(file: UploadFile = File(...)):
    """
    Detect the most likely landmark in an uploaded image using CLIP.

    Returns:
        200 with {landmark, confidence, all_scores} when CLIP is available.
        503 with {available: false, message: ...} when dependencies are missing.
    """
    if not _clip_available():
        return JSONResponse(
            status_code=503,
            content={
                "available": False,
                "message": (
                    "CLIP model dependencies (torch, transformers) are not installed. "
                    "Install them with: pip install torch transformers pillow"
                ),
            },
        )

    # Lazy import so the module still loads when CLIP is absent
    from app.ml.landmark_detector import detect_landmark

    content = file.file.read()

    # Write to a temp file so detect_landmark (which uses Image.open(path)) can read it
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = detect_landmark(tmp_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Landmark detection failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return result
