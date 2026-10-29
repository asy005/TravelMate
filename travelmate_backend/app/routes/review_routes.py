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

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hotel import Hotel
from app.models.package import Package
from app.models.review import Review
from app.schemas.review_schema import ReviewCreateIn, ReviewOut, ReviewSummaryOut
from app.services.auth_utils import get_current_user
from app.services.sentiment_analyser import classify_review

router = APIRouter(prefix="/reviews", tags=["reviews"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_summary(
    entity_type: str,
    entity_id: int,
    reviews: List[Review],
    recent_limit: int = 5,
) -> ReviewSummaryOut:
    total = len(reviews)
    if total == 0:
        return ReviewSummaryOut(
            entity_type=entity_type,
            entity_id=entity_id,
            total_reviews=0,
            average_rating=None,
            positive_count=0,
            neutral_count=0,
            negative_count=0,
            positive_pct=0.0,
            negative_pct=0.0,
            recent_reviews=[],
        )

    avg_rating = round(sum(r.rating for r in reviews) / total, 2)
    pos = sum(1 for r in reviews if r.sentiment_label == "positive")
    neg = sum(1 for r in reviews if r.sentiment_label == "negative")
    neu = total - pos - neg

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
