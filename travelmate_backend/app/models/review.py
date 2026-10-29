# app/models/review.py
"""
Review model for Phase 3 - Reviews and Sentiment Analysis.

A Review belongs to exactly one entity: either a Hotel or a Package
(never both simultaneously -- enforced by check_constraint at migration time).
Users are linked optionally via user_id (FK) or a guest reference string
(csv_user_id) for CSV-imported seed data.

Sentiment is stored as a pre-computed string ('positive'|'neutral'|'negative')
so reads stay O(1) without re-scoring.  The sentiment_score column holds the
raw compound float produced by the SentimentAnalyser for transparency/debugging.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Date,
    ForeignKey, CheckConstraint, Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)

    # --- CSV provenance -------------------------------------------------------
    csv_review_id = Column(String(32), nullable=True, unique=True, index=True)
    # Raw user identifier from the CSV (e.g. "U0110").  May not correspond to
    # any row in the users table if the CSV user never registered.
    csv_user_id = Column(String(32), nullable=True, index=True)

    # --- Linked authenticated user (null for guest / CSV-only reviews) --------
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # --- Reviewed entity: exactly one of hotel_id / package_id is non-null ---
    hotel_id = Column(Integer, ForeignKey("hotels.id", ondelete="CASCADE"), nullable=True, index=True)
    package_id = Column(Integer, ForeignKey("packages.id", ondelete="CASCADE"), nullable=True, index=True)

    # --- Review content -------------------------------------------------------
    rating = Column(Float, nullable=False)          # 1.0 – 5.0
    review_text = Column(Text, nullable=False, default="")
    review_date = Column(Date, nullable=True)       # parsed from CSV; null for API-submitted reviews on import error
    images = Column(Text, nullable=True)            # semicolon-separated filenames (raw from CSV)

    # --- Sentiment (computed at write time) -----------------------------------
    # 'positive' | 'neutral' | 'negative'
    sentiment_label = Column(String(16), nullable=True)
    # Raw compound score from the lexicon analyser (-1.0 to +1.0)
    sentiment_score = Column(Float, nullable=True)

    # --- Timestamps -----------------------------------------------------------
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # --- Relationships --------------------------------------------------------
    user = relationship("User", back_populates="reviews")

    # --- Table-level constraints ---------------------------------------------
    __table_args__ = (
        CheckConstraint(
            "(hotel_id IS NOT NULL AND package_id IS NULL) OR "
            "(hotel_id IS NULL AND package_id IS NOT NULL)",
            name="ck_review_exactly_one_entity",
        ),
        CheckConstraint("rating >= 1.0 AND rating <= 5.0", name="ck_review_rating_range"),
        # Prevent the same authenticated user from posting duplicate reviews on the same entity
        Index(
            "uq_review_user_hotel",
            "user_id", "hotel_id",
            unique=True,
            postgresql_where=Column("user_id") != None,  # noqa: E711  -- partial index
        ),
        Index(
            "uq_review_user_package",
            "user_id", "package_id",
            unique=True,
            postgresql_where=Column("user_id") != None,  # noqa: E711
        ),
    )
