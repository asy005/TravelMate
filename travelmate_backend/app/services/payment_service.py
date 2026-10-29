# app/services/payment_service.py
"""
Razorpay payment integration with safe demo simulation support.
- Production safety: Demo payments are strictly prohibited in production,
  regardless of configuration.
- Real credentials: When valid Razorpay credentials are configured, standard
  Razorpay order creation and HMAC-SHA256 signature verification run.
- Placeholder detection: Missing or placeholder keys are detected without
  calling the Razorpay API.
- Simulated demo flow: When ENABLE_DEMO_PAYMENT is enabled in development/test,
  orders and verifications follow an explicit simulated flow and are clearly
  labelled as simulated.
"""
import hashlib
import hmac
import time
from typing import Optional

import razorpay

from app.config import settings

PLACEHOLDER_KEY_PATTERNS = [
    "your_key",
    "placeholder",
    "dummy",
    "xxx",
    "todo",
    "rzp_test_your_key_id",
    "your_secret",
]


class PaymentError(Exception):
    pass


def is_razorpay_configured() -> bool:
    """
    Returns True only if both RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set
    and do not match placeholder patterns.
    """
    key_id = (settings.RAZORPAY_KEY_ID or "").strip()
    key_secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
    if not key_id or not key_secret:
        return False

    key_id_lower = key_id.lower()
    key_secret_lower = key_secret.lower()

    for pattern in PLACEHOLDER_KEY_PATTERNS:
        if pattern in key_id_lower or pattern in key_secret_lower:
            return False

    return True


def is_demo_payment_allowed() -> bool:
    """
    Demo payment is only allowed in development or test environments, and only
    when ENABLE_DEMO_PAYMENT is explicitly True. It is impossible in production.
    """
    env = (getattr(settings, "ENVIRONMENT", "") or "development").strip().lower()
    if env in ("production", "prod"):
        return False
    return bool(getattr(settings, "ENABLE_DEMO_PAYMENT", False))


def is_demo_order(order_id: Optional[str]) -> bool:
    return bool(order_id and str(order_id).startswith("demo_order_"))


def _client() -> razorpay.Client:
    if not is_razorpay_configured():
        raise PaymentError("Razorpay is not configured (missing or placeholder credentials).")
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_order(amount_inr: float, receipt: str) -> dict:
    """
    Creates either a real Razorpay order or a simulated demo order.
    Amount is in INR (rupees); returned amount is in paise.
    """
    amount_paise = int(round(amount_inr * 100))

    if is_razorpay_configured():
        client = _client()
        try:
            order = client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "payment_capture": 1,
            })
        except Exception as e:
            raise PaymentError(f"Failed to create Razorpay order: {e}")

        return {
            "order_id": order["id"],
            "amount": amount_paise,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
            "is_demo": False,
            "simulation_notice": None,
        }

    # If Razorpay is not configured, check if demo mode is permitted
    if is_demo_payment_allowed():
        demo_order_id = f"demo_order_{receipt}_{int(time.time())}"
        return {
            "order_id": demo_order_id,
            "amount": amount_paise,
            "currency": "INR",
            "key_id": "demo_key_simulated",
            "is_demo": True,
            "simulation_notice": "SIMULATED PAYMENT: Demo mode active. No actual funds will be transferred.",
        }

    env = (getattr(settings, "ENVIRONMENT", "") or "development").strip().lower()
    if env in ("production", "prod"):
        raise PaymentError("Razorpay is not configured. Demo payments are strictly prohibited in production.")
    raise PaymentError("Razorpay is not configured and ENABLE_DEMO_PAYMENT is disabled.")


def verify_demo_payment(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Verifies a simulated demo payment.
    Requires demo mode to be permitted, payment_id to be explicitly demo-prefixed,
    and signature to match the demo expected signature.
    """
    if not is_demo_payment_allowed():
        raise PaymentError("Simulated payments are not permitted in this environment.")

    if not is_demo_order(order_id):
        return False

    if not payment_id or not payment_id.startswith("demo_pay_"):
        return False

    expected_sig = f"demo_sig_{order_id}"
    return hmac.compare_digest(expected_sig, signature)


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Standard Razorpay checkout verification: HMAC-SHA256 of
    "{order_id}|{payment_id}" using the account's key secret, compared to
    the signature returned by Razorpay's checkout callback.
    """
    if is_demo_order(order_id):
        raise PaymentError("Cannot verify simulated demo order with real Razorpay verification.")

    if not is_razorpay_configured() or not settings.RAZORPAY_KEY_SECRET:
        raise PaymentError("Razorpay is not configured (missing RAZORPAY_KEY_SECRET).")

    payload = f"{order_id}|{payment_id}".encode()
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)
