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
from .station_visibility import production_station_filter
from .station_health import resolve_station_health_batch


PILOT_DISTRICT_CODES = ("ismoili-somoni", "shohmansur", "sino", "firdavsi")


async def build_dashboard_summary(db: AsyncSession) -> DashboardSummaryOut:
    stations = (
        await db.execute(
            select(Station)
            .join(OperationalRegion, Station.city_id == OperationalRegion.id)
            .where(
                OperationalRegion.code == "dushanbe",
                production_station_filter(),
            )
            .options(selectinload(Station.district))
        )
    ).scalars().all()
    station_ids = [station.id for station in stations]
    health_by_station = await resolve_station_health_batch(db, list(stations))
    statuses = Counter(health_by_station[station.id].overall_status for station in stations)
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
                production_station_filter(),
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
        counts = Counter(health_by_station[station.id].overall_status for station in district_stations)
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
            select(Alert)
            .join(Station, Alert.station_id == Station.id)
            .where(Alert.resolved_at.is_(None), production_station_filter())
            .order_by(Alert.created_at.desc())
            .limit(6)
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)

    def problem_score(station: Station) -> tuple[float, int, int, int, int]:
        health = health_by_station[station.id]
        offline_seconds = health.current_state_duration_seconds or 0 if health.overall_status == StationStatus.offline.value else 0
        return (
            offline_seconds,
            alerts_by_station.get(station.id, 0),
            1 if health.overall_status == StationStatus.degraded.value else 0,
            station.last_ping_ms or -1,
            camera_failures.get(station.id, 0),
        )

    problem_stations = [
        station
        for station in stations
        if health_by_station[station.id].overall_status != StationStatus.online.value
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
            status=health_by_station[station.id].overall_status,
            vpn_ip=station.vpn_ip,
            last_ping_ms=station.last_ping_ms,
            last_seen_at=station.last_seen_at,
            offline_since=(
                health_by_station[station.id].current_state_started_at
                if health_by_station[station.id].overall_status == StationStatus.offline.value
                else None
            ),
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
