"""Add application presence and Telegram station workflow audit.

Revision ID: 0004_operator_activity
Revises: 0003_station_operational_area
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_operator_activity"
down_revision = "0003_station_operational_area"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_activity_source", sa.String(length=16), nullable=True))
    op.create_index("ix_users_last_activity_at", "users", ["last_activity_at"])
    op.create_table(
        "telegram_station_workflows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_role", sa.String(length=16), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(length=64), nullable=True),
        sa.Column("workflow_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="in_progress"),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("station_code", sa.String(length=32), nullable=True),
        sa.Column("current_step", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_telegram_workflow_actor", "telegram_station_workflows", ["actor_user_id"])
    op.create_index("ix_telegram_workflow_status_activity", "telegram_station_workflows", ["status", "last_activity_at"])
    op.create_index("ix_telegram_workflow_station", "telegram_station_workflows", ["station_id"])
    op.create_index("ix_telegram_station_workflows_correlation_id", "telegram_station_workflows", ["correlation_id"])
    op.create_table(
        "operator_activity_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("workflow_id", sa.String(length=36), sa.ForeignKey("telegram_station_workflows.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_role", sa.String(length=16), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("station_code", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("workflow_status", sa.String(length=16), nullable=True),
        sa.Column("current_step", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_operator_activity_actor", "operator_activity_events", ["actor_user_id"])
    op.create_index("ix_operator_activity_action", "operator_activity_events", ["action"])
    op.create_index("ix_operator_activity_station", "operator_activity_events", ["station_id"])
    op.create_index("ix_operator_activity_timestamp", "operator_activity_events", ["timestamp"])


def downgrade() -> None:
    op.drop_table("operator_activity_events")
    op.drop_table("telegram_station_workflows")
    op.drop_index("ix_users_last_activity_at", table_name="users")
    op.drop_column("users", "last_activity_source")
    op.drop_column("users", "last_activity_at")
