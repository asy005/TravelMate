# scripts/seed_hotels.py
import os
import sys
sys.path.append(os.path.abspath("."))

from app.database import SessionLocal, engine, Base
from app.models.destination import Destination
from app.models.hotel import Hotel

Base.metadata.create_all(bind=engine)

# 3 price tiers per destination, so hotel_recommender always has a match
# for any budget slot value.
HOTEL_TEMPLATES = [
    {"suffix": "Budget Inn", "tier": "low", "type": "hotel", "price": 1800, "rating": 3.5,
     "amenities": "wifi,breakfast"},
    {"suffix": "Comfort Stay", "tier": "medium", "type": "hotel", "price": 4500, "rating": 4.2,
     "amenities": "wifi,breakfast,pool"},
    {"suffix": "Homestay Retreat", "tier": "medium", "type": "homestay", "price": 3800, "rating": 4.4,
     "amenities": "wifi,home-cooked meals,local host"},
    {"suffix": "Grand Resort", "tier": "luxury", "type": "resort", "price": 11000, "rating": 4.8,
     "amenities": "wifi,pool,spa,fine dining"},
]


def seed():
    db = SessionLocal()
    try:
        if db.query(Hotel).first():
            print("Hotels already seeded (skipping).")
            return

        destinations = db.query(Destination).all()
        if not destinations:
            print("No destinations found -- run scripts/seed_global_destinations.py first.")
            return

        objs = []
        for dest in destinations:
            for tpl in HOTEL_TEMPLATES:
                objs.append(Hotel(
                    destination_id=dest.id,
                    name=f"{dest.name} {tpl['suffix']}",
                    partner_name=f"{tpl['suffix']} Group",
                    accommodation_type=tpl["type"],
                    price_tier=tpl["tier"],
                    price_per_night=tpl["price"],
                    star_rating=tpl["rating"],
                    amenities=tpl["amenities"],
                    thumbnail_url="",
                    description=(
                        f"{tpl['suffix']} is a {tpl['type']} in {dest.name} offering "
                        f"{tpl['amenities'].replace(',', ', ')}. A comfortable choice "
                        f"for travelers seeking a {tpl['tier']}-tier stay."
                    ),
                    photos=[],
                    lat=dest.lat,
                    lon=dest.lon,
                ))

        db.add_all(objs)
        db.commit()
        print(f"Seeded {len(objs)} hotels across {len(destinations)} destinations.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
