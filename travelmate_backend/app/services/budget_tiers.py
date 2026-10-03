# app/services/budget_tiers.py
"""
Single source of truth for mapping a free-text budget slot value to one of
the platform's three price tiers (low/medium/luxury). Split out from
budget_optimizer.py so hotel_recommender.py and package_recommender.py can
both depend on it without an import cycle (budget_optimizer also depends on
the recommenders to find a default listing to price against).
"""
from typing import Optional

TIER_DAILY_PER_PERSON = {"low": 2000, "medium": 4500, "luxury": 9000}

_TIER_ALIASES = {
    "low": "low", "affordable": "low", "budget": "low", "cheap": "low",
    "luxury": "luxury", "expensive": "luxury", "high": "luxury", "premium": "luxury",
}


def budget_tier(budget_label: Optional[str]) -> str:
    key = (budget_label or "medium").lower().strip()
    return _TIER_ALIASES.get(key, key if key in TIER_DAILY_PER_PERSON else "medium")
