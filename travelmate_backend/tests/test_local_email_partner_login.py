"""
Regression test: partner users with .local email addresses must be able to
log in without a 422 Unprocessable Entity error.

Before the CompatibleEmail fix in user_schema.py, `email_validator` would
reject .local domains (non-IANA TLD) with a validation error, causing FastAPI
to return HTTP 422 before the route even ran.

This test exercises the full request path through the TestClient (so the
schema validation layer runs) to confirm .local addresses are accepted.
"""
import pytest
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.services.auth_utils import create_token, hash_password

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker


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
# .local email login tests
# ---------------------------------------------------------------------------

LOCAL_EMAIL_VARIANTS = [
    "partner@company.local",
    "admin@travelmates.local",
    "info@resort.local",
    "Partner@Company.LOCAL",          # case-insensitive
]


@pytest.mark.parametrize("email", LOCAL_EMAIL_VARIANTS)
def test_local_email_schema_accepts_without_422(client, db, email):
    """
    Posting a .local email to /auth/login must never return 422.

    We expect 400 (invalid credentials, since no user exists yet) rather
    than 422 (schema rejection).  422 would mean CompatibleEmail is still
    rejecting .local domains.
    """
    res = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert res.status_code != 422, (
        f".local email '{email}' was rejected with 422 (schema validation error). "
        f"Response: {res.text}"
    )
    # Expected: 400 (bad credentials), not 422 (schema error)
    assert res.status_code == 400, (
        f"Expected 400 (invalid credentials) for non-existent user, got {res.status_code}: {res.text}"
    )


def test_local_email_partner_full_login_flow(client, db):
    """
    A partner user registered with a .local email can log in and receives
    a valid token with role='partner'.
    """
    local_email = "operator@mountains.local"

    # Seed: create partner user with .local email directly in DB
    user = User(
        username="mountains_op",
        email=local_email,
        password=hash_password("SecurePass!1"),
        role="partner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Login must NOT return 422 (schema error)
    res = client.post(
        "/auth/login",
        json={"email": local_email, "password": "SecurePass!1"},
    )
    assert res.status_code == 200, (
        f"Partner .local login failed with {res.status_code}: {res.text}"
    )

    data = res.json()
    assert "token" in data and len(data["token"]) > 0, "Access token missing"
    assert "refresh_token" in data and len(data["refresh_token"]) > 0, "Refresh token missing"
    assert data["role"] == "partner", f"Expected role='partner', got {data['role']!r}"
    assert data["email"] == local_email.lower(), (
        f"Expected normalized email {local_email.lower()!r}, got {data['email']!r}"
    )


def test_local_email_signup_roundtrip(client, db):
    """
    A new user can sign up with a .local email and immediately log in.
    """
    email = "newpartner@agency.local"

    # Signup
    signup_res = client.post(
        "/auth/signup",
        json={"username": "agency_partner", "email": email, "password": "Pass@word1"},
    )
    assert signup_res.status_code == 200, (
        f"Signup with .local email failed: {signup_res.text}"
    )
    assert "token" in signup_res.json()

    # Login
    login_res = client.post(
        "/auth/login",
        json={"email": email, "password": "Pass@word1"},
    )
    assert login_res.status_code == 200, (
        f"Login with .local email failed: {login_res.text}"
    )
    assert login_res.json()["email"] == email.lower()
