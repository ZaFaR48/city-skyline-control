"""telegram workflow integrity

Revision ID: 0006_telegram_workflow_integrity
Revises: 0005_hysteresis_language_summary
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_telegram_workflow_integrity"
down_revision = "0005_hysteresis_language_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("telegram_station_workflows", sa.Column("mode", sa.String(length=16), nullable=True))
    op.add_column("telegram_station_workflows", sa.Column("version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("telegram_station_workflows", sa.Column("active_prompt_message_id", sa.BigInteger(), nullable=True))
    op.add_column("telegram_station_workflows", sa.Column("last_telegram_update_id", sa.BigInteger(), nullable=True))
    op.add_column("telegram_station_workflows", sa.Column("preview_hash", sa.String(length=64), nullable=True))
    op.add_column("telegram_station_workflows", sa.Column("preview_consumed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE telegram_station_workflows SET mode = CASE WHEN workflow_type = 'registration' THEN 'create' ELSE 'update' END")
    op.alter_column("telegram_station_workflows", "mode", nullable=False)


def downgrade() -> None:
    op.drop_column("telegram_station_workflows", "preview_consumed_at")
    op.drop_column("telegram_station_workflows", "preview_hash")
    op.drop_column("telegram_station_workflows", "last_telegram_update_id")
    op.drop_column("telegram_station_workflows", "active_prompt_message_id")
    op.drop_column("telegram_station_workflows", "version")
    op.drop_column("telegram_station_workflows", "mode")
