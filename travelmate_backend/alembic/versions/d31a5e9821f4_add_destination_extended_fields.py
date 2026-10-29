"""add destination extended fields

Revision ID: d31a5e9821f4
Revises: c21ed5c1343f
Create Date: 2026-10-25 12:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d31a5e9821f4"
down_revision: Union[str, Sequence[str], None] = "c21ed5c1343f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Safely add extended fields from datasets/destinations.csv to destinations table."""
    op.add_column("destinations", sa.Column("csv_destination_id", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_destinations_csv_destination_id"), "destinations", ["csv_destination_id"], unique=False)
    op.add_column("destinations", sa.Column("state", sa.String(length=128), nullable=True))
    op.add_column("destinations", sa.Column("city", sa.String(length=128), nullable=True))
    op.add_column("destinations", sa.Column("category", sa.String(length=64), nullable=True))
    op.add_column("destinations", sa.Column("best_season", sa.String(length=64), nullable=True))
    op.add_column("destinations", sa.Column("average_budget", sa.Float(), nullable=True))
    op.add_column("destinations", sa.Column("ideal_duration", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Safely revert extended fields from destinations table."""
    op.drop_column("destinations", "ideal_duration")
    op.drop_column("destinations", "average_budget")
    op.drop_column("destinations", "best_season")
    op.drop_column("destinations", "category")
    op.drop_column("destinations", "city")
    op.drop_column("destinations", "state")
    op.drop_index(op.f("ix_destinations_csv_destination_id"), table_name="destinations")
    op.drop_column("destinations", "csv_destination_id")
