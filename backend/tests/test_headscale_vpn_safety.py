from __future__ import annotations

from fastapi import HTTPException
import pytest
from sqlalchemy import select
from starlette.requests import Request

from app.models import ApprovalStatus, AuditLog, HeadscaleNode, OperationalRegion, Station, User
from app.routers.headscale import (
    apply_node_classification,
    approve_node,
    preview_node_approval,
    preview_node_classification,
    list_nodes,
)
from app.routers.stations import update_station
from app.schemas import (
    HeadscaleApproveConfirmIn,
    HeadscaleApproveIn,
    HeadscaleClassificationApplyIn,
    HeadscaleClassificationIn,
    StationUpdate,
)


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


@pytest.mark.asyncio
async def test_approved_unknown_node_can_be_classified_linked_and_remains_approved(db, monkeypatch):
    station, node, admin = await inventory(db, "93203")
    node.approval_status = "approved"
    node.device_type = "unknown"
    await db.flush()
    preview = await preview_node_classification(
        node.id,
        HeadscaleClassificationIn(device_type="station", station_id=station.id),
        db,
        admin,
    )
    assert preview.valid and preview.preview_token
    assert preview.confirmation_phrase == f"LINK NODE {node.id} TO STATION {station.station_code}"
    assert preview.station_vpn_ip == "100.64.0.10"
    assert preview.proposed_station_vpn_ip == node.vpn_ip

    pinged = []

    async def no_ping(station_id):
        pinged.append(station_id)

    monkeypatch.setattr("app.routers.headscale.ping_station", no_ping)
    await apply_node_classification(
        node.id,
        HeadscaleClassificationApplyIn(
            device_type="station",
            station_id=station.id,
            preview_token=preview.preview_token,
            confirmation=preview.confirmation_phrase,
        ),
        request(),
        db,
        admin,
    )
    await db.refresh(node)
    await db.refresh(station)
    assert node.approval_status == "approved"
    assert node.device_type == "station" and node.station_id == station.id
    assert station.vpn_ip == node.vpn_ip
    assert pinged == [station.id]
    actions = set((await db.execute(select(AuditLog.action))).scalars().all())
    assert {"headscale.reclassify", "headscale.link", "station.vpn_sync_headscale"} <= actions


@pytest.mark.asyncio
async def test_classification_enforces_one_to_one_and_never_targets_production_node(db):
    station, node, admin = await inventory(db, "93204")
    node.approval_status = "approved"
    other = HeadscaleNode(
        node_key="occupied-node",
        hostname="occupied-node",
        vpn_ip="100.64.9.9",
        station_id=station.id,
        device_type="station",
        approval_status="approved",
        online=False,
    )
    db.add(other)
    await db.flush()
    preview = await preview_node_classification(
        node.id,
        HeadscaleClassificationIn(device_type="station", station_id=station.id),
        db,
        admin,
    )
    assert not preview.valid and preview.preview_token is None
    assert any("another Headscale node" in error for error in preview.errors)
    assert node.vpn_ip != "100.64.0.23"


@pytest.mark.asyncio
async def test_headscale_search_combines_with_filters_and_matches_node_and_station(db):
    station, node, admin = await inventory(db, "93205")
    node.approval_status = "approved"
    node.device_type = "station"
    node.station_id = station.id
    await db.flush()
    by_id = await list_nodes(q=str(node.id), approval_status=ApprovalStatus.approved, db=db, _=admin)
    by_station = await list_nodes(q=station.station_code, linked=True, db=db, _=admin)
    assert node.id in {item.id for item in by_id}
    assert node.id in {item.id for item in by_station}
