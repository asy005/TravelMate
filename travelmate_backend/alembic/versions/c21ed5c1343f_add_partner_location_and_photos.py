"""add partner location and photos

Revision ID: c21ed5c1343f
Revises: 25516c7e5180
Create Date: 2026-10-24 18:06:38.991328

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c21ed5c1343f'
down_revision: Union[str, Sequence[str], None] = '25516c7e5180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("partners", sa.Column("address", sa.String(length=256), nullable=True))
    op.add_column("partners", sa.Column("city", sa.String(length=128), nullable=True))
    op.add_column("partners", sa.Column("state", sa.String(length=128), nullable=True))
    op.add_column("partners", sa.Column("postal_code", sa.String(length=32), nullable=True))
    op.add_column("partners", sa.Column("photos", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("partners", "photos")
    op.drop_column("partners", "postal_code")
    op.drop_column("partners", "state")
    op.drop_column("partners", "city")
    op.drop_column("partners", "address")
