# app/models/booking.py
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Date, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_reference = Column(String(32), unique=True, index=True, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Generic across listing types -- exactly one of hotel_id/package_id is
    # set, discriminated by listing_type. Package bookings aren't created by
    # any flow yet (no package booking UI exists), but the columns exist now
    # so adding that flow later doesn't require another migration.
    listing_type = Column(String(16), nullable=False, default="hotel")  # "hotel" | "package"
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    destination_id = Column(Integer, ForeignKey("destinations.id"), nullable=True)
    session_id = Column(String(64), nullable=True)  # links back to the AI conversation, if any

    guest_name = Column(String(256), nullable=False)
    guest_email = Column(String(256), nullable=False)
    guest_phone = Column(String(64), nullable=False)

    check_in_date = Column(Date, nullable=False)
    check_out_date = Column(Date, nullable=False)
    num_rooms = Column(Integer, nullable=False, default=1)
    num_guests = Column(Integer, nullable=False, default=1)
    special_requests = Column(Text, nullable=True)

    total_amount = Column(Float, nullable=True)
    currency = Column(String(8), nullable=False, default="INR")

    # Booking lifecycle status -- kept separate from payment status so a
    # payment gateway can be plugged in later purely by adding rows to a
    # future `payments` table (FK'd to booking_id) without touching this
    # table's shape or the booking-creation flow itself.
    # Values: "Pending Payment" | "Confirmed" | "Cancelled"
    status = Column(String(32), nullable=False, default="Pending Payment")

    # Reserved for the future payment module -- intentionally unused today.
    payment_reference = Column(String(128), nullable=True)   # Razorpay payment_id once paid
    payment_order_id = Column(String(128), nullable=True)    # Razorpay order_id, set when checkout starts

    created_at = Column(DateTime(timezone=True), server_default=func.now())
