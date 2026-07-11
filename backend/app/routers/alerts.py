from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Alert, AlertSeverity, Role, Station, User
from ..schemas import AlertOut
from ..services.audit import add_audit
from ..services.station_visibility import production_station_filter


router = APIRouter()


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    severity: AlertSeverity | None = None,
    acknowledged: bool | None = None,
    active: bool | None = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = (
        select(Alert)
        .join(Station, Alert.station_id == Station.id)
        .where(production_station_filter())
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    if severity:
        stmt = stmt.where(Alert.severity == severity.value)
    if acknowledged is not None:
        stmt = stmt.where(Alert.acknowledged == acknowledged)
    if active is not None:
        stmt = stmt.where(Alert.resolved_at.is_(None) if active else Alert.resolved_at.is_not(None))
    return (await db.execute(stmt)).scalars().all()


@router.post("/{alert_id}/ack", response_model=AlertOut)
async def ack_alert(
    alert_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin, Role.operator)),
):
    alert = await _alert_or_404(db, alert_id)
    alert.acknowledged = True
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    add_audit(db, action="alert.acknowledge", entity_type="alert", entity_id=alert.id, actor=user, after={"acknowledged": True}, request=request)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    alert = await _alert_or_404(db, alert_id)
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = user.id
    add_audit(db, action="alert.resolve", entity_type="alert", entity_id=alert.id, actor=user, after={"resolved": True}, request=request)
    await db.commit()
    await db.refresh(alert)
    return alert


async def _alert_or_404(db: AsyncSession, alert_id: int) -> Alert:
    alert = (
        await db.execute(
            select(Alert)
            .join(Station, Alert.station_id == Station.id)
            .where(Alert.id == alert_id, production_station_filter())
        )
    ).scalar_one_or_none()
    if not alert:
        raise HTTPException(404, "Alert not found")
    return alert
