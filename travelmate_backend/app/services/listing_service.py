# app/services/listing_service.py
"""
Generic listing abstraction shared by both accommodation partners (hotels,
homestays, resorts) and experience partners (travel agencies, tour
operators, local guides).

Two underlying tables exist (Hotel, Package) because a per-night stay and a
multi-day fixed-price package genuinely have different shapes. This module
is what makes them behave identically to everything above it (Partner
Portal routes, the frontend) -- callers work with plain dicts keyed by
`listing_type`, never with the ORM models directly.

Adding a future listing type (e.g. a fundamentally different shape) means
adding one more entry to LISTING_MODELS and one more serializer branch --
not touching any route or the frontend's rendering logic.
"""
from typing import Dict, Any, List
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.hotel import Hotel
from app.models.package import Package
from app.models.partner import Partner

LISTING_MODELS = {"hotel": Hotel, "package": Package}


def _serialize(listing_type: str, obj) -> Dict[str, Any]:
    if listing_type == "hotel":
        return {
            "listing_type": "hotel",
            "id": obj.id,
            "partner_id": obj.partner_id,
            "destination_id": obj.destination_id,
            "name": obj.name,
            "category": obj.accommodation_type,
            "price_tier": obj.price_tier,
            "price": obj.price_per_night,
            "rating": obj.star_rating,
            "amenities": (obj.amenities or "").split(",") if obj.amenities else [],
            "description": obj.description,
            "photos": obj.photos or [],
            "thumbnail_url": obj.thumbnail_url,
            "extra": {"duration_days": None, "capacity": None},
        }
    # package
    return {
        "listing_type": "package",
        "id": obj.id,
        "partner_id": obj.partner_id,
        "destination_id": obj.destination_id,
        "name": obj.title,
        "category": obj.category,
        "price_tier": obj.price_tier,
        "price": obj.price_per_package,
        "rating": obj.rating,
        "amenities": (obj.amenities or "").split(",") if obj.amenities else [],
        "description": obj.description,
        "photos": obj.photos or [],
        "thumbnail_url": obj.thumbnail_url,
        "extra": {"duration_days": obj.duration_days, "capacity": obj.capacity},
    }


def list_partner_listings(db: Session, partner_id: int) -> List[Dict[str, Any]]:
    hotels = db.query(Hotel).filter(Hotel.partner_id == partner_id).all()
    packages = db.query(Package).filter(Package.partner_id == partner_id).all()
    return (
        [_serialize("hotel", h) for h in hotels]
        + [_serialize("package", p) for p in packages]
    )


def get_listing(db: Session, listing_type: str, listing_id: int):
    model = LISTING_MODELS.get(listing_type)
    if not model:
        raise HTTPException(status_code=400, detail="Unknown listing type")
    obj = db.query(model).filter(model.id == listing_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Listing not found")
    return obj


def _assert_owns(obj, partner: Partner):
    if obj.partner_id != partner.id:
        raise HTTPException(status_code=403, detail="You do not own this listing")


def create_listing(db: Session, partner: Partner, listing_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    amenities = payload.get("amenities")
    amenities_str = ",".join(amenities) if isinstance(amenities, list) else amenities

    if listing_type == "hotel":
        obj = Hotel(
            partner_id=partner.id,
            destination_id=payload["destination_id"],
            name=payload["name"],
            partner_name=partner.business_name,
            accommodation_type=payload.get("category", "hotel"),
            price_tier=payload.get("price_tier", "medium"),
            price_per_night=payload.get("price"),
            star_rating=payload.get("rating"),
            amenities=amenities_str,
            thumbnail_url=payload.get("thumbnail_url"),
            description=payload.get("description"),
            photos=payload.get("photos", []),
        )
    elif listing_type == "package":
        extra = payload.get("extra") or {}
        obj = Package(
            partner_id=partner.id,
            destination_id=payload["destination_id"],
            title=payload["name"],
            category=payload.get("category", "travel_agency"),
            price_tier=payload.get("price_tier", "medium"),
            price_per_package=payload.get("price"),
            duration_days=extra.get("duration_days"),
            capacity=extra.get("capacity"),
            rating=payload.get("rating"),
            amenities=amenities_str,
            thumbnail_url=payload.get("thumbnail_url"),
            description=payload.get("description"),
            photos=payload.get("photos", []),
        )
    else:
        raise HTTPException(status_code=400, detail="Unknown listing type")

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _serialize(listing_type, obj)


def update_listing(db: Session, partner: Partner, listing_type: str, listing_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    obj = get_listing(db, listing_type, listing_id)
    _assert_owns(obj, partner)

    if "name" in payload:
        setattr(obj, "name" if listing_type == "hotel" else "title", payload["name"])
    if "category" in payload:
        setattr(obj, "accommodation_type" if listing_type == "hotel" else "category", payload["category"])
    if "price" in payload:
        setattr(obj, "price_per_night" if listing_type == "hotel" else "price_per_package", payload["price"])
    if "price_tier" in payload:
        obj.price_tier = payload["price_tier"]
    if "rating" in payload:
        setattr(obj, "star_rating" if listing_type == "hotel" else "rating", payload["rating"])
    if "amenities" in payload:
        amenities = payload["amenities"]
        obj.amenities = ",".join(amenities) if isinstance(amenities, list) else amenities
    if "description" in payload:
        obj.description = payload["description"]
    if "thumbnail_url" in payload:
        obj.thumbnail_url = payload["thumbnail_url"]
    if "photos" in payload:
        obj.photos = payload["photos"]
    if listing_type == "package" and "extra" in payload:
        extra = payload["extra"] or {}
        obj.duration_days = extra.get("duration_days", obj.duration_days)
        obj.capacity = extra.get("capacity", obj.capacity)

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _serialize(listing_type, obj)
