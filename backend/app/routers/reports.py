from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Role, User
from ..schemas import ReportStationRow
from ..services.audit import add_audit
from ..services.uptime_reports import build_uptime_report


router = APIRouter()


@router.get("/uptime", response_model=list[ReportStationRow])
async def uptime_report(
    start: datetime,
    end: datetime,
    station_id: int | None = None,
    district_id: int | None = None,
    status: str | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if end <= start:
        raise HTTPException(422, "end must be after start")
    return await build_uptime_report(db, start=start, end=end, station_id=station_id, district_id=district_id, status=status, source=source)


@router.get("/uptime.csv")
async def export_uptime_csv(
    start: datetime,
    end: datetime,
    request: Request,
    station_id: int | None = None,
    district_id: int | None = None,
    status: str | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    rows = await build_uptime_report(db, start=start, end=end, station_id=station_id, district_id=district_id, status=status, source=source)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(ReportStationRow.model_fields))
    writer.writeheader()
    for row in rows:
        writer.writerow(row.model_dump())
    add_audit(db, action="report.export", entity_type="uptime_report", entity_id=None, actor=user, after={"start": start, "end": end, "rows": len(rows)}, request=request)
    await db.commit()
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=city-parking-uptime.csv"})
