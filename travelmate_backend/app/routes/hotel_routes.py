# app/routes/hotel_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.database import get_db
from app.models.destination import Destination
from app.models.hotel import Hotel
from app.models.conversation import ConversationSession
from app.services.hotel_recommender import recommend_hotels
from app.services.geo_lookup import guess_coordinates, get_nearby_attractions
from app.services.budget_optimizer import allocate_budget

router = APIRouter(prefix="/hotels", tags=["hotels"])


class HotelRecommendIn(BaseModel):
    destination_id: int
    slots: Optional[Dict[str, Any]] = {}


class SelectHotelIn(BaseModel):
    session_id: str
    destination_id: int
    hotel_id: int


@router.post("/recommend")
def recommend(payload: HotelRecommendIn, db: Session = Depends(get_db)):
    dest = db.query(Destination).filter(Destination.id == payload.destination_id).first()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    return {
        "destination_id": dest.id,
        "destination_name": dest.name,
        "hotels": recommend_hotels(db, dest.id, payload.slots or {}),
    }


def _mock_room_types(hotel: Hotel):
    base = hotel.price_per_night or 3000
    return [
        {
            "type": "Standard Room",
            "price_per_night": round(base * 0.8),
            "capacity": 2,
            "bed": "1 Queen Bed",
        },
        {
            "type": "Deluxe Room",
            "price_per_night": round(base),
            "capacity": 2,
            "bed": "1 King Bed",
        },
        {
            "type": "Family Suite",
            "price_per_night": round(base * 1.5),
            "capacity": 4,
            "bed": "2 Queen Beds",
        },
    ]


@router.get("/{hotel_id}")
def get_hotel_details(hotel_id: int, db: Session = Depends(get_db)):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    dest = db.query(Destination).filter(Destination.id == hotel.destination_id).first()

    lat, lon = hotel.lat, hotel.lon
    if not lat or not lon:
        lat, lon = guess_coordinates(dest.name if dest else "")

    return {
        "id": hotel.id,
        "name": hotel.name,
        "partner_name": hotel.partner_name,
        "accommodation_type": hotel.accommodation_type,
        "price_tier": hotel.price_tier,
        "price_per_night": hotel.price_per_night,
        "star_rating": hotel.star_rating,
        "amenities": (hotel.amenities or "").split(",") if hotel.amenities else [],
        "description": hotel.description,
        "photos": hotel.photos or [],
        "thumbnail_url": hotel.thumbnail_url,
        "location": {
            "lat": lat, "lon": lon,
            "destination_name": dest.name if dest else None,
            "country": dest.country if dest else None,
        },
        "nearby_attractions": get_nearby_attractions(lat, lon),
        "room_types": _mock_room_types(hotel),
    }


@router.post("/select")
def select_hotel(payload: SelectHotelIn, db: Session = Depends(get_db)):
    """
    Updates the AI-generated plan stored on a conversation session with the
    user's chosen hotel for a given destination. Booking/payment are not
    implemented -- this only records the selection on the plan.
    """
    session = db.query(ConversationSession).filter(
        ConversationSession.session_id == payload.session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    hotel = db.query(Hotel).filter(Hotel.id == payload.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    plan = session.generated_plan
    if not plan:
        raise HTTPException(status_code=400, detail="This session has no generated plan yet")

    updated = False
    for dest_block in plan.get("destinations", []):
        if dest_block.get("id") == payload.destination_id:
            hotel_dict = {
                "id": hotel.id,
                "name": hotel.name,
                "price_per_night": hotel.price_per_night,
                "star_rating": hotel.star_rating,
                "accommodation_type": hotel.accommodation_type,
            }
            dest_block["selected_hotel"] = hotel_dict
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Destination not found in this plan")

    # Budget math lives in exactly one place (budget_optimizer.allocate_budget)
    # -- recompute it here using the newly selected hotel so the dashboard
    # always reflects one consistent calculation.
    slots = session.slots or {}
    duration_days = slots.get("duration_days") or 3
    travelers = slots.get("travelers") or 1
    existing_package = next(
        (d.get("selected_package") for d in plan.get("destinations", []) if d.get("id") == payload.destination_id),
        None,
    )
    plan["budget"] = allocate_budget(
        db, slots, duration_days, travelers,
        destination_id=payload.destination_id,
        selected_hotel=hotel_dict,
        selected_package=existing_package,
    )

    session.generated_plan = plan
    db.add(session)
    db.commit()
    db.refresh(session)

    return {"msg": "Hotel selected", "plan": session.generated_plan}
