from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from starlette.requests import Request

from app.models import (
    AuditLog,
    OperatorActivityEvent,
    OperationalRegion,
    Role,
    Station,
    TelegramIdentity,
    TelegramStationWorkflow,
    User,
)
from app.routers.activity import (
    start_telegram_workflow,
    telegram_create_station,
    telegram_update_station,
)
from app.schemas import TelegramStationCreateIn, TelegramStationUpdateIn, TelegramWorkflowStartIn
from app.services.operator_activity import (
    abandon_inactive_workflows_in_db,
    presence_state,
    safe_values,
    touch_presence,
)
from app.services.station_permissions import enforce_station_create_policy, enforce_station_update_policy


def request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1)})


async def actors_and_regions(db, suffix: str):
    service_admin = User(username=f"service-{suffix}", email=f"service-{suffix}@test.invalid", hashed_password="x", role="admin", is_active=True)
    operator = User(username=f"operator-{suffix}", email=f"operator-{suffix}@test.invalid", hashed_password="x", role="operator", is_active=True)
    city = OperationalRegion(code=f"city-{suffix}", name="Dushanbe", region_type="city", is_active=True)
    db.add_all([service_admin, operator, city])
    await db.flush()
    district = OperationalRegion(code=f"district-{suffix}", name="Sino", region_type="district", parent_id=city.id, is_active=True)
    db.add(district)
    await db.flush()
    identity = TelegramIdentity(user_id=operator.id, telegram_user_id=810000 + operator.id, telegram_username=f"tg_{suffix}")
    db.add(identity)
    await db.flush()
    return service_admin, operator, identity, city, district


@pytest.mark.asyncio
async def test_presence_is_application_activity_and_writes_are_throttled(db):
    user = User(username="presence-operator", email="presence@test.invalid", hashed_password="x", role="operator", is_active=True)
    db.add(user)
    await db.flush()
    now = datetime.now(timezone.utc)
    assert await touch_presence(db, user, "web", now=now)
    assert not await touch_presence(db, user, "web", now=now + timedelta(seconds=1))
    assert await touch_presence(db, user, "telegram", now=now + timedelta(seconds=1))
    assert presence_state(now, now=now + timedelta(minutes=1)) == "online"
    assert presence_state(now, now=now + timedelta(minutes=10)) == "recently_active"
    assert presence_state(now, now=now + timedelta(hours=1)) == "offline"


def test_activity_values_are_allowlisted_and_secrets_are_removed():
    assert safe_values({"address": "Rudaki 10", "password": "secret", "token": "secret", "random": "hidden"}) == {"address": "Rudaki 10"}


def test_operator_station_policy_rejects_infrastructure_and_lifecycle_fields():
    operator = User(username="policy-op", email="policy@test.invalid", hashed_password="x", role="operator", is_active=True)
    with pytest.raises(HTTPException) as create_error:
        enforce_station_create_policy(operator, {"vpn_ip": "100.64.0.99"})
    assert create_error.value.status_code == 403
    with pytest.raises(HTTPException) as update_error:
        enforce_station_update_policy(operator, {"is_archived": True})
    assert update_error.value.status_code == 403
    enforce_station_update_policy(operator, {"address": "Allowed", "latitude": 38.5})


@pytest.mark.asyncio
async def test_telegram_operator_create_is_pending_and_attributed(db):
    admin, operator, identity, city, district = await actors_and_regions(db, "create")
    workflow_id = "00000000-0000-0000-0000-000000000101"
    actor = {"telegram_user_id": identity.telegram_user_id, "telegram_username": identity.telegram_username}
    await start_telegram_workflow(
        TelegramWorkflowStartIn(**actor, workflow_id=workflow_id, workflow_type="registration", current_step="station_code", correlation_id="correlation-create"),
        db,
        admin,
    )
    result = await telegram_create_station(
        TelegramStationCreateIn(
            **actor,
            workflow_id=workflow_id,
            station_code="OP-CREATE-101",
            name="Operator station",
            city_id=city.id,
            district_id=district.id,
            operational_area="Customs",
            address="Rudaki 10",
        ),
        request(),
        db,
        admin,
    )
    station = await db.get(Station, result.id)
    assert station is not None
    assert station.approved_at is None and station.approved_by is None
    assert station.is_active is True and station.is_archived is False
    assert station.vpn_ip is None and station.local_ip is None and station.rustdesk_id is None
    audit = (await db.execute(select(AuditLog).where(AuditLog.entity_id == str(station.id), AuditLog.action == "station.create"))).scalar_one()
    assert audit.actor_user_id == operator.id and audit.source == "telegram"
    assert result.created_by_username == operator.username and result.created_by_role == Role.operator
    repeated = await telegram_create_station(
        TelegramStationCreateIn(
            **actor,
            workflow_id=workflow_id,
            station_code="OP-CREATE-101",
            name="Operator station",
            city_id=city.id,
            district_id=district.id,
            operational_area="Customs",
            address="Rudaki 10",
        ),
        request(),
        db,
        admin,
    )
    assert repeated.id == result.id
    assert await db.scalar(select(func.count()).select_from(Station).where(Station.station_code == "OP-CREATE-101")) == 1


@pytest.mark.asyncio
async def test_telegram_operator_update_preserves_approval_and_infrastructure(db):
    admin, operator, identity, city, district = await actors_and_regions(db, "update")
    station = Station(
        station_code="OP-UPDATE-102",
        name="Before",
        city_id=city.id,
        district_id=district.id,
        address="Before address",
        vpn_ip="100.64.0.102",
        approved_at=datetime.now(timezone.utc),
        approved_by=admin.id,
    )
    db.add(station)
    await db.flush()
    approved_at, approved_by, vpn_ip = station.approved_at, station.approved_by, station.vpn_ip
    workflow_id = "00000000-0000-0000-0000-000000000102"
    actor = {"telegram_user_id": identity.telegram_user_id, "telegram_username": identity.telegram_username}
    await start_telegram_workflow(
        TelegramWorkflowStartIn(**actor, workflow_id=workflow_id, workflow_type="update", station_code=station.station_code, current_step="station_code", correlation_id="correlation-update"),
        db,
        admin,
    )
    result = await telegram_update_station(
        station.id,
        TelegramStationUpdateIn(**actor, workflow_id=workflow_id, address="After address", name="After"),
        request(),
        db,
        admin,
    )
    await db.refresh(station)
    assert result.address == "After address" and result.name == "After"
    assert station.approved_at == approved_at and station.approved_by == approved_by and station.vpn_ip == vpn_ip


@pytest.mark.asyncio
async def test_live_role_change_blocks_started_operator_workflow(db):
    admin, operator, identity, _, _ = await actors_and_regions(db, "role-change")
    workflow_id = "00000000-0000-0000-0000-000000000103"
    actor = {"telegram_user_id": identity.telegram_user_id, "telegram_username": identity.telegram_username}
    await start_telegram_workflow(
        TelegramWorkflowStartIn(**actor, workflow_id=workflow_id, workflow_type="registration", current_step="station_code", correlation_id="correlation-role"),
        db,
        admin,
    )
    operator.role = "viewer"
    await db.flush()
    with pytest.raises(HTTPException) as exc:
        await start_telegram_workflow(
            TelegramWorkflowStartIn(**actor, workflow_id="00000000-0000-0000-0000-000000000104", workflow_type="registration", current_step="station_code", correlation_id="correlation-role-2"),
            db,
            admin,
        )
    assert exc.value.status_code == 403
    denied = await db.scalar(select(func.count()).select_from(OperatorActivityEvent).where(OperatorActivityEvent.action == "telegram.permission_denied"))
    assert denied == 1


@pytest.mark.asyncio
async def test_inactive_workflow_is_abandoned_exactly_once(db):
    _, operator, identity, _, _ = await actors_and_regions(db, "abandon")
    now = datetime.now(timezone.utc)
    workflow = TelegramStationWorkflow(
        id="00000000-0000-0000-0000-000000000105",
        actor_user_id=operator.id,
        actor_role=operator.role,
        telegram_user_id=identity.telegram_user_id,
        workflow_type="registration",
        status="in_progress",
        current_step="address",
        last_activity_at=now - timedelta(hours=2),
        correlation_id="correlation-abandon",
    )
    db.add(workflow)
    await db.flush()
    assert await abandon_inactive_workflows_in_db(db, now) == 1
    await db.flush()
    assert await abandon_inactive_workflows_in_db(db, now) == 0
    events = await db.scalar(select(func.count()).select_from(OperatorActivityEvent).where(OperatorActivityEvent.workflow_id == workflow.id, OperatorActivityEvent.action == "telegram.station_workflow.abandoned"))
    assert workflow.status == "abandoned" and events == 1
