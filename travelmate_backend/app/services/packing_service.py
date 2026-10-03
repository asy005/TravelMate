# app/services/packing_service.py
"""
Shared packing-list generator.

This is the same logic previously inlined inside app/routes/plan_routes.py,
extracted so the new plan_orchestrator.py can reuse it without duplicating
the heuristics. Behavior is unchanged from the original inline version.
"""
from typing import List


def generate_packing(climate: str, duration_days: int, activities: List[str]) -> List[str]:
    items: List[str] = []
    climate = (climate or "").lower()

    if "tropical" in climate or "hot" in climate:
        items += ["light shirts", "shorts", "sunscreen", "hat"]
    elif "cold" in climate:
        items += ["warm jacket", "thermal wear"]
    else:
        items += ["light jacket", "comfortable clothes"]

    if any("trek" in a for a in activities):
        items += ["trekking shoes", "backpack"]
    if any("beach" in a for a in activities):
        items += ["swimwear", "beach towel"]

    items += ["toiletries", "phone charger", "travel documents"]

    if duration_days and duration_days > 7:
        items += ["extra clothes", "medicine kit"]

    seen = set()
    ordered = []
    for it in items:
        if it not in seen:
            ordered.append(it)
            seen.add(it)
    return ordered
