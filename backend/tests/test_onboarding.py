from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from sqlalchemy import select
from starlette.datastructures import UploadFile

from app.models import Alert, HeadscaleNode, OperationalRegion, Station
from app.routers.headscale import _serialize_nodes
from app.routers.onboarding import (
    _district_preview,
    _parse_district_csv,
    duplicate_alert_report,
    duplicate_vpn_report,
    station_by_exact_code,
)
from app.schemas import DistrictAssignmentIn


async def create_station(db, code: str, *, vpn_ip: str | None = None) -> Station:
    city = (
        await db.execute(select(OperationalRegion).where(OperationalRegion.code == "dushanbe"))
    ).scalar_one()
    station = Station(
        station_code=code,
        name=f"Station {code}",
        city_id=city.id,
        address="Test address",
        vpn_ip=vpn_ip,
        status="unknown",
        is_active=True,
        is_archived=False,
    )
    db.add(station)
    await db.flush()
    return station


@pytest.mark.asyncio
async def test_invalid_district_and_rudaki_are_rejected(db):
    await create_station(db, "92001")

    invalid = await _district_preview(
        db, [DistrictAssignmentIn(station_code="92001", district="Not a district")]
    )
    rudaki = await _district_preview(
        db, [DistrictAssignmentIn(station_code="92001", district="Rudaki")]
    )

    assert not invalid.valid and invalid.preview_token is None
    assert not rudaki.valid and rudaki.preview_token is None
    assert "Ismoili Somoni" in invalid.errors[0].message


@pytest.mark.asyncio
async def test_csv_dry_run_parses_and_does_not_assign(db):
    station = await create_station(db, "92002")
    upload = UploadFile(
        filename="districts.csv",
        file=BytesIO(b"station_code,district\n92002,Sino\n"),
    )

    assignments, errors = await _parse_district_csv(upload)
    preview = await _district_preview(db, assignments)

    assert errors == []
    assert preview.valid and preview.rows[0].proposed_district == "Sino"
    assert preview.preview_token
    await db.refresh(station)
    assert station.district_id is None


@pytest.mark.asyncio
async def test_exact_code_lookup_includes_pending_station(db):
    station = await create_station(db, "92020")
    rendered = await station_by_exact_code(" 92020 ", db, None)
    assert rendered.id == station.id
    assert rendered.approved_at is None


@pytest.mark.asyncio
async def test_duplicate_vpn_report_and_node_warning_are_read_only(db):
    first = await create_station(db, "92003", vpn_ip="100.100.92.3")
    second = await create_station(db, "92004", vpn_ip="100.100.92.3")
    node = HeadscaleNode(
        node_key="onboarding-duplicate-node",
        hostname="station-mini-pc",
        vpn_ip="100.100.92.3",
        station_id=first.id,
        device_type="station",
        approval_status="approved",
        online=True,
    )
    db.add(node)
    await db.flush()

    groups = await duplicate_vpn_report(db=db, _=None)
    rendered = await _serialize_nodes(db, [node])

    group = next(item for item in groups if item.vpn_ip == "100.100.92.3")
    assert {item.station_code for item in group.stations} == {"92003", "92004"}
    assert rendered[0].duplicate_vpn_ip is True
    assert first.vpn_ip == second.vpn_ip == "100.100.92.3"


@pytest.mark.asyncio
async def test_duplicate_alert_dry_run_preserves_alerts(db):
    station = await create_station(db, "92005")
    oldest = Alert(
        station_id=station.id,
        type="vpn_lost",
        severity="warning",
        message="First",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    newest = Alert(
        station_id=station.id,
        type="vpn_lost",
        severity="warning",
        message="Second",
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([oldest, newest])
    await db.flush()

    groups = await duplicate_alert_report(db=db, _=None)
    group = next(item for item in groups if item.station_code == "92005")

    assert group.open_alert_count == 2
    assert group.canonical_alert_id == oldest.id
    assert group.proposed_resolve_alert_ids == [newest.id]
    assert group.preview_token
    assert oldest.resolved_at is None and newest.resolved_at is None
