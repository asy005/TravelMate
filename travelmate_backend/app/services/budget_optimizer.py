# app/services/budget_optimizer.py
"""
Intelligent budget allocation.

This is intentionally the ONLY place budget math happens -- plan_orchestrator
and hotel_routes both call allocate_budget() rather than each computing
their own numbers, so the dashboard's budget always reflects one consistent
calculation regardless of what triggered the recompute (initial plan
generation vs. a hotel selection change).
"""
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.services.hotel_recommender import recommend_hotels
from app.services.budget_tiers import TIER_DAILY_PER_PERSON as _TIER_DAILY_PER_PERSON, budget_tier as _budget_tier

# Baseline relative weights for the non-hotel spend categories. These get
# nudged by transport preference / travel style before being normalized.
_BASE_WEIGHTS = {
    "transport": 0.25,
    "food": 0.35,
    "activities": 0.25,
    "misc": 0.15,
}

EMERGENCY_RESERVE_PCT = 0.10  # 10% of total budget, standard travel-advice rule of thumb
NEAR_LIMIT_THRESHOLD_PCT = 0.05  # remaining < 5% of total => "Near Budget Limit"


def parse_total_budget(budget_label: Optional[str], duration_days: int, travelers: int) -> Dict[str, Any]:
    """
    Determines the total trip budget to allocate against.
    - If the user gave a number (e.g. "50000", "Rs 60,000", "60k"), use it directly.
    - Otherwise, treat it as a tier label (low/medium/luxury) and imply a
      total budget from the tier's daily-per-person baseline.
    Returns {"total": float, "source": "explicit" | "implied", "tier": str}.
    """
    label = (budget_label or "").strip().lower().replace("rs", "").replace("inr", "")
    label = label.replace("\u20b9", "").replace(",", "")

    match = re.search(r"(\d+)\s*(k)?", label)
    if match and match.group(1):
        try:
            amount = float(match.group(1))
            if match.group(2):  # "k" suffix -> thousands
                amount *= 1000
            if amount >= 1000:  # guard against matching small unrelated numbers
                tier = _budget_tier(budget_label)
                return {"total": amount, "source": "explicit", "tier": tier}
        except ValueError:
            pass

    tier = _budget_tier(budget_label)
    daily_per_person = _TIER_DAILY_PER_PERSON.get(tier, _TIER_DAILY_PER_PERSON["medium"])
    implied_total = daily_per_person * max(duration_days, 1) * max(travelers, 1)
    return {"total": implied_total, "source": "implied", "tier": tier}


def _adjust_weights(transport_pref: Optional[str], travel_style: Optional[str], activities: List[str]) -> Dict[str, float]:
    weights = dict(_BASE_WEIGHTS)

    transport_pref = (transport_pref or "").lower()
    if any(k in transport_pref for k in ["flight", "fly", "air"]):
        weights["transport"] += 0.08
    elif any(k in transport_pref for k in ["own car", "self drive", "bike"]):
        weights["transport"] -= 0.05

    travel_style = (travel_style or "").lower()
    if any(k in travel_style for k in ["luxury", "relax", "romantic"]):
        weights["activities"] -= 0.03
        weights["food"] += 0.03
    elif any(k in travel_style for k in ["adventurous", "adventure", "trek"]):
        weights["activities"] += 0.08
        weights["transport"] += 0.02

    if activities and len(activities) >= 3:
        weights["activities"] += 0.05

    # Clamp and re-normalize so the four weights always sum to 1.0
    for key in weights:
        weights[key] = max(weights[key], 0.05)
    total_weight = sum(weights.values())
    return {k: v / total_weight for k, v in weights.items()}


def _health_status(remaining: float, total_budget: float) -> str:
    if remaining < 0:
        return "Over Budget"
    if total_budget > 0 and remaining < total_budget * NEAR_LIMIT_THRESHOLD_PCT:
        return "Near Budget Limit"
    return "Within Budget"


def allocate_budget(
    db: Session,
    slots: Dict[str, Any],
    duration_days: int,
    travelers: int,
    destination_id: Optional[int] = None,
    selected_hotel: Optional[Dict[str, Any]] = None,
    selected_package: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Core budget allocation. `selected_hotel`/`selected_package` are dicts if
    the user has picked one; otherwise the top recommended hotel for the
    destination/budget tier is used as the working assumption so the
    dashboard always has a concrete number, not just a vague tier. Packages
    are opt-in only (no default package is assumed if none is selected).
    """
    duration_days = max(int(duration_days or 1), 1)
    travelers = max(int(travelers or 1), 1)

    budget_info = parse_total_budget(slots.get("budget"), duration_days, travelers)
    total_budget = budget_info["total"]

    working_hotel = selected_hotel
    if not working_hotel and destination_id is not None:
        candidates = recommend_hotels(db, destination_id, slots, max_results=1)
        working_hotel = candidates[0] if candidates else None

    if working_hotel and working_hotel.get("price_per_night"):
        hotel_cost = working_hotel["price_per_night"] * duration_days
    else:
        tier_daily = _TIER_DAILY_PER_PERSON.get(budget_info["tier"], _TIER_DAILY_PER_PERSON["medium"])
        hotel_cost = tier_daily * 0.45 * duration_days

    package_cost = 0
    if selected_package and selected_package.get("price_per_package"):
        package_cost = selected_package["price_per_package"]

    activities_list = [a.strip() for a in (slots.get("interests") or "").split(",") if a.strip()]
    weights = _adjust_weights(slots.get("transport_pref"), slots.get("travel_style"), activities_list)

    remaining_after_stay = max(total_budget - hotel_cost - package_cost, 0)

    # A selected package typically bundles guided activities (and often some
    # meals), so most of what would have gone to "activities" is already
    # covered -- only a small residual (for extras/tips) is allocated there,
    # and the freed-up share is redistributed to the remaining categories.
    if selected_package:
        residual_activities_weight = weights["activities"] * 0.2
        freed_weight = weights["activities"] - residual_activities_weight
        weights["activities"] = residual_activities_weight
        for key in ("transport", "food", "misc"):
            weights[key] += freed_weight / 3

    transport_cost = remaining_after_stay * weights["transport"]
    food_cost = remaining_after_stay * weights["food"]
    activities_cost = remaining_after_stay * weights["activities"]
    misc_cost = remaining_after_stay * weights["misc"]
    emergency_reserve = total_budget * EMERGENCY_RESERVE_PCT

    total_allocated = (
        hotel_cost + package_cost + transport_cost + food_cost
        + activities_cost + misc_cost + emergency_reserve
    )
    remaining_budget = total_budget - total_allocated

    status = _health_status(remaining_budget, total_budget)

    alternative_hotels = []
    if status == "Over Budget" and destination_id is not None:
        alternative_hotels = [
            h for h in recommend_hotels(db, destination_id, {**slots, "budget": "low"}, max_results=3)
            if not working_hotel or h["id"] != working_hotel.get("id")
        ]

    breakdown = {
        "hotel": round(hotel_cost),
        "transportation": round(transport_cost),
        "food": round(food_cost),
        "activities": round(activities_cost),
        "miscellaneous": round(misc_cost),
        "emergency_reserve": round(emergency_reserve),
    }
    if selected_package:
        breakdown["package"] = round(package_cost)

    return {
        "tier": budget_info["tier"],
        "budget_source": budget_info["source"],
        "currency": "INR",
        "total_budget": round(total_budget),
        "breakdown": breakdown,
        "estimated_total": round(total_allocated),
        "remaining_budget": round(remaining_budget),
        "cost_per_traveler": round(total_allocated / travelers),
        "cost_per_day": round(total_allocated / duration_days),
        "status": status,
        "hotel_used": working_hotel,
        "package_used": selected_package,
        "alternative_hotels": alternative_hotels,
    }
