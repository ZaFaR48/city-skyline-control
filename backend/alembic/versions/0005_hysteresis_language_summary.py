"""Add monitoring hysteresis and Telegram preferences.

Revision ID: 0005_hysteresis_language_summary
Revises: 0004_operator_activity
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_hysteresis_language_summary"
down_revision = "0004_operator_activity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stations", sa.Column("consecutive_ping_successes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("stations", sa.Column("consecutive_high_latency", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("stations", sa.Column("consecutive_low_latency", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("stations", sa.Column("recovery_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_registration_requests", sa.Column("preferred_language", sa.String(length=2), nullable=False, server_default="tj"))
    op.create_check_constraint("ck_registration_preferred_language", "user_registration_requests", "preferred_language IN ('tj', 'ru', 'en')")
    op.add_column("telegram_identities", sa.Column("preferred_language", sa.String(length=2), nullable=False, server_default="tj"))
    op.create_check_constraint("ck_telegram_identity_preferred_language", "telegram_identities", "preferred_language IN ('tj', 'ru', 'en')")
    op.add_column("telegram_identities", sa.Column("automatic_summary_recipient", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "telegram_summary_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("interval_minutes > 0", name="ck_telegram_summary_interval_positive"),
    )
    op.execute("INSERT INTO telegram_summary_settings (id, enabled, interval_minutes) VALUES (1, true, 10)")


def downgrade() -> None:
    op.drop_table("telegram_summary_settings")
    op.drop_column("telegram_identities", "automatic_summary_recipient")
    op.drop_constraint("ck_telegram_identity_preferred_language", "telegram_identities", type_="check")
    op.drop_column("telegram_identities", "preferred_language")
    op.drop_constraint("ck_registration_preferred_language", "user_registration_requests", type_="check")
    op.drop_column("user_registration_requests", "preferred_language")
    op.drop_column("stations", "recovery_started_at")
    op.drop_column("stations", "consecutive_low_latency")
    op.drop_column("stations", "consecutive_high_latency")
    op.drop_column("stations", "consecutive_ping_successes")
