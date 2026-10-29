# app/schemas/partner_schema.py
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from app.schemas.user_schema import CompatibleEmail


class PartnerRegisterIn(BaseModel):
    business_name: str
    partner_type: str  # hotel | homestay | resort | travel_agency | tour_operator | local_guide
    contact_email: Optional[CompatibleEmail] = None
    contact_phone: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    photos: Optional[List[str]] = None

    @field_validator("contact_email", mode="before")
    @classmethod
    def empty_email_to_none(cls, v):
        if v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("business_name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        s = v.strip() if isinstance(v, str) else ""
        if not s:
            raise ValueError("Business name cannot be empty")
        return s


class PartnerOut(BaseModel):
    id: int
    business_name: str
    partner_type: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    photos: Optional[List[str]] = None
    status: str

    class Config:
        from_attributes = True
        orm_mode = True


class ListingIn(BaseModel):
    """
    Generic across hotel and package listings. `extra` carries fields only
    relevant to one type (e.g. duration_days/capacity for packages) so the
    schema doesn't need one variant per listing type.
    """
    destination_id: int
    name: str
    category: Optional[str] = None
    price_tier: str = "medium"
    price: Optional[float] = None
    rating: Optional[float] = None
    amenities: Optional[List[str]] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    photos: Optional[List[str]] = None
    extra: Optional[Dict[str, Any]] = None


class BookingStatusUpdateIn(BaseModel):
    status: str  # Confirmed | Cancelled | Completed
