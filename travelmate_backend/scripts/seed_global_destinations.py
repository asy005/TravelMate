# scripts/seed_global_destinations.py
import os
import sys
sys.path.append(os.path.abspath("."))

from app.database import SessionLocal, engine, Base   # adjust import if your project uses different names
from app.models.destination import Destination        # adjust if import path differs

# Create tables if not exists
Base.metadata.create_all(bind=engine)

# NOTE: field names below match the actual Destination model
# (name, country, description, lat, lon, tags, thumbnail_url, avg_rating).
# "best_season" and "climate" are folded into the free-text `tags` field so
# they remain useful for the mood-based tag filtering in plan_routes.py.
DESTINATIONS = [
    {"name": "Goa", "country": "India", "description": "Beaches, nightlife and laid-back coastal vibe.",
     "lat": 15.4909, "lon": 73.8278, "tags": "beach,tropical,best:Nov-Mar", "thumbnail_url": "", "avg_rating": 4.1},
    {"name": "Manali", "country": "India", "description": "Himalayan hill-station with treks and rivers.",
     "lat": 32.2396, "lon": 77.1887, "tags": "mountain,cold,trekking,best:Apr-Jun", "thumbnail_url": "", "avg_rating": 4.4},
    {"name": "Paris", "country": "France", "description": "City of lights — museums, cafes and romance.",
     "lat": 48.8566, "lon": 2.3522, "tags": "temperate,culture,best:Apr-Jun", "thumbnail_url": "", "avg_rating": 4.3},
    {"name": "Tokyo", "country": "Japan", "description": "Ultra-modern city with temples and food culture.",
     "lat": 35.6762, "lon": 139.6503, "tags": "temperate,culture,best:Mar-Apr", "thumbnail_url": "", "avg_rating": 4.2},
    {"name": "Bali", "country": "Indonesia", "description": "Tropical island, rice terraces and beaches.",
     "lat": -8.3405, "lon": 115.0920, "tags": "beach,tropical,best:Apr-Oct", "thumbnail_url": "", "avg_rating": 4.0},
    {"name": "New York", "country": "USA", "description": "Skyscrapers, museums and diverse neighbourhoods.",
     "lat": 40.7128, "lon": -74.0060, "tags": "temperate,culture,best:Apr-Jun", "thumbnail_url": "", "avg_rating": 4.1},
    {"name": "London", "country": "United Kingdom", "description": "Historic landmarks, museums and theatre.",
     "lat": 51.5074, "lon": -0.1278, "tags": "temperate,culture,best:May-Sep", "thumbnail_url": "", "avg_rating": 4.2},
    {"name": "Dubai", "country": "UAE", "description": "Luxury shopping, deserts and modern architecture.",
     "lat": 25.2048, "lon": 55.2708, "tags": "hot,shopping,best:Nov-Mar", "thumbnail_url": "", "avg_rating": 4.0},
    {"name": "Kyoto", "country": "Japan", "description": "Temples, gardens and traditional Japan.",
     "lat": 35.0116, "lon": 135.7681, "tags": "temperate,culture,best:Mar-Apr", "thumbnail_url": "", "avg_rating": 4.4},
    {"name": "Reykjavik", "country": "Iceland", "description": "Gateway to Icelandic nature and northern lights.",
     "lat": 64.1466, "lon": -21.9426, "tags": "cold,nature,best:Sep-Mar", "thumbnail_url": "", "avg_rating": 4.3},
    {"name": "Hampi", "country": "India", "description": "Ancient ruins and heritage sites in India.",
     "lat": 15.3350, "lon": 76.4600, "tags": "temperate,culture,heritage,best:Oct-Mar", "thumbnail_url": "", "avg_rating": 4.5},
    {"name": "Rio de Janeiro", "country": "Brazil", "description": "Beaches, carnival and scenic vistas.",
     "lat": -22.9068, "lon": -43.1729, "tags": "beach,tropical,best:May-Oct", "thumbnail_url": "", "avg_rating": 3.9},
    {"name": "Cusco", "country": "Peru", "description": "Access to Machu Picchu and Andean culture.",
     "lat": -13.5319, "lon": -71.9675, "tags": "temperate,adventure,trekking,best:May-Sep", "thumbnail_url": "", "avg_rating": 4.2},
    {"name": "Queenstown", "country": "New Zealand", "description": "Adventure sports and alpine scenery in NZ.",
     "lat": -45.0312, "lon": 168.6626, "tags": "temperate,adventure,best:Dec-Feb", "thumbnail_url": "", "avg_rating": 4.4},
    {"name": "Santorini", "country": "Greece", "description": "Aegean island, white houses, sunsets.",
     "lat": 36.3932, "lon": 25.4615, "tags": "beach,mediterranean,best:May-Sep", "thumbnail_url": "", "avg_rating": 4.3},
    {"name": "Vancouver", "country": "Canada", "description": "Coastal city with mountains and outdoor life.",
     "lat": 49.2827, "lon": -123.1207, "tags": "temperate,nature,best:Jun-Sep", "thumbnail_url": "", "avg_rating": 4.2},
    {"name": "Buenos Aires", "country": "Argentina", "description": "Tango, European architecture and food.",
     "lat": -34.6037, "lon": -58.3816, "tags": "temperate,culture,best:Sep-Nov", "thumbnail_url": "", "avg_rating": 4.0},
    {"name": "Bergen", "country": "Norway", "description": "Norwegian fjords and scenic drives.",
     "lat": 60.3913, "lon": 5.3221, "tags": "cold,nature,best:May-Sep", "thumbnail_url": "", "avg_rating": 4.1},
    {"name": "Cape Town", "country": "South Africa", "description": "Beaches, Table Mountain and vineyards.",
     "lat": -33.9249, "lon": 18.4241, "tags": "beach,mediterranean,best:Nov-Mar", "thumbnail_url": "", "avg_rating": 4.0},
    {"name": "Zurich", "country": "Switzerland", "description": "Swiss city, lakes and alpine trips.",
     "lat": 47.3769, "lon": 8.5417, "tags": "temperate,nature,best:Jun-Sep", "thumbnail_url": "", "avg_rating": 4.2},
]

def seed():
    db = SessionLocal()
    try:
        existing = db.query(Destination).first()
        if existing:
            print("DB already seeded (skipping).")
            return
        objs = []
        for d in DESTINATIONS:
            objs.append(Destination(**d))
        db.add_all(objs)
        db.commit()
        print(f"Seeded {len(objs)} destinations.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
