"""Headscale inventory synchronization without automatic station creation/linking."""

from __future__ import annotations

from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import SessionLocal
from ..models import ApprovalStatus, DeviceType, HeadscaleNode, Station
from .audit import add_audit


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def sync_headscale_nodes() -> int:
    if not settings.HEADSCALE_URL or not settings.HEADSCALE_API_KEY:
        return 0
    headers = {"Authorization": f"Bearer {settings.HEADSCALE_API_KEY}"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{settings.HEADSCALE_URL}/api/v1/node", headers=headers)
        response.raise_for_status()
        nodes = response.json().get("nodes", [])

    added = 0
    async with SessionLocal() as db:
        for raw in nodes:
            stable_id = raw.get("nodeKey") or raw.get("node_key") or raw.get("id")
            if stable_id is None:
                continue
            key = str(stable_id)
            node = (
                await db.execute(select(HeadscaleNode).where(HeadscaleNode.node_key == key))
            ).scalar_one_or_none()
            addresses = raw.get("ipAddresses") or raw.get("ip_addresses") or []
            vpn_ip = addresses[0] if addresses else None
            hostname = raw.get("name") or raw.get("hostname") or raw.get("givenName") or "unknown"
            given_name = raw.get("givenName") or raw.get("given_name")
            last_seen = _parse_datetime(raw.get("lastSeen") or raw.get("last_seen"))
            operating_system = raw.get("os") or raw.get("operatingSystem")
            tags = raw.get("forcedTags") or raw.get("tags") or None

            if node is None:
                node = HeadscaleNode(
                    node_key=key,
                    hostname=hostname,
                    given_name=given_name,
                    vpn_ip=vpn_ip,
                    online=bool(raw.get("online", False)),
                    last_seen_at=last_seen,
                    operating_system=operating_system,
                    tags=tags,
                    device_type=DeviceType.unknown.value,
                    approval_status=ApprovalStatus.pending.value,
                )
                db.add(node)
                added += 1
            else:
                previous_node_vpn = node.vpn_ip
                node.hostname = hostname
                node.given_name = given_name
                node.vpn_ip = vpn_ip
                node.online = bool(raw.get("online", False))
                node.last_seen_at = last_seen or node.last_seen_at
                node.operating_system = operating_system or node.operating_system
                node.tags = tags

            if (
                node.station_id
                and node.approval_status == ApprovalStatus.approved.value
                and node.device_type == DeviceType.station.value
                and vpn_ip
            ):
                station = await db.get(Station, node.station_id)
                if station:
                    await sync_linked_station_vpn(
                        db, station, node, vpn_ip, last_seen=last_seen,
                        authoritative_ip_changed=previous_node_vpn != vpn_ip,
                    )
        await db.commit()
    return added


async def sync_linked_station_vpn(
    db: AsyncSession, station: Station, node: HeadscaleNode, vpn_ip: str,
    *, last_seen: datetime | None, authoritative_ip_changed: bool,
) -> bool:
    conflict = await db.scalar(
        select(Station.id).where(
            Station.id != station.id, Station.is_active.is_(True), Station.is_archived.is_(False),
            Station.vpn_ip == vpn_ip,
        ).limit(1)
    )
    node_conflict = await db.scalar(
        select(HeadscaleNode.id).join(Station, Station.id == HeadscaleNode.station_id).where(
            HeadscaleNode.id != node.id, HeadscaleNode.vpn_ip == vpn_ip,
            HeadscaleNode.device_type == DeviceType.station.value,
            HeadscaleNode.approval_status == ApprovalStatus.approved.value,
            Station.id != station.id, Station.is_active.is_(True), Station.is_archived.is_(False),
        ).limit(1)
    )
    changed = False
    if not conflict and not node_conflict and station.vpn_ip != vpn_ip:
        previous = station.vpn_ip
        station.vpn_ip = vpn_ip
        add_audit(
            db, action="station.vpn_sync_headscale", entity_type="station", entity_id=station.id,
            actor=None, before={"vpn_ip": previous, "headscale_node_id": node.id},
            after={"vpn_ip": vpn_ip, "headscale_node_id": node.id}, source="system",
        )
        changed = True
    elif (conflict or node_conflict) and authoritative_ip_changed:
        add_audit(
            db, action="station.vpn_sync_headscale_conflict", entity_type="station",
            entity_id=station.id, actor=None,
            before={"vpn_ip": station.vpn_ip, "headscale_node_id": node.id},
            after={"authoritative_vpn_ip": vpn_ip, "conflicting_station_id": conflict,
                   "conflicting_node_id": node_conflict}, source="system",
        )
    station.last_seen_at = last_seen or station.last_seen_at
    return changed
