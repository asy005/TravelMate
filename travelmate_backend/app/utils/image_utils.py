from PIL import Image
import io
from typing import Dict

def analyze_image(file_bytes: bytes) -> Dict:
    try:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        pixels = img.resize((50,50)).getdata()
        avg = sum(sum(px)/3 for px in pixels) / (50*50)
        mood = "bright" if avg > 100 else "calm"
        tags = ["beach"] if avg > 120 else ["mountain"]
        return {"predicted_mood": mood, "tags": tags, "brightness": avg}
    except Exception as e:
        return {"error": str(e)}
