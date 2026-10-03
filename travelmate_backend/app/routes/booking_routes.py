# app/routes/booking_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.booking import Booking
from app.models.hotel import Hotel
from app.schemas.booking_schema import BookingCreateIn, BookingOut, PaymentOrderOut, PaymentVerifyIn
from app.services.booking_service import create_booking
from app.services.auth_utils import get_current_user_optional
from app.services.payment_service import create_order, verify_payment_signature, PaymentError

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _to_booking_out(booking: Booking, hotel: Hotel = None) -> BookingOut:
    return BookingOut(
        booking_reference=booking.booking_reference,
        status=booking.status,
        hotel_id=booking.hotel_id,
        hotel_name=hotel.name if hotel else None,
        guest_name=booking.guest_name,
        guest_email=booking.guest_email,
        guest_phone=booking.guest_phone,
        check_in_date=booking.check_in_date,
        check_out_date=booking.check_out_date,
        num_rooms=booking.num_rooms,
        num_guests=booking.num_guests,
        special_requests=booking.special_requests,
        total_amount=booking.total_amount,
        currency=booking.currency,
        payment_reference=booking.payment_reference,
    )


@router.post("/", response_model=BookingOut)
def create_new_booking(
    payload: BookingCreateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    booking = create_booking(db, user.id if user else None, payload)
    hotel = db.query(Hotel).filter(Hotel.id == booking.hotel_id).first()
    return _to_booking_out(booking, hotel)


@router.get("/{booking_reference}", response_model=BookingOut)
def get_booking(booking_reference: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(
        Booking.booking_reference == booking_reference
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    hotel = db.query(Hotel).filter(Hotel.id == booking.hotel_id).first()
    return _to_booking_out(booking, hotel)


@router.post("/{booking_reference}/create-order", response_model=PaymentOrderOut)
def create_payment_order(booking_reference: str, db: Session = Depends(get_db)):
    """
    Creates a Razorpay order for an existing (still Pending Payment) booking.
    Reuses the booking's already-computed total_amount -- no new pricing
    logic here, just handing that number to Razorpay. The order_id is
    stored on the booking so verify-payment can confirm the signature
    belongs to *this* booking's order, not just any valid signature.
    """
    booking = db.query(Booking).filter(Booking.booking_reference == booking_reference).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "Pending Payment":
        raise HTTPException(status_code=400, detail=f"Booking is already '{booking.status}', cannot pay again")

    if not booking.total_amount or booking.total_amount <= 0:
        raise HTTPException(status_code=400, detail="This booking has no payable amount")

    try:
        order = create_order(booking.total_amount, receipt=booking.booking_reference)
    except PaymentError as e:
        raise HTTPException(status_code=502, detail=str(e))

    booking.payment_order_id = order["order_id"]
    db.add(booking)
    db.commit()

    return {**order, "booking_reference": booking.booking_reference}


@router.post("/{booking_reference}/verify-payment", response_model=BookingOut)
def verify_payment(booking_reference: str, payload: PaymentVerifyIn, db: Session = Depends(get_db)):
    """
    Called by the frontend after Razorpay's checkout succeeds.
    - Success: booking status -> "Confirmed", payment_reference stored.
    - Failure (bad signature, or order_id doesn't match this booking): the
      booking is left exactly as-is ("Pending Payment"), per spec -- no
      partial/uncertain state is ever written.
    """
    booking = db.query(Booking).filter(Booking.booking_reference == booking_reference).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if not booking.payment_order_id or booking.payment_order_id != payload.razorpay_order_id:
        raise HTTPException(status_code=400, detail="This payment does not match this booking's order")

    try:
        is_valid = verify_payment_signature(
            payload.razorpay_order_id,
            payload.razorpay_payment_id,
            payload.razorpay_signature,
        )
    except PaymentError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not is_valid:
        # Explicitly do NOT touch booking.status or payment_reference here --
        # it stays "Pending Payment" exactly as before this call.
        raise HTTPException(status_code=400, detail="Payment verification failed")

    booking.status = "Confirmed"
    booking.payment_reference = payload.razorpay_payment_id
    db.add(booking)
    db.commit()
    db.refresh(booking)

    hotel = db.query(Hotel).filter(Hotel.id == booking.hotel_id).first()
    return _to_booking_out(booking, hotel)
