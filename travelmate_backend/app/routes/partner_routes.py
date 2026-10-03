# app/routes/partner_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.partner import Partner, PARTNER_TYPES
from app.schemas.partner_schema import PartnerRegisterIn, PartnerOut, ListingIn, BookingStatusUpdateIn
from app.services.auth_utils import get_current_user
from app.services import listing_service
from app.services.partner_service import (
    get_partner_bookings,
    get_partner_booking_or_none,
    compute_analytics,
    VALID_STATUS_TRANSITIONS,
)

router = APIRouter(prefix="/partners", tags=["partners"])


def _get_current_partner(user, db: Session) -> Partner:
    partner = db.query(Partner).filter(Partner.owner_user_id == user.id).first()
    if not partner:
        raise HTTPException(status_code=403, detail="You need to register as a partner first")
    return partner


# -----------------------
# REGISTRATION
# -----------------------
@router.post("/register", response_model=PartnerOut)
def register_partner(
    payload: PartnerRegisterIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if payload.partner_type not in PARTNER_TYPES:
        raise HTTPException(status_code=400, detail=f"partner_type must be one of {PARTNER_TYPES}")

    existing = db.query(Partner).filter(Partner.owner_user_id == user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="This account is already registered as a partner")

    partner = Partner(
        owner_user_id=user.id,
        business_name=payload.business_name,
        partner_type=payload.partner_type,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        description=payload.description,
    )
    db.add(partner)

    user.role = "partner"
    db.add(user)

    db.commit()
    db.refresh(partner)
    return partner


@router.get("/me", response_model=PartnerOut)
def get_my_partner_profile(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _get_current_partner(user, db)


# -----------------------
# LISTINGS (generic: hotel | package)
# -----------------------
@router.get("/listings")
def get_my_listings(db: Session = Depends(get_db), user=Depends(get_current_user)):
    partner = _get_current_partner(user, db)
    return listing_service.list_partner_listings(db, partner.id)


@router.post("/listings/{listing_type}")
def create_listing(
    listing_type: str,
    payload: ListingIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    partner = _get_current_partner(user, db)
    return listing_service.create_listing(db, partner, listing_type, payload.dict())


@router.put("/listings/{listing_type}/{listing_id}")
def update_listing(
    listing_type: str,
    listing_id: int,
    payload: ListingIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    partner = _get_current_partner(user, db)
    return listing_service.update_listing(db, partner, listing_type, listing_id, payload.dict(exclude_unset=True))


# -----------------------
# BOOKINGS
# -----------------------
@router.get("/bookings")
def get_my_bookings(db: Session = Depends(get_db), user=Depends(get_current_user)):
    partner = _get_current_partner(user, db)
    bookings = get_partner_bookings(db, partner.id)
    return [
        {
            "booking_reference": b.booking_reference,
            "listing_type": b.listing_type,
            "guest_name": b.guest_name,
            "guest_email": b.guest_email,
            "guest_phone": b.guest_phone,
            "check_in_date": b.check_in_date,
            "check_out_date": b.check_out_date,
            "num_rooms": b.num_rooms,
            "num_guests": b.num_guests,
            "special_requests": b.special_requests,
            "total_amount": b.total_amount,
            "currency": b.currency,
            "status": b.status,
            "created_at": b.created_at,
        }
        for b in bookings
    ]


@router.get("/bookings/{booking_reference}")
def get_booking_detail(
    booking_reference: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    partner = _get_current_partner(user, db)
    booking = get_partner_booking_or_none(db, partner.id, booking_reference)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.patch("/bookings/{booking_reference}/status")
def update_booking_status(
    booking_reference: str,
    payload: BookingStatusUpdateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    partner = _get_current_partner(user, db)
    booking = get_partner_booking_or_none(db, partner.id, booking_reference)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if payload.status not in VALID_STATUS_TRANSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(VALID_STATUS_TRANSITIONS)}",
        )

    booking.status = payload.status
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"msg": "Booking status updated", "booking_reference": booking.booking_reference, "status": booking.status}


# -----------------------
# ANALYTICS
# -----------------------
@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db), user=Depends(get_current_user)):
    partner = _get_current_partner(user, db)
    return compute_analytics(db, partner.id)
