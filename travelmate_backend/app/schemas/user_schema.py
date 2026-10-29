import re
from typing import Annotated
from pydantic import BaseModel, BeforeValidator
from email_validator import validate_email

LOCAL_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.local$", re.IGNORECASE)

def validate_custom_email(v: str) -> str:
    if not isinstance(v, str):
        raise ValueError("Invalid email format")
    v = v.strip()
    if LOCAL_EMAIL_REGEX.match(v):
        return v.lower()
    valid = validate_email(v, check_deliverability=False)
    return valid.normalized

CompatibleEmail = Annotated[str, BeforeValidator(validate_custom_email)]

class UserCreate(BaseModel):
    username: str
    email: CompatibleEmail
    password: str

class UserLogin(BaseModel):
    email: CompatibleEmail
    password: str

class RefreshTokenIn(BaseModel):
    refresh_token: str

class PasswordResetRequestIn(BaseModel):
    email: CompatibleEmail

class PasswordResetConfirmIn(BaseModel):
    token: str
    new_password: str
