# app/services/partner_service.py
"""
Booking visibility and analytics for a partner's own listings. Written to
stay listing-type-agnostic (checks both hotel_id and package_id ownership)
so it doesn't need duplicating when package bookings exist in the future.
"""
from typing import Dict, Any, List
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.booking import Booking
from app.models.hotel import Hotel
from app.models.package import Package

VALID_STATUS_TRANSITIONS = {"Confirmed", "Cancelled", "Completed"}
REVENUE_COUNTED_STATUSES = {"Confirmed", "Completed"}


def _owned_listing_ids(db: Session, partner_id: int):
    hotel_ids = [h.id for h in db.query(Hotel.id).filter(Hotel.partner_id == partner_id).all()]
    package_ids = [p.id for p in db.query(Package.id).filter(Package.partner_id == partner_id).all()]
    return hotel_ids, package_ids


def get_partner_bookings(db: Session, partner_id: int) -> List[Booking]:
    hotel_ids, package_ids = _owned_listing_ids(db, partner_id)
    if not hotel_ids and not package_ids:
        return []

    return db.query(Booking).filter(
        or_(
            Booking.hotel_id.in_(hotel_ids),
            Booking.package_id.in_(package_ids),
        )
    ).order_by(Booking.created_at.desc()).all()


def get_partner_booking_or_none(db: Session, partner_id: int, booking_reference: str):
    hotel_ids, package_ids = _owned_listing_ids(db, partner_id)
    booking = db.query(Booking).filter(Booking.booking_reference == booking_reference).first()
    if not booking:
        return None
    owns = (booking.hotel_id in hotel_ids) or (booking.package_id in package_ids)
    return booking if owns else None


def compute_analytics(db: Session, partner_id: int) -> Dict[str, Any]:
    bookings = get_partner_bookings(db, partner_id)

    total_bookings = len(bookings)
    pending_bookings = len([b for b in bookings if b.status == "Pending Payment"])
    revenue_estimate = sum(
        (b.total_amount or 0) for b in bookings if b.status in REVENUE_COUNTED_STATUSES
    )

    listing_counter = Counter()
    hotel_names = {h.id: h.name for h in db.query(Hotel).filter(Hotel.partner_id == partner_id).all()}
    package_titles = {p.id: p.title for p in db.query(Package).filter(Package.partner_id == partner_id).all()}

    for b in bookings:
        if b.hotel_id and b.hotel_id in hotel_names:
            listing_counter[hotel_names[b.hotel_id]] += 1
        elif b.package_id and b.package_id in package_titles:
            listing_counter[package_titles[b.package_id]] += 1

    popular_listings = [
        {"name": name, "bookings": count}
        for name, count in listing_counter.most_common(5)
    ]

    return {
        "total_bookings": total_bookings,
        "pending_bookings": pending_bookings,
        "revenue_estimate": round(revenue_estimate),
        "popular_listings": popular_listings,
    }
