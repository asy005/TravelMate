"""
Focused tests for safe demo payment and Razorpay integration:
- Placeholder and missing credential detection
- Production prohibition: demo payment is strictly impossible in production
- Explicit simulated demo flow when ENABLE_DEMO_PAYMENT is enabled in dev/test
- Real Razorpay order creation and HMAC-SHA256 signature verification preservation
- Route-level payment order creation and signature verification
"""
import hashlib
import hmac
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.payment_service import (
    PaymentError,
    create_order,
    is_demo_order,
    is_demo_payment_allowed,
    is_razorpay_configured,
    verify_demo_payment,
    verify_payment_signature,
)


# ---------------------------------------------------------------------------
# 1. CREDENTIAL DETECTION TESTS
# ---------------------------------------------------------------------------

def test_is_razorpay_configured_detects_missing():
    with patch.object(settings, "RAZORPAY_KEY_ID", ""), patch.object(settings, "RAZORPAY_KEY_SECRET", ""):
        assert is_razorpay_configured() is False

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_valid123"), patch.object(settings, "RAZORPAY_KEY_SECRET", ""):
        assert is_razorpay_configured() is False


def test_is_razorpay_configured_detects_placeholders():
    placeholders = [
        ("rzp_test_your_key_id", "your_secret"),
        ("rzp_test_your_key_id", "placeholder_secret"),
        ("rzp_test_dummy_key", "dummy_secret"),
        ("rzp_test_xxx", "xxx"),
    ]
    for key_id, secret in placeholders:
        with patch.object(settings, "RAZORPAY_KEY_ID", key_id), patch.object(settings, "RAZORPAY_KEY_SECRET", secret):
            assert is_razorpay_configured() is False, f"Failed for {key_id}"


def test_is_razorpay_configured_accepts_valid_credentials():
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_9876543210abcd"), patch.object(settings, "RAZORPAY_KEY_SECRET", "super_secret_production_key_12345"):
        assert is_razorpay_configured() is True


# ---------------------------------------------------------------------------
# 2. DEMO PAYMENT ALLOWANCE & PRODUCTION PROHIBITION
# ---------------------------------------------------------------------------

def test_demo_payment_prohibited_in_production():
    """Demo payment must NEVER be allowed in production, regardless of flag."""
    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(settings, "ENABLE_DEMO_PAYMENT", True):
        assert is_demo_payment_allowed() is False

    with patch.object(settings, "ENVIRONMENT", "prod"), patch.object(settings, "ENABLE_DEMO_PAYMENT", True):
        assert is_demo_payment_allowed() is False


def test_demo_payment_allowed_only_in_dev_and_test_when_enabled():
    with patch.object(settings, "ENVIRONMENT", "development"), patch.object(settings, "ENABLE_DEMO_PAYMENT", True):
        assert is_demo_payment_allowed() is True

    with patch.object(settings, "ENVIRONMENT", "test"), patch.object(settings, "ENABLE_DEMO_PAYMENT", True):
        assert is_demo_payment_allowed() is True

    with patch.object(settings, "ENVIRONMENT", "development"), patch.object(settings, "ENABLE_DEMO_PAYMENT", False):
        assert is_demo_payment_allowed() is False


# ---------------------------------------------------------------------------
# 3. ORDER CREATION TESTS
# ---------------------------------------------------------------------------

def test_create_order_demo_flow():
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_your_key_id"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "your_secret"), \
         patch.object(settings, "ENVIRONMENT", "development"), \
         patch.object(settings, "ENABLE_DEMO_PAYMENT", True):

        order = create_order(amount_inr=1500.0, receipt="TM-TEST001")
        assert order["is_demo"] is True
        assert order["order_id"].startswith("demo_order_TM-TEST001")
        assert order["amount"] == 150000  # paise
        assert order["currency"] == "INR"
        assert "simulation_notice" in order
        assert "SIMULATED" in order["simulation_notice"]


def test_create_order_strictly_fails_in_production_without_real_keys():
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_your_key_id"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "your_secret"), \
         patch.object(settings, "ENVIRONMENT", "production"), \
         patch.object(settings, "ENABLE_DEMO_PAYMENT", True):

        with pytest.raises(PaymentError) as exc_info:
            create_order(amount_inr=1500.0, receipt="TM-PROD001")
        assert "prohibited in production" in str(exc_info.value).lower()


def test_create_order_fails_when_demo_disabled_and_no_real_keys():
    with patch.object(settings, "RAZORPAY_KEY_ID", ""), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", ""), \
         patch.object(settings, "ENVIRONMENT", "development"), \
         patch.object(settings, "ENABLE_DEMO_PAYMENT", False):

        with pytest.raises(PaymentError) as exc_info:
            create_order(amount_inr=1500.0, receipt="TM-FAIL001")
        assert "disabled" in str(exc_info.value).lower() or "not configured" in str(exc_info.value).lower()


def test_create_order_real_razorpay_preserved():
    mock_client = MagicMock()
    mock_client.order.create.return_value = {"id": "order_real_12345"}

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_realvalidkey12"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "realvalidsecret456"), \
         patch("app.services.payment_service.razorpay.Client", return_value=mock_client):

        order = create_order(amount_inr=2000.0, receipt="TM-REAL001")
        assert order["is_demo"] is False
        assert order["order_id"] == "order_real_12345"
        assert order["amount"] == 200000
        mock_client.order.create.assert_called_once_with({
            "amount": 200000,
            "currency": "INR",
            "receipt": "TM-REAL001",
            "payment_capture": 1,
        })


# ---------------------------------------------------------------------------
# 4. SIGNATURE VERIFICATION TESTS
# ---------------------------------------------------------------------------

def test_verify_payment_signature_real_razorpay():
    key_secret = "test_secret_for_hmac"
    order_id = "order_rzp_999"
    payment_id = "pay_rzp_888"

    payload = f"{order_id}|{payment_id}".encode()
    valid_sig = hmac.new(key_secret.encode(), payload, hashlib.sha256).hexdigest()

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_realvalidkey12"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", key_secret):

        assert verify_payment_signature(order_id, payment_id, valid_sig) is True
        assert verify_payment_signature(order_id, payment_id, "tampered_signature") is False


def test_verify_payment_signature_rejects_demo_order():
    """Demo orders must never be verified through the real Razorpay HMAC function."""
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_realvalidkey12"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "secret"):
        with pytest.raises(PaymentError) as exc_info:
            verify_payment_signature("demo_order_123", "pay_123", "sig_123")
        assert "Cannot verify simulated demo order" in str(exc_info.value)


def test_verify_demo_payment_flow():
    order_id = "demo_order_TM-123_456"
    payment_id = "demo_pay_1700000000"
    valid_sig = f"demo_sig_{order_id}"

    with patch.object(settings, "ENVIRONMENT", "development"), patch.object(settings, "ENABLE_DEMO_PAYMENT", True):
        assert verify_demo_payment(order_id, payment_id, valid_sig) is True
        assert verify_demo_payment(order_id, payment_id, "wrong_sig") is False
        assert verify_demo_payment(order_id, "real_pay_123", valid_sig) is False


def test_verify_demo_payment_fails_in_production():
    order_id = "demo_order_TM-123_456"
    payment_id = "demo_pay_1700000000"
    valid_sig = f"demo_sig_{order_id}"

    with patch.object(settings, "ENVIRONMENT", "production"), patch.object(settings, "ENABLE_DEMO_PAYMENT", True):
        with pytest.raises(PaymentError) as exc_info:
            verify_demo_payment(order_id, payment_id, valid_sig)
        assert "not permitted in this environment" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 5. ROUTE-LEVEL DEMO PAYMENT INTEGRATION TESTS
# ---------------------------------------------------------------------------

def test_booking_demo_payment_route_lifecycle():
    client = TestClient(app)

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_your_key_id"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "your_secret"), \
         patch.object(settings, "ENVIRONMENT", "development"), \
         patch.object(settings, "ENABLE_DEMO_PAYMENT", True):

        # 1. Create booking
        booking_res = client.post("/bookings/", json={
            "hotel_id": 1,
            "guest_name": "Demo Traveler",
            "guest_email": "traveler@example.com",
            "guest_phone": "+919999999999",
            "check_in_date": "2026-11-01",
            "check_out_date": "2026-11-04",
            "num_rooms": 1,
            "num_guests": 2,
        })
        assert booking_res.status_code == 200, booking_res.text
        booking_data = booking_res.json()
        ref = booking_data["booking_reference"]
        assert booking_data["status"] == "Pending Payment"

        # 2. Create demo payment order
        order_res = client.post(f"/bookings/{ref}/create-order")
        assert order_res.status_code == 200, order_res.text
        order_data = order_res.json()
        assert order_data["is_demo"] is True
        assert order_data["order_id"].startswith("demo_order_")

        # 3. Verify with invalid signature -> rejected, booking remains Pending Payment
        bad_verify = client.post(f"/bookings/{ref}/verify-payment", json={
            "razorpay_order_id": order_data["order_id"],
            "razorpay_payment_id": "demo_pay_111",
            "razorpay_signature": "invalid_sig",
        })
        assert bad_verify.status_code == 400

        check_res = client.get(f"/bookings/{ref}")
        assert check_res.json()["status"] == "Pending Payment"

        # 4. Verify with valid demo signature -> succeeds, Confirmed, is_simulated=True
        good_verify = client.post(f"/bookings/{ref}/verify-payment", json={
            "razorpay_order_id": order_data["order_id"],
            "razorpay_payment_id": "demo_pay_111",
            "razorpay_signature": f"demo_sig_{order_data['order_id']}",
        })
        assert good_verify.status_code == 200, good_verify.text
        confirmed_data = good_verify.json()
        assert confirmed_data["status"] == "Confirmed"
        assert confirmed_data["is_simulated"] is True
        assert confirmed_data["payment_reference"] == "demo_pay_111"
