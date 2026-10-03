"""clean initial schema -- generated from the current, fully-registered models

This replaces the previous migration history. Table creation order respects
FK dependencies: users/destinations first (no deps), then partners (-> users),
then hotels/packages (-> destinations, partners), then favorites/bookings
(-> users, hotels, packages, destinations), then the auth-support tables
(-> users).

Revision ID: 25516c7e5180
Revises:
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa

revision = "25516c7e5180"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("username", sa.String(), unique=True, index=True),
        sa.Column("email", sa.String(), unique=True, index=True),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("home_city", sa.String(), nullable=True),
        sa.Column("preferred_language", sa.String(), nullable=True, server_default="en"),
        sa.Column("preferred_currency", sa.String(), nullable=True, server_default="INR"),
        sa.Column("role", sa.String(), nullable=False, server_default="customer"),
    )

    # ---- destinations ----
    op.create_table(
        "destinations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("tags", sa.String(length=512), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=512), nullable=True),
        sa.Column("avg_rating", sa.Float(), server_default="5.0"),
    )

    # ---- partners (-> users) ----
    op.create_table(
        "partners",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("business_name", sa.String(length=256), nullable=False),
        sa.Column("partner_type", sa.String(length=32), nullable=False),
        sa.Column("contact_email", sa.String(length=256), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="approved"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- hotels (-> destinations, partners) ----
    op.create_table(
        "hotels",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("destination_id", sa.Integer(), sa.ForeignKey("destinations.id"), nullable=False, index=True),
        sa.Column("partner_id", sa.Integer(), sa.ForeignKey("partners.id"), nullable=True, index=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("partner_name", sa.String(length=256), nullable=True),
        sa.Column("accommodation_type", sa.String(length=64), nullable=True),
        sa.Column("price_tier", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("price_per_night", sa.Float(), nullable=True),
        sa.Column("star_rating", sa.Float(), nullable=True),
        sa.Column("amenities", sa.String(length=512), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("photos", sa.JSON(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
    )

    # ---- packages (-> destinations, partners) ----
    op.create_table(
        "packages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("destination_id", sa.Integer(), sa.ForeignKey("destinations.id"), nullable=False, index=True),
        sa.Column("partner_id", sa.Integer(), sa.ForeignKey("partners.id"), nullable=False, index=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("price_tier", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("price_per_package", sa.Float(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("amenities", sa.String(length=512), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("photos", sa.JSON(), nullable=True),
    )

    # ---- favorites (-> users, destinations) ----
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("destination_id", sa.Integer(), sa.ForeignKey("destinations.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("image", sa.String(), nullable=True),
    )

    # ---- bookings (-> users, hotels, packages, destinations) ----
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("booking_reference", sa.String(length=32), unique=True, index=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("listing_type", sa.String(length=16), nullable=False, server_default="hotel"),
        sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotels.id"), nullable=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("packages.id"), nullable=True),
        sa.Column("destination_id", sa.Integer(), sa.ForeignKey("destinations.id"), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("guest_name", sa.String(length=256), nullable=False),
        sa.Column("guest_email", sa.String(length=256), nullable=False),
        sa.Column("guest_phone", sa.String(length=64), nullable=False),
        sa.Column("check_in_date", sa.Date(), nullable=False),
        sa.Column("check_out_date", sa.Date(), nullable=False),
        sa.Column("num_rooms", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("num_guests", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="Pending Payment"),
        sa.Column("payment_reference", sa.String(length=128), nullable=True),
        sa.Column("payment_order_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- conversation_sessions (-> users) ----
    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.String(length=64), unique=True, index=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("messages", sa.JSON(), nullable=True),
        sa.Column("slots", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="collecting"),
        sa.Column("generated_plan", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- refresh_tokens (-> users) ----
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), unique=True, index=True, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # ---- password_reset_tokens (-> users) ----
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), unique=True, index=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("conversation_sessions")
    op.drop_table("bookings")
    op.drop_table("favorites")
    op.drop_table("packages")
    op.drop_table("hotels")
    op.drop_table("partners")
    op.drop_table("destinations")
    op.drop_table("users")
