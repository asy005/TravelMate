# app/routes/review_routes.py
"""
Review API endpoints (Phase 3).

Endpoints
---------
POST /reviews/              Submit a new review (authenticated users only).
GET  /reviews/hotel/{id}    List reviews + summary for a hotel.
GET  /reviews/package/{id}  List reviews + summary for a package.
GET  /reviews/me            List the current user's own reviews.
"""
from __future__ import annotations

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.destination import Destination
from app.models.hotel import Hotel
from app.models.package import Package
from app.models.review import Review
from app.schemas.review_schema import ReviewCreateIn, ReviewOut, ReviewSummaryOut
from app.services.auth_utils import get_current_user
from app.services.sentiment_analyser import (
    classify_review,
    extract_aspects_and_complaints,
    generate_sentiment_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_attractions_cache: Optional[Dict[str, Dict[str, Any]]] = None
_restaurants_cache: Optional[Dict[str, Dict[str, Any]]] = None


def _parse_safe_rating(val: Any) -> Optional[float]:
    """
    Parse a numeric rating string safely.
    Returns None if missing, blank, non-numeric, or outside valid range [1.0, 5.0].
    Never fabricates a fallback rating.
    """
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s:
        return None
    try:
        r = float(s)
        if 1.0 <= r <= 5.0:
            return round(r, 2)
        return None
    except (ValueError, TypeError):
        return None


def _find_datasets_file(filename: str) -> Optional[Path]:
    candidates = [
        Path(__file__).resolve().parents[3] / "datasets" / filename,
        Path(os.getcwd()) / "datasets" / filename,
        Path(os.getcwd()).parent / "datasets" / filename,
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def _get_attraction_by_id(att_id: str) -> Optional[Dict[str, Any]]:
    global _attractions_cache
    if _attractions_cache is None:
        cache: Dict[str, Dict[str, Any]] = {}
        csv_path = _find_datasets_file("attractions.csv")
        if csv_path:
            try:
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        aid = (row.get("attraction_id") or "").strip()
                        if not aid:
                            continue
                        rating = _parse_safe_rating(row.get("rating"))
                        entry = {
                            "id": aid,
                            "name": row.get("attraction_name", ""),
                            "city": row.get("city", ""),
                            "state": row.get("state", ""),
                            "category": row.get("category", ""),
                            "rating": rating,
                        }
                        cache[aid.upper()] = entry
            except FileNotFoundError:
                logger.warning("attractions.csv file not found at %s", csv_path)
            except Exception as exc:
                logger.error("Failed to load attractions from %s: %s", csv_path, exc, exc_info=True)
        else:
            logger.warning("attractions.csv could not be located in datasets directories")
        _attractions_cache = cache
    return _attractions_cache.get(att_id.strip().upper())


def _get_restaurant_by_id(rst_id: str) -> Optional[Dict[str, Any]]:
    global _restaurants_cache
    if _restaurants_cache is None:
        cache: Dict[str, Dict[str, Any]] = {}
        csv_path = _find_datasets_file("restaurants.csv")
        if csv_path:
            try:
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        rid = (row.get("restaurant_id") or "").strip()
                        if not rid:
                            continue
                        rating = _parse_safe_rating(row.get("rating"))
                        entry = {
                            "id": rid,
                            "name": row.get("restaurant_name", ""),
                            "city": row.get("city", ""),
                            "cuisine": row.get("cuisine", ""),
                            "price_range": row.get("price_range", ""),
                            "address": row.get("address", ""),
                            "rating": rating,
                        }
                        cache[rid.upper()] = entry
            except FileNotFoundError:
                logger.warning("restaurants.csv file not found at %s", csv_path)
            except Exception as exc:
                logger.error("Failed to load restaurants from %s: %s", csv_path, exc, exc_info=True)
        else:
            logger.warning("restaurants.csv could not be located in datasets directories")
        _restaurants_cache = cache
    return _restaurants_cache.get(rst_id.strip().upper())


def _build_summary(
    entity_type: str,
    entity_id: Union[int, str],
    reviews: List[Review],
    recent_limit: int = 5,
    fallback_rating: Optional[float] = None,
) -> ReviewSummaryOut:
    total = len(reviews)
    if total == 0:
        return ReviewSummaryOut(
            entity_type=entity_type,
            entity_id=entity_id,
            total_reviews=0,
            average_rating=fallback_rating,
            positive_count=0,
            neutral_count=0,
            negative_count=0,
            positive_pct=0.0,
            negative_pct=0.0,
            sentiment_summary=None,
            praised_aspects=[],
            recurring_complaints=[],
            recent_reviews=[],
        )

    avg_rating = round(sum(r.rating for r in reviews) / total, 2)
    pos = sum(1 for r in reviews if r.sentiment_label == "positive")
    neg = sum(1 for r in reviews if r.sentiment_label == "negative")
    neu = total - pos - neg

    texts = [r.review_text for r in reviews if r.review_text]
    praised, complaints = extract_aspects_and_complaints(texts)
    summary_text = generate_sentiment_summary(total, pos, neu, neg)

    # Most recent N reviews (created_at desc)
    from datetime import datetime, date as _date
    _epoch = datetime(1970, 1, 1)
    sorted_reviews = sorted(
        reviews,
        key=lambda r: (r.created_at or _epoch),
        reverse=True,
    )
    recent = sorted_reviews[:recent_limit]

    return ReviewSummaryOut(
        entity_type=entity_type,
        entity_id=entity_id,
        total_reviews=total,
        average_rating=avg_rating,
        positive_count=pos,
        neutral_count=neu,
        negative_count=neg,
        positive_pct=round(pos / total * 100, 1),
        negative_pct=round(neg / total * 100, 1),
        sentiment_summary=summary_text,
        praised_aspects=praised,
        recurring_complaints=complaints,
        recent_reviews=[ReviewOut.model_validate(r) for r in recent],
    )


# ---------------------------------------------------------------------------
# POST /reviews/ -- submit a new review
# ---------------------------------------------------------------------------

@router.post("/", response_model=ReviewOut, status_code=201)
def submit_review(
    payload: ReviewCreateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Submit a review for a hotel or package.

    Rules
    -----
    * Authenticated users only (403 if no valid token).
    * Exactly one of hotel_id / package_id must be provided (validated by schema).
    * The referenced entity must exist (404 if not).
    * Each user may review a given hotel/package only once (409 on duplicate).
    * Sentiment is computed automatically from review_text (+ rating fallback).
    """
    # --- Verify entity exists ---
    if payload.hotel_id is not None:
        entity = db.query(Hotel).filter(Hotel.id == payload.hotel_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="Hotel not found")
        # Duplicate check for this user
        existing = (
            db.query(Review)
            .filter(
                Review.user_id == current_user.id,
                Review.hotel_id == payload.hotel_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="You have already reviewed this hotel. Edit or delete your existing review.",
            )

    else:  # package
        entity = db.query(Package).filter(Package.id == payload.package_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="Package not found")
        existing = (
            db.query(Review)
            .filter(
                Review.user_id == current_user.id,
                Review.package_id == payload.package_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="You have already reviewed this package. Edit or delete your existing review.",
            )

    # --- Compute sentiment ---
    sentiment = classify_review(payload.review_text, payload.rating)

    # --- Persist ---
    review = Review(
        user_id=current_user.id,
        hotel_id=payload.hotel_id,
        package_id=payload.package_id,
        rating=payload.rating,
        review_text=payload.review_text,
        sentiment_label=sentiment.label,
        sentiment_score=sentiment.score,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return ReviewOut.model_validate(review)


# ---------------------------------------------------------------------------
# GET /reviews/hotel/{hotel_id}
# ---------------------------------------------------------------------------

@router.get("/hotel/{hotel_id}", response_model=ReviewSummaryOut)
def get_hotel_reviews(
    hotel_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
):
    """Return paginated reviews and a sentiment summary for a hotel."""
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    all_reviews = db.query(Review).filter(Review.hotel_id == hotel_id).all()
    return _build_summary("hotel", hotel_id, all_reviews)


# ---------------------------------------------------------------------------
# GET /reviews/package/{package_id}
# ---------------------------------------------------------------------------

@router.get("/package/{package_id}", response_model=ReviewSummaryOut)
def get_package_reviews(
    package_id: int,
    db: Session = Depends(get_db),
):
    """Return reviews and a sentiment summary for a package."""
    pkg = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    all_reviews = db.query(Review).filter(Review.package_id == package_id).all()
    return _build_summary("package", package_id, all_reviews)


# ---------------------------------------------------------------------------
# GET /reviews/destination/{destination_id}
# ---------------------------------------------------------------------------

@router.get("/destination/{destination_id}", response_model=ReviewSummaryOut)
def get_destination_reviews(
    destination_id: int,
    db: Session = Depends(get_db),
):
    """Return aggregated reviews, sentiment summary, praised aspects, and complaints for a destination."""
    dest = db.query(Destination).filter(Destination.id == destination_id).first()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    hotel_ids = [h[0] for h in db.query(Hotel.id).filter(Hotel.destination_id == destination_id).all()]
    package_ids = [p[0] for p in db.query(Package.id).filter(Package.destination_id == destination_id).all()]

    filters = []
    if hotel_ids:
        filters.append(Review.hotel_id.in_(hotel_ids))
    if package_ids:
        filters.append(Review.package_id.in_(package_ids))

    all_reviews: List[Review] = []
    if filters:
        all_reviews = db.query(Review).filter(or_(*filters)).all()

    return _build_summary(
        "destination",
        destination_id,
        all_reviews,
        fallback_rating=getattr(dest, "avg_rating", None),
    )


# ---------------------------------------------------------------------------
# GET /reviews/attraction/{attraction_id}
# ---------------------------------------------------------------------------

@router.get("/attraction/{attraction_id}", response_model=ReviewSummaryOut)
def get_attraction_reviews(
    attraction_id: str,
):
    """Return available rating and sentiment overview for an attraction from attractions dataset."""
    att = _get_attraction_by_id(attraction_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attraction not found")

    rating = att.get("rating")
    summary_text = (
        f"Verified visitor rating: {rating:.1f}/5.0 based on tourism dataset records."
        if rating is not None
        else "No ratings available yet."
    )
    return ReviewSummaryOut(
        entity_type="attraction",
        entity_id=attraction_id,
        total_reviews=0,
        average_rating=rating,
        positive_count=0,
        neutral_count=0,
        negative_count=0,
        positive_pct=0.0,
        negative_pct=0.0,
        sentiment_summary=summary_text,
        praised_aspects=[],
        recurring_complaints=[],
        recent_reviews=[],
    )


# ---------------------------------------------------------------------------
# GET /reviews/restaurant/{restaurant_id}
# ---------------------------------------------------------------------------

@router.get("/restaurant/{restaurant_id}", response_model=ReviewSummaryOut)
def get_restaurant_reviews(
    restaurant_id: str,
):
    """Return available rating and sentiment overview for a restaurant from restaurants dataset."""
    rst = _get_restaurant_by_id(restaurant_id)
    if not rst:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    rating = rst.get("rating")
    summary_text = (
        f"Verified diner rating: {rating:.1f}/5.0 based on restaurant dataset records."
        if rating is not None
        else "No ratings available yet."
    )
    return ReviewSummaryOut(
        entity_type="restaurant",
        entity_id=restaurant_id,
        total_reviews=0,
        average_rating=rating,
        positive_count=0,
        neutral_count=0,
        negative_count=0,
        positive_pct=0.0,
        negative_pct=0.0,
        sentiment_summary=summary_text,
        praised_aspects=[],
        recurring_complaints=[],
        recent_reviews=[],
    )


# ---------------------------------------------------------------------------
# GET /reviews/me -- current user's reviews
# ---------------------------------------------------------------------------

@router.get("/me", response_model=List[ReviewOut])
def my_reviews(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Return the authenticated user's submitted reviews."""
    reviews = (
        db.query(Review)
        .filter(Review.user_id == current_user.id)
        .order_by(Review.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [ReviewOut.model_validate(r) for r in reviews]
