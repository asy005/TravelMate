# app/schemas/review_schema.py
"""Pydantic v2 schemas for Review endpoints (Phase 3)."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class ReviewCreateIn(BaseModel):
    """Payload sent by an authenticated user to submit a new review."""

    hotel_id: Optional[int] = Field(None, description="ID of the hotel being reviewed")
    package_id: Optional[int] = Field(None, description="ID of the package being reviewed")

    rating: float = Field(..., ge=1.0, le=5.0, description="Star rating 1.0–5.0")
    review_text: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Review body text (1–4096 characters)",
    )

    @field_validator("review_text", mode="before")
    @classmethod
    def strip_review_text(cls, v: str) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("review_text must not be blank or whitespace-only")
            return stripped
        return v

    @model_validator(mode="after")
    def exactly_one_entity(self) -> "ReviewCreateIn":
        hotel_id = self.hotel_id
        package_id = self.package_id
        if hotel_id is None and package_id is None:
            raise ValueError("Exactly one of hotel_id or package_id must be provided")
        if hotel_id is not None and package_id is not None:
            raise ValueError("Only one of hotel_id or package_id may be provided, not both")
        return self


class ReviewOut(BaseModel):
    """Response schema for a single review."""

    id: int
    csv_review_id: Optional[str] = None
    csv_user_id: Optional[str] = None
    user_id: Optional[int] = None

    hotel_id: Optional[int] = None
    package_id: Optional[int] = None

    rating: float
    review_text: str
    review_date: Optional[date] = None
    images: Optional[str] = None

    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None

    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReviewSummaryOut(BaseModel):
    """Aggregated review summary for a hotel or package."""

    entity_type: str            # 'hotel' | 'package'
    entity_id: int
    total_reviews: int
    average_rating: Optional[float] = None
    positive_count: int
    neutral_count: int
    negative_count: int
    positive_pct: float
    negative_pct: float
    recent_reviews: List[ReviewOut] = []

    model_config = {"from_attributes": True}
