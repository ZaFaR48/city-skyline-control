from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import Base


class StrEnum(str, Enum):
    pass


class Role(StrEnum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class StationStatus(StrEnum):
    online = "online"
    degraded = "degraded"
    offline = "offline"
    unknown = "unknown"


class RegionType(StrEnum):
    city = "city"
    district = "district"
    operational_zone = "operational_zone"


class DeviceType(StrEnum):
    station = "station"
    operator_pc = "operator_pc"
    admin_pc = "admin_pc"
    phone = "phone"
    server = "server"
    unknown = "unknown"


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class EventSource(StrEnum):
    headscale = "headscale"
    ping = "ping"
    agent_heartbeat = "agent_heartbeat"
    camera_monitor = "camera_monitor"
    manual = "manual"
    system = "system"


class AlertSeverity(StrEnum):
    critical = "critical"
    warning = "warning"
    info = "info"


class AlertType(StrEnum):
    offline_station = "offline_station"
    camera_offline = "camera_offline"
    vpn_lost = "vpn_lost"
    disk_full = "disk_full"
    cpu_high = "cpu_high"
    ram_high = "ram_high"


class RegistrationStatus(StrEnum):
    pre_approved = "pre_approved"
    pending = "pending"
    clarification_requested = "clarification_requested"
    approved = "approved"
    rejected = "rejected"
    activated = "activated"


class AuditSource(StrEnum):
    web = "web"
    api = "api"
    telegram = "telegram"
    system = "system"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default=Role.viewer.value, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_activity_source: Mapped[str | None] = mapped_column(String(16), nullable=True)


class OperationalRegion(Base):
    __tablename__ = "operational_regions"
    __table_args__ = (
        Index("ix_operational_regions_active", "is_active"),
        Index("ix_operational_regions_region_type", "region_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    region_type: Mapped[str] = mapped_column(String(32))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_regions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    parent: Mapped[OperationalRegion | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[OperationalRegion]] = relationship(back_populates="parent")


class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (Index("ix_stations_active_archived", "is_active", "is_archived"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    station_code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    city_id: Mapped[int] = mapped_column(ForeignKey("operational_regions.id", ondelete="RESTRICT"), index=True)
    district_id: Mapped[int | None] = mapped_column(
        ForeignKey("operational_regions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    legacy_region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str] = mapped_column(String(255), default="")
    operational_area: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    vpn_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    local_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rustdesk_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=StationStatus.unknown.value, index=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ping_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_ping_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offline_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_ping_failures: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_ping_successes: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_high_latency: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_low_latency: Mapped[int] = mapped_column(Integer, default=0)
    recovery_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    cpu: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ram: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disk: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telemetry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    city: Mapped[OperationalRegion] = relationship(foreign_keys=[city_id])
    district: Mapped[OperationalRegion | None] = relationship(foreign_keys=[district_id])
    cameras: Mapped[list[Camera]] = relationship(back_populates="station", cascade="all, delete-orphan")
    headscale_node: Mapped[HeadscaleNode | None] = relationship(back_populates="station", uselist=False)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    ip: Mapped[str] = mapped_column(String(64))
    rtsp_url: Mapped[str] = mapped_column(Text)
    ptz: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution: Mapped[str] = mapped_column(String(32), default="1920x1080")
    fps: Mapped[int] = mapped_column(Integer, default=25)
    status: Mapped[str] = mapped_column(String(16), default=StationStatus.unknown.value)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    station: Mapped[Station] = relationship(back_populates="cameras")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class HeadscaleNode(Base):
    __tablename__ = "headscale_nodes"
    __table_args__ = (
        UniqueConstraint("station_id", name="uq_headscale_nodes_station_id"),
        Index("ix_headscale_device_type", "device_type"),
        Index("ix_headscale_approval_status", "approval_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    node_key: Mapped[str] = mapped_column(String(255), unique=True)
    hostname: Mapped[str] = mapped_column(String(255))
    given_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vpn_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    operating_system: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), default=DeviceType.unknown.value)
    approval_status: Mapped[str] = mapped_column(String(32), default=ApprovalStatus.pending.value)
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    station: Mapped[Station | None] = relationship(back_populates="headscale_node")


class RustdeskDevice(Base):
    __tablename__ = "rustdesk_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), unique=True)
    rustdesk_id: Mapped[str] = mapped_column(String(64), index=True)
    permanent_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PingHistory(Base):
    __tablename__ = "ping_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    packet_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)


Index("ix_ping_station_time", PingHistory.station_id, PingHistory.checked_at.desc())


class StationStatusEvent(Base):
    __tablename__ = "station_status_events"
    __table_args__ = (
        Index("ix_status_events_station", "station_id"),
        Index("ix_status_events_started", "started_at"),
        Index("ix_status_events_source", "source"),
        Index("ix_status_events_open", "ended_at"),
        Index("ix_station_status_events_new_status", "new_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    previous_status: Mapped[str] = mapped_column(String(16))
    new_status: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"
    __table_args__ = (
        Index("ix_telemetry_station", "station_id"),
        Index("ix_telemetry_checked", "checked_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    ram_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserRegistrationRequest(Base):
    __tablename__ = "user_registration_requests"
    __table_args__ = (
        Index("ix_registration_telegram", "telegram_user_id", unique=True),
        Index("ix_registration_status", "status"),
        CheckConstraint("preferred_language IN ('tj', 'ru', 'en')", name="ck_registration_preferred_language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=RegistrationStatus.pending.value)
    assigned_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(2), default="tj")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    clarification: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramIdentity(Base):
    __tablename__ = "telegram_identities"
    __table_args__ = (
        Index("ix_telegram_identity_user", "telegram_user_id", unique=True),
        CheckConstraint("preferred_language IN ('tj', 'ru', 'en')", name="ck_telegram_identity_preferred_language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(2), default="tj")
    automatic_summary_recipient: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramSummarySetting(Base):
    __tablename__ = "telegram_summary_settings"
    __table_args__ = (CheckConstraint("interval_minutes > 0", name="ck_telegram_summary_interval_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=10)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramStationWorkflow(Base):
    __tablename__ = "telegram_station_workflows"
    __table_args__ = (
        Index("ix_telegram_workflow_actor", "actor_user_id"),
        Index("ix_telegram_workflow_status_activity", "status", "last_activity_at"),
        Index("ix_telegram_workflow_station", "station_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_role: Mapped[str] = mapped_column(String(16))
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_type: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id", ondelete="SET NULL"), nullable=True)
    station_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_step: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=0)
    active_prompt_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_telegram_update_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    preview_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preview_consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)


class OperatorActivityEvent(Base):
    __tablename__ = "operator_activity_events"
    __table_args__ = (
        Index("ix_operator_activity_actor", "actor_user_id"),
        Index("ix_operator_activity_action", "action"),
        Index("ix_operator_activity_station", "station_id"),
        Index("ix_operator_activity_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workflow_id: Mapped[str | None] = mapped_column(ForeignKey("telegram_station_workflows.id", ondelete="SET NULL"), nullable=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_role: Mapped[str] = mapped_column(String(16))
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(16))
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id", ondelete="SET NULL"), nullable=True)
    station_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    workflow_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    current_step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserActivationToken(Base):
    __tablename__ = "user_activation_tokens"
    __table_args__ = (
        Index("ix_activation_user", "user_id"),
        Index("ix_activation_hash", "token_hash", unique=True),
        Index("ix_activation_expiry", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_actor", "actor_user_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str] = mapped_column(String(32), default=AuditSource.api.value)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
