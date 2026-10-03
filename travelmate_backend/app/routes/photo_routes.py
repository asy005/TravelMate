# app/routes/photo_routes.py
from fastapi import APIRouter, UploadFile, File
import os, requests
from PIL import Image
import io, base64, json

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
