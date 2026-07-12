from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import SessionLocal
from ..models import OperatorActivityEvent, TelegramIdentity, TelegramStationWorkflow, User
from .audit import sanitize


SAFE_OPERATIONAL_FIELDS = {
    "city_id", "district_id", "operational_area", "address", "name", "latitude", "longitude",
    "station_code", "is_active", "is_archived", "approved_at", "approved_by", "vpn_ip", "station_id",
    "device_type", "approval_status",
}


async def resolve_telegram_user(db: AsyncSession, telegram_user_id: int) -> tuple[User, TelegramIdentity] | None:
    row = (
        await db.execute(
            select(User, TelegramIdentity)
            .join(TelegramIdentity, TelegramIdentity.user_id == User.id)
            .where(TelegramIdentity.telegram_user_id == telegram_user_id, User.is_active.is_(True))
        )
    ).one_or_none()
    return row if row else None


async def touch_presence(db: AsyncSession, user: User, source: str, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    threshold = timedelta(seconds=settings.PRESENCE_WRITE_THROTTLE_SECONDS)
    if user.last_activity_at and current - user.last_activity_at < threshold and user.last_activity_source == source:
        return False
    user.last_activity_at = current
    user.last_activity_source = source
    return True


def presence_state(last_activity_at: datetime | None, *, now: datetime | None = None) -> str:
    if last_activity_at is None:
        return "offline"
    age = (now or datetime.now(timezone.utc)) - last_activity_at
    if age <= timedelta(minutes=settings.PRESENCE_ONLINE_MINUTES):
        return "online"
    if age <= timedelta(minutes=settings.PRESENCE_RECENT_MINUTES):
        return "recently_active"
    return "offline"


def safe_values(values: dict[str, Any] | None) -> dict[str, Any] | None:
    if values is None:
        return None
    return sanitize({key: value for key, value in values.items() if key in SAFE_OPERATIONAL_FIELDS})


def add_activity_event(
    db: AsyncSession,
    *,
    user: User,
    action: str,
    source: str,
    workflow: TelegramStationWorkflow | None = None,
    telegram_user_id: int | None = None,
    telegram_username: str | None = None,
    station_id: int | None = None,
    station_code: str | None = None,
    status: str | None = None,
    step: str | None = None,
    changed_fields: list[str] | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    correlation_id: str | None = None,
) -> None:
    completed_at = workflow.completed_at if workflow else None
    duration = None
    if workflow and completed_at:
        duration = max(0, int((completed_at - workflow.started_at).total_seconds()))
    db.add(OperatorActivityEvent(
        workflow_id=workflow.id if workflow else None,
        actor_user_id=user.id,
        actor_role=user.role,
        telegram_user_id=telegram_user_id,
        telegram_username=telegram_username,
        source=source,
        station_id=station_id,
        station_code=station_code,
        action=action,
        workflow_status=status or (workflow.status if workflow else None),
        current_step=step or (workflow.current_step if workflow else None),
        started_at=workflow.started_at if workflow else None,
        last_activity_at=workflow.last_activity_at if workflow else None,
        completed_at=completed_at,
        duration_seconds=duration,
        changed_fields=changed_fields or [],
        before_data=safe_values(before),
        after_data=safe_values(after),
        failure_reason=reason,
        correlation_id=correlation_id or (workflow.correlation_id if workflow else None),
    ))


async def abandon_inactive_workflows(now: datetime | None = None) -> int:
    current = now or datetime.now(timezone.utc)
    async with SessionLocal() as db:
        count = await abandon_inactive_workflows_in_db(db, current)
        await db.commit()
        return count


async def abandon_inactive_workflows_in_db(db: AsyncSession, current: datetime) -> int:
    cutoff = current - timedelta(minutes=settings.TELEGRAM_WORKFLOW_ABANDON_MINUTES)
    workflows = list((await db.execute(
        select(TelegramStationWorkflow).where(
            TelegramStationWorkflow.status == "in_progress",
            TelegramStationWorkflow.last_activity_at < cutoff,
        ).with_for_update(skip_locked=True)
    )).scalars().all())
    for workflow in workflows:
        workflow.status = "abandoned"
        workflow.completed_at = current
        user = await db.get(User, workflow.actor_user_id)
        if user is None:
            continue
        add_activity_event(
            db,
            user=user,
            action="telegram.station_workflow.abandoned",
            source="telegram",
            workflow=workflow,
            telegram_user_id=workflow.telegram_user_id,
            telegram_username=workflow.telegram_username,
            station_id=workflow.station_id,
            station_code=workflow.station_code,
            status="abandoned",
            reason="workflow inactivity timeout",
        )
    return len(workflows)
