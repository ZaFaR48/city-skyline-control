from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Literal

from sqlalchemy import Integer, column, select, true, values
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
from .performance import record_resolver_duration


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
    degraded_enter_latency_ms: int
    degraded_exit_latency_ms: int
    recovery_samples: int
    recovery_samples_required: int
    recovery_started_at: datetime | None
    recovery_stable_seconds_elapsed: int
    recovery_stable_seconds_required: int

    def model_values(self) -> dict:
        return asdict(self)


async def resolve_station_health_batch(
    db: AsyncSession,
    stations: list[Station],
    *,
    now: datetime | None = None,
    nodes: list[HeadscaleNode] | None = None,
    cameras: list[Camera] | None = None,
) -> dict[int, StationHealth]:
    if not stations:
        return {}
    resolver_started = perf_counter()
    current = now or datetime.now(timezone.utc)
    station_ids = [station.id for station in stations]
    if nodes is None:
        nodes = list((await db.execute(
            select(HeadscaleNode).where(HeadscaleNode.station_id.in_(station_ids))
        )).scalars().all())
    monitoring_nodes = [
        node
        for node in nodes
        if node.station_id in station_ids
        and node.approval_status == ApprovalStatus.approved.value
        and node.device_type == DeviceType.station.value
    ]

    # A DISTINCT ON query over ping_history made PostgreSQL read and sort every
    # historical row for the selected stations. Drive one LIMIT 1 index lookup
    # per station instead; ix_ping_station_time already supports this access
    # pattern, so no additional production index is required.
    station_values = values(
        column("station_id", Integer),
        name="requested_station_ids",
    ).data([(station_id,) for station_id in station_ids])
    latest_ping_id = (
        select(PingHistory.id.label("ping_id"))
        .where(PingHistory.station_id == station_values.c.station_id)
        .correlate(station_values)
        .order_by(PingHistory.checked_at.desc(), PingHistory.id.desc())
        .limit(1)
        .lateral("latest_ping")
    )
    latest_pings = list((await db.execute(
        select(PingHistory)
        .select_from(
            station_values
            .join(latest_ping_id, true())
            .join(PingHistory, PingHistory.id == latest_ping_id.c.ping_id)
        )
    )).scalars().all())
    if cameras is None:
        cameras = list((await db.execute(
            select(Camera).where(Camera.station_id.in_(station_ids))
        )).scalars().all())
    open_events = list((await db.execute(
        select(StationStatusEvent)
        .where(StationStatusEvent.station_id.in_(station_ids), StationStatusEvent.ended_at.is_(None))
        .order_by(StationStatusEvent.station_id, StationStatusEvent.started_at.desc())
    )).scalars().all())

    node_by_station = {node.station_id: node for node in monitoring_nodes}
    ping_by_station = {ping.station_id: ping for ping in latest_pings}
    cameras_by_station: dict[int, list[Camera]] = {station_id: [] for station_id in station_ids}
    for camera in cameras:
        cameras_by_station[camera.station_id].append(camera)
    event_by_station: dict[int, StationStatusEvent] = {}
    for event in open_events:
        event_by_station.setdefault(event.station_id, event)

    result = {
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
    record_resolver_duration((perf_counter() - resolver_started) * 1000)
    return result


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
    recovery_elapsed = (
        max(0, int((now - station.recovery_started_at).total_seconds()))
        if station.recovery_started_at
        else 0
    )
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
        degraded_enter_latency_ms=settings.DEGRADED_ENTER_MS,
        degraded_exit_latency_ms=settings.DEGRADED_EXIT_MS,
        recovery_samples=int(station.consecutive_low_latency or 0),
        recovery_samples_required=settings.DEGRADED_EXIT_CONSECUTIVE_CHECKS,
        recovery_started_at=station.recovery_started_at,
        recovery_stable_seconds_elapsed=recovery_elapsed,
        recovery_stable_seconds_required=settings.RECOVERY_STABLE_SECONDS,
    )
