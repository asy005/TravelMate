# app/services/hotel_recommender.py
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.hotel import Hotel
from app.services.budget_tiers import budget_tier as _budget_tier


def recommend_hotels(
    db: Session,
    destination_id: int,
    slots: Dict[str, Any],
    max_results: int = 3,
) -> List[Dict[str, Any]]:
    tier = _budget_tier(slots.get("budget"))
    accommodation_pref = (slots.get("accommodation_pref") or "").lower()

    q = db.query(Hotel).filter(Hotel.destination_id == destination_id)

    tier_filtered = q.filter(Hotel.price_tier == tier).all()
    results = tier_filtered

    if accommodation_pref:
        pref_matches = [
            h for h in results
            if h.accommodation_type and accommodation_pref in h.accommodation_type.lower()
        ]
        if pref_matches:
            results = pref_matches

    if not results:
        # No exact tier match -- fall back to any hotel for this destination
        # rather than returning nothing.
        results = db.query(Hotel).filter(Hotel.destination_id == destination_id).all()

    # Inventory-aware ranking: registered-partner listings (partner_id set)
    # are prioritized over platform-seeded placeholder inventory
    # (partner_id is null), with star rating as the tiebreaker within each
    # group. Generic/seeded hotels only surface when no partner inventory
    # exists for this destination/tier.
    results = sorted(
        results,
        key=lambda h: (h.partner_id is not None, h.star_rating or 0),
        reverse=True,
    )[:max_results]

    return [
        {
            "id": h.id,
            "name": h.name,
            "partner_name": h.partner_name,
            "is_partner_listing": h.partner_id is not None,
            "accommodation_type": h.accommodation_type,
            "price_tier": h.price_tier,
            "price_per_night": h.price_per_night,
            "star_rating": h.star_rating,
            "amenities": (h.amenities or "").split(",") if h.amenities else [],
            "thumbnail_url": h.thumbnail_url,
        }
        for h in results
    ]
