from __future__ import annotations

from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (
    OperatorActivityEvent,
    OperationalRegion,
    Role,
    Station,
    TelegramIdentity,
    TelegramStationWorkflow,
    TelegramSummarySetting,
    User,
)
from ..schemas import (
    OperatorActivityOut,
    OperatorPresenceOut,
    PresenceHeartbeatOut,
    StationOut,
    TelegramActorIn,
    TelegramRoleOut,
    TelegramStationCreateIn,
    TelegramStationUpdateIn,
    TelegramSummaryControlIn,
    TelegramSummaryControlOut,
    TelegramWorkflowEventIn,
    TelegramWorkflowStartIn,
)
from ..services.audit import add_audit
from ..services.operator_activity import (
    add_activity_event,
    presence_state,
    resolve_telegram_user,
    safe_values,
    touch_presence,
)
from ..services.station_views import serialize_stations
from ..services.operations_summary import snapshot_summary_cursor


router = APIRouter()
TELEGRAM_STATION_ROLES = {Role.admin.value, Role.operator.value}


@router.post("/heartbeat", response_model=PresenceHeartbeatOut)
async def web_heartbeat(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    changed = await touch_presence(db, user, "web")
    if changed:
        await db.commit()
    return PresenceHeartbeatOut(
        last_activity_at=user.last_activity_at,
        source="web",
        write_performed=changed,
    )


@router.post("/telegram/resolve", response_model=TelegramRoleOut)
async def telegram_resolve(
    data: TelegramActorIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    resolved = await resolve_telegram_user(db, data.telegram_user_id)
    if not resolved:
        raise HTTPException(403, "TELEGRAM_IDENTITY_NOT_ACTIVE")
    user, identity = resolved
    identity.telegram_username = data.telegram_username or identity.telegram_username
    await touch_presence(db, user, "telegram")
    await db.commit()
    return TelegramRoleOut(user_id=user.id, username=user.username, role=user.role, is_active=user.is_active, preferred_language=identity.preferred_language)


@router.post("/telegram/summary-control", response_model=TelegramSummaryControlOut)
async def telegram_summary_control(
    data: TelegramSummaryControlIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    user, identity = await _require_telegram_actor(db, data, {Role.admin.value})
    setting = await db.get(TelegramSummarySetting, 1)
    if setting is None:
        setting = TelegramSummarySetting(id=1, enabled=True, interval_minutes=settings.TELEGRAM_SUMMARY_INTERVAL_MINUTES)
        db.add(setting)
        await db.flush()
    setting.interval_minutes = settings.TELEGRAM_SUMMARY_INTERVAL_MINUTES
    if data.action == "enable":
        authorized_recipient_count = int(await db.scalar(
            select(func.count(TelegramIdentity.id))
            .join(User, User.id == TelegramIdentity.user_id)
            .where(
                TelegramIdentity.automatic_summary_recipient.is_(True),
                User.is_active.is_(True),
                User.role.in_((Role.admin.value, Role.operator.value)),
            )
        ) or 0)
        if not setting.enabled or authorized_recipient_count == 0:
            await snapshot_summary_cursor(db, reason="automatic summary enabled")
        setting.enabled = True
        setting.updated_by = user.id
        identity.automatic_summary_recipient = True
    elif data.action == "disable":
        setting.enabled = False
        setting.updated_by = user.id
    if data.action != "status":
        add_activity_event(
            db,
            user=user,
            action=f"telegram.automatic_summary.{data.action}d",
            source="telegram",
            telegram_user_id=identity.telegram_user_id,
            telegram_username=identity.telegram_username,
            status="completed",
        )
        await db.commit()
    elif db.is_modified(setting):
        await db.commit()
    recipients = list((await db.execute(
        select(TelegramIdentity, User)
        .join(User, User.id == TelegramIdentity.user_id)
        .where(
            TelegramIdentity.automatic_summary_recipient.is_(True),
            User.is_active.is_(True),
            User.role.in_((Role.admin.value, Role.operator.value)),
        )
        .order_by(User.username)
    )).all())
    return TelegramSummaryControlOut(
        enabled=setting.enabled,
        interval_minutes=setting.interval_minutes,
        recipient_count=len(recipients),
        caller_is_recipient=identity.automatic_summary_recipient,
        recipients=[
            {
                "telegram_user_id": recipient.telegram_user_id,
                "username": recipient_user.username,
                "role": recipient_user.role,
                "language": recipient.preferred_language,
            }
            for recipient, recipient_user in recipients
        ],
    )


@router.post("/telegram/workflows/start")
async def start_telegram_workflow(
    data: TelegramWorkflowStartIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    user, identity = await _require_telegram_actor(db, data, TELEGRAM_STATION_ROLES)
    existing = await db.get(TelegramStationWorkflow, data.workflow_id)
    if existing:
        if existing.actor_user_id != user.id:
            raise HTTPException(409, "WORKFLOW_ID_CONFLICT")
        return {"workflow_id": existing.id, "status": existing.status}
    if (data.workflow_type == "registration") != (data.mode == "create"):
        raise HTTPException(422, "WORKFLOW_MODE_MISMATCH")
    current = datetime.now(timezone.utc)
    old_workflows = list((await db.execute(
        select(TelegramStationWorkflow).where(
            TelegramStationWorkflow.actor_user_id == user.id,
            TelegramStationWorkflow.status == "in_progress",
        ).with_for_update()
    )).scalars().all())
    cancelled_prompt_message_ids = []
    for old in old_workflows:
        old.status = "cancelled"
        old.current_step = "cancelled"
        old.last_activity_at = old.completed_at = current
        if old.active_prompt_message_id is not None:
            cancelled_prompt_message_ids.append(old.active_prompt_message_id)
        add_activity_event(
            db, user=user, action="telegram.station_workflow.cancelled",
            source="telegram", workflow=old, telegram_user_id=identity.telegram_user_id,
            telegram_username=data.telegram_username or identity.telegram_username,
            status="cancelled", step="cancelled", reason="superseded by a new workflow",
        )
    workflow = TelegramStationWorkflow(
        id=data.workflow_id,
        actor_user_id=user.id,
        actor_role=user.role,
        telegram_user_id=identity.telegram_user_id,
        telegram_username=data.telegram_username or identity.telegram_username,
        workflow_type=data.workflow_type,
        mode=data.mode,
        status="in_progress",
        station_code=data.station_code,
        current_step=data.current_step,
        correlation_id=data.correlation_id,
    )
    db.add(workflow)
    await db.flush()
    add_activity_event(
        db,
        user=user,
        action=f"telegram.station_{data.workflow_type}.started",
        source="telegram",
        workflow=workflow,
        telegram_user_id=identity.telegram_user_id,
        telegram_username=workflow.telegram_username,
        station_code=data.station_code,
    )
    await db.commit()
    return {"workflow_id": workflow.id, "status": workflow.status, "cancelled_prompt_message_ids": cancelled_prompt_message_ids}


@router.post("/telegram/workflows/{workflow_id}/event")
async def telegram_workflow_event(
    workflow_id: str,
    data: TelegramWorkflowEventIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    user, identity = await _require_telegram_actor(db, data, TELEGRAM_STATION_ROLES)
    workflow = await db.scalar(select(TelegramStationWorkflow).where(TelegramStationWorkflow.id == workflow_id).with_for_update())
    if not workflow or workflow.actor_user_id != user.id:
        raise HTTPException(404, "WORKFLOW_NOT_FOUND")
    if workflow.status != "in_progress" and data.status == "in_progress":
        raise HTTPException(409, "WORKFLOW_ALREADY_FINISHED")
    if data.version < workflow.version:
        raise HTTPException(409, "WORKFLOW_VERSION_STALE")
    if data.telegram_update_id is not None and workflow.last_telegram_update_id == data.telegram_update_id:
        return {"workflow_id": workflow.id, "status": workflow.status, "duplicate": True, "preview_hash": workflow.preview_hash}
    current = datetime.now(timezone.utc)
    workflow.actor_role = user.role
    workflow.current_step = data.current_step
    workflow.version = data.version
    workflow.active_prompt_message_id = data.active_prompt_message_id
    if data.telegram_update_id is not None:
        workflow.last_telegram_update_id = data.telegram_update_id
    workflow.last_activity_at = current
    workflow.station_id = data.station_id or workflow.station_id
    workflow.station_code = data.station_code or workflow.station_code
    if "changed_fields" in data.model_fields_set:
        workflow.changed_fields = data.changed_fields
    if "before_data" in data.model_fields_set:
        workflow.before_data = safe_values(data.before_data)
    if "after_data" in data.model_fields_set:
        workflow.after_data = safe_values(data.after_data)
    if "failure_reason" in data.model_fields_set:
        workflow.failure_reason = data.failure_reason
    if data.action == "telegram.station_preview.generated":
        workflow.preview_hash = secrets.token_urlsafe(12)
        workflow.preview_consumed_at = None
    workflow.status = data.status
    if data.status in {"completed", "cancelled", "failed"}:
        workflow.completed_at = current
    await touch_presence(db, user, "telegram", now=current)
    add_activity_event(
        db,
        user=user,
        action=data.action,
        source="telegram",
        workflow=workflow,
        telegram_user_id=identity.telegram_user_id,
        telegram_username=data.telegram_username or identity.telegram_username,
        station_id=workflow.station_id,
        station_code=workflow.station_code,
        status=data.status,
        step=data.current_step,
        changed_fields=data.changed_fields,
        before=data.before_data,
        after=data.after_data,
        reason=data.failure_reason,
    )
    await db.commit()
    return {"workflow_id": workflow.id, "status": workflow.status, "preview_hash": workflow.preview_hash}


@router.post("/telegram/stations", response_model=StationOut, status_code=201)
async def telegram_create_station(
    data: TelegramStationCreateIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    user, identity = await _require_telegram_actor(db, data, TELEGRAM_STATION_ROLES)
    existing_workflow = await db.scalar(select(TelegramStationWorkflow).where(TelegramStationWorkflow.id == data.workflow_id).with_for_update())
    if (
        existing_workflow
        and existing_workflow.actor_user_id == user.id
        and existing_workflow.workflow_type == "registration"
        and existing_workflow.status == "completed"
        and existing_workflow.station_id is not None
        and existing_workflow.preview_hash == data.preview_hash
    ):
        existing_station = await _load_station(db, existing_workflow.station_id)
        return (await serialize_stations(db, [existing_station]))[0]
    workflow = await _active_actor_workflow(db, data.workflow_id, user, "registration")
    _consume_preview(workflow, data.workflow_version, data.preview_hash)
    await _validate_regions(db, data.city_id, data.district_id)
    station = Station(
        station_code=data.station_code,
        name=data.name,
        city_id=data.city_id,
        district_id=data.district_id,
        operational_area=data.operational_area,
        address=data.address,
        latitude=data.latitude,
        longitude=data.longitude,
        is_active=True,
        is_archived=False,
        approved_at=None,
        approved_by=None,
    )
    db.add(station)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "STATION_CODE_EXISTS") from exc
    workflow.station_id = station.id
    workflow.station_code = station.station_code
    workflow.status = "completed"
    workflow.current_step = "completed"
    workflow.last_activity_at = workflow.completed_at = datetime.now(timezone.utc)
    after = {
        "station_code": station.station_code,
        "name": station.name,
        "city_id": station.city_id,
        "district_id": station.district_id,
        "operational_area": station.operational_area,
        "address": station.address,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "operator_username": user.username,
        "operator_display_name": " ".join(filter(None, [identity.first_name, identity.last_name])) or user.username,
        "telegram_user_id": identity.telegram_user_id,
        "telegram_username": data.telegram_username or identity.telegram_username,
        "approval_status": "pending",
    }
    add_audit(db, action="station.create", entity_type="station", entity_id=station.id, actor=user, after=after, request=request, source="telegram")
    add_activity_event(
        db,
        user=user,
        action="station.created",
        source="telegram",
        workflow=workflow,
        telegram_user_id=identity.telegram_user_id,
        telegram_username=data.telegram_username or identity.telegram_username,
        station_id=station.id,
        station_code=station.station_code,
        status="completed",
        changed_fields=["station_code", "name", "city_id", "district_id", "operational_area", "address", "latitude", "longitude"],
        after=after,
    )
    await touch_presence(db, user, "telegram")
    await db.commit()
    station = await _load_station(db, station.id)
    return (await serialize_stations(db, [station]))[0]


@router.patch("/telegram/stations/{station_id}", response_model=StationOut)
async def telegram_update_station(
    station_id: int,
    data: TelegramStationUpdateIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    user, identity = await _require_telegram_actor(db, data, TELEGRAM_STATION_ROLES)
    existing_workflow = await db.scalar(select(TelegramStationWorkflow).where(TelegramStationWorkflow.id == data.workflow_id).with_for_update())
    if (
        existing_workflow
        and existing_workflow.actor_user_id == user.id
        and existing_workflow.workflow_type == "update"
        and existing_workflow.status == "completed"
        and existing_workflow.station_id == station_id
        and existing_workflow.preview_hash == data.preview_hash
    ):
        existing_station = await _load_station(db, station_id)
        return (await serialize_stations(db, [existing_station]))[0]
    workflow = await _active_actor_workflow(db, data.workflow_id, user, "update")
    _consume_preview(workflow, data.workflow_version, data.preview_hash)
    station = await _load_station(db, station_id)
    excluded = {"telegram_user_id", "telegram_username", "workflow_id", "workflow_version", "preview_hash", "expected_before"}
    changes = {key: value for key, value in data.model_dump(exclude_unset=True).items() if key not in excluded}
    if not changes:
        raise HTTPException(422, "NO_STATION_FIELDS")
    if set(changes) not in ({"city_id"}, {"district_id"}, {"operational_area"}, {"address"}, {"name"}, {"latitude", "longitude"}):
        raise HTTPException(422, "ONE_LOGICAL_FIELD_REQUIRED")
    await _validate_regions(db, changes.get("city_id", station.city_id), changes.get("district_id", station.district_id))
    before = {key: getattr(station, key) for key in changes}
    if set(data.expected_before) != set(changes) or any(before[key] != data.expected_before.get(key) for key in changes):
        raise HTTPException(409, "STATION_CHANGED_AFTER_PREVIEW")
    effective = {key: value for key, value in changes.items() if before[key] != value}
    for key, value in effective.items():
        setattr(station, key, value)
    workflow.station_id = station.id
    workflow.station_code = station.station_code
    workflow.status = "completed"
    workflow.current_step = "completed"
    workflow.changed_fields = sorted(effective)
    workflow.before_data = safe_values(before)
    workflow.after_data = safe_values(effective)
    workflow.last_activity_at = workflow.completed_at = datetime.now(timezone.utc)
    add_audit(
        db,
        action="station.update",
        entity_type="station",
        entity_id=station.id,
        actor=user,
        before={**before, "actor_role": user.role, "telegram_user_id": identity.telegram_user_id},
        after={**effective, "actor_role": user.role, "telegram_user_id": identity.telegram_user_id},
        request=request,
        source="telegram",
    )
    add_activity_event(
        db,
        user=user,
        action="station.updated",
        source="telegram",
        workflow=workflow,
        telegram_user_id=identity.telegram_user_id,
        telegram_username=data.telegram_username or identity.telegram_username,
        station_id=station.id,
        station_code=station.station_code,
        status="completed",
        changed_fields=sorted(effective),
        before=before,
        after=effective,
    )
    await touch_presence(db, user, "telegram")
    await db.commit()
    station = await _load_station(db, station.id)
    return (await serialize_stations(db, [station]))[0]


@router.get("/admin/presence", response_model=list[OperatorPresenceOut])
async def admin_presence(
    q: str | None = None,
    role: Role | None = None,
    presence: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    users = list((await db.execute(select(User).where(User.is_active.is_(True)).order_by(User.username))).scalars().all())
    identities = list((await db.execute(select(TelegramIdentity))).scalars().all())
    identity_by_user = {identity.user_id: identity for identity in identities}
    workflows = list((await db.execute(select(TelegramStationWorkflow).where(TelegramStationWorkflow.status == "in_progress"))).scalars().all())
    workflow_by_user = {workflow.actor_user_id: workflow for workflow in workflows}
    output = []
    for user in users:
        identity = identity_by_user.get(user.id)
        state = presence_state(user.last_activity_at)
        display_name = " ".join(filter(None, [identity.first_name, identity.last_name])) if identity else user.username
        row = OperatorPresenceOut(
            user_id=user.id,
            display_name=display_name or user.username,
            username=user.username,
            telegram_username=identity.telegram_username if identity else None,
            telegram_user_id=identity.telegram_user_id if identity else None,
            role=user.role,
            presence=state,
            last_activity_at=user.last_activity_at,
            last_activity_source=user.last_activity_source,
            current_workflow_state=(workflow_by_user[user.id].current_step if user.id in workflow_by_user else None),
        )
        haystack = f"{row.display_name} {row.username} {row.telegram_username or ''} {row.telegram_user_id or ''}".casefold()
        if q and q.casefold() not in haystack:
            continue
        if role and row.role != role:
            continue
        if presence and row.presence != presence:
            continue
        output.append(row)
    return output


@router.get("/admin/events", response_model=list[OperatorActivityOut])
async def admin_activity_events(
    q: str | None = None,
    role: Role | None = None,
    status: str | None = None,
    source: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    stmt = select(OperatorActivityEvent, User).join(User, User.id == OperatorActivityEvent.actor_user_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            User.username.ilike(like),
            OperatorActivityEvent.telegram_username.ilike(like),
            cast(OperatorActivityEvent.telegram_user_id, String).ilike(like),
            OperatorActivityEvent.station_code.ilike(like),
            OperatorActivityEvent.action.ilike(like),
        ))
    if role:
        stmt = stmt.where(OperatorActivityEvent.actor_role == role.value)
    if status:
        stmt = stmt.where(OperatorActivityEvent.workflow_status == status)
    if source:
        stmt = stmt.where(OperatorActivityEvent.source == source)
    if start:
        stmt = stmt.where(OperatorActivityEvent.timestamp >= start)
    if end:
        stmt = stmt.where(OperatorActivityEvent.timestamp <= end)
    rows = (await db.execute(stmt.order_by(OperatorActivityEvent.timestamp.desc()).limit(limit))).all()
    return [
        OperatorActivityOut(
            **event.__dict__,
            actor_username=user.username,
            actor_display_name=user.username,
        )
        for event, user in rows
    ]


async def _require_telegram_actor(db: AsyncSession, data: TelegramActorIn, roles: set[str]) -> tuple[User, TelegramIdentity]:
    resolved = await resolve_telegram_user(db, data.telegram_user_id)
    if not resolved:
        raise HTTPException(403, "TELEGRAM_IDENTITY_NOT_ACTIVE")
    user, identity = resolved
    if user.role not in roles:
        add_activity_event(
            db,
            user=user,
            action="telegram.permission_denied",
            source="telegram",
            telegram_user_id=identity.telegram_user_id,
            telegram_username=data.telegram_username or identity.telegram_username,
            status="failed",
            reason="role not permitted",
        )
        await db.commit()
        raise HTTPException(403, "TELEGRAM_ROLE_FORBIDDEN")
    return user, identity


async def _active_actor_workflow(db: AsyncSession, workflow_id: str, user: User, workflow_type: str) -> TelegramStationWorkflow:
    workflow = await db.get(TelegramStationWorkflow, workflow_id)
    if not workflow or workflow.actor_user_id != user.id or workflow.workflow_type != workflow_type:
        raise HTTPException(404, "WORKFLOW_NOT_FOUND")
    if workflow.status != "in_progress":
        raise HTTPException(409, "WORKFLOW_ALREADY_FINISHED")
    return workflow


def _consume_preview(workflow: TelegramStationWorkflow, version: int, preview_hash: str) -> None:
    if workflow.version != version or workflow.preview_hash != preview_hash:
        raise HTTPException(409, "WORKFLOW_PREVIEW_STALE")
    if workflow.preview_consumed_at is not None:
        raise HTTPException(409, "WORKFLOW_PREVIEW_CONSUMED")
    workflow.preview_consumed_at = datetime.now(timezone.utc)


async def _validate_regions(db: AsyncSession, city_id: int, district_id: int | None) -> None:
    city = await db.get(OperationalRegion, city_id)
    if not city or city.region_type != "city":
        raise HTTPException(422, "INVALID_CITY")
    if district_id is not None:
        district = await db.get(OperationalRegion, district_id)
        if not district or district.region_type != "district" or district.parent_id != city_id:
            raise HTTPException(422, "INVALID_DISTRICT")


async def _load_station(db: AsyncSession, station_id: int) -> Station:
    station = (
        await db.execute(
            select(Station)
            .where(Station.id == station_id)
            .options(selectinload(Station.city), selectinload(Station.district))
        )
    ).scalar_one_or_none()
    if not station:
        raise HTTPException(404, "STATION_NOT_FOUND")
    return station
