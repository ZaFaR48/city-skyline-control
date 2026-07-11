from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Alert,
    ApprovalStatus,
    DeviceType,
    HeadscaleNode,
    OperationalRegion,
    Station,
    StationStatus,
    StationStatusEvent,
)
from app.services.dashboard import build_dashboard_summary
from app.services.station_status import StationStatusResolver
from app.services.station_views import serialize_stations


async def station(db, code: str, status: str = "unknown", *, approved: bool = True) -> Station:
    city = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "dushanbe"))).scalar_one()
    row = Station(station_code=code, name=f"Station {code}", city_id=city.id, address="", status=status, is_active=True, is_archived=False, vpn_ip=f"100.100.0.{int(code[-2:])}", approved_at=datetime.now(timezone.utc) if approved else None)
    db.add(row)
    await db.flush()
    return row


async def node(db, station_id: int | None, *, device_type="station", approval="approved", online=True, key="key") -> HeadscaleNode:
    row = HeadscaleNode(node_key=key, hostname=key, vpn_ip="100.100.0.1", station_id=station_id, device_type=device_type, approval_status=approval, online=online)
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_phone_and_unapproved_nodes_do_not_count_as_station_vpn_nodes(db):
    first = await station(db, "91001")
    await node(db, None, device_type=DeviceType.phone.value, key="phone")
    await node(db, None, approval=ApprovalStatus.pending.value, key="pending")
    await node(db, first.id, key="approved-station")
    summary = await build_dashboard_summary(db)
    assert summary.approved_station_vpn_nodes == 1


@pytest.mark.asyncio
async def test_station_node_is_one_to_one(db):
    first = await station(db, "91002")
    await node(db, first.id, key="one")
    db.add(HeadscaleNode(node_key="two", hostname="two", station_id=first.id, device_type="station", approval_status="approved"))
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_one_ping_failure_is_not_offline(db):
    first = await station(db, "91003", StationStatus.online.value)
    await node(db, first.id, key="failure-node")
    result = await StationStatusResolver.resolve_ping(db, first, success=False, latency_ms=None, error_type="unreachable")
    assert result.new_status == StationStatus.degraded.value
    assert first.consecutive_ping_failures == 1


@pytest.mark.asyncio
async def test_offline_transition_is_single_and_recovery_closes_event(db):
    first = await station(db, "91004", StationStatus.online.value)
    await node(db, first.id, key="transition-node")
    first.consecutive_ping_failures = 2
    offline = await StationStatusResolver.resolve_ping(db, first, success=False, latency_ms=None, error_type="unreachable")
    assert offline.new_status == StationStatus.offline.value
    await StationStatusResolver.resolve_ping(db, first, success=False, latency_ms=None, error_type="unreachable")
    open_count = (await db.execute(select(func.count(StationStatusEvent.id)).where(StationStatusEvent.station_id == first.id, StationStatusEvent.ended_at.is_(None)))).scalar_one()
    assert open_count == 1
    await StationStatusResolver.resolve_ping(db, first, success=True, latency_ms=20)
    offline_event = (await db.execute(select(StationStatusEvent).where(StationStatusEvent.station_id == first.id, StationStatusEvent.new_status == "offline"))).scalar_one()
    assert offline_event.ended_at is not None
    assert offline_event.duration_seconds is not None and offline_event.duration_seconds >= 0


@pytest.mark.asyncio
async def test_unknown_transition_does_not_resolve_offline_alert(db):
    first = await station(db, "91005", StationStatus.offline.value)
    alert = Alert(
        station_id=first.id,
        type="offline_station",
        severity="critical",
        message="Confirmed outage",
    )
    db.add(alert)
    await db.flush()
    await StationStatusResolver.transition(
        db,
        first,
        new_status=StationStatus.unknown,
        source="system",
        reason="Monitoring not configured",
    )
    assert alert.resolved_at is None


@pytest.mark.asyncio
async def test_dashboard_arithmetic_and_missing_telemetry(db):
    rows = [
        await station(db, "91011", "online"),
        await station(db, "91012", "offline"),
        await station(db, "91013", "degraded"),
        await station(db, "91014", "unknown"),
    ]
    summary = await build_dashboard_summary(db)
    assert summary.total_stations == summary.online_stations + summary.offline_stations + summary.degraded_stations + summary.unknown_stations
    rendered = (await serialize_stations(db, [rows[-1]]))[0]
    assert rendered.cpu is None and rendered.ram is None and rendered.disk is None


@pytest.mark.asyncio
async def test_unapproved_station_is_excluded_and_approved_station_is_included(db):
    pending = await station(db, "91021", approved=False)
    approved = await station(db, "91022", approved=True)
    summary = await build_dashboard_summary(db)
    assert summary.total_stations == 1
    assert approved.id != pending.id
