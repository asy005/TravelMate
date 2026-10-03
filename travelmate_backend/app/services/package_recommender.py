# app/services/package_recommender.py
"""
Recommends travel-agency/tour-operator/local-guide packages for a
destination. Packages only ever come from registered partners (there is no
"platform-seeded" package inventory the way there is for hotels), so this
function is inherently inventory-aware: it simply returns nothing if no
partner has listed a matching package, and the caller (plan_orchestrator)
only surfaces a packages section when this returns results.
"""
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.package import Package
from app.models.partner import Partner
from app.services.budget_tiers import budget_tier


def recommend_packages(
    db: Session,
    destination_id: int,
    slots: Dict[str, Any],
    max_results: int = 3,
) -> List[Dict[str, Any]]:
    tier = budget_tier(slots.get("budget"))
    duration_days = slots.get("duration_days")
    travelers = slots.get("travelers") or 1

    q = db.query(Package).filter(Package.destination_id == destination_id)

    tier_filtered = q.filter(Package.price_tier == tier).all()
    results = tier_filtered or db.query(Package).filter(Package.destination_id == destination_id).all()

    # Capacity must fit the group -- a package that can't hold the party
    # isn't a usable recommendation regardless of how well it otherwise fits.
    results = [p for p in results if not p.capacity or p.capacity >= travelers]

    def _duration_fit(p: Package) -> int:
        if not duration_days or not p.duration_days:
            return 0
        return -abs(p.duration_days - int(duration_days))  # closer to 0 is better

    results = sorted(
        results,
        key=lambda p: (_duration_fit(p), p.rating or 0),
        reverse=True,
    )[:max_results]

    partner_names = {
        pt.id: pt.business_name
        for pt in db.query(Partner).filter(Partner.id.in_([p.partner_id for p in results])).all()
    } if results else {}

    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "category": p.category,
            "duration_days": p.duration_days,
            "capacity": p.capacity,
            "price_tier": p.price_tier,
            "price_per_package": p.price_per_package,
            "rating": p.rating,
            "amenities": (p.amenities or "").split(",") if p.amenities else [],
            "thumbnail_url": p.thumbnail_url,
            "partner_name": partner_names.get(p.partner_id),
        }
        for p in results
    ]


def should_recommend_packages(slots: Dict[str, Any], packages: List[Dict[str, Any]]) -> bool:
    """
    Decides whether packages are actually worth surfacing for this trip,
    rather than always bolting them on whenever any exist. A package is
    worth showing when it reasonably fits the trip's duration or the
    traveler's stated style suggests a guided/structured experience.
    """
    if not packages:
        return False

    travel_style = (slots.get("travel_style") or "").lower()
    interests = (slots.get("interests") or "").lower()
    guided_signal = any(
        k in travel_style or k in interests
        for k in ["guided", "tour", "adventure", "trek", "cultural", "heritage"]
    )

    duration_days = slots.get("duration_days")
    close_duration_match = any(
        p.get("duration_days") and duration_days and abs(p["duration_days"] - int(duration_days)) <= 2
        for p in packages
    )

    return guided_signal or close_duration_match
