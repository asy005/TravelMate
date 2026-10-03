from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

Base.metadata.create_all(bind=engine)


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


@app.get("/")
def root():
    return {"message": "TravelMate Backend Running!"}
