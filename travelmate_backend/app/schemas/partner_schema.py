# app/schemas/partner_schema.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any


class PartnerRegisterIn(BaseModel):
    business_name: str
    partner_type: str  # hotel | homestay | resort | travel_agency | tour_operator | local_guide
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    description: Optional[str] = None


class PartnerOut(BaseModel):
    id: int
    business_name: str
    partner_type: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    description: Optional[str] = None
    status: str

    class Config:
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
