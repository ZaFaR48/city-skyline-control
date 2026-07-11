from __future__ import annotations

from starlette.requests import Request
import pytest
from sqlalchemy import select

from app.models import AuditLog, HeadscaleNode, OperationalRegion, Station, User
from app.routers.onboarding import apply_station_repair, preview_station_repair
from app.schemas import StationRepairApplyIn, StationRepairIn


def request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1)})


async def inventory(db, code: str):
    city = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "dushanbe"))).scalar_one()
    district = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "sino"))).scalar_one()
    admin = User(username=f"repair-{code}", email=f"repair-{code}@test.invalid", hashed_password="unchanged", role="admin", is_active=True)
    station = Station(
        station_code=code,
        name="Sino",
        city_id=city.id,
        district_id=district.id,
        address="Customs",
        is_active=True,
        is_archived=False,
    )
    db.add_all([admin, station])
    await db.flush()
    return station, admin


@pytest.mark.asyncio
async def test_repair_requires_preview_and_confirmation_and_writes_field_audit(db):
    station, admin = await inventory(db, "93101")
    preview = await preview_station_repair(
        station.id,
        StationRepairIn(name="Sino — Customs", address="Rudaki Avenue 10"),
        db,
        admin,
    )
    assert preview.valid and preview.preview_token
    assert [(item.field, item.current, item.proposed) for item in preview.changes] == [
        ("name", "Sino", "Sino — Customs"),
        ("address", "Customs", "Rudaki Avenue 10"),
    ]
    await apply_station_repair(
        station.id,
        StationRepairApplyIn(
            name="Sino — Customs",
            address="Rudaki Avenue 10",
            preview_token=preview.preview_token,
            confirmation=preview.confirmation_phrase,
        ),
        request(),
        db,
        admin,
    )
    await db.refresh(station)
    assert station.name == "Sino — Customs" and station.address == "Rudaki Avenue 10"
    audit = (await db.execute(select(AuditLog).where(AuditLog.action == "station.data_repair"))).scalar_one()
    assert audit.before_data == {"name": "Sino", "address": "Customs"}
    assert audit.after_data == {"name": "Sino — Customs", "address": "Rudaki Avenue 10"}


@pytest.mark.asyncio
async def test_repair_rejects_vpn_conflict_with_approved_linked_node(db):
    station, admin = await inventory(db, "93102")
    station.vpn_ip = "100.64.0.20"
    db.add(HeadscaleNode(
        node_key="repair-vpn-node",
        hostname="repair-vpn-node",
        vpn_ip="100.64.0.20",
        station_id=station.id,
        device_type="station",
        approval_status="approved",
        online=False,
    ))
    await db.flush()
    preview = await preview_station_repair(station.id, StationRepairIn(vpn_ip="100.64.0.99"), db, admin)
    assert not preview.valid and preview.preview_token is None
    assert any("Headscale" in error for error in preview.errors)
