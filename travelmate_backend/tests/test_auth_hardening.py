import pytest
from fastapi import HTTPException

from app.models.user import User
from app.services.auth_utils import (
    hash_password,
    create_refresh_token,
    verify_and_rotate_refresh_token,
    revoke_refresh_token,
    create_password_reset_token,
    consume_password_reset_token,
    require_role,
)


def _make_user(db_session, role="customer", email="tester@example.com"):
    user = User(
        username="tester",
        email=email,
        password=hash_password("hunter2"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_refresh_token_issue_and_verify(db_session):
    user = _make_user(db_session)
    raw_token = create_refresh_token(db_session, user.id)

    verified_user = verify_and_rotate_refresh_token(db_session, raw_token)
    assert verified_user is not None
    assert verified_user.id == user.id


def test_revoked_refresh_token_cannot_be_used(db_session):
    user = _make_user(db_session)
    raw_token = create_refresh_token(db_session, user.id)

    assert revoke_refresh_token(db_session, raw_token) is True
    assert verify_and_rotate_refresh_token(db_session, raw_token) is None


def test_garbage_refresh_token_is_rejected(db_session):
    _make_user(db_session)
    assert verify_and_rotate_refresh_token(db_session, "not-a-real-token") is None


def test_password_reset_token_is_single_use(db_session):
    user = _make_user(db_session)
    raw_token = create_password_reset_token(db_session, user.id)

    first_use = consume_password_reset_token(db_session, raw_token)
    assert first_use is not None
    assert first_use.id == user.id

    second_use = consume_password_reset_token(db_session, raw_token)
    assert second_use is None


def test_expired_reset_token_is_rejected(db_session):
    from datetime import datetime, timedelta
    from app.models.password_reset_token import PasswordResetToken
    from app.services.auth_utils import _hash_opaque_token

    user = _make_user(db_session)
    raw_token = "already-expired-token"
    record = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_opaque_token(raw_token),
        expires_at=datetime.utcnow() - timedelta(minutes=1),
        used=False,
    )
    db_session.add(record)
    db_session.commit()

    assert consume_password_reset_token(db_session, raw_token) is None


def test_require_role_allows_matching_role(db_session):
    admin = _make_user(db_session, role="admin", email="admin@example.com")
    checker = require_role("admin")
    # require_role's inner function's only real dependency is the resolved
    # User -- calling it directly with an explicit user exercises the same
    # role-check logic FastAPI's DI would run.
    result = checker(user=admin)
    assert result.id == admin.id


def test_require_role_rejects_non_matching_role(db_session):
    customer = _make_user(db_session, role="customer", email="customer@example.com")
    checker = require_role("admin")

    with pytest.raises(HTTPException) as exc_info:
        checker(user=customer)

    assert exc_info.value.status_code == 403


def test_auth_login_invalid_credentials_returns_400(db_session):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            # Non-existent user
            res = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
            assert res.status_code == 400
            assert "Invalid credentials" in res.json().get("detail", "")

            # Existing user, wrong password
            _make_user(db_session, email="known@example.com")
            res2 = client.post("/auth/login", json={"email": "known@example.com", "password": "wrongpassword"})
            assert res2.status_code == 400
            assert "Invalid credentials" in res2.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_auth_login_successful_traveller_returns_schema(db_session):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            user = _make_user(db_session, role="customer", email="traveller@example.com")
            res = client.post("/auth/login", json={"email": "traveller@example.com", "password": "hunter2"})
            assert res.status_code == 200
            data = res.json()
            assert "token" in data and len(data["token"]) > 0
            assert "refresh_token" in data and len(data["refresh_token"]) > 0
            assert data["role"] == "customer"
            assert data["email"] == "traveller@example.com"
            assert data["username"] == user.username
    finally:
        app.dependency_overrides.clear()


def test_auth_login_partner_returns_partner_role(db_session):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            _make_user(db_session, role="partner", email="partner@example.com")
            res = client.post("/auth/login", json={"email": "partner@example.com", "password": "hunter2"})
            assert res.status_code == 200
            data = res.json()
            assert "token" in data
            assert data["role"] == "partner"
    finally:
        app.dependency_overrides.clear()

