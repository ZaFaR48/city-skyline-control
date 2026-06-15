from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Alert, AlertSeverity, Role, User
from ..schemas import AlertOut

router = APIRouter()


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    severity: AlertSeverity | None = None,
    acknowledged: bool | None = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if severity: stmt = stmt.where(Alert.severity == severity)
    if acknowledged is not None: stmt = stmt.where(Alert.acknowledged == acknowledged)
    return (await db.execute(stmt)).scalars().all()


@router.post("/{alert_id}/ack", response_model=AlertOut,
             dependencies=[Depends(require_roles(Role.admin, Role.operator))])
async def ack_alert(alert_id: int, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    a = await db.get(Alert, alert_id)
    if not a: raise HTTPException(404, "Alert not found")
    a.acknowledged = True
    a.acknowledged_by = user.id
    a.resolved_at = datetime.now(timezone.utc)
    await db.commit(); await db.refresh(a)
    return a
