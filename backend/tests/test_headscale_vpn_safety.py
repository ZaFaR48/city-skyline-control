from __future__ import annotations

from fastapi import HTTPException
import pytest
from sqlalchemy import select
from starlette.requests import Request

from app.models import AuditLog, HeadscaleNode, OperationalRegion, Station, User
from app.routers.headscale import approve_node, preview_node_approval
from app.routers.stations import update_station
from app.schemas import HeadscaleApproveConfirmIn, HeadscaleApproveIn, StationUpdate


def request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1)})


async def inventory(db, code: str):
    city = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "dushanbe"))).scalar_one()
    district = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "sino"))).scalar_one()
    admin = User(username=f"headscale-{code}", email=f"headscale-{code}@test.invalid", hashed_password="unchanged", role="admin", is_active=True)
    station = Station(
        station_code=code,
        name=f"Station {code}",
        city_id=city.id,
        district_id=district.id,
        address="Rudaki 10",
        vpn_ip="100.64.0.10",
        is_active=True,
        is_archived=False,
    )
    node = HeadscaleNode(
        node_key=f"node-{code}",
        hostname=f"node-{code}",
        vpn_ip="100.64.0.11",
        device_type="unknown",
        approval_status="pending",
        online=False,
    )
    db.add_all([admin, station, node])
    await db.flush()
    return station, node, admin


@pytest.mark.asyncio
async def test_headscale_preview_warns_then_syncs_station_vpn_with_separate_audit(db, monkeypatch):
    station, node, admin = await inventory(db, "93201")
    preview = await preview_node_approval(
        node.id,
        HeadscaleApproveIn(device_type="station", station_id=station.id),
        db,
        admin,
    )
    assert preview["valid"] and preview["preview_token"]
    assert "100.64.0.10" in preview["vpn_replacement_warning"]

    async def no_ping(_station_id):
        return None

    monkeypatch.setattr("app.routers.headscale.ping_station", no_ping)
    await approve_node(
        node.id,
        HeadscaleApproveConfirmIn(
            device_type="station",
            station_id=station.id,
            preview_token=preview["preview_token"],
            confirmation="APPROVE AND LINK",
        ),
        request(),
        db,
        admin,
    )
    await db.refresh(station)
    assert station.vpn_ip == node.vpn_ip
    actions = set((await db.execute(select(AuditLog.action))).scalars().all())
    assert {"headscale.approve", "station.vpn_sync_headscale"} <= actions


@pytest.mark.asyncio
async def test_manual_station_vpn_cannot_conflict_with_approved_linked_node(db):
    station, node, admin = await inventory(db, "93202")
    node.station_id = station.id
    node.device_type = "station"
    node.approval_status = "approved"
    station.vpn_ip = node.vpn_ip
    await db.flush()
    with pytest.raises(HTTPException) as exc:
        await update_station(
            station.id,
            StationUpdate(vpn_ip="100.64.0.99"),
            request(),
            db,
            admin,
        )
    assert exc.value.status_code == 409
    assert station.vpn_ip == node.vpn_ip
