# app/schemas/booking_schema.py
from datetime import date
from typing import Optional
from pydantic import BaseModel, EmailStr


class BookingCreateIn(BaseModel):
    hotel_id: int
    destination_id: Optional[int] = None
    session_id: Optional[str] = None

    guest_name: str
    guest_email: EmailStr
    guest_phone: str

    check_in_date: date
    check_out_date: date
    num_rooms: int = 1
    num_guests: int = 1
    special_requests: Optional[str] = None


class BookingOut(BaseModel):
    booking_reference: str
    status: str
    hotel_id: int
    hotel_name: Optional[str] = None
    guest_name: str
    guest_email: str
    guest_phone: str
    check_in_date: date
    check_out_date: date
    num_rooms: int
    num_guests: int
    special_requests: Optional[str] = None
    total_amount: Optional[float] = None
    currency: str
    payment_reference: Optional[str] = None
    is_simulated: Optional[bool] = False

    class Config:
        orm_mode = True


class PaymentOrderOut(BaseModel):
    order_id: str
    amount: int  # paise
    currency: str
    key_id: str
    booking_reference: str
    is_demo: bool = False
    simulation_notice: Optional[str] = None


class PaymentVerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
