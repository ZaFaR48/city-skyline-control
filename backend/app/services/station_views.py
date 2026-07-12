from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Alert,
    ApprovalStatus,
    AuditLog,
    Camera,
    DeviceType,
    HeadscaleNode,
    OperationalRegion,
    Station,
    StationStatus,
    User,
)
from ..schemas import StationOut
from .station_health import resolve_station_health_batch


async def serialize_stations(
    db: AsyncSession,
    stations: list[Station],
    *,
    include_actor_attribution: bool = False,
) -> list[StationOut]:
    if not stations:
        return []
    ids = [station.id for station in stations]
    region_ids = {
        region_id
        for station in stations
        for region_id in (station.city_id, station.district_id)
        if region_id is not None
    }
    regions = {
        region.id: region
        for region in (
            await db.execute(select(OperationalRegion).where(OperationalRegion.id.in_(region_ids)))
        ).scalars().all()
    }
    camera_rows = (
        await db.execute(
            select(
                Camera.station_id,
                func.count(Camera.id),
                func.count(Camera.id).filter(Camera.status == StationStatus.online.value),
            )
            .where(Camera.station_id.in_(ids))
            .group_by(Camera.station_id)
        )
    ).all()
    alert_rows = (
        await db.execute(
            select(Alert.station_id, func.count(Alert.id))
            .where(Alert.station_id.in_(ids), Alert.resolved_at.is_(None))
            .group_by(Alert.station_id)
        )
    ).all()
    nodes = (
        await db.execute(
            select(HeadscaleNode).where(HeadscaleNode.station_id.in_(ids))
        )
    ).scalars().all()
    camera_counts = {row[0]: (row[1], row[2]) for row in camera_rows}
    alert_counts = dict(alert_rows)
    node_by_station = {node.station_id: node for node in nodes}
    health_by_station = await resolve_station_health_batch(db, stations)
    audit_rows = []
    if include_actor_attribution:
        audit_rows = list((
            await db.execute(
                select(AuditLog)
                .where(
                    AuditLog.entity_type == "station",
                    AuditLog.entity_id.in_([str(station_id) for station_id in ids]),
                    AuditLog.action.in_(("station.create", "station.update")),
                )
                .order_by(AuditLog.timestamp, AuditLog.id)
            )
        ).scalars().all())
    actor_ids = {row.actor_user_id for row in audit_rows if row.actor_user_id is not None}
    actors = {
        user.id: user
        for user in (
            await db.execute(select(User).where(User.id.in_(actor_ids)))
        ).scalars().all()
    } if actor_ids else {}
    created_by_station: dict[int, User] = {}
    updated_by_station: dict[int, User] = {}
    for row in audit_rows:
        try:
            station_id = int(row.entity_id or "")
        except ValueError:
            continue
        actor = actors.get(row.actor_user_id)
        if not actor:
            continue
        if row.action == "station.create":
            created_by_station.setdefault(station_id, actor)
        updated_by_station[station_id] = actor

    output = []
    for station in stations:
        camera_total, camera_online = camera_counts.get(station.id, (0, 0))
        node = node_by_station.get(station.id)
        monitoring_node = (
            node
            if node
            and node.approval_status == ApprovalStatus.approved.value
            and node.device_type == DeviceType.station.value
            else None
        )
        creator = created_by_station.get(station.id)
        updater = updated_by_station.get(station.id)
        health = health_by_station[station.id]
        warnings = []
        district_name = regions[station.district_id].name if station.district_id else None
        normalized_name = station.name.casefold().removeprefix("н.").strip()
        if district_name and normalized_name == district_name.casefold():
            warnings.append("Station name duplicates the district name")
        if station.address and len(station.address.strip()) <= 64 and not any(char.isdigit() for char in station.address):
            warnings.append("Address may contain only a landmark; verify an exact address")
        if station.vpn_ip and not monitoring_node:
            warnings.append("Manual VPN IP is stored without an approved linked Headscale station node")
        if station.local_ip and not monitoring_node:
            warnings.append("Local IP is stored without a configured monitoring agent")
        output.append(
            StationOut(
                id=station.id,
                station_code=station.station_code,
                name=station.name,
                city_id=station.city_id,
                city=regions[station.city_id].name,
                district_id=station.district_id,
                district=regions[station.district_id].name if station.district_id else None,
                address=station.address,
                operational_area=station.operational_area,
                latitude=station.latitude,
                longitude=station.longitude,
                vpn_ip=station.vpn_ip,
                local_ip=station.local_ip,
                rustdesk_id=station.rustdesk_id,
                status=health.overall_status,
                status_reason=health.overall_reason_code,
                last_seen_at=station.last_seen_at,
                last_ping_at=station.last_ping_at,
                last_ping_ms=station.last_ping_ms,
                offline_since=station.offline_since,
                cpu=station.cpu,
                ram=station.ram,
                disk=station.disk,
                telemetry_at=station.telemetry_at,
                is_active=station.is_active,
                is_archived=station.is_archived,
                approved_at=station.approved_at,
                approved_by=station.approved_by,
                created_by_username=creator.username if creator else None,
                created_by_role=creator.role if creator else None,
                last_updated_by_username=updater.username if updater else None,
                last_updated_by_role=updater.role if updater else None,
                monitoring_configured=bool(station.vpn_ip and monitoring_node),
                headscale_linked=monitoring_node is not None,
                headscale_hostname=node.hostname if node else None,
                headscale_approval_status=node.approval_status if node else None,
                cameras_total=camera_total,
                cameras_online=camera_online,
                active_alerts=alert_counts.get(station.id, 0),
                data_quality_warnings=warnings,
                health=health.model_values(),
            )
        )
    return output
