"""Add nullable station operational area.

Revision ID: 0003_station_operational_area
Revises: 0002_production_monitoring
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_station_operational_area"
down_revision = "0002_production_monitoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stations", sa.Column("operational_area", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("stations", "operational_area")
