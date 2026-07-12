from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import OperationalRegion, Station, StationStatus, StationStatusEvent
from ..schemas import ReportStationRow
from .station_visibility import production_station_filter
from .station_health import resolve_station_health_batch


async def build_uptime_report(
    db: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    station_id: int | None = None,
    district_id: int | None = None,
    status: str | None = None,
    source: str | None = None,
) -> list[ReportStationRow]:
    logging.getLogger(__name__).info(
        "uptime_report_generation start=%s end=%s station_id=%s district_id=%s status=%s source=%s",
        start,
        end,
        station_id,
        district_id,
        status,
        source,
    )
    now = datetime.now(timezone.utc)
    end = min(end, now)
    if start >= end:
        return []
    station_stmt = (
        select(Station)
        .join(OperationalRegion, Station.city_id == OperationalRegion.id)
        .where(OperationalRegion.code == "dushanbe", production_station_filter())
        .options(selectinload(Station.district))
    )
    if station_id:
        station_stmt = station_stmt.where(Station.id == station_id)
    if district_id:
        station_stmt = station_stmt.where(Station.district_id == district_id)
    stations = (await db.execute(station_stmt.order_by(Station.station_code))).scalars().all()
    health_by_station = await resolve_station_health_batch(db, list(stations), now=end)
    if status:
        stations = [station for station in stations if health_by_station[station.id].overall_status == status]
    if not stations:
        return []

    event_stmt = select(StationStatusEvent).where(
        StationStatusEvent.station_id.in_([station.id for station in stations]),
        StationStatusEvent.started_at < end,
        or_(StationStatusEvent.ended_at.is_(None), StationStatusEvent.ended_at > start),
    )
    if source:
        event_stmt = event_stmt.where(StationStatusEvent.source == source)
    events = (await db.execute(event_stmt.order_by(StationStatusEvent.station_id, StationStatusEvent.started_at))).scalars().all()
    grouped: dict[int, list[StationStatusEvent]] = defaultdict(list)
    for event in events:
        grouped[event.station_id].append(event)

    total_seconds = max(0, int((end - start).total_seconds()))
    rows = []
    for station in stations:
        durations = defaultdict(int)
        outages = []
        cursor = start
        for event in grouped[station.id]:
            segment_start = max(start, event.started_at, cursor)
            segment_end = min(end, event.ended_at or end)
            seconds = max(0, int((segment_end - segment_start).total_seconds()))
            if seconds:
                status_value = event.new_status if event.new_status in {
                    StationStatus.online.value,
                    StationStatus.offline.value,
                    StationStatus.degraded.value,
                    StationStatus.unknown.value,
                } else StationStatus.unknown.value
                durations[status_value] += seconds
                if status_value == StationStatus.offline.value:
                    outages.append(seconds)
                cursor = max(cursor, segment_end)
        known = sum(durations[value] for value in (
            StationStatus.online.value,
            StationStatus.offline.value,
            StationStatus.degraded.value,
        ))
        unknown = max(0, total_seconds - known)
        durations[StationStatus.unknown.value] = unknown
        availability = round(durations[StationStatus.online.value] * 100 / known, 2) if known else None
        coverage = round(known * 100 / total_seconds, 2) if total_seconds else 0.0
        health = health_by_station[station.id]
        current_outage = None
        if health.overall_status == StationStatus.offline.value and health.current_state_started_at:
            current_outage = max(0, int((end - max(start, health.current_state_started_at)).total_seconds()))
        last_change = max((event.started_at for event in grouped[station.id]), default=None)
        rows.append(
            ReportStationRow(
                station_id=station.id,
                station_code=station.station_code,
                station_name=station.name,
                district=station.district.name if station.district else None,
                total_monitored_seconds=total_seconds,
                online_seconds=durations[StationStatus.online.value],
                offline_seconds=durations[StationStatus.offline.value],
                degraded_seconds=durations[StationStatus.degraded.value],
                unknown_seconds=unknown,
                availability_percentage=availability,
                data_coverage_percentage=coverage,
                outages=len(outages),
                longest_outage_seconds=max(outages, default=0),
                average_outage_seconds=round(sum(outages) / len(outages), 2) if outages else None,
                current_outage_seconds=current_outage,
                last_status_change_at=last_change,
                current_status=health.overall_status,
            )
        )
    return rows
