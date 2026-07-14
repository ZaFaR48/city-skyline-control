from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
import pytest
from sqlalchemy import select
from starlette.requests import Request

from app.models import ApprovalStatus, AuditLog, HeadscaleNode, OperationalRegion, Station, User
from app.routers.headscale import (
    apply_ip_reconciliation,
    apply_node_classification,
    approve_node,
    preview_node_approval,
    preview_node_classification,
    list_nodes,
    ip_reconciliation,
    preview_ip_reconciliation,
)
from app.routers.stations import update_station
from app.schemas import (
    HeadscaleApproveConfirmIn,
    HeadscaleApproveIn,
    HeadscaleClassificationApplyIn,
    HeadscaleClassificationIn,
    HeadscaleReconciliationApplyIn,
    HeadscaleReconciliationPreviewIn,
    StationUpdate,
)
from app.services.headscale import sync_linked_station_vpn


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


@pytest.mark.asyncio
async def test_reconciliation_dry_run_and_confirmed_refresh_preserve_approval(db):
    station, node, admin = await inventory(db, "93206")
    station.approved_at = datetime.now(timezone.utc)
    station.approved_by = admin.id
    node.station_id = station.id
    node.device_type = "station"
    node.approval_status = "approved"
    await db.flush()
    row = next(item for item in await ip_reconciliation(db=db, _=admin) if item.station_id == station.id)
    assert row.status == "linked_node_changed_ip"
    preview = await preview_ip_reconciliation(
        station.id, HeadscaleReconciliationPreviewIn(action="refresh_vpn"), db, admin,
    )
    assert preview.valid and preview.preview_token
    approved_at, approved_by = station.approved_at, station.approved_by
    result = await apply_ip_reconciliation(
        station.id,
        HeadscaleReconciliationApplyIn(
            action="refresh_vpn", preview_token=preview.preview_token,
            confirmation=preview.confirmation_phrase,
        ),
        request(), db, admin,
    )
    await db.refresh(station)
    assert result.status == "OK" and station.vpn_ip == node.vpn_ip
    assert (station.approved_at, station.approved_by) == (approved_at, approved_by)


@pytest.mark.asyncio
async def test_node_replacement_requires_preview_and_typed_confirmation(db):
    station, old_node, admin = await inventory(db, "93207")
    old_node.station_id = station.id
    old_node.device_type = "station"
    old_node.approval_status = "approved"
    candidate = HeadscaleNode(
        node_key="replacement-93207", hostname="93207", vpn_ip="100.64.7.7",
        device_type="station", approval_status="approved", online=True,
    )
    db.add(candidate)
    await db.flush()
    preview = await preview_ip_reconciliation(
        station.id,
        HeadscaleReconciliationPreviewIn(action="replace_node", candidate_node_id=candidate.id),
        db, admin,
    )
    assert preview.valid and str(old_node.id) in preview.confirmation_phrase
    with pytest.raises(HTTPException) as exc:
        await apply_ip_reconciliation(
            station.id,
            HeadscaleReconciliationApplyIn(
                action="replace_node", candidate_node_id=candidate.id,
                preview_token=preview.preview_token, confirmation="WRONG",
            ),
            request(), db, admin,
        )
    assert exc.value.status_code == 422
    assert old_node.station_id == station.id and candidate.station_id is None


@pytest.mark.asyncio
async def test_linked_node_ip_sync_is_audited_once_and_conflict_safe(db):
    station, node, _ = await inventory(db, "93208")
    node.station_id = station.id
    node.device_type = "station"
    node.approval_status = "approved"
    changed = await sync_linked_station_vpn(
        db, station, node, "100.64.8.8", last_seen=None, authoritative_ip_changed=True,
    )
    assert changed and station.vpn_ip == "100.64.8.8"
    changed_again = await sync_linked_station_vpn(
        db, station, node, "100.64.8.8", last_seen=None, authoritative_ip_changed=False,
    )
    assert not changed_again
    audits = list((await db.execute(
        select(AuditLog).where(AuditLog.action == "station.vpn_sync_headscale", AuditLog.entity_id == str(station.id))
    )).scalars().all())
    assert len(audits) == 1 and audits[0].actor_user_id is None

    conflict = Station(
        station_code="93208-CONFLICT", name="Conflict", city_id=station.city_id,
        district_id=station.district_id, vpn_ip="100.64.8.9", is_active=True, is_archived=False,
    )
    db.add(conflict)
    await db.flush()
    assert not await sync_linked_station_vpn(
        db, station, node, "100.64.8.9", last_seen=None, authoritative_ip_changed=True,
    )
    assert station.vpn_ip == "100.64.8.8"
