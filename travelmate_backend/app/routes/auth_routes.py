from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user_schema import (
    UserCreate,
    UserLogin,
    RefreshTokenIn,
    PasswordResetRequestIn,
    PasswordResetConfirmIn,
)
from app.services.auth_utils import (
    hash_password,
    verify_password,
    create_token,
    create_refresh_token,
    verify_and_rotate_refresh_token,
    revoke_refresh_token,
    create_password_reset_token,
    consume_password_reset_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# -----------------------
# SIGNUP
# -----------------------
@router.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):

    # Check if email already exists
    exists = db.query(User).filter(User.email == user.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    new_user = User(
        username=user.username,
        email=user.email,
        password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create access + refresh token after signup
    token = create_token({"user_id": new_user.id})
    refresh_token = create_refresh_token(db, new_user.id)

    return {
        "token": token,
        "refresh_token": refresh_token,
        "username": new_user.username,
        "email": new_user.email,
        "role": new_user.role,
    }


# -----------------------
# LOGIN
# -----------------------
@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):

    found = db.query(User).filter(User.email == user.email).first()

    # Wrong password or no user
    if not found or not verify_password(user.password, found.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token = create_token({"user_id": found.id})
    refresh_token = create_refresh_token(db, found.id)

    return {
        "token": token,
        "refresh_token": refresh_token,
        "username": found.username,
        "email": found.email,
        "role": found.role,
    }


# -----------------------
# REFRESH ACCESS TOKEN
# -----------------------
@router.post("/refresh")
def refresh(payload: RefreshTokenIn, db: Session = Depends(get_db)):
    user = verify_and_rotate_refresh_token(db, payload.refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    new_access_token = create_token({"user_id": user.id})
    return {"token": new_access_token}


# -----------------------
# LOGOUT (revoke refresh token)
# -----------------------
@router.post("/logout")
def logout(payload: RefreshTokenIn, db: Session = Depends(get_db)):
    revoke_refresh_token(db, payload.refresh_token)
    return {"msg": "Logged out"}


# -----------------------
# PASSWORD RESET -- REQUEST
# -----------------------
@router.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequestIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    # Always return a generic success message, whether or not the email
    # exists, so this endpoint can't be used to enumerate registered emails.
    if user:
        reset_token = create_password_reset_token(db, user.id)
        # NOTE: no email-sending service exists yet (that's a notification
        # module, not built). Logging the link here as an explicit, visible
        # stand-in rather than silently pretending an email was sent.
        print(f"[password-reset] (no email service yet) reset link for {user.email}: "
              f"/reset-password?token={reset_token}")

    return {"msg": "If that email is registered, a reset link has been sent."}


# -----------------------
# PASSWORD RESET -- CONFIRM
# -----------------------
@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirmIn, db: Session = Depends(get_db)):
    user = consume_password_reset_token(db, payload.token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.password = hash_password(payload.new_password)
    db.add(user)
    db.commit()

    return {"msg": "Password updated successfully"}
