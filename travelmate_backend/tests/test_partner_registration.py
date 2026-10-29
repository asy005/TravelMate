"""
Tests for partner registration (Task 2).

Verifies that:
- Authenticated users can register as partners (POST /partners/register).
- Unauthenticated requests receive 401 (not bypassed).
- Expired / missing token returns 401, not 403 or 500.
- Location fields (address, city, state, postal_code) are persisted correctly.
- Duplicate registration returns 400.
- GET /partners/me returns 401 without a token.
- Photo upload endpoint validates file type and size.
"""
import io
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.partner import Partner
from app.services.auth_utils import create_token, hash_password


# ---------------------------------------------------------------------------
# In-memory DB fixture
# ---------------------------------------------------------------------------
@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(db_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _create_user_and_token(db, email="partner@test.com"):
    u = User(
        username=email.split("@")[0],
        email=email,
        password=hash_password("password123"),
        role="customer",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    token = create_token({"user_id": u.id})
    return u, token


_VALID_PAYLOAD = {
    "business_name": "Sunshine Resorts",
    "partner_type": "resort",
    "contact_email": "info@sunshine.com",
    "contact_phone": "+91 98765 43210",
    "description": "Luxury resort in Goa",
    "address": "123 Beach Road",
    "city": "Panaji",
    "state": "Goa",
    "postal_code": "403001",
}


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------
class TestPartnerAuth:
    def test_register_without_token_returns_401(self, client, db):
        res = client.post("/partners/register", json=_VALID_PAYLOAD)
        assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.text}"

    def test_get_me_without_token_returns_401(self, client, db):
        res = client.get("/partners/me")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.text}"

    def test_register_with_invalid_token_returns_401(self, client, db):
        res = client.post(
            "/partners/register",
            json=_VALID_PAYLOAD,
            headers={"Authorization": "Bearer totally_fake_token"},
        )
        assert res.status_code == 401

    def test_register_with_valid_token_succeeds(self, client, db):
        _, token = _create_user_and_token(db)
        res = client.post(
            "/partners/register",
            json=_VALID_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["business_name"] == "Sunshine Resorts"
        assert data["status"] == "approved"

    def test_get_me_with_valid_token_after_registration(self, client, db):
        _, token = _create_user_and_token(db)
        client.post(
            "/partners/register",
            json=_VALID_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        res = client.get(
            "/partners/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["business_name"] == "Sunshine Resorts"

    def test_get_me_before_registration_returns_403(self, client, db):
        """User is authenticated but not yet a partner — should get 403."""
        _, token = _create_user_and_token(db)
        res = client.get(
            "/partners/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403


# ---------------------------------------------------------------------------
# Location persistence tests
# ---------------------------------------------------------------------------
class TestLocationPersistence:
    def test_location_fields_stored_correctly(self, client, db):
        _, token = _create_user_and_token(db)
        res = client.post(
            "/partners/register",
            json=_VALID_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["address"] == "123 Beach Road"
        assert data["city"] == "Panaji"
        assert data["state"] == "Goa"
        assert data["postal_code"] == "403001"

    def test_location_fields_reflected_in_db(self, client, db):
        u, token = _create_user_and_token(db)
        client.post(
            "/partners/register",
            json=_VALID_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        db.expire_all()
        partner = db.query(Partner).filter(Partner.owner_user_id == u.id).first()
        assert partner is not None
        assert partner.city == "Panaji"
        assert partner.state == "Goa"
        assert partner.postal_code == "403001"

    def test_registration_without_location_succeeds(self, client, db):
        """Location fields are optional — registration without them must work."""
        _, token = _create_user_and_token(db)
        minimal = {
            "business_name": "Minimal Inc",
            "partner_type": "hotel",
        }
        res = client.post(
            "/partners/register",
            json=minimal,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["city"] is None


# ---------------------------------------------------------------------------
# Duplicate registration
# ---------------------------------------------------------------------------
class TestDuplicateRegistration:
    def test_duplicate_registration_returns_400(self, client, db):
        _, token = _create_user_and_token(db)
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/partners/register", json=_VALID_PAYLOAD, headers=headers)
        res2 = client.post("/partners/register", json=_VALID_PAYLOAD, headers=headers)
        assert res2.status_code == 400
        assert "already registered" in res2.json()["detail"]

    def test_invalid_partner_type_returns_400(self, client, db):
        _, token = _create_user_and_token(db)
        bad = dict(_VALID_PAYLOAD, partner_type="spaceship")
        res = client.post(
            "/partners/register",
            json=bad,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# Photo upload validation tests
# ---------------------------------------------------------------------------
class TestPhotoUpload:
    def _make_jpeg_bytes(self, size_bytes: int = 1024) -> bytes:
        """Return minimal valid JPEG bytes (SOI + EOI markers)."""
        # A real JPEG always starts with FF D8 FF and ends with FF D9
        header = b"\xff\xd8\xff\xe0" + b"\x00" * 16  # APP0 segment stub
        padding = b"\x00" * max(0, size_bytes - len(header) - 2)
        footer = b"\xff\xd9"
        return header + padding + footer

    def test_upload_jpeg_succeeds(self, client, db):
        _, token = _create_user_and_token(db)
        data = self._make_jpeg_bytes(512)
        res = client.post(
            "/partners/upload-photo",
            files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert "url" in body
        assert body["url"].startswith("/uploads/partners/")
        # Cleanup
        fname = body["filename"]
        upload_path = os.path.join(
            os.path.dirname(__file__), "..", "uploads", "partners", fname
        )
        if os.path.exists(upload_path):
            os.remove(upload_path)

    def test_upload_without_auth_returns_401(self, client, db):
        data = self._make_jpeg_bytes(512)
        res = client.post(
            "/partners/upload-photo",
            files={"file": ("test.jpg", io.BytesIO(data), "image/jpeg")},
        )
        assert res.status_code == 401

    def test_upload_unsupported_type_returns_415(self, client, db):
        _, token = _create_user_and_token(db)
        res = client.post(
            "/partners/upload-photo",
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 415

    def test_upload_oversized_file_returns_413(self, client, db):
        _, token = _create_user_and_token(db)
        # 6 MB > 5 MB limit
        big_data = b"\xff\xd8\xff\xe0" + b"\x00" * (6 * 1024 * 1024)
        res = client.post(
            "/partners/upload-photo",
            files={"file": ("big.jpg", io.BytesIO(big_data), "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 413

    def test_upload_png_succeeds(self, client, db):
        _, token = _create_user_and_token(db)
        # Minimal PNG: 8-byte signature + IHDR + IDAT + IEND (just enough bytes)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n"  # PNG signature
            + b"\x00" * 100        # stub chunks
        )
        res = client.post(
            "/partners/upload-photo",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        fname = res.json().get("filename", "")
        upload_path = os.path.join(
            os.path.dirname(__file__), "..", "uploads", "partners", fname
        )
        if os.path.exists(upload_path):
            os.remove(upload_path)


# ---------------------------------------------------------------------------
# Multiple photos and edge cases
# ---------------------------------------------------------------------------
class TestMultiplePhotosAndSanitization:
    def test_registration_with_empty_strings_sanitizes_contact_email_to_none(self, client, db):
        _, token = _create_user_and_token(db)
        payload = {
            "business_name": "Coorg Homestay",
            "partner_type": "homestay",
            "contact_email": "",  # Empty string from frontend input
            "contact_phone": "",
            "description": "",
            "address": "",
            "city": "",
            "state": "",
            "postal_code": "",
        }
        res = client.post(
            "/partners/register",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["business_name"] == "Coorg Homestay"
        assert data["contact_email"] is None

    def test_registration_with_multiple_photos_persisted(self, client, db):
        u, token = _create_user_and_token(db)
        payload = dict(_VALID_PAYLOAD, photos=[
            "/uploads/partners/photo1.jpg",
            "/uploads/partners/photo2.jpg",
            "/uploads/partners/photo3.jpg",
        ])
        res = client.post(
            "/partners/register",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["photos"]) == 3
        assert data["photos"][0] == "/uploads/partners/photo1.jpg"

        # Verify DB persistence
        db.expire_all()
        partner = db.query(Partner).filter(Partner.owner_user_id == u.id).first()
        assert partner is not None
        assert partner.photos == [
            "/uploads/partners/photo1.jpg",
            "/uploads/partners/photo2.jpg",
            "/uploads/partners/photo3.jpg",
        ]

    def test_blank_business_name_returns_422(self, client, db):
        _, token = _create_user_and_token(db)
        bad = dict(_VALID_PAYLOAD, business_name="   ")
        res = client.post(
            "/partners/register",
            json=bad,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    def test_uploaded_photo_accessible_via_static_mount(self, client, db):
        _, token = _create_user_and_token(db)
        header = b"\xff\xd8\xff\xe0" + b"\x00" * 16
        footer = b"\xff\xd9"
        jpeg_data = header + footer

        res = client.post(
            "/partners/upload-photo",
            files={"file": ("view.jpg", io.BytesIO(jpeg_data), "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        photo_url = res.json()["url"]
        fname = res.json()["filename"]

        # Test GET on the static mount
        get_res = client.get(photo_url)
        assert get_res.status_code == 200
        assert get_res.content == jpeg_data

        # Cleanup
        upload_path = os.path.join(
            os.path.dirname(__file__), "..", "uploads", "partners", fname
        )
        if os.path.exists(upload_path):
            os.remove(upload_path)
