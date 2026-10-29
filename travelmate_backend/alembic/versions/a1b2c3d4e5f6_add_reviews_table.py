"""add reviews table with sentiment

Revision ID: a1b2c3d4e5f6
Revises: d31a5e9821f4
Create Date: 2026-10-25 21:25:00.000000

Adds the reviews table supporting:
  - Hotel or Package reviews (exactly one FK set; enforced via check constraint)
  - Optional link to authenticated users (nullable; CSV imports use csv_user_id)
  - Rating (1.0-5.0 check constraint)
  - Pre-computed sentiment_label + sentiment_score
  - Unique partial indexes to prevent authenticated users from double-reviewing
  - csv_review_id for idempotent CSV imports (unique)

Reversible: downgrade() drops the table and all its indexes/constraints cleanly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "d31a5e9821f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),

        # CSV provenance
        sa.Column("csv_review_id", sa.String(length=32), nullable=True, unique=True),
        sa.Column("csv_user_id", sa.String(length=32), nullable=True),

        # Optional FK to authenticated user
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Reviewed entity (exactly one non-null enforced by check constraint below)
        sa.Column(
            "hotel_id",
            sa.Integer(),
            sa.ForeignKey("hotels.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "package_id",
            sa.Integer(),
            sa.ForeignKey("packages.id", ondelete="CASCADE"),
            nullable=True,
        ),

        # Content
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("review_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("images", sa.Text(), nullable=True),

        # Sentiment
        sa.Column("sentiment_label", sa.String(length=16), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),

        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),

        # Table-level constraints
        sa.CheckConstraint(
            "(hotel_id IS NOT NULL AND package_id IS NULL) OR "
            "(hotel_id IS NULL AND package_id IS NOT NULL)",
            name="ck_review_exactly_one_entity",
        ),
        sa.CheckConstraint(
            "rating >= 1.0 AND rating <= 5.0",
            name="ck_review_rating_range",
        ),
    )

    # Indexes
    op.create_index("ix_reviews_csv_review_id", "reviews", ["csv_review_id"], unique=True)
    op.create_index("ix_reviews_csv_user_id", "reviews", ["csv_user_id"])
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])
    op.create_index("ix_reviews_hotel_id", "reviews", ["hotel_id"])
    op.create_index("ix_reviews_package_id", "reviews", ["package_id"])

    # Partial unique indexes: one review per authenticated user per entity
    op.execute(
        "CREATE UNIQUE INDEX uq_review_user_hotel "
        "ON reviews (user_id, hotel_id) "
        "WHERE user_id IS NOT NULL AND hotel_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_review_user_package "
        "ON reviews (user_id, package_id) "
        "WHERE user_id IS NOT NULL AND package_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("uq_review_user_package", table_name="reviews")
    op.drop_index("uq_review_user_hotel", table_name="reviews")
    op.drop_index("ix_reviews_package_id", table_name="reviews")
    op.drop_index("ix_reviews_hotel_id", table_name="reviews")
    op.drop_index("ix_reviews_user_id", table_name="reviews")
    op.drop_index("ix_reviews_csv_user_id", table_name="reviews")
    op.drop_index("ix_reviews_csv_review_id", table_name="reviews")
    op.drop_table("reviews")
