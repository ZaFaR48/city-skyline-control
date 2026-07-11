"""Production monitoring domain model.

Revision ID: 0002_production_monitoring
Revises: 0001_initial
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_production_monitoring"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE stationstatus ADD VALUE IF NOT EXISTS 'degraded'")
            op.execute("ALTER TYPE stationstatus ADD VALUE IF NOT EXISTS 'unknown'")

    op.create_table(
        "operational_regions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("region_type", sa.String(32), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("operational_regions.id", ondelete="RESTRICT")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_operational_regions_parent_id", "operational_regions", ["parent_id"])
    op.create_index("ix_operational_regions_active", "operational_regions", ["is_active"])
    op.create_index("ix_operational_regions_region_type", "operational_regions", ["region_type"])

    op.execute(
        """
        INSERT INTO operational_regions (code, name, region_type, is_active, sort_order)
        VALUES ('dushanbe', 'Dushanbe', 'city', true, 10),
               ('rudaki', 'Rudaki', 'operational_zone', false, 90)
        """
    )
    op.execute(
        """
        INSERT INTO operational_regions (code, name, region_type, parent_id, is_active, sort_order)
        SELECT v.code, v.name, 'district', c.id, true, v.sort_order
        FROM (VALUES
            ('ismoili-somoni', 'Ismoili Somoni', 10),
            ('shohmansur', 'Shohmansur', 20),
            ('sino', 'Sino', 30),
            ('firdavsi', 'Firdavsi', 40)
        ) AS v(code, name, sort_order)
        CROSS JOIN operational_regions c
        WHERE c.code = 'dushanbe'
        """
    )

    op.alter_column("stations", "code", new_column_name="station_code")
    op.alter_column("stations", "region", new_column_name="legacy_region")
    op.alter_column("stations", "legacy_region", nullable=True)
    op.alter_column("stations", "lat", new_column_name="latitude", nullable=True)
    op.alter_column("stations", "lng", new_column_name="longitude", nullable=True)
    op.alter_column("stations", "last_seen", new_column_name="last_seen_at")
    op.alter_column("stations", "vpn_ip", nullable=True)
    op.alter_column("stations", "local_ip", nullable=True)
    op.alter_column("stations", "cpu", nullable=True, server_default=None)
    op.alter_column("stations", "ram", nullable=True, server_default=None)
    op.alter_column("stations", "disk", nullable=True, server_default=None)
    op.alter_column("stations", "last_ping_ms", nullable=True, server_default=None)
    op.alter_column("stations", "created_at", nullable=False)
    op.drop_index("ix_stations_region", table_name="stations")
    op.add_column("stations", sa.Column("city_id", sa.Integer(), nullable=True))
    op.add_column("stations", sa.Column("district_id", sa.Integer(), nullable=True))
    op.add_column("stations", sa.Column("status_reason", sa.Text(), nullable=True))
    op.add_column("stations", sa.Column("last_ping_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stations", sa.Column("offline_since", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stations", sa.Column("consecutive_ping_failures", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("stations", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stations", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.add_column("stations", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("stations", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("stations", sa.Column("telemetry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stations", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.execute("UPDATE stations SET city_id=(SELECT id FROM operational_regions WHERE code='dushanbe')")
    op.execute("UPDATE stations SET cpu=NULL, ram=NULL, disk=NULL")
    op.execute("UPDATE stations SET last_ping_ms=NULL WHERE last_ping_ms=0")
    op.execute("UPDATE stations SET status='degraded' WHERE status='warning'")
    op.alter_column("stations", "city_id", nullable=False)
    op.alter_column("stations", "updated_at", nullable=False)
    op.create_foreign_key("fk_stations_city", "stations", "operational_regions", ["city_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_stations_district", "stations", "operational_regions", ["district_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_stations_approved_by", "stations", "users", ["approved_by"], ["id"])
    op.create_index("ix_stations_city_id", "stations", ["city_id"])
    op.create_index("ix_stations_district_id", "stations", ["district_id"])
    op.create_index("ix_stations_active_archived", "stations", ["is_active", "is_archived"])
    op.create_index("ix_stations_status", "stations", ["status"])

    op.alter_column("headscale_nodes", "last_seen", new_column_name="last_seen_at")
    op.add_column("headscale_nodes", sa.Column("given_name", sa.String(255), nullable=True))
    op.add_column("headscale_nodes", sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("headscale_nodes", sa.Column("operating_system", sa.String(128), nullable=True))
    op.add_column("headscale_nodes", sa.Column("tags", sa.JSON(), nullable=True))
    op.add_column("headscale_nodes", sa.Column("device_type", sa.String(32), nullable=False, server_default="unknown"))
    op.add_column("headscale_nodes", sa.Column("approval_status", sa.String(32), nullable=False, server_default="pending"))
    op.add_column("headscale_nodes", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.add_column("headscale_nodes", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("headscale_nodes", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.execute("UPDATE headscale_nodes SET station_id=NULL, device_type='unknown', approval_status='pending'")
    op.create_unique_constraint("uq_headscale_nodes_station_id", "headscale_nodes", ["station_id"])
    op.create_foreign_key("fk_headscale_approved_by", "headscale_nodes", "users", ["approved_by"], ["id"])
    op.create_index("ix_headscale_device_type", "headscale_nodes", ["device_type"])
    op.create_index("ix_headscale_approval_status", "headscale_nodes", ["approval_status"])
    op.alter_column("headscale_nodes", "online", nullable=False)
    op.alter_column("headscale_nodes", "first_seen_at", nullable=False)
    op.alter_column("headscale_nodes", "created_at", nullable=False)
    op.alter_column("headscale_nodes", "updated_at", nullable=False)

    op.alter_column("ping_history", "created_at", new_column_name="checked_at")
    op.alter_column("ping_history", "latency_ms", nullable=True)
    op.alter_column("ping_history", "success", nullable=False)
    op.alter_column("ping_history", "checked_at", nullable=False)
    op.add_column("ping_history", sa.Column("error_type", sa.String(64), nullable=True))
    op.execute("UPDATE ping_history SET latency_ms=NULL, error_type='unreachable' WHERE success=false")
    op.drop_index("ix_ping_history_created_at", table_name="ping_history")
    op.drop_index("ix_ping_station_time", table_name="ping_history")
    op.create_index("ix_ping_history_checked_at", "ping_history", ["checked_at"])
    op.create_index("ix_ping_station_time", "ping_history", ["station_id", sa.text("checked_at DESC")])

    op.alter_column("cameras", "last_seen", new_column_name="last_seen_at")
    op.execute("UPDATE cameras SET status='unknown' WHERE last_seen_at IS NULL")
    op.alter_column("cameras", "ptz", nullable=False)
    op.alter_column("cameras", "resolution", nullable=False)
    op.alter_column("cameras", "fps", nullable=False)
    op.alter_column("cameras", "status", nullable=False)

    op.add_column("alerts", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alerts", sa.Column("resolved_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_alerts_resolved_by", "alerts", "users", ["resolved_by"], ["id"])
    op.alter_column("alerts", "acknowledged", nullable=False)
    op.alter_column("alerts", "created_at", nullable=False)
    op.create_index("ix_alerts_type", "alerts", ["type"])

    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.alter_column("users", "created_at", nullable=False)
    op.alter_column("users", "updated_at", nullable=False)
    op.create_index("ix_users_role", "users", ["role"])
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
        op.execute("ALTER TABLE stations ALTER COLUMN status DROP DEFAULT")
        op.execute("ALTER TABLE cameras ALTER COLUMN status DROP DEFAULT")
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE varchar(16) USING role::text")
        op.execute("ALTER TABLE stations ALTER COLUMN status TYPE varchar(16) USING status::text")
        op.execute("ALTER TABLE cameras ALTER COLUMN status TYPE varchar(16) USING status::text")
        op.execute("ALTER TABLE alerts ALTER COLUMN type TYPE varchar(32) USING type::text")
        op.execute("ALTER TABLE alerts ALTER COLUMN severity TYPE varchar(16) USING severity::text")
        op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'viewer'")
        op.execute("ALTER TABLE stations ALTER COLUMN status SET DEFAULT 'unknown'")
        op.execute("ALTER TABLE cameras ALTER COLUMN status SET DEFAULT 'unknown'")

    op.create_table(
        "station_status_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(16), nullable=False),
        sa.Column("new_status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_status_events_station", "station_status_events", ["station_id"])
    op.create_index("ix_status_events_started", "station_status_events", ["started_at"])
    op.create_index("ix_status_events_source", "station_status_events", ["source"])
    op.create_index("ix_status_events_open", "station_status_events", ["ended_at"])
    op.create_index("ix_station_status_events_new_status", "station_status_events", ["new_status"])

    op.create_table(
        "telemetry_samples",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cpu_percent", sa.Float()),
        sa.Column("ram_percent", sa.Float()),
        sa.Column("disk_percent", sa.Float()),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_telemetry_station", "telemetry_samples", ["station_id"])
    op.create_index("ix_telemetry_checked", "telemetry_samples", ["checked_at"])

    op.create_table(
        "user_registration_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("telegram_username", sa.String(64)),
        sa.Column("first_name", sa.String(128)),
        sa.Column("last_name", sa.String(128)),
        sa.Column("display_name", sa.String(255)),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("assigned_role", sa.String(16)),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("clarification", sa.Text()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_registration_telegram", "user_registration_requests", ["telegram_user_id"], unique=True)
    op.create_index("ix_registration_status", "user_registration_requests", ["status"])

    op.create_table(
        "telegram_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("telegram_username", sa.String(64)),
        sa.Column("first_name", sa.String(128)),
        sa.Column("last_name", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_telegram_identity_user", "telegram_identities", ["telegram_user_id"], unique=True)

    op.create_table(
        "user_activation_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_activation_user", "user_activation_tokens", ["user_id"])
    op.create_index("ix_activation_expiry", "user_activation_tokens", ["expires_at"])
    op.create_index("ix_activation_hash", "user_activation_tokens", ["token_hash"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("before_data", sa.JSON()),
        sa.Column("after_data", sa.JSON()),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.String(32), nullable=False, server_default="api"),
        sa.Column("ip_address", sa.String(64)),
    )
    op.create_index("ix_audit_actor", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])
    op.create_index("ix_audit_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_timestamp", "audit_logs", ["timestamp"])
    op.alter_column("rustdesk_devices", "updated_at", nullable=False)


def downgrade() -> None:
    raise RuntimeError("Production monitoring migration is intentionally irreversible; restore the pre-migration backup.")
