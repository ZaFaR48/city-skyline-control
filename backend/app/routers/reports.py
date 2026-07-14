from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Role, User
from ..schemas import ReportStationRow
from ..services.audit import add_audit
from ..services.uptime_reports import build_uptime_report
from ..services.performance import record_result_count


router = APIRouter()
EXPORT_FIELDS = list(ReportStationRow.model_fields)


def _validate_range(start: datetime, end: datetime) -> None:
    now = datetime.now(timezone.utc)
    if end <= start:
        raise HTTPException(422, "end must be after start")
    if start >= now:
        raise HTTPException(422, "start must be in the past")
    if end > now + timedelta(minutes=1):
        raise HTTPException(422, "end must not be in the future")


def _filename(extension: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"city-skyline-uptime-{timestamp}.{extension}"


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
    _validate_range(start, end)
    rows = await build_uptime_report(db, start=start, end=end, station_id=station_id, district_id=district_id, status=status, source=source)
    record_result_count(len(rows))
    return rows


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
    user: User = Depends(require_roles(Role.admin, Role.operator)),
):
    _validate_range(start, end)
    rows = await build_uptime_report(db, start=start, end=end, station_id=station_id, district_id=district_id, status=status, source=source)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row.model_dump())
    add_audit(db, action="report.export", entity_type="uptime_report", entity_id=None, actor=user, after={"format": "csv", "start": start, "end": end, "station_id": station_id, "district_id": district_id, "status": status, "source": source, "rows": len(rows)}, request=request)
    await db.commit()
    logging.getLogger(__name__).info("uptime_export_success format=csv rows=%s actor_user_id=%s", len(rows), user.id)
    payload = ("\ufeff" + output.getvalue()).encode("utf-8")
    return StreamingResponse(
        iter([payload]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_filename("csv")}"'},
    )


@router.get("/uptime.xlsx")
async def export_uptime_xlsx(
    start: datetime,
    end: datetime,
    request: Request,
    station_id: int | None = None,
    district_id: int | None = None,
    status: str | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin, Role.operator)),
):
    _validate_range(start, end)
    rows = await build_uptime_report(db, start=start, end=end, station_id=station_id, district_id=district_id, status=status, source=source)
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Uptime")
    sheet.append(EXPORT_FIELDS)
    for row in rows:
        values = row.model_dump()
        sheet.append([
            values[field].isoformat() if isinstance(values[field], datetime) else values[field]
            for field in EXPORT_FIELDS
        ])
    output = io.BytesIO()
    workbook.save(output)
    add_audit(db, action="report.export", entity_type="uptime_report", entity_id=None, actor=user, after={"format": "xlsx", "start": start, "end": end, "station_id": station_id, "district_id": district_id, "status": status, "source": source, "rows": len(rows)}, request=request)
    await db.commit()
    logging.getLogger(__name__).info("uptime_export_success format=xlsx rows=%s actor_user_id=%s", len(rows), user.id)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_filename("xlsx")}"'},
    )
