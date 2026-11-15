from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Any, List, Dict
from datetime import datetime

from app.database import get_db
from app.models.saved_trip import SavedTrip
from app.services.auth_utils import get_current_user

router = APIRouter(prefix="/saved-trips", tags=["saved-trips"])


class SavedTripPayload(BaseModel):
    destination_id: Optional[int] = None
    destination_name: str
    trip_title: Optional[str] = None
    trip_duration_days: Optional[int] = 3
    travel_dates: Optional[str] = None
    destination_data: Optional[Dict[str, Any]] = None
    itinerary: Optional[Any] = None
    selected_attractions: Optional[List[Any]] = None
    selected_activities: Optional[List[Any]] = None
    route_stops: Optional[List[Any]] = None
    route_details: Optional[Dict[str, Any]] = None
    packing_checklist: Optional[Dict[str, Any]] = None
    custom_packing_items: Optional[List[Any]] = None
    trip_preferences: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class SavedTripResponse(BaseModel):
    id: int
    user_id: int
    destination_id: Optional[int] = None
    destination_name: str
    trip_title: Optional[str] = None
    trip_duration_days: Optional[int] = 3
    travel_dates: Optional[str] = None
    destination_data: Optional[Dict[str, Any]] = None
    itinerary: Optional[Any] = None
    selected_attractions: Optional[List[Any]] = None
    selected_activities: Optional[List[Any]] = None
    route_stops: Optional[List[Any]] = None
    route_details: Optional[Dict[str, Any]] = None
    packing_checklist: Optional[Dict[str, Any]] = None
    custom_packing_items: Optional[List[Any]] = None
    trip_preferences: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True


@router.get("/", response_model=List[SavedTripResponse])
def get_all_saved_trips(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all saved customized trips belonging to the authenticated user."""
    return (
        db.query(SavedTrip)
        .filter(SavedTrip.user_id == user.id)
        .order_by(SavedTrip.updated_at.desc())
        .all()
    )


@router.get("/by-destination/{destination_id}", response_model=Optional[SavedTripResponse])
def get_saved_trip_by_destination(
    destination_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve the user's saved trip for a specific destination, if one exists."""
    trip = (
        db.query(SavedTrip)
        .filter(
            SavedTrip.user_id == user.id,
            SavedTrip.destination_id == destination_id,
        )
        .order_by(SavedTrip.updated_at.desc())
        .first()
    )
    return trip


@router.get("/{trip_id}", response_model=SavedTripResponse)
def get_saved_trip(
    trip_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a single saved trip by ID, enforcing user ownership."""
    trip = db.query(SavedTrip).filter(SavedTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Saved trip not found")
    if trip.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this saved trip")
    return trip


@router.post("/", response_model=SavedTripResponse)
def save_or_update_trip(
    payload: SavedTripPayload,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save or update a customized trip.
    Prevents duplicate trip records for the same user and destination by updating
    the existing record if it already exists.
    """
    existing = None
    if payload.destination_id:
        existing = (
            db.query(SavedTrip)
            .filter(
                SavedTrip.user_id == user.id,
                SavedTrip.destination_id == payload.destination_id,
            )
            .first()
        )
    elif payload.destination_name:
        existing = (
            db.query(SavedTrip)
            .filter(
                SavedTrip.user_id == user.id,
                SavedTrip.destination_name.ilike(payload.destination_name.strip()),
            )
            .first()
        )

    if existing:
        # Update existing record
        existing.destination_name = payload.destination_name
        existing.trip_title = payload.trip_title or existing.trip_title or f"Trip to {payload.destination_name}"
        existing.trip_duration_days = payload.trip_duration_days or existing.trip_duration_days
        existing.travel_dates = payload.travel_dates or existing.travel_dates
        if payload.destination_data is not None:
            existing.destination_data = payload.destination_data
        if payload.itinerary is not None:
            existing.itinerary = payload.itinerary
        if payload.selected_attractions is not None:
            existing.selected_attractions = payload.selected_attractions
        if payload.selected_activities is not None:
            existing.selected_activities = payload.selected_activities
        if payload.route_stops is not None:
            existing.route_stops = payload.route_stops
        if payload.route_details is not None:
            existing.route_details = payload.route_details
        if payload.packing_checklist is not None:
            existing.packing_checklist = payload.packing_checklist
        if payload.custom_packing_items is not None:
            existing.custom_packing_items = payload.custom_packing_items
        if payload.trip_preferences is not None:
            existing.trip_preferences = payload.trip_preferences
        if payload.notes is not None:
            existing.notes = payload.notes
        existing.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(existing)
        return existing

    # Create new saved trip record
    new_trip = SavedTrip(
        user_id=user.id,
        destination_id=payload.destination_id,
        destination_name=payload.destination_name,
        trip_title=payload.trip_title or f"Trip to {payload.destination_name}",
        trip_duration_days=payload.trip_duration_days or 3,
        travel_dates=payload.travel_dates,
        destination_data=payload.destination_data,
        itinerary=payload.itinerary,
        selected_attractions=payload.selected_attractions,
        selected_activities=payload.selected_activities,
        route_stops=payload.route_stops,
        route_details=payload.route_details,
        packing_checklist=payload.packing_checklist,
        custom_packing_items=payload.custom_packing_items,
        trip_preferences=payload.trip_preferences,
        notes=payload.notes,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_trip)
    db.commit()
    db.refresh(new_trip)
    return new_trip


@router.put("/{trip_id}", response_model=SavedTripResponse)
def update_saved_trip(
    trip_id: int,
    payload: SavedTripPayload,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing saved trip, enforcing user ownership."""
    trip = db.query(SavedTrip).filter(SavedTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Saved trip not found")
    if trip.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this saved trip")

    trip.destination_name = payload.destination_name
    if payload.trip_title:
        trip.trip_title = payload.trip_title
    if payload.trip_duration_days is not None:
        trip.trip_duration_days = payload.trip_duration_days
    if payload.travel_dates:
        trip.travel_dates = payload.travel_dates
    if payload.destination_data is not None:
        trip.destination_data = payload.destination_data
    if payload.itinerary is not None:
        trip.itinerary = payload.itinerary
    if payload.selected_attractions is not None:
        trip.selected_attractions = payload.selected_attractions
    if payload.selected_activities is not None:
        trip.selected_activities = payload.selected_activities
    if payload.route_stops is not None:
        trip.route_stops = payload.route_stops
    if payload.route_details is not None:
        trip.route_details = payload.route_details
    if payload.packing_checklist is not None:
        trip.packing_checklist = payload.packing_checklist
    if payload.custom_packing_items is not None:
        trip.custom_packing_items = payload.custom_packing_items
    if payload.trip_preferences is not None:
        trip.trip_preferences = payload.trip_preferences
    if payload.notes is not None:
        trip.notes = payload.notes
    trip.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(trip)
    return trip


@router.delete("/{trip_id}")
def delete_saved_trip(
    trip_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a saved trip, enforcing user ownership."""
    trip = db.query(SavedTrip).filter(SavedTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Saved trip not found")
    if trip.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this saved trip")

    db.delete(trip)
    db.commit()
    return {"message": "Saved trip deleted successfully", "id": trip_id}
