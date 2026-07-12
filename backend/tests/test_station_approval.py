from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import func, select
from starlette.requests import Request

from app.database import get_db
from app.deps import get_current_user
from app.main import app
from app.models import AuditLog, HeadscaleNode, OperationalRegion, Station, User
from app.routers.onboarding import (
    approve_station_for_production,
    preview_station_approval,
    preview_station_revocation,
    station_approval_inventory,
    revoke_station_from_production,
)
from app.schemas import StationApprovalApplyIn


def request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1)})


async def create_admin(db) -> User:
    user = User(username="approval-admin", email="approval-admin@test.invalid", hashed_password="unchanged", role="admin", is_active=True)
    db.add(user)
    await db.flush()
    return user


async def create_station(db, code: str, *, approved: bool = False) -> Station:
    city = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "dushanbe"))).scalar_one()
    district = (await db.execute(select(OperationalRegion).where(OperationalRegion.code == "sino"))).scalar_one()
    row = Station(
        station_code=code,
        name=f"Station {code}",
        city_id=city.id,
        district_id=district.id,
        address="Verified address",
        vpn_ip="100.100.93.1",
        status="unknown",
        is_active=True,
        is_archived=False,
        approved_at=datetime.now(timezone.utc) if approved else None,
    )
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_unapproved_station_is_excluded_from_default_station_map_feed_and_admin_sees_pending(db):
    pending = await create_station(db, "93001")
    admin = await create_admin(db)

    async def current_user_override():
        return admin

    async def db_override():
        yield db

    app.dependency_overrides[get_current_user] = current_user_override
    app.dependency_overrides[get_db] = db_override
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            production = await client.get("/api/stations?limit=200")
            onboarding = await client.get("/api/onboarding/stations?approval=pending")
        assert production.status_code == 200
        assert pending.station_code not in {item["station_code"] for item in production.json()["items"]}
        assert pending.station_code in {item["station_code"] for item in onboarding.json()}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_approval_blocks_pending_or_unconfigured_headscale_node(db):
    station = await create_station(db, "93002")
    admin = await create_admin(db)
    node = HeadscaleNode(
        node_key="approval-independent-node",
        hostname="pending-node",
        station_id=station.id,
        device_type="unknown",
        approval_status="pending",
        online=False,
    )
    db.add(node)
    await db.flush()

    preview = await preview_station_approval(station.id, db, admin)
    assert not preview.valid and preview.preview_token is None
    assert not preview.monitoring_ready
    assert {item.key for item in preview.checklist if not item.ready} == {
        "approved_station_node",
        "monitoring_configured",
    }


@pytest.mark.asyncio
async def test_approval_accepts_approved_offline_station_node_and_writes_audit(db):
    station = await create_station(db, "93004")
    admin = await create_admin(db)
    node = HeadscaleNode(
        node_key="approval-offline-node",
        hostname="approved-offline-node",
        vpn_ip=station.vpn_ip,
        station_id=station.id,
        device_type="station",
        approval_status="approved",
        online=False,
    )
    db.add(node)
    await db.flush()

    preview = await preview_station_approval(station.id, db, admin)
    assert preview.valid and preview.preview_token
    assert preview.monitoring_ready
    assert all(item.ready for item in preview.checklist)
    assert preview.warning and "offline" in preview.warning
    result = await approve_station_for_production(
        station.id,
        StationApprovalApplyIn(preview_token=preview.preview_token, confirmation=preview.confirmation_phrase),
        request(),
        db,
        admin,
    )
    await db.refresh(station)
    await db.refresh(node)
    assert result.approved_at is not None
    assert station.approved_by == admin.id
    assert node.approval_status == "approved"
    audit = (await db.execute(select(AuditLog).where(AuditLog.action == "station.production_approve"))).scalar_one()
    assert audit.actor_user_id == admin.id
    pending_rows = await station_approval_inventory("pending", None, db, admin)
    assert station.id not in {row.id for row in pending_rows}


@pytest.mark.asyncio
async def test_revocation_returns_station_to_pending_without_deleting_it(db):
    station = await create_station(db, "93003", approved=True)
    admin = await create_admin(db)
    preview = await preview_station_revocation(station.id, db, admin)
    await revoke_station_from_production(
        station.id,
        StationApprovalApplyIn(preview_token=preview.preview_token or "", confirmation=preview.confirmation_phrase),
        request(),
        db,
        admin,
    )
    persisted = await db.get(Station, station.id)
    assert persisted is not None
    assert persisted.approved_at is None and persisted.approved_by is None
    assert await db.scalar(select(func.count()).select_from(Station).where(Station.id == station.id)) == 1
    audit = (await db.execute(select(AuditLog).where(AuditLog.action == "station.production_revoke"))).scalar_one()
    assert audit.actor_user_id == admin.id
