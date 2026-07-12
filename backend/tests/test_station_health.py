from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Camera, HeadscaleNode, PingHistory, Station, StationStatus, StationStatusEvent
from app.services.station_health import resolve_station_health


NOW = datetime(2026, 7, 13, 0, 0, tzinfo=timezone.utc)


def station() -> Station:
    return Station(id=1, station_code="95001", name="Health", city_id=1, vpn_ip="100.64.0.1", consecutive_ping_failures=0)


def node(*, online: bool = True) -> HeadscaleNode:
    return HeadscaleNode(id=5, node_key="health-node", hostname="health", station_id=1, online=online, last_seen_at=NOW)


def ping(*, success: bool = True, latency: float = 20) -> PingHistory:
    return PingHistory(id=8, station_id=1, success=success, latency_ms=latency, checked_at=NOW - timedelta(seconds=10))


def event(status: str, minutes: int = 12) -> StationStatusEvent:
    return StationStatusEvent(id=9, station_id=1, previous_status="unknown", new_status=status, source="ping", started_at=NOW - timedelta(minutes=minutes))


def test_online_health_has_online_duration_and_no_offline_state():
    result = resolve_station_health(station(), node=node(), ping=ping(), cameras=[], current_event=event("online"), now=NOW)
    assert result.overall_status == "online"
    assert result.current_state_duration_seconds == 12 * 60
    assert result.camera_status == "not_configured"


def test_camera_failure_degrades_reachable_station():
    camera = Camera(id=1, station_id=1, name="Camera", ip="10.0.0.2", rtsp_url="rtsp://camera", status="offline")
    result = resolve_station_health(station(), node=node(), ping=ping(), cameras=[camera], current_event=None, now=NOW)
    assert result.overall_status == "degraded"
    assert result.connectivity_status == "online"
    assert result.overall_reason_code == "CAMERA_OFFLINE"


def test_confirmed_ping_failure_is_offline_with_exact_start():
    row = station()
    row.consecutive_ping_failures = 3
    open_event = event("offline", 47)
    result = resolve_station_health(row, node=node(online=False), ping=ping(success=False), cameras=[], current_event=open_event, now=NOW)
    assert result.overall_status == "offline"
    assert result.current_state_started_at == open_event.started_at
    assert result.current_state_duration_seconds == 47 * 60


def test_missing_fresh_measurement_is_unknown_not_offline():
    result = resolve_station_health(station(), node=node(), ping=None, cameras=[], current_event=None, now=NOW)
    assert result.overall_status == StationStatus.unknown.value
    assert result.overall_reason_code == "INSUFFICIENT_FRESH_DATA"


def test_unconfigured_monitoring_is_unknown():
    row = station()
    row.vpn_ip = None
    result = resolve_station_health(row, node=None, ping=None, cameras=[], current_event=None, now=NOW)
    assert result.overall_status == "unknown"
    assert result.overall_reason_code == "MONITORING_NOT_CONFIGURED"
