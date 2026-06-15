"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-15

Generated manually for the City Parking Control Center.
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    role = sa.Enum("admin", "operator", "viewer", name="role")
    status = sa.Enum("online", "warning", "offline", name="stationstatus")
    severity = sa.Enum("critical", "warning", "info", name="alertseverity")
    atype = sa.Enum("offline_station", "camera_offline", "vpn_lost",
                    "disk_full", "cpu_high", "ram_high", name="alerttype")
    role.create(op.get_bind(), checkfirst=True)
    status.create(op.get_bind(), checkfirst=True)
    severity.create(op.get_bind(), checkfirst=True)
    atype.create(op.get_bind(), checkfirst=True)

    op.create_table("users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", role, nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("stations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("region", sa.String(64), nullable=False, index=True),
        sa.Column("address", sa.String(255), nullable=False),
        sa.Column("vpn_ip", sa.String(64), nullable=False, index=True),
        sa.Column("local_ip", sa.String(64), nullable=False),
        sa.Column("rustdesk_id", sa.String(64)),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("status", status, nullable=False, server_default="offline"),
        sa.Column("cpu", sa.Integer, server_default="0"),
        sa.Column("ram", sa.Integer, server_default="0"),
        sa.Column("disk", sa.Integer, server_default="0"),
        sa.Column("last_ping_ms", sa.Integer, server_default="0"),
        sa.Column("last_seen", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("cameras",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("station_id", sa.Integer, sa.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("ip", sa.String(64), nullable=False),
        sa.Column("rtsp_url", sa.Text, nullable=False),
        sa.Column("ptz", sa.Boolean, server_default=sa.false()),
        sa.Column("resolution", sa.String(32), server_default="1920x1080"),
        sa.Column("fps", sa.Integer, server_default="25"),
        sa.Column("status", status, server_default="offline"),
        sa.Column("last_seen", sa.DateTime(timezone=True)),
    )

    op.create_table("alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("station_id", sa.Integer, sa.ForeignKey("stations.id", ondelete="SET NULL"), index=True),
        sa.Column("type", atype, nullable=False),
        sa.Column("severity", severity, nullable=False, index=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("acknowledged", sa.Boolean, server_default=sa.false(), index=True),
        sa.Column("acknowledged_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )

    op.create_table("headscale_nodes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("node_key", sa.String(255), unique=True, nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("vpn_ip", sa.String(64), index=True),
        sa.Column("online", sa.Boolean, server_default=sa.false()),
        sa.Column("last_seen", sa.DateTime(timezone=True)),
        sa.Column("station_id", sa.Integer, sa.ForeignKey("stations.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("rustdesk_devices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("station_id", sa.Integer, sa.ForeignKey("stations.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("rustdesk_id", sa.String(64), nullable=False, index=True),
        sa.Column("permanent_password", sa.String(255)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("ping_history",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("station_id", sa.Integer, sa.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("packet_loss", sa.Float, server_default="0"),
        sa.Column("success", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_ping_station_time", "ping_history", ["station_id", "created_at"])


def downgrade() -> None:
    op.drop_table("ping_history")
    op.drop_table("rustdesk_devices")
    op.drop_table("headscale_nodes")
    op.drop_table("alerts")
    op.drop_table("cameras")
    op.drop_table("stations")
    op.drop_table("users")
    for n in ("alerttype", "alertseverity", "stationstatus", "role"):
        sa.Enum(name=n).drop(op.get_bind(), checkfirst=True)
