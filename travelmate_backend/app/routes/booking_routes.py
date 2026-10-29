# app/routes/booking_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.booking import Booking
from app.models.hotel import Hotel
from app.schemas.booking_schema import BookingCreateIn, BookingOut, PaymentOrderOut, PaymentVerifyIn
from app.services.booking_service import create_booking
from app.services.auth_utils import get_current_user_optional
from app.services.payment_service import (
    create_order,
    verify_payment_signature,
    verify_demo_payment,
    is_demo_order,
    is_demo_payment_allowed,
    PaymentError,
)

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _to_booking_out(booking: Booking, hotel: Hotel = None) -> BookingOut:
    is_simulated = bool(
        (booking.payment_reference and (
            booking.payment_reference.startswith("demo_pay_")
            or booking.payment_reference.startswith("SIMULATED_")
        ))
        or (booking.payment_order_id and booking.payment_order_id.startswith("demo_order_"))
    )
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
        is_simulated=is_simulated,
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
    Creates an order (real Razorpay order if configured, or simulated demo order
    if ENABLE_DEMO_PAYMENT is enabled in dev/test) for an existing pending booking.
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
    Verifies payment completion:
    - Real Razorpay verification when the order was created via Razorpay.
    - Explicit simulated verification when the order was created in demo mode.
    - Rejects demo verification if running in production or if demo payments disabled.
    - Leaves booking as 'Pending Payment' on any verification failure.
    """
    booking = db.query(Booking).filter(Booking.booking_reference == booking_reference).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if not booking.payment_order_id or booking.payment_order_id != payload.razorpay_order_id:
        raise HTTPException(status_code=400, detail="This payment does not match this booking's order")

    # If the booking's order is a demo order, verify via the explicit simulated path
    if is_demo_order(booking.payment_order_id):
        if not is_demo_payment_allowed():
            raise HTTPException(
                status_code=403,
                detail="Simulated payments are not permitted in this environment.",
            )

        try:
            is_valid = verify_demo_payment(
                payload.razorpay_order_id,
                payload.razorpay_payment_id,
                payload.razorpay_signature,
            )
        except PaymentError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if not is_valid:
            raise HTTPException(status_code=400, detail="Payment verification failed")

        booking.status = "Confirmed"
        booking.payment_reference = payload.razorpay_payment_id
        db.add(booking)
        db.commit()
        db.refresh(booking)

        hotel = db.query(Hotel).filter(Hotel.id == booking.hotel_id).first()
        return _to_booking_out(booking, hotel)

    # Real Razorpay verification
    try:
        is_valid = verify_payment_signature(
            payload.razorpay_order_id,
            payload.razorpay_payment_id,
            payload.razorpay_signature,
        )
    except PaymentError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not is_valid:
        raise HTTPException(status_code=400, detail="Payment verification failed")

    booking.status = "Confirmed"
    booking.payment_reference = payload.razorpay_payment_id
    db.add(booking)
    db.commit()
    db.refresh(booking)

    hotel = db.query(Hotel).filter(Hotel.id == booking.hotel_id).first()
    return _to_booking_out(booking, hotel)
