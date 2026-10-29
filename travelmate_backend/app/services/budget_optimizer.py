import re
import math
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.services.hotel_recommender import recommend_hotels
from app.services.budget_tiers import (
    TIER_DAILY_PER_PERSON as _TIER_DAILY_PER_PERSON,
    budget_tier as _budget_tier,
)

logger = logging.getLogger(__name__)

_BASE_WEIGHTS = {
    "transport": 0.25,
    "food": 0.35,
    "activities": 0.25,
    "misc": 0.15,
}

EMERGENCY_RESERVE_PCT = 0.10
NEAR_LIMIT_THRESHOLD_PCT = 0.05

DISCLAIMER_TEXT = (
    "Estimates are for planning purposes only and not confirmed booking prices. "
    "Actual costs may vary based on seasonal rates, availability, and specific vendor selections."
)


def is_solver_available() -> bool:
    """Check if scipy linear programming solver is importable."""
    try:
        from scipy.optimize import linprog  # noqa: F401
        return True
    except (ImportError, Exception):
        return False


def solve_flexible_budget_lp(
    available: float,
    weights: Dict[str, float],
    floors: Dict[str, float],
) -> Optional[Dict[str, int]]:
    """
    Solve constrained flexible budget allocation using scipy.optimize.linprog.
    Optimizes for traveler preference weights subject to:
    - sum(x_i) == available
    - x_i >= floor_i for all i
    - misc <= max(floor_misc, 0.20 * available)
    - minimizing L1 weighted goal deviation: sum( |x_i - w_i * available| / w_i )
    """
    try:
        from scipy.optimize import linprog
        categories = ["transport", "food", "activities", "misc"]
        n = len(categories)

        # Objective: minimize sum( t_i / w_i )
        c = [0.0] * n + [1.0 / max(weights.get(cat, 0.1), 0.01) for cat in categories]

        # Equality: sum(x_i) == available
        A_eq = [[1.0] * n + [0.0] * n]
        b_eq = [float(available)]

        # Inequality constraints:
        # x_i - t_i <= target_i
        # -x_i - t_i <= -target_i
        A_ub = []
        b_ub = []
        for i, cat in enumerate(categories):
            target = weights[cat] * available
            # x_i - t_i <= target
            row1 = [0.0] * (2 * n)
            row1[i] = 1.0
            row1[n + i] = -1.0
            A_ub.append(row1)
            b_ub.append(target)

            # -x_i - t_i <= -target
            row2 = [0.0] * (2 * n)
            row2[i] = -1.0
            row2[n + i] = -1.0
            A_ub.append(row2)
            b_ub.append(-target)

        # Cap misc spending to prevent excess padding of miscellaneous expenses
        misc_idx = categories.index("misc")
        misc_cap = max(floors["misc"], 0.20 * available)
        misc_row = [0.0] * (2 * n)
        misc_row[misc_idx] = 1.0
        A_ub.append(misc_row)
        b_ub.append(misc_cap)

        bounds = [(floors[cat], None) for cat in categories] + [(0, None) for _ in categories]

        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
        if res.success and res.x is not None:
            raw_alloc = {cat: round(float(res.x[i])) for i, cat in enumerate(categories)}
            # Fix integer rounding to ensure exact sum match
            diff = round(available) - sum(raw_alloc.values())
            raw_alloc["misc"] += diff
            return raw_alloc
        return None
    except Exception as exc:
        logger.warning("LP budget solver failed: %s. Using analytical fallback.", exc)
        return None


def solve_flexible_budget_analytical(
    available: float,
    weights: Dict[str, float],
    floors: Dict[str, float],
) -> Dict[str, int]:
    """
    Deterministic analytical fallback for budget allocation.
    Guarantees floor constraints and exact total conservation.
    """
    categories = ["transport", "food", "activities", "misc"]
    min_sum = sum(floors[c] for c in categories)

    if available < min_sum:
        return {cat: round(floors[cat]) for cat in categories}

    # If available >= min_sum, allocate floors and distribute surplus
    alloc = {cat: round(floors[cat]) for cat in categories}
    surplus = round(available) - sum(alloc.values())

    if surplus > 0:
        weight_sum = sum(weights.values())
        norm_weights = {k: v / weight_sum for k, v in weights.items()}
        for cat in categories:
            added = int(surplus * norm_weights[cat])
            alloc[cat] += added

        rounding_diff = round(available) - sum(alloc.values())
        alloc["misc"] += rounding_diff

    return alloc


def parse_total_budget(
    budget_label: Optional[str],
    duration_days: int,
    travelers: int,
) -> Dict[str, Any]:
    duration_days = max(int(duration_days or 1), 1)
    travelers = max(int(travelers or 1), 1)

    label = (budget_label or "").strip().lower()
    label = label.replace("rs.", "").replace("rs", "").replace("inr", "")
    label = label.replace("₹", "").replace(",", "").strip()

    match = re.search(r"(\d+(?:\.\d+)?)\s*(k)?", label)

    if match:
        try:
            amount = float(match.group(1))
            if match.group(2):
                amount *= 1000

            if amount >= 1000:
                tier = _budget_tier(budget_label)
                if tier == "medium":
                    daily_rate = amount / (duration_days * travelers)
                    if daily_rate < 2500:
                        tier = "low"
                    elif daily_rate > 7000:
                        tier = "luxury"
                return {
                    "total": amount,
                    "source": "explicit",
                    "tier": tier,
                }
        except ValueError:
            pass

    tier = _budget_tier(budget_label)
    daily_per_person = _TIER_DAILY_PER_PERSON.get(
        tier, _TIER_DAILY_PER_PERSON["medium"]
    )
    implied_total = (
        daily_per_person
        * duration_days
        * travelers
    )

    return {
        "total": implied_total,
        "source": "implied",
        "tier": tier,
    }


def _adjust_weights(
    transport_pref: Optional[str],
    travel_style: Optional[str],
    activities: List[str],
) -> Dict[str, float]:
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

    for key in weights:
        weights[key] = max(weights[key], 0.05)

    total_weight = sum(weights.values())
    return {key: value / total_weight for key, value in weights.items()}


def _inspect_package_inclusions(pkg: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    if not pkg:
        return {
            "hotel": False,
            "transport": False,
            "activities": False,
            "breakfast": False,
            "all_meals": False,
        }

    amenities_raw = pkg.get("amenities") or []
    if isinstance(amenities_raw, str):
        pkg_amenities = [a.strip().lower() for a in amenities_raw.split(",")]
    else:
        pkg_amenities = [str(a).strip().lower() for a in amenities_raw]
    pkg_desc = (pkg.get("description") or "").lower()
    pkg_cat = (pkg.get("category") or "").lower()

    includes_hotel = (
        pkg.get("includes_hotel") is True
        or any(k in pkg_desc for k in ["including stay", "includes stay", "hotel included", "resort stay", "accommodation included"])
        or any(k in a for a in pkg_amenities for k in ["hotel", "resort stay", "homestay", "accommodation", "lodging"])
    )

    includes_activities = (
        pkg_cat in ("tour_operator", "local_guide", "sightseeing")
        or any(k in a for a in pkg_amenities for k in ["guide", "tour", "sightseeing", "pass", "activity", "trekking"])
        or any(k in pkg_desc for k in ["guided", "tour", "sightseeing", "pass"])
    )

    includes_transport = (
        any(k in a for a in pkg_amenities for k in ["transport", "cab", "transfers", "driver", "vehicle"])
        or "transport" in pkg_desc
    )

    includes_all_meals = (
        any(k in a for a in pkg_amenities for k in ["all meals", "all-inclusive", "lunch and dinner", "full board"])
        or "all meals" in pkg_desc
    )

    includes_breakfast = (
        includes_all_meals
        or any(k in a for a in pkg_amenities for k in ["breakfast", "meal", "snack"])
        or "breakfast" in pkg_desc
    )

    return {
        "hotel": includes_hotel,
        "transport": includes_transport,
        "activities": includes_activities,
        "breakfast": includes_breakfast,
        "all_meals": includes_all_meals,
    }


def _health_status(remaining: float, total_budget: float) -> str:
    if remaining < 0:
        return "Over Budget"

    if (
        total_budget > 0
        and remaining < total_budget * NEAR_LIMIT_THRESHOLD_PCT
    ):
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
    currency: Optional[str] = "INR",
) -> Dict[str, Any]:
    duration_days = max(int(duration_days or 1), 1)
    travelers = max(int(travelers or 1), 1)
    person_days = duration_days * travelers

    budget_info = parse_total_budget(
        slots.get("budget"), duration_days, travelers
    )
    total_budget = float(budget_info["total"])
    tier = budget_info["tier"]

    # Package inclusions analysis (accounting for overlaps)
    pkg_inclusions = _inspect_package_inclusions(selected_package)

    # 1. Package cost
    package_cost = 0.0
    if selected_package and selected_package.get("price_per_package"):
        package_cost = float(selected_package["price_per_package"])

    # 2. Hotel cost
    working_hotel = selected_hotel
    if not working_hotel and destination_id is not None:
        candidates = recommend_hotels(
            db, destination_id, slots, max_results=1
        )
        working_hotel = candidates[0] if candidates else None

    if pkg_inclusions["hotel"]:
        # Hotel stay is covered by the package; do not charge separately
        hotel_cost = 0.0
        hotel_estimated = False
    elif working_hotel and working_hotel.get("price_per_night"):
        hotel_cost = float(working_hotel["price_per_night"]) * duration_days
        hotel_estimated = False
    else:
        tier_daily = _TIER_DAILY_PER_PERSON.get(
            tier,
            _TIER_DAILY_PER_PERSON["medium"],
        )
        hotel_cost = min(
            float(tier_daily) * 0.35 * duration_days * max(1, math.ceil(travelers / 2)),
            total_budget * 0.40,
        )
        hotel_cost = max(hotel_cost, 1200.0 * duration_days)
        hotel_estimated = True

    # 3. Emergency reserve (10% of total budget)
    emergency_reserve = round(total_budget * EMERGENCY_RESERVE_PCT)

    # 4. Weights calculation with package adjustments
    activities_list = [
        item.strip()
        for item in (slots.get("interests") or "").split(",")
        if item.strip()
    ]
    weights = _adjust_weights(
        slots.get("transport_pref"),
        slots.get("travel_style"),
        activities_list,
    )

    if selected_package:
        if pkg_inclusions["activities"]:
            old_act = weights["activities"]
            weights["activities"] = old_act * 0.20
            freed = old_act - weights["activities"]
            for key in ("transport", "food", "misc"):
                weights[key] += freed / 3.0

        if pkg_inclusions["transport"]:
            old_trans = weights["transport"]
            weights["transport"] = old_trans * 0.50
            freed = old_trans - weights["transport"]
            for key in ("food", "activities", "misc"):
                weights[key] += freed / 3.0

        if pkg_inclusions["all_meals"]:
            old_food = weights["food"]
            weights["food"] = old_food * 0.25
            freed = old_food - weights["food"]
            for key in ("transport", "activities", "misc"):
                weights[key] += freed / 3.0
        elif pkg_inclusions["breakfast"]:
            old_food = weights["food"]
            weights["food"] = old_food * 0.75
            freed = old_food - weights["food"]
            for key in ("transport", "activities", "misc"):
                weights[key] += freed / 3.0

        weight_sum = sum(weights.values())
        weights = {k: v / weight_sum for k, v in weights.items()}

    # 5. Baseline realistic daily flexible expenses per person
    tier_daily = float(_TIER_DAILY_PER_PERSON.get(tier, _TIER_DAILY_PER_PERSON["medium"]))
    per_person_day_budget = total_budget / person_days
    flex_ref = max(min(per_person_day_budget, tier_daily), 1200.0) * 0.45

    daily_food = flex_ref * 0.35
    daily_transport = flex_ref * 0.25
    daily_act = flex_ref * 0.25
    daily_misc = flex_ref * 0.15

    if pkg_inclusions["activities"]:
        daily_act = max(daily_act * 0.20, 60.0)
    else:
        daily_act = max(daily_act, 120.0)

    if pkg_inclusions["transport"]:
        daily_transport = max(daily_transport * 0.50, 100.0)
    else:
        daily_transport = max(daily_transport, 180.0)

    if pkg_inclusions["all_meals"]:
        daily_food = max(daily_food * 0.25, 120.0)
    elif pkg_inclusions["breakfast"]:
        daily_food = max(daily_food * 0.75, 250.0)
    else:
        daily_food = max(daily_food, 350.0)

    daily_misc = max(daily_misc, 100.0)

    min_transport = round(daily_transport * person_days)
    min_food = round(daily_food * person_days)
    min_activities = round(daily_act * person_days)
    min_misc = round(daily_misc * person_days)
    min_flexible_total = min_transport + min_food + min_activities + min_misc

    floors = {
        "transport": float(min_transport),
        "food": float(min_food),
        "activities": float(min_activities),
        "misc": float(min_misc),
    }

    # 6. Allocation of flexible budget using Solver or Fallback
    available_for_flexible = total_budget - emergency_reserve - hotel_cost - package_cost
    optimization_method = "unconstrained_proportional"

    if available_for_flexible >= min_flexible_total:
        lp_alloc = solve_flexible_budget_lp(available_for_flexible, weights, floors)
        if lp_alloc is not None:
            transport_cost = lp_alloc["transport"]
            food_cost = lp_alloc["food"]
            activities_cost = lp_alloc["activities"]
            misc_cost = lp_alloc["misc"]
            optimization_method = "scipy_linprog"
        else:
            fb_alloc = solve_flexible_budget_analytical(available_for_flexible, weights, floors)
            transport_cost = fb_alloc["transport"]
            food_cost = fb_alloc["food"]
            activities_cost = fb_alloc["activities"]
            misc_cost = fb_alloc["misc"]
            optimization_method = "analytical_fallback"
    else:
        # Over-budget / constrained: maintain non-zero realistic estimates!
        transport_cost = min_transport
        food_cost = min_food
        activities_cost = min_activities
        misc_cost = min_misc
        optimization_method = "floor_constrained"

    # 7. Build breakdown
    breakdown: Dict[str, Any] = {
        "hotel": round(hotel_cost),
        "transportation": round(transport_cost),
        "food": round(food_cost),
        "activities": round(activities_cost),
        "miscellaneous": round(misc_cost),
        "emergency_reserve": round(emergency_reserve),
    }

    if selected_package:
        breakdown["package"] = round(package_cost)

    # 8. Totals and health status
    total_allocated = sum(breakdown.values())
    remaining_budget = round(total_budget - total_allocated)
    status = _health_status(remaining_budget, total_budget)

    # 9. Alternative hotels if over budget
    alternative_hotels = []
    if status == "Over Budget" and destination_id is not None:
        alternatives = recommend_hotels(
            db,
            destination_id,
            {**slots, "budget": "low"},
            max_results=3,
        )
        alternative_hotels = [
            hotel
            for hotel in alternatives
            if not working_hotel
            or hotel.get("id") != working_hotel.get("id")
        ]

    budget_output = {
        "tier": tier,
        "budget_source": budget_info["source"],
        "currency": "INR",
        "currency_symbol": "₹",
        "total_budget": round(total_budget),
        "breakdown": breakdown,
        "estimated_total": round(total_allocated),
        "remaining_budget": remaining_budget,
        "cost_per_traveler": round(total_allocated / travelers),
        "cost_per_day": round(total_allocated / duration_days),
        "status": status,
        "hotel_used": working_hotel,
        "hotel_cost_is_estimated": hotel_estimated,
        "package_used": selected_package,
        "alternative_hotels": alternative_hotels,
        "optimization_method": optimization_method,
        "disclaimer": DISCLAIMER_TEXT,
        "price_guarantee": False,
    }

    # If foreign currency requested, convert via currency_service
    if currency and currency.upper() != "INR":
        try:
            from app.services.currency_service import convert_budget_data
            return convert_budget_data(budget_output, currency.upper())
        except Exception as exc:
            logger.warning("Currency conversion failed in allocate_budget: %s", exc)

    return budget_output
