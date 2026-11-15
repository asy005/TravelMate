"""add saved trips table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-13 22:30:00.000000

Adds the saved_trips table for full customized trip persistence:
  - user_id (FK to users)
  - destination_id (FK to destinations)
  - destination_name, trip_title, trip_duration_days, travel_dates
  - destination_data snapshot
  - itinerary, selected_attractions, selected_activities
  - route_stops, route_details
  - packing_checklist, custom_packing_items
  - trip_preferences, notes
  - created_at, updated_at
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_trips",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("destination_id", sa.Integer(), sa.ForeignKey("destinations.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("destination_name", sa.String(length=255), nullable=False),
        sa.Column("trip_title", sa.String(length=255), nullable=True),
        sa.Column("trip_duration_days", sa.Integer(), nullable=True, server_default="3"),
        sa.Column("travel_dates", sa.String(length=255), nullable=True),
        sa.Column("destination_data", sa.JSON(), nullable=True),
        sa.Column("itinerary", sa.JSON(), nullable=True),
        sa.Column("selected_attractions", sa.JSON(), nullable=True),
        sa.Column("selected_activities", sa.JSON(), nullable=True),
        sa.Column("route_stops", sa.JSON(), nullable=True),
        sa.Column("route_details", sa.JSON(), nullable=True),
        sa.Column("packing_checklist", sa.JSON(), nullable=True),
        sa.Column("custom_packing_items", sa.JSON(), nullable=True),
        sa.Column("trip_preferences", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("saved_trips")
