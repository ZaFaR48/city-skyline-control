from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from ..schemas import StationOut


async def serialize_stations(db: AsyncSession, stations: list[Station]) -> list[StationOut]:
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
                latitude=station.latitude,
                longitude=station.longitude,
                vpn_ip=station.vpn_ip,
                local_ip=station.local_ip,
                rustdesk_id=station.rustdesk_id,
                status=station.status,
                status_reason=station.status_reason,
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
                monitoring_configured=bool(station.vpn_ip and monitoring_node),
                headscale_linked=monitoring_node is not None,
                headscale_hostname=node.hostname if node else None,
                headscale_approval_status=node.approval_status if node else None,
                cameras_total=camera_total,
                cameras_online=camera_online,
                active_alerts=alert_counts.get(station.id, 0),
            )
        )
    return output
