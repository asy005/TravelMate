# app/ml/landmark_detector.py
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

# Load once (cached)
_model = None
_processor = None

def _load_clip():
    global _model, _processor
    if _model is None:
        _model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    return _model, _processor


# Landmark library (expand anytime)
LANDMARKS = [
    "Taj Mahal",
    "Eiffel Tower",
    "Burj Khalifa",
    "Statue of Liberty",
    "Mount Fuji",
    "Golden Gate Bridge",
    "Colosseum",
    "Pyramids of Giza",
    "Sydney Opera House",
]


def detect_landmark(image_path: str):
    model, proc = _load_clip()

    image = Image.open(image_path).convert("RGB")

    # Model input
    inputs = proc(
        text=LANDMARKS,
        images=image,
        return_tensors="pt",
        padding=True
    )

    with torch.no_grad():
        output = model(**inputs)
        logits = output.logits_per_image  # shape = [1, len(LANDMARKS)]
        probs = logits.softmax(dim=1).cpu().numpy()[0]

    best_idx = probs.argmax()
    confidence = float(probs[best_idx])
    landmark = LANDMARKS[best_idx]

    return {
        "landmark": landmark,
        "confidence": confidence,
        "all_scores": {LANDMARKS[i]: float(probs[i]) for i in range(len(LANDMARKS))}
    }
