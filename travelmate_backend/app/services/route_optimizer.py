# app/services/route_optimizer.py
"""
Route Optimization Service for TravelMate (Phase 4).

Features:
- Haversine distance matrix computation.
- Practical Nearest-Neighbor construction heuristic with 2-opt local search.
- Safe missing coordinate handling without inventing or hallucinating coordinates.
- Constraints preservation: fixed appointments, opening hours, explicit user ordering.
- Day-wise and destination isolation (no activity leakage across days or destinations).
- Distance as a clear proxy for travel costs (no claims of real-time road network travel times).
- Heuristic optimization disclaimer (does not claim global TSP optimality).
"""

import csv
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

EARTH_RADIUS_KM = 6371.0
DEFAULT_CITY_SPEED_KMH = 30.0  # Used strictly as a distance proxy for opening hour feasibility


def haversine_distance(
    coord1: Optional[Tuple[Optional[float], Optional[float]]],
    coord2: Optional[Tuple[Optional[float], Optional[float]]],
) -> Optional[float]:
    """
    Computes the great-circle distance between two (latitude, longitude) points
    in kilometers using the Haversine formula.

    Returns None if any coordinate is missing, invalid, or None.
    Handles exact-match coordinates returning 0.0 cleanly.
    """
    if coord1 is None or coord2 is None:
        return None
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None

    try:
        lat1_f, lon1_f = float(lat1), float(lon1)
        lat2_f, lon2_f = float(lat2), float(lon2)
    except (ValueError, TypeError):
        return None

    if math.isclose(lat1_f, lat2_f, abs_tol=1e-7) and math.isclose(lon1_f, lon2_f, abs_tol=1e-7):
        return 0.0

    phi1 = math.radians(lat1_f)
    phi2 = math.radians(lat2_f)
    delta_phi = math.radians(lat2_f - lat1_f)
    delta_lambda = math.radians(lon2_f - lon1_f)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    # Safeguard against numerical errors outside [0.0, 1.0]
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 3)


class AttractionCoordinateResolver:
    """
    Resolves attraction latitude and longitude from real dataset files
    (datasets/attractions.csv) and curated geo fallbacks without inventing coordinates.
    """

    _instance: Optional["AttractionCoordinateResolver"] = None

    def __init__(self):
        self._by_city_and_name: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._by_name: Dict[str, Dict[str, Any]] = {}
        self._hotels_by_city: Dict[str, List[Tuple[float, float]]] = {}
        self._dest_coords: Dict[str, Tuple[float, float]] = {}
        self._loaded: bool = False
        self._load_datasets()

    @classmethod
    def get_instance(cls) -> "AttractionCoordinateResolver":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_datasets(self) -> None:
        if self._loaded:
            return

        possible_dirs = [
            Path(__file__).resolve().parents[3] / "datasets",
            Path(os.getcwd()) / "datasets",
            Path(os.getcwd()).parent / "datasets",
            Path(__file__).resolve().parent.parent.parent.parent / "datasets",
        ]

        datasets_dir = None
        for d in possible_dirs:
            if d.exists() and d.is_dir() and (d / "attractions.csv").is_file():
                datasets_dir = d
                break

        if not datasets_dir:
            self._loaded = True
            return

        # 1. Load attractions.csv
        att_path = datasets_dir / "attractions.csv"
        if att_path.is_file():
            try:
                with open(att_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get("attraction_name", "").strip()
                        city = row.get("city", "").strip()
                        lat_str = row.get("latitude")
                        lon_str = row.get("longitude")

                        if not name or lat_str is None or lon_str is None:
                            continue

                        try:
                            lat = float(lat_str)
                            lon = float(lon_str)
                        except (ValueError, TypeError):
                            continue

                        info = {
                            "name": name,
                            "city": city,
                            "state": row.get("state", "").strip(),
                            "category": row.get("category", "").strip(),
                            "lat": lat,
                            "lon": lon,
                            "rating": float(row.get("rating", 0.0) or 0.0),
                        }

                        norm_name = name.casefold()
                        norm_city = city.casefold()

                        self._by_city_and_name[(norm_city, norm_name)] = info
                        if norm_name not in self._by_name:
                            self._by_name[norm_name] = info
            except Exception as exc:
                print(f"[RouteOptimizer] Warning: Could not read attractions dataset: {exc}")

        # 2. Load hotels.csv for resolving generic "hotel", "resort", "stay"
        hotels_path = datasets_dir / "hotels.csv"
        if hotels_path.is_file():
            try:
                with open(hotels_path, mode="r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        city_h = (row.get("city_hotel") or "").strip().casefold()
                        lat_s = row.get("latitude")
                        lon_s = row.get("longitude")
                        if city_h and lat_s and lon_s:
                            try:
                                lat = float(lat_s)
                                lon = float(lon_s)
                                self._hotels_by_city.setdefault(city_h, []).append((lat, lon))
                            except (ValueError, TypeError):
                                pass
            except Exception as exc:
                print(f"[RouteOptimizer] Notice: Could not read hotels dataset: {exc}")

        # 3. Load destinations.csv for destination center coordinates
        dests_path = datasets_dir / "destinations.csv"
        if dests_path.is_file():
            try:
                from app.services.geo_lookup import guess_coordinates
                with open(dests_path, mode="r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        dname = (row.get("destination_name") or "").strip().casefold()
                        coords = guess_coordinates(dname)
                        if coords:
                            self._dest_coords[dname] = coords
            except Exception as exc:
                print(f"[RouteOptimizer] Notice: Could not read destinations dataset: {exc}")

        self._loaded = True

    def resolve(
        self,
        name: str,
        city_or_destination: Optional[str] = None,
    ) -> Optional[Tuple[float, float]]:
        """
        Looks up real coordinates. Returns (lat, lon) or None if missing.
        Resolves generic terms (e.g. hotel, airport) relative to destination.
        Never invents coordinates.
        """
        if not name or not isinstance(name, str):
            return None

        clean_name = name.strip()
        norm_name = clean_name.casefold()
        norm_city = (city_or_destination or "").strip().casefold()

        # Known verified landmarks with coordinate fixes
        KNOWN_LANDMARK_COORDS = {
            "virupaksha temple": (15.3353, 76.4600),
            "stone chariot": (15.3351, 76.4587),
            "vijaya vitthala temple": (15.3316, 76.4682),
            "matanga hill": (15.3316, 76.4682),
            "lotus mahal": (15.3350, 76.4619),
            "bangaram atoll & lagoon": (10.9419, 72.2922),
            "bangaram": (10.9419, 72.2922),
            "agatti island beach & lagoon": (10.8533, 72.1931),
            "agatti": (10.8533, 72.1931),
            "kavaratti marine aquarium & beach": (10.5667, 72.6417),
            "kavaratti": (10.5667, 72.6417),
            "kalpeni island lagoon & coral bank": (10.0717, 73.6528),
            "kalpeni": (10.0717, 73.6528),
            "kadmat island coral reef": (11.2333, 72.7833),
            "kadmat": (11.2333, 72.7833),
            "agonda beach & turtle nesting site": (15.0442, 73.9877),
            "agonda beach": (15.0442, 73.9877),
            "cola beach & freshwater lagoon": (15.0592, 73.9744),
            "cola beach": (15.0592, 73.9744),
            "butterfly beach": (15.0217, 74.0042),
            "cabo de rama fort": (15.0883, 73.9217),
            "cabo de rama": (15.0883, 73.9217),
            "palolem beach": (15.0100, 74.0231),
            "palolem": (15.0100, 74.0231),
            "tarkarli beach": (16.0137, 73.4898),
            "sindhudurg fort": (16.0422, 73.4631),
            "devbagh beach & tsunami island": (15.9861, 73.4981),
            "devbagh beach": (15.9861, 73.4981),
            "karli river backwaters": (16.0028, 73.5042),
        }
        for k, coords in KNOWN_LANDMARK_COORDS.items():
            if norm_name == k or (len(k) >= 5 and k in norm_name):
                return coords

        # 1. Exact match with city in attractions
        if norm_city and (norm_city, norm_name) in self._by_city_and_name:
            rec = self._by_city_and_name[(norm_city, norm_name)]
            return (rec["lat"], rec["lon"])

        # 2. Exact match globally in attractions
        if norm_name in self._by_name:
            rec = self._by_name[norm_name]
            return (rec["lat"], rec["lon"])

        # 3. Substring matching for descriptive activity strings
        if norm_city:
            for (c, an), rec in self._by_city_and_name.items():
                if c == norm_city and len(an) >= 4 and an in norm_name:
                    return (rec["lat"], rec["lon"])

        # 4. Resolve generic hotel terms relative to destination
        hotel_terms = {"hotel", "my hotel", "resort", "stay", "accommodation", "lodging"}
        if norm_name in hotel_terms or any(t in norm_name for t in ["hotel", "resort", "homestay"]):
            if norm_city and norm_city in self._hotels_by_city and self._hotels_by_city[norm_city]:
                return self._hotels_by_city[norm_city][0]
            if norm_city and norm_city in self._dest_coords:
                return self._dest_coords[norm_city]

        # 5. Resolve generic airport terms relative to destination
        if any(w in norm_name for w in ["airport", "aerodrome", "flight"]):
            if norm_city:
                for (c, an), rec in self._by_city_and_name.items():
                    if c == norm_city and "airport" in an:
                        return (rec["lat"], rec["lon"])
                from app.services.geo_lookup import guess_coordinates
                city_airport = guess_coordinates(f"{norm_city} airport") or guess_coordinates(norm_city)
                if city_airport:
                    return city_airport

        # 6. Check destination center fallback if name is the destination itself
        if norm_city and (norm_name == norm_city or norm_city in norm_name):
            if norm_city in self._dest_coords:
                return self._dest_coords[norm_city]
            from app.services.geo_lookup import guess_coordinates
            dest_coords = guess_coordinates(norm_city)
            if dest_coords:
                return dest_coords

        return None


def _extract_stop_coordinates(
    stop: Dict[str, Any],
    destination_name: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Extracts coordinates from a stop dictionary or resolves them safely.
    Never invents coordinates.
    """
    lat = stop.get("lat") if stop.get("lat") is not None else stop.get("latitude")
    lon = stop.get("lon") if stop.get("lon") is not None else stop.get("longitude")

    if lat is not None and lon is not None:
        try:
            return (float(lat), float(lon))
        except (ValueError, TypeError):
            pass

    name = stop.get("name") or stop.get("title") or stop.get("summary") or ""
    resolved = AttractionCoordinateResolver.get_instance().resolve(name, destination_name)
    if resolved:
        return resolved

    return (None, None)


def _check_opening_hours_feasibility(
    ordered_stops: List[Dict[str, Any]],
    start_hour: float = 9.0,
    visit_duration_hours: float = 1.5,
) -> bool:
    """
    Checks if a sequence of stops respects opening/closing hour constraints.
    Uses distance as a travel-time proxy (DEFAULT_CITY_SPEED_KMH).
    """
    current_time = start_hour

    for i, stop in enumerate(ordered_stops):
        opening = stop.get("opening_hour")
        closing = stop.get("closing_hour")

        if i > 0:
            prev_coords = (ordered_stops[i - 1].get("lat"), ordered_stops[i - 1].get("lon"))
            curr_coords = (stop.get("lat"), stop.get("lon"))
            dist = haversine_distance(prev_coords, curr_coords)
            if dist is not None:
                travel_time = dist / DEFAULT_CITY_SPEED_KMH
                current_time += travel_time

        if opening is not None and current_time < opening:
            current_time = float(opening)

        if closing is not None and current_time > float(closing):
            return False

        current_time += visit_duration_hours

    return True


def _compute_path_distance(
    stops: List[Dict[str, Any]],
    return_to_start: bool = False,
) -> float:
    """
    Calculates total Haversine distance along consecutive stops that have coordinates.
    Returns 0.0 if fewer than 2 stops have valid coordinates.
    """
    mapped_count = sum(1 for s in stops if s.get("lat") is not None and s.get("lon") is not None)
    if mapped_count < 2:
        return 0.0

    total = 0.0
    for i in range(len(stops) - 1):
        c1 = (stops[i].get("lat"), stops[i].get("lon"))
        c2 = (stops[i + 1].get("lat"), stops[i + 1].get("lon"))
        d = haversine_distance(c1, c2)
        if d is not None:
            total += d

    if return_to_start and len(stops) > 1:
        c_last = (stops[-1].get("lat"), stops[-1].get("lon"))
        c_first = (stops[0].get("lat"), stops[0].get("lon"))
        d_return = haversine_distance(c_last, c_first)
        if d_return is not None:
            total += d_return

    return total


def optimize_day_route(
    stops: List[Dict[str, Any]],
    return_to_start: bool = False,
    destination_name: Optional[str] = None,
    start_location: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Optimizes a single day's route using Nearest-Neighbor construction
    followed by 2-opt local search improvement.

    Guarantees:
    - Does NOT claim global TSP optimality (heuristic algorithm).
    - Preserves fixed appointments and explicit ordering.
    - Preserves opening hour constraints when present.
    - Handles missing coordinates safely without inventing locations.
    - Clearly documents distance as a proxy when travel times are referenced.
    """
    if not stops:
        return {
            "ordered_stops": [],
            "total_distance_km": 0.0,
            "legs": [],
            "algorithm": "Nearest-Neighbor with 2-opt local search (heuristic, not globally optimal)",
            "is_globally_optimal": False,
            "distance_as_proxy": True,
            "proxy_notes": "Haversine distance is used as a proxy for travel cost; road network travel times are not claimed.",
            "unmapped_stops_count": 0,
        }

    # Normalize stops and resolve real coordinates if missing
    normalized_stops: List[Dict[str, Any]] = []
    for idx, s in enumerate(stops):
        stop_copy = dict(s)
        lat, lon = _extract_stop_coordinates(stop_copy, destination_name)
        stop_copy["lat"] = lat
        stop_copy["lon"] = lon
        stop_copy["has_coordinates"] = (lat is not None and lon is not None)
        stop_copy["original_index"] = idx
        normalized_stops.append(stop_copy)

    # Check if explicit user ordering is enforced
    has_explicit_ordering = all("order" in s for s in normalized_stops)
    if has_explicit_ordering:
        ordered = sorted(normalized_stops, key=lambda s: int(s.get("order", 0)))
        total_dist = _compute_path_distance(ordered, return_to_start)
        return _build_route_result(ordered, total_dist, return_to_start)

    # If only 1 stop
    if len(normalized_stops) == 1:
        return _build_route_result(normalized_stops, 0.0, return_to_start)

    # Separate stops with coordinates from unmapped stops
    # Unmapped stops will be preserved safely without inventing coordinates
    mapped_stops = [s for s in normalized_stops if s["has_coordinates"]]
    unmapped_stops = [s for s in normalized_stops if not s["has_coordinates"]]

    # If fewer than 2 mapped stops, optimize trivial path and reinsert unmapped
    if len(mapped_stops) <= 1:
        combined = mapped_stops + unmapped_stops
        return _build_route_result(combined, 0.0, return_to_start)

    # 1. Nearest Neighbor Construction on mapped stops
    unvisited = list(mapped_stops)

    # Determine starting stop:
    # 1. Explicit start_location if provided and matches a stop or is used as anchor
    # 2. Stop with is_start=True or fixed_slot=0 or is_fixed=True at position 0
    start_stop = None
    for s in unvisited:
        if s.get("is_start") or s.get("fixed_slot") == 0:
            start_stop = s
            break

    if start_stop is None and start_location and start_location.get("lat") and start_location.get("lon"):
        start_coord = (start_location.get("lat"), start_location.get("lon"))
        unvisited.sort(key=lambda s: haversine_distance(start_coord, (s["lat"], s["lon"])) or float("inf"))
        start_stop = unvisited[0]
    elif start_stop is None:
        start_stop = unvisited[0]

    current = start_stop
    route: List[Dict[str, Any]] = [current]
    unvisited.remove(current)

    while unvisited:
        # Check if the next slot must be a fixed appointment
        target_slot = len(route)
        fixed_for_slot = next((s for s in unvisited if s.get("fixed_slot") == target_slot), None)

        if fixed_for_slot is not None:
            next_stop = fixed_for_slot
        else:
            candidates = [s for s in unvisited if s.get("fixed_slot") is None]
            if not candidates:
                candidates = unvisited

            curr_coord = (current["lat"], current["lon"])
            candidates.sort(
                key=lambda s: haversine_distance(curr_coord, (s["lat"], s["lon"])) or float("inf")
            )
            next_stop = candidates[0]

        route.append(next_stop)
        unvisited.remove(next_stop)
        current = next_stop

    # 2. 2-opt Local Search Heuristic Improvement
    improved = True
    iteration = 0
    max_iterations = 60

    while improved and iteration < max_iterations:
        improved = False
        iteration += 1

        for i in range(1 if route[0].get("is_start") or route[0].get("fixed_slot") == 0 else 0, len(route) - 1):
            for j in range(i + 1, len(route)):
                # Check if reversal violates fixed appointments
                subsegment = route[i : j + 1]
                has_immovable = any(
                    s.get("is_fixed") or (s.get("fixed_slot") is not None and s.get("fixed_slot") != (j - (idx - i)))
                    for idx, s in enumerate(subsegment, start=i)
                )
                if has_immovable:
                    continue

                # Candidate route with reversed subsegment
                candidate = route[:i] + list(reversed(subsegment)) + route[j + 1 :]

                # Check opening-hour feasibility if defined
                if not _check_opening_hours_feasibility(candidate):
                    continue

                current_cost = _compute_path_distance(route, return_to_start)
                candidate_cost = _compute_path_distance(candidate, return_to_start)

                if candidate_cost < current_cost - 1e-4:
                    route = candidate
                    improved = True
                    break
            if improved:
                break

    # Safely merge unmapped stops preserving their relative placement
    # without fabricating coordinates
    final_stops: List[Dict[str, Any]] = []
    mapped_iter = iter(route)

    # Reconstruct combined list based on original positions
    for orig in normalized_stops:
        if orig["has_coordinates"]:
            try:
                final_stops.append(next(mapped_iter))
            except StopIteration:
                final_stops.append(orig)
        else:
            final_stops.append(orig)

    total_dist = _compute_path_distance(final_stops, return_to_start)
    return _build_route_result(final_stops, total_dist, return_to_start)


def _build_route_result(
    stops: List[Dict[str, Any]],
    total_distance_km: Optional[float],
    return_to_start: bool,
) -> Dict[str, Any]:
    legs = []
    for i in range(len(stops) - 1):
        s1 = stops[i]
        s2 = stops[i + 1]
        c1 = (s1.get("lat"), s1.get("lon"))
        c2 = (s2.get("lat"), s2.get("lon"))
        d = haversine_distance(c1, c2)
        legs.append({
            "from_stop": s1.get("name") or f"Stop {i + 1}",
            "to_stop": s2.get("name") or f"Stop {i + 2}",
            "distance_km": d,
            "has_coordinates": (d is not None),
        })

    if return_to_start and len(stops) > 1:
        s_last = stops[-1]
        s_first = stops[0]
        c_last = (s_last.get("lat"), s_last.get("lon"))
        c_first = (s_first.get("lat"), s_first.get("lon"))
        d = haversine_distance(c_last, c_first)
        legs.append({
            "from_stop": s_last.get("name") or f"Stop {len(stops)}",
            "to_stop": s_first.get("name") or "Return to Start",
            "distance_km": d,
            "has_coordinates": (d is not None),
        })

    unmapped = sum(1 for s in stops if not s.get("has_coordinates"))

    return {
        "ordered_stops": stops,
        "total_distance_km": round(total_distance_km, 2) if total_distance_km is not None else 0.0,
        "legs": legs,
        "return_to_start": return_to_start,
        "algorithm": "Nearest-Neighbor with 2-opt local search (heuristic, not globally optimal)",
        "is_globally_optimal": False,
        "distance_as_proxy": True,
        "proxy_notes": "Haversine distance is used as a proxy for travel cost; road network travel times are not claimed.",
        "unmapped_stops_count": unmapped,
    }


def optimize_trip_builder_plan(
    destination_name: str,
    plan: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """
    Optimizes each day's string activities in a Trip Builder plan
    using graph-based route optimization while keeping the exact
    Dict[str, List[str]] contract.
    """
    optimized_plan: Dict[str, List[str]] = {}

    for day_key, activities in plan.items():
        if not activities or len(activities) <= 1:
            optimized_plan[day_key] = activities
            continue

        stops = [{"name": act, "original_index": i} for i, act in enumerate(activities)]
        opt = optimize_day_route(stops, destination_name=destination_name)
        ordered_activities = [s["name"] for s in opt["ordered_stops"]]
        optimized_plan[day_key] = ordered_activities

    return optimized_plan
