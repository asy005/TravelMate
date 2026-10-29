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


# Metadata dictionary for supported landmarks
LANDMARK_METADATA = {
    "Taj Mahal": {
        "city": "Agra",
        "country": "India",
        "lat": 27.1751,
        "lon": 78.0421,
        "description": "The Taj Mahal is an ivory-white marble mausoleum on the right bank of the river Yamuna in Agra, Uttar Pradesh, India, commissioned in 1631 by Mughal emperor Shah Jahan.",
    },
    "Eiffel Tower": {
        "city": "Paris",
        "country": "France",
        "lat": 48.8584,
        "lon": 2.2945,
        "description": "The Eiffel Tower is a world-famous wrought-iron lattice tower on the Champ de Mars in Paris, France, named after engineer Gustave Eiffel.",
    },
    "Burj Khalifa": {
        "city": "Dubai",
        "country": "United Arab Emirates",
        "lat": 25.1972,
        "lon": 55.2744,
        "description": "The Burj Khalifa is a renowned skyscraper in Dubai, United Arab Emirates, and the world's tallest architectural structure.",
    },
    "Statue of Liberty": {
        "city": "New York",
        "country": "United States",
        "lat": 40.6892,
        "lon": -74.0445,
        "description": "The Statue of Liberty is a colossal neoclassical sculpture on Liberty Island in New York Harbor, United States.",
    },
    "Mount Fuji": {
        "city": "Honshu",
        "country": "Japan",
        "lat": 35.3606,
        "lon": 138.7274,
        "description": "Mount Fuji is an active stratovolcano and Japan's highest peak at 3,776 meters, celebrated worldwide in art and literature.",
    },
    "Golden Gate Bridge": {
        "city": "San Francisco",
        "country": "United States",
        "lat": 37.8199,
        "lon": -122.4783,
        "description": "The Golden Gate Bridge is an iconic suspension bridge spanning the Golden Gate strait connecting San Francisco and California's Marin County.",
    },
    "Colosseum": {
        "city": "Rome",
        "country": "Italy",
        "lat": 41.8902,
        "lon": 12.4922,
        "description": "The Colosseum is an ancient elliptical amphitheatre in the centre of Rome, Italy, recognized as a wonder of classical engineering.",
    },
    "Pyramids of Giza": {
        "city": "Giza",
        "country": "Egypt",
        "lat": 29.9792,
        "lon": 31.1342,
        "description": "The Giza pyramid complex is an ancient archaeological site on the Giza Plateau outside Cairo, Egypt, featuring the Great Pyramid.",
    },
    "Sydney Opera House": {
        "city": "Sydney",
        "country": "Australia",
        "lat": -33.8568,
        "lon": 151.2153,
        "description": "The Sydney Opera House is a multi-venue performing arts centre in Sydney Harbour, New South Wales, Australia, designed by Jørn Utzon.",
    },
}

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
    meta = LANDMARK_METADATA.get(landmark, {})

    return {
        "landmark": landmark,
        "confidence": confidence,
        "all_scores": {LANDMARKS[i]: float(probs[i]) for i in range(len(LANDMARKS))},
        "city": meta.get("city", "Unknown"),
        "country": meta.get("country", "Unknown"),
        "lat": meta.get("lat"),
        "lon": meta.get("lon"),
        "description": meta.get("description", f"AI detected landmark: {landmark}"),
    }
