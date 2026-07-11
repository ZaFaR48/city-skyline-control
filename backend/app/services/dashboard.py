from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    Alert,
    ApprovalStatus,
    Camera,
    DeviceType,
    HeadscaleNode,
    OperationalRegion,
    Station,
    StationStatus,
)
from ..schemas import AttentionStation, DashboardSummaryOut, DistrictHealth


PILOT_DISTRICT_CODES = ("ismoili-somoni", "shohmansur", "sino", "firdavsi")


async def build_dashboard_summary(db: AsyncSession) -> DashboardSummaryOut:
    stations = (
        await db.execute(
            select(Station)
            .join(OperationalRegion, Station.city_id == OperationalRegion.id)
            .where(
                OperationalRegion.code == "dushanbe",
                Station.is_active.is_(True),
                Station.is_archived.is_(False),
            )
            .options(selectinload(Station.district))
        )
    ).scalars().all()
    station_ids = [station.id for station in stations]
    statuses = Counter(station.status for station in stations)
    total = len(stations)

    camera_total = 0
    camera_online = 0
    camera_offline = 0
    camera_failures: dict[int, int] = {}
    if station_ids:
        camera_rows = (
            await db.execute(
                select(
                    Camera.station_id,
                    func.count(Camera.id),
                    func.count(Camera.id).filter(Camera.status == StationStatus.online.value),
                    func.count(Camera.id).filter(Camera.status == StationStatus.offline.value),
                )
                .where(Camera.station_id.in_(station_ids))
                .group_by(Camera.station_id)
            )
        ).all()
        camera_total = sum(row[1] for row in camera_rows)
        camera_online = sum(row[2] for row in camera_rows)
        camera_offline = sum(row[3] for row in camera_rows)
        camera_failures = {row[0]: row[3] for row in camera_rows}

    active_alert_rows = []
    if station_ids:
        active_alert_rows = (
            await db.execute(
                select(Alert.station_id, func.count(Alert.id))
                .where(Alert.station_id.in_(station_ids), Alert.resolved_at.is_(None))
                .group_by(Alert.station_id)
            )
        ).all()
    alerts_by_station = dict(active_alert_rows)
    active_alerts = sum(alerts_by_station.values())

    approved_nodes = (
        await db.execute(
            select(func.count(HeadscaleNode.id))
            .join(Station, HeadscaleNode.station_id == Station.id)
            .where(
                HeadscaleNode.approval_status == ApprovalStatus.approved.value,
                HeadscaleNode.device_type == DeviceType.station.value,
                Station.is_active.is_(True),
                Station.is_archived.is_(False),
            )
        )
    ).scalar_one()
    pending_nodes = (
        await db.execute(
            select(func.count(HeadscaleNode.id)).where(
                HeadscaleNode.approval_status == ApprovalStatus.pending.value
            )
        )
    ).scalar_one()

    districts = (
        await db.execute(
            select(OperationalRegion)
            .where(OperationalRegion.code.in_(PILOT_DISTRICT_CODES), OperationalRegion.is_active.is_(True))
            .order_by(OperationalRegion.sort_order)
        )
    ).scalars().all()
    district_health = []
    for district in districts:
        district_stations = [station for station in stations if station.district_id == district.id]
        counts = Counter(station.status for station in district_stations)
        district_total = len(district_stations)
        district_health.append(
            DistrictHealth(
                id=district.id,
                code=district.code,
                name=district.name,
                total_stations=district_total,
                online=counts[StationStatus.online.value],
                offline=counts[StationStatus.offline.value],
                degraded=counts[StationStatus.degraded.value],
                unknown=counts[StationStatus.unknown.value],
                availability_percentage=(
                    round(counts[StationStatus.online.value] * 100 / district_total, 1)
                    if district_total
                    else None
                ),
            )
        )

    recent_alerts = (
        await db.execute(
            select(Alert).where(Alert.resolved_at.is_(None)).order_by(Alert.created_at.desc()).limit(6)
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)

    def problem_score(station: Station) -> tuple[float, int, int, int, int]:
        offline_seconds = (
            (now - station.offline_since).total_seconds()
            if station.status == StationStatus.offline.value and station.offline_since
            else 0
        )
        return (
            offline_seconds,
            alerts_by_station.get(station.id, 0),
            1 if station.status == StationStatus.degraded.value else 0,
            station.last_ping_ms or -1,
            camera_failures.get(station.id, 0),
        )

    problem_stations = [
        station
        for station in stations
        if station.status != StationStatus.online.value
        or alerts_by_station.get(station.id, 0)
        or camera_failures.get(station.id, 0)
    ]
    problem_stations.sort(key=problem_score, reverse=True)
    attention = [
        AttentionStation(
            station_id=station.id,
            station_code=station.station_code,
            name=station.name,
            district=station.district.name if station.district else None,
            status=station.status,
            vpn_ip=station.vpn_ip,
            last_ping_ms=station.last_ping_ms,
            last_seen_at=station.last_seen_at,
            offline_since=station.offline_since,
            active_alerts=alerts_by_station.get(station.id, 0),
        )
        for station in problem_stations[:10]
    ]

    return DashboardSummaryOut(
        total_stations=total,
        online_stations=statuses[StationStatus.online.value],
        offline_stations=statuses[StationStatus.offline.value],
        degraded_stations=statuses[StationStatus.degraded.value],
        unknown_stations=statuses[StationStatus.unknown.value],
        online_percentage=round(statuses[StationStatus.online.value] * 100 / total, 1) if total else None,
        total_cameras=camera_total if camera_total else None,
        online_cameras=camera_online if camera_total else None,
        offline_cameras=camera_offline if camera_total else None,
        camera_monitoring_configured=camera_total > 0,
        active_alerts=active_alerts,
        approved_station_vpn_nodes=approved_nodes,
        pending_headscale_nodes=pending_nodes,
        district_health=district_health,
        recent_alerts=list(recent_alerts),
        top_problem_stations=attention,
    )
