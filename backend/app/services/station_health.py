from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import (
    ApprovalStatus,
    Camera,
    DeviceType,
    HeadscaleNode,
    PingHistory,
    Station,
    StationStatus,
    StationStatusEvent,
)


ComponentStatus = Literal["online", "degraded", "offline", "unknown", "stale", "not_configured"]


REASON_TEXT_KEYS = {
    "HEALTHY": "health.reason.healthy",
    "HEADSCALE_OFFLINE": "health.reason.headscale_offline",
    "HEADSCALE_LAST_SEEN_STALE": "health.reason.headscale_stale",
    "PING_TIMEOUT": "health.reason.ping_timeout",
    "PING_HIGH_LATENCY": "health.reason.ping_high_latency",
    "AGENT_HEARTBEAT_STALE": "health.reason.agent_stale",
    "CAMERA_OFFLINE": "health.reason.camera_offline",
    "CAMERA_RTSP_FAILED": "health.reason.camera_rtsp_failed",
    "MONITORING_NOT_CONFIGURED": "health.reason.monitoring_not_configured",
    "INSUFFICIENT_FRESH_DATA": "health.reason.insufficient_fresh_data",
    "CONFLICTING_TELEMETRY": "health.reason.conflicting_telemetry",
}


@dataclass(frozen=True)
class StationHealth:
    overall_status: str
    overall_reason_code: str
    overall_reason_text_key: str
    observed_at: datetime | None
    last_seen_at: datetime | None
    current_state_started_at: datetime | None
    current_state_duration_seconds: int | None
    connectivity_status: ComponentStatus
    headscale_status: ComponentStatus
    agent_status: ComponentStatus
    camera_status: ComponentStatus
    internet_status: ComponentStatus
    local_service_status: ComponentStatus
    monitoring_coverage: str
    evidence: dict[str, datetime | None]
    current_event_id: int | None
    linked_node_id: int | None

    def model_values(self) -> dict:
        return asdict(self)


async def resolve_station_health_batch(
    db: AsyncSession,
    stations: list[Station],
    *,
    now: datetime | None = None,
) -> dict[int, StationHealth]:
    if not stations:
        return {}
    current = now or datetime.now(timezone.utc)
    station_ids = [station.id for station in stations]
    nodes = list((await db.execute(
        select(HeadscaleNode).where(
            HeadscaleNode.station_id.in_(station_ids),
            HeadscaleNode.approval_status == ApprovalStatus.approved.value,
            HeadscaleNode.device_type == DeviceType.station.value,
        )
    )).scalars().all())
    latest_pings = list((await db.execute(
        select(PingHistory)
        .where(PingHistory.station_id.in_(station_ids))
        .distinct(PingHistory.station_id)
        .order_by(PingHistory.station_id, PingHistory.checked_at.desc(), PingHistory.id.desc())
    )).scalars().all())
    cameras = list((await db.execute(select(Camera).where(Camera.station_id.in_(station_ids)))).scalars().all())
    open_events = list((await db.execute(
        select(StationStatusEvent)
        .where(StationStatusEvent.station_id.in_(station_ids), StationStatusEvent.ended_at.is_(None))
        .order_by(StationStatusEvent.station_id, StationStatusEvent.started_at.desc())
    )).scalars().all())

    node_by_station = {node.station_id: node for node in nodes}
    ping_by_station = {ping.station_id: ping for ping in latest_pings}
    cameras_by_station: dict[int, list[Camera]] = {station_id: [] for station_id in station_ids}
    for camera in cameras:
        cameras_by_station[camera.station_id].append(camera)
    event_by_station: dict[int, StationStatusEvent] = {}
    for event in open_events:
        event_by_station.setdefault(event.station_id, event)

    return {
        station.id: resolve_station_health(
            station,
            node=node_by_station.get(station.id),
            ping=ping_by_station.get(station.id),
            cameras=cameras_by_station[station.id],
            current_event=event_by_station.get(station.id),
            now=current,
        )
        for station in stations
    }


def resolve_station_health(
    station: Station,
    *,
    node: HeadscaleNode | None,
    ping: PingHistory | None,
    cameras: list[Camera],
    current_event: StationStatusEvent | None,
    now: datetime,
) -> StationHealth:
    headscale_status: ComponentStatus = "not_configured"
    if node:
        if node.online:
            headscale_status = "online"
        elif node.last_seen_at and (now - node.last_seen_at).total_seconds() < settings.OFFLINE_AFTER_SECONDS:
            headscale_status = "offline"
        else:
            headscale_status = "stale"

    camera_status: ComponentStatus = "not_configured"
    if cameras:
        statuses = {camera.status for camera in cameras}
        if StationStatus.offline.value in statuses:
            camera_status = "offline"
        elif statuses == {StationStatus.online.value}:
            camera_status = "online"
        elif StationStatus.degraded.value in statuses:
            camera_status = "degraded"
        else:
            camera_status = "unknown"

    agent_status: ComponentStatus = "not_configured"
    if station.telemetry_at:
        agent_status = (
            "online"
            if (now - station.telemetry_at).total_seconds() <= settings.TELEMETRY_FRESHNESS_SECONDS
            else "stale"
        )

    connectivity_status: ComponentStatus = "unknown"
    reason_code = "INSUFFICIENT_FRESH_DATA"
    overall_status = StationStatus.unknown.value
    ping_age = (now - ping.checked_at).total_seconds() if ping else None

    if not station.vpn_ip or node is None:
        reason_code = "MONITORING_NOT_CONFIGURED"
    elif ping is None or ping_age is None or ping_age > settings.OFFLINE_AFTER_SECONDS:
        reason_code = "INSUFFICIENT_FRESH_DATA"
    elif (
        station.status == StationStatus.offline.value
        or int(station.consecutive_ping_failures or 0) >= settings.PING_FAIL_THRESHOLD
    ):
        connectivity_status = "offline"
        overall_status, reason_code = StationStatus.offline.value, "PING_TIMEOUT"
    elif ping.success:
        connectivity_status = "online"
        if camera_status == "offline":
            overall_status, reason_code = StationStatus.degraded.value, "CAMERA_OFFLINE"
        elif agent_status == "stale":
            overall_status, reason_code = StationStatus.degraded.value, "AGENT_HEARTBEAT_STALE"
        elif headscale_status in {"offline", "stale"}:
            overall_status = StationStatus.degraded.value
            reason_code = "HEADSCALE_OFFLINE" if headscale_status == "offline" else "HEADSCALE_LAST_SEEN_STALE"
        elif (
            station.status == StationStatus.degraded.value
            and (station.status_reason or "").startswith("PING_HIGH_LATENCY")
        ):
            overall_status, reason_code = StationStatus.degraded.value, "PING_HIGH_LATENCY"
        else:
            overall_status, reason_code = StationStatus.online.value, "HEALTHY"
    else:
        connectivity_status = "degraded"
        overall_status = station.status if station.status in {
            StationStatus.online.value,
            StationStatus.degraded.value,
        } else StationStatus.unknown.value
        reason_code = (
            "PING_HIGH_LATENCY"
            if overall_status == StationStatus.degraded.value
            and (station.status_reason or "").startswith("PING_HIGH_LATENCY")
            else "HEALTHY" if overall_status == StationStatus.online.value else "INSUFFICIENT_FRESH_DATA"
        )

    state_started = (
        current_event.started_at
        if current_event and current_event.new_status == overall_status
        else None
    )
    duration = max(0, int((now - state_started).total_seconds())) if state_started else None
    configured = [station.vpn_ip is not None and node is not None, bool(cameras), station.telemetry_at is not None]
    coverage = "none" if not configured[0] else "full" if all(configured) else "partial"
    return StationHealth(
        overall_status=overall_status,
        overall_reason_code=reason_code,
        overall_reason_text_key=REASON_TEXT_KEYS[reason_code],
        observed_at=ping.checked_at if ping else None,
        last_seen_at=station.last_seen_at,
        current_state_started_at=state_started,
        current_state_duration_seconds=duration,
        connectivity_status=connectivity_status,
        headscale_status=headscale_status,
        agent_status=agent_status,
        camera_status=camera_status,
        internet_status="not_configured",
        local_service_status="not_configured",
        monitoring_coverage=coverage,
        evidence={
            "ping_checked_at": ping.checked_at if ping else None,
            "headscale_last_seen_at": node.last_seen_at if node else None,
            "agent_heartbeat_at": station.telemetry_at,
            "camera_observed_at": max((camera.last_seen_at for camera in cameras if camera.last_seen_at), default=None),
        },
        current_event_id=current_event.id if current_event and current_event.new_status == overall_status else None,
        linked_node_id=node.id if node else None,
    )
