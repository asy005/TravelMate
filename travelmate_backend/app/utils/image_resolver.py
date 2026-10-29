"""
image_resolver.py
-----------------
Resolves dataset image URLs for destinations, attractions, and hotels.

All image files live under:
  <project_root>/datasets/images/<category>/

This module is at:
  travelmate_backend/app/utils/image_resolver.py
  parents[0]=utils, parents[1]=app, parents[2]=travelmate_backend, parents[3]=project_root

URL paths are served by the /dataset-images StaticFiles mount defined in main.py.
"""

from pathlib import Path
from typing import Optional, Dict

# ── Base path ───────────────────────────────────────────────────────────────
_IMAGES_BASE: Path = Path(__file__).resolve().parents[3] / "datasets" / "images"

# ── Module-level caches (populated lazily on first call) ────────────────────
_dest_cache: Optional[Dict[str, str]] = None   # csv_id prefix -> filename
_att_cache: Optional[Dict[str, str]] = None    # att_id prefix -> filename
_hotel_cache: Optional[Dict[str, str]] = None  # type name -> filename


# ── Internal helpers ────────────────────────────────────────────────────────

def _build_dest_cache() -> Dict[str, str]:
    """Scan destinations/ once and map csv_id prefix (e.g. 'D0001') -> filename."""
    cache: Dict[str, str] = {}
    dest_dir = _IMAGES_BASE / "destinations"
    if not dest_dir.exists():
        return cache
    for f in dest_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            # File names like D0001_Goa.jpg — key is the prefix before the first '_'
            prefix = f.stem.split("_")[0].upper()
            cache[prefix] = f.name
    return cache


def _build_att_cache() -> Dict[str, str]:
    """Scan attractions/ once and map numeric att_id -> filename."""
    cache: Dict[str, str] = {}
    att_dir = _IMAGES_BASE / "attractions"
    if not att_dir.exists():
        return cache
    for f in att_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            # File names like ATT0003_Akshardham_Temple.jpg
            # Key: the full prefix before first '_', e.g. 'ATT0003'
            prefix = f.stem.split("_")[0].upper()
            cache[prefix] = f.name
    return cache


def _build_hotel_cache() -> Dict[str, str]:
    """Scan hotels/ once and map type name (lowercase, no spaces) -> filename."""
    cache: Dict[str, str] = {}
    hotel_dir = _IMAGES_BASE / "hotels"
    if not hotel_dir.exists():
        return cache
    for f in hotel_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            # File names like Hotel.jpg, Resort.jpg, Guest_House.jpg
            key = f.stem.lower().replace("_", " ").replace("-", " ")
            cache[key] = f.name
    return cache


# ── Public API ───────────────────────────────────────────────────────────────

def resolve_destination_image(
    destination_id: int,
    csv_destination_id: Optional[str] = None,
) -> str:
    """
    Return the URL path for a destination image, or "" if none found.

    Looks for files matching pattern D{csv_id}_*.jpg in datasets/images/destinations/.
    The csv_destination_id is like "D0001".
    """
    global _dest_cache
    if _dest_cache is None:
        _dest_cache = _build_dest_cache()

    if not csv_destination_id:
        return ""

    prefix = csv_destination_id.strip().upper()
    filename = _dest_cache.get(prefix)
    if filename:
        return f"/dataset-images/destinations/{filename}"
    return ""


def resolve_attraction_image(attraction_id: str) -> str:
    """
    Return the URL path for an attraction image, or "" if none found.

    Looks for files matching ATT{id}_*.jpg in datasets/images/attractions/.
    The attraction_id should be like "ATT0003" or "0003" (normalized internally).
    """
    global _att_cache
    if _att_cache is None:
        _att_cache = _build_att_cache()

    if not attraction_id:
        return ""

    # Normalize: ensure it starts with ATT and is uppercase
    att_id = attraction_id.strip().upper()
    if not att_id.startswith("ATT"):
        att_id = "ATT" + att_id

    filename = _att_cache.get(att_id)
    if filename:
        return f"/dataset-images/attractions/{filename}"
    return ""


def resolve_hotel_image(accommodation_type: str) -> str:
    """
    Return the URL path for a hotel type image, or "" if none found.

    Looks for generic type images (Hotel.jpg, Resort.jpg, etc.) in datasets/images/hotels/.
    Matching is case-insensitive.
    """
    global _hotel_cache
    if _hotel_cache is None:
        _hotel_cache = _build_hotel_cache()

    if not accommodation_type:
        return ""

    # Normalize: lowercase, collapse underscores/hyphens to spaces
    key = accommodation_type.strip().lower().replace("_", " ").replace("-", " ")
    filename = _hotel_cache.get(key)
    if filename:
        return f"/dataset-images/hotels/{filename}"
    return ""
