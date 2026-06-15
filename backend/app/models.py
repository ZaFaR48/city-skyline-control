from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    Enum as SAEnum, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import Base


class Role(str, Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class StationStatus(str, Enum):
    online = "online"
    warning = "warning"
    offline = "offline"


class AlertSeverity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class AlertType(str, Enum):
    offline_station = "offline_station"
    camera_offline = "camera_offline"
    vpn_lost = "vpn_lost"
    disk_full = "disk_full"
    cpu_high = "cpu_high"
    ram_high = "ram_high"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.viewer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Station(Base):
    __tablename__ = "stations"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    region: Mapped[str] = mapped_column(String(64), index=True)
    address: Mapped[str] = mapped_column(String(255))
    vpn_ip: Mapped[str] = mapped_column(String(64), index=True)
    local_ip: Mapped[str] = mapped_column(String(64))
    rustdesk_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    status: Mapped[StationStatus] = mapped_column(SAEnum(StationStatus), default=StationStatus.offline)
    cpu: Mapped[int] = mapped_column(Integer, default=0)
    ram: Mapped[int] = mapped_column(Integer, default=0)
    disk: Mapped[int] = mapped_column(Integer, default=0)
    last_ping_ms: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cameras: Mapped[list["Camera"]] = relationship(back_populates="station", cascade="all, delete-orphan")


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
    status: Mapped[StationStatus] = mapped_column(SAEnum(StationStatus), default=StationStatus.offline)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    station: Mapped[Station] = relationship(back_populates="cameras")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id", ondelete="SET NULL"), nullable=True, index=True)
    type: Mapped[AlertType] = mapped_column(SAEnum(AlertType))
    severity: Mapped[AlertSeverity] = mapped_column(SAEnum(AlertSeverity), index=True)
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HeadscaleNode(Base):
    __tablename__ = "headscale_nodes"
    id: Mapped[int] = mapped_column(primary_key=True)
    node_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255))
    vpn_ip: Mapped[str] = mapped_column(String(64), index=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RustdeskDevice(Base):
    __tablename__ = "rustdesk_devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), unique=True)
    rustdesk_id: Mapped[str] = mapped_column(String(64), index=True)
    permanent_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PingHistory(Base):
    __tablename__ = "ping_history"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), index=True)
    latency_ms: Mapped[float] = mapped_column(Float)
    packet_loss: Mapped[float] = mapped_column(Float, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


Index("ix_ping_station_time", PingHistory.station_id, PingHistory.created_at.desc())
