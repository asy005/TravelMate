# app/services/payment_service.py
"""
Razorpay integration, kept deliberately thin: this module only creates
orders and verifies payment signatures. It does not know about bookings --
booking_routes.py is what ties a Razorpay order/payment back to a specific
Booking row, using the existing `status`/`payment_reference` fields
(see the extension-point note in models/booking.py and booking_service.py).
No new tables were needed to add this.
"""
import hmac
import hashlib
import razorpay

from app.config import settings


class PaymentError(Exception):
    pass


def _client() -> razorpay.Client:
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise PaymentError("Razorpay is not configured (missing RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET).")
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_order(amount_inr: float, receipt: str) -> dict:
    """
    Amount is in INR (rupees); Razorpay expects the smallest currency unit
    (paise), so we convert here -- callers always deal in rupees.
    """
    client = _client()
    amount_paise = int(round(amount_inr * 100))

    try:
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1,  # auto-capture on successful authorization
        })
    except Exception as e:  # razorpay raises its own error types; keep this generic and safe
        raise PaymentError(f"Failed to create Razorpay order: {e}")

    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
    }


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Standard Razorpay checkout verification: HMAC-SHA256 of
    "{order_id}|{payment_id}" using the account's key secret, compared to
    the signature returned by Razorpay's checkout callback.
    """
    if not settings.RAZORPAY_KEY_SECRET:
        raise PaymentError("Razorpay is not configured (missing RAZORPAY_KEY_SECRET).")

    payload = f"{order_id}|{payment_id}".encode()
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)
