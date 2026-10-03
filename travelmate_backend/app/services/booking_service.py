# app/services/booking_service.py
"""
Booking creation logic.

Deliberately payment-agnostic: create_booking() only ever sets status to
"Pending Payment" and stops there. A future payment module hooks in by:
  1. Adding a `payments` table FK'd to booking.id
  2. Calling a (future) confirm_booking_payment(db, booking) that flips
     status to "Confirmed" once a gateway confirms payment
Nothing in this module or the booking_routes flow needs to change for that
to work -- the extension point is the `status` field on Booking.
"""
import random
import string
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.booking import Booking
from app.models.hotel import Hotel
from app.schemas.booking_schema import BookingCreateIn


def _generate_booking_reference(db: Session) -> str:
    """
    Format: TM-XXXXXXXX (8 uppercase alphanumeric chars). Retries on the
    astronomically unlikely collision rather than trusting randomness alone.
    """
    for _ in range(10):
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        reference = f"TM-{suffix}"
        exists = db.query(Booking).filter(Booking.booking_reference == reference).first()
        if not exists:
            return reference
    raise RuntimeError("Could not generate a unique booking reference")


def create_booking(db: Session, user_id: Optional[int], payload: BookingCreateIn) -> Booking:
    hotel = db.query(Hotel).filter(Hotel.id == payload.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    if payload.check_out_date <= payload.check_in_date:
        raise HTTPException(status_code=400, detail="Check-out date must be after check-in date")

    nights = (payload.check_out_date - payload.check_in_date).days
    price_per_night = hotel.price_per_night or 0
    total_amount = price_per_night * nights * max(payload.num_rooms, 1)

    booking = Booking(
        booking_reference=_generate_booking_reference(db),
        user_id=user_id,
        hotel_id=hotel.id,
        destination_id=payload.destination_id or hotel.destination_id,
        session_id=payload.session_id,
        guest_name=payload.guest_name,
        guest_email=payload.guest_email,
        guest_phone=payload.guest_phone,
        check_in_date=payload.check_in_date,
        check_out_date=payload.check_out_date,
        num_rooms=payload.num_rooms,
        num_guests=payload.num_guests,
        special_requests=payload.special_requests,
        total_amount=total_amount,
        currency="INR",
        status="Pending Payment",
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking
