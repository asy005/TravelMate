from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from app.config import settings
from app.database import engine, Base
from app.services.rag_engine import init_vector_store

from app.routes import (
    auth_routes,
    recommend_routes,
    image_routes,
    destination_routes,
    favorites_routes,
    nearby_routes,
    chat_routes,
    photo_routes,
    mood_routes,
    packing_routes,
    route_routes,
    plan_routes,
    hotel_routes,
)
from app.routes.highlight_routes import router as highlight_router
from app.routes.itinerary_routes import router as itinerary_router
from app.routes import assistant_routes
from app.routes import booking_routes
from app.routes import partner_routes
from app.routes import package_routes
from app.routes import review_routes  # Phase 3
from app.routes import voice_routes
from app.routes import ocr_routes  # Phase 6
from app.routes import translation_routes
from app.routes import currency_routes  # Phase 7  # Phase 6  # Phase 5

app = FastAPI()

# ----------------------------
# CORS — restricted to configured origins (see ALLOWED_ORIGINS in .env)
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    Base.metadata.create_all(bind=engine)
except Exception as exc:
    print(f"[DB] Notice: Could not connect to database on import ({exc}). Live DB required for runtime operations.")


@app.on_event("startup")
def startup_event():
    print("Initializing private knowledge base...")
    init_vector_store()
    print("Knowledge base loaded successfully.")


# Routes (each router included exactly once)
app.include_router(auth_routes.router)
app.include_router(recommend_routes.router)
app.include_router(image_routes.router)
app.include_router(destination_routes.router)
app.include_router(favorites_routes.router)
app.include_router(nearby_routes.router)
app.include_router(chat_routes.router)
app.include_router(photo_routes.router)
app.include_router(mood_routes.router)
app.include_router(packing_routes.router)
app.include_router(route_routes.router)
app.include_router(plan_routes.router)
app.include_router(hotel_routes.router)
app.include_router(highlight_router)
app.include_router(itinerary_router)
app.include_router(assistant_routes.router)
app.include_router(booking_routes.router)
app.include_router(partner_routes.router)
app.include_router(package_routes.router)
app.include_router(review_routes.router)  # Phase 3
app.include_router(voice_routes.router)  # Phase 5
app.include_router(ocr_routes.router)  # Phase 6
app.include_router(translation_routes.router)  # Phase 6
app.include_router(currency_routes.router)  # Phase 7

# ----------------------------
# Static file serving for uploads (partner photos, etc.)
# Served at /uploads/<path>; stored in travelmate_backend/uploads/
# ----------------------------
_UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(_UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_UPLOADS_DIR), name="uploads")

# ----------------------------
# Static file serving for dataset images (destinations, attractions, hotels, activities)
# Served at /dataset-images/<subfolder>/<filename>
# Path: main.py -> app -> travelmate_backend -> project_root -> datasets/images
# ----------------------------
_DATASET_IMAGES_DIR = Path(__file__).resolve().parents[2] / "datasets" / "images"
if _DATASET_IMAGES_DIR.exists():
    app.mount(
        "/dataset-images",
        StaticFiles(directory=str(_DATASET_IMAGES_DIR)),
        name="dataset-images",
    )
else:
    print(f"[WARNING] Dataset images directory not found at {_DATASET_IMAGES_DIR}; /dataset-images mount skipped.")


@app.get("/")
def root():
    return {"message": "TravelMate Backend Running!"}
