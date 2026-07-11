"""Headscale auto-discovery.

Polls the Headscale API and inserts any unknown nodes into headscale_nodes
so they appear automatically in the dashboard.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from ..config import settings
from ..database import SessionLocal
from ..models import HeadscaleNode, Station


async def sync_headscale_nodes() -> int:
    if not settings.HEADSCALE_URL or not settings.HEADSCALE_API_KEY:
        return 0
    headers = {"Authorization": f"Bearer {settings.HEADSCALE_API_KEY}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{settings.HEADSCALE_URL}/api/v1/node", headers=headers)
        if r.status_code != 200:
            return 0
        nodes = r.json().get("nodes", [])

    added = 0
    async with SessionLocal() as db:
        for n in nodes:
            key = n.get("nodeKey") or n.get("node_key") or n.get("id")
            existing = (await db.execute(
                select(HeadscaleNode).where(HeadscaleNode.node_key == str(key))
            )).scalar_one_or_none()

            ip_list = n.get("ipAddresses") or n.get("ip_addresses") or []
            vpn_ip = ip_list[0] if ip_list else ""
            online = bool(n.get("online", False))
            last_seen = n.get("lastSeen") or n.get("last_seen")
            ls = datetime.fromisoformat(last_seen.replace("Z", "+00:00")) if last_seen else None

            # Match station by VPN IP
            station = None
            if vpn_ip:
                station = (await db.execute(
                    select(Station).where(Station.vpn_ip == vpn_ip)
                )).scalars().first()

            if existing:
                existing.online = online
                existing.last_seen = ls or existing.last_seen
                existing.vpn_ip = vpn_ip or existing.vpn_ip
                if station and existing.station_id != station.id:
                    existing.station_id = station.id
            else:
                db.add(HeadscaleNode(
                    node_key=str(key),
                    hostname=n.get("name") or n.get("givenName") or "unknown",
                    vpn_ip=vpn_ip, online=online,
                    last_seen=ls or datetime.now(timezone.utc),
                    station_id=station.id if station else None,
                ))
                added += 1
        await db.commit()
    return added
