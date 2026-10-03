import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer

from app.database import get_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.password_reset_token import PasswordResetToken
from app.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = 60          # 1 hour (tightened in M2; was 24h)
REFRESH_TOKEN_EXPIRE_DAYS = 30
PASSWORD_RESET_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# --------------------------
# PASSWORD HASHING
# --------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# --------------------------
# ACCESS TOKEN (JWT)
# --------------------------
def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# --------------------------
# REFRESH TOKENS
# --------------------------
def _hash_opaque_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_refresh_token(db: Session, user_id: int) -> str:
    """
    Returns the raw refresh token (given to the client). Only its hash is
    stored server-side, so a leaked database dump doesn't hand out usable
    refresh tokens.
    """
    raw_token = secrets.token_urlsafe(48)
    record = RefreshToken(
        user_id=user_id,
        token_hash=_hash_opaque_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        revoked=False,
    )
    db.add(record)
    db.commit()
    return raw_token


def verify_and_rotate_refresh_token(db: Session, raw_token: str) -> Optional[User]:
    """
    Validates a refresh token and returns the associated user, or None if
    invalid/expired/revoked. Does not rotate/revoke by itself -- callers
    (the /auth/refresh endpoint) decide whether to issue a new access token.
    """
    token_hash = _hash_opaque_token(raw_token)
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not record or record.revoked:
        return None
    if record.expires_at < datetime.utcnow():
        return None

    return db.query(User).filter(User.id == record.user_id).first()


def revoke_refresh_token(db: Session, raw_token: str) -> bool:
    token_hash = _hash_opaque_token(raw_token)
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not record:
        return False
    record.revoked = True
    db.add(record)
    db.commit()
    return True


# --------------------------
# PASSWORD RESET TOKENS
# --------------------------
def create_password_reset_token(db: Session, user_id: int) -> str:
    raw_token = secrets.token_urlsafe(32)
    record = PasswordResetToken(
        user_id=user_id,
        token_hash=_hash_opaque_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
        used=False,
    )
    db.add(record)
    db.commit()
    return raw_token


def consume_password_reset_token(db: Session, raw_token: str) -> Optional[User]:
    token_hash = _hash_opaque_token(raw_token)
    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()

    if not record or record.used or record.expires_at < datetime.utcnow():
        return None

    record.used = True
    db.add(record)
    db.commit()

    return db.query(User).filter(User.id == record.user_id).first()


# --------------------------
# GET CURRENT USER
# --------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id: int = payload.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


def get_current_user_optional(
    token: Optional[str] = Depends(OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)),
    db: Session = Depends(get_db),
):
    """
    Same as get_current_user, but returns None instead of raising when no/invalid
    token is provided -- used by guest-friendly endpoints (e.g. bookings) that
    associate a user when logged in but don't require it.
    """
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return db.query(User).filter(User.id == payload.get("user_id")).first()


# --------------------------
# ROLE-BASED ACCESS CONTROL
# --------------------------
def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory. Usage:
        @router.get("/admin/x")
        def handler(user = Depends(require_role("admin"))): ...

    Not used by any route yet (no partner/admin routes exist in this module),
    but ready for the Partner Portal / Admin Dashboard modules.
    """
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check
