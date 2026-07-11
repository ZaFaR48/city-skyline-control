"""Persistent connectivity monitoring for active stations."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from icmplib import async_ping
from sqlalchemy import select

from ..config import settings
from ..database import SessionLocal
from ..models import PingHistory, Station, StationStatus
from .n8n import forward_event
from .station_status import StationStatusResolver
from .telegram import send_telegram


async def _ping_one(station: Station) -> tuple[float | None, float | None, bool, str | None]:
    if not station.vpn_ip:
        return None, None, False, "not_configured"
    try:
        host = await async_ping(
            station.vpn_ip,
            count=3,
            timeout=settings.PING_TIMEOUT_SEC,
            privileged=True,
        )
        if not host.is_alive:
            return None, host.packet_loss * 100, False, "unreachable"
        return host.avg_rtt, host.packet_loss * 100, True, None
    except PermissionError:
        return None, None, False, "ping_permission_denied"
    except Exception:
        return None, None, False, "ping_error"


async def ping_station(station_id: int) -> None:
    async with SessionLocal() as db:
        station = await db.get(Station, station_id)
        if not station or not station.is_active or station.is_archived:
            return
        latency, loss, success, error_type = await _ping_one(station)
        now = datetime.now(timezone.utc)
        db.add(
            PingHistory(
                station_id=station.id,
                latency_ms=latency,
                packet_loss=loss,
                success=success,
                error_type=error_type,
                checked_at=now,
            )
        )
        resolution = await StationStatusResolver.resolve_ping(
            db,
            station,
            success=success,
            latency_ms=latency,
            checked_at=now,
            error_type=error_type,
        )
        await db.commit()
        if resolution.transitioned and resolution.new_status == StationStatus.offline.value:
            await _notify_offline(station, resolution.reason, now)


async def ping_all_stations() -> None:
    async with SessionLocal() as db:
        ids = (
            await db.execute(
                select(Station.id).where(Station.is_active.is_(True), Station.is_archived.is_(False))
            )
        ).scalars().all()
    await asyncio.gather(*(ping_station(station_id) for station_id in ids))


async def _notify_offline(station: Station, reason: str, occurred_at: datetime) -> None:
    await send_telegram(
        f"🚨 Station Offline\nStation: {station.station_code} — {station.name}\n"
        f"VPN: {station.vpn_ip or '—'}\nTime: {occurred_at.astimezone().isoformat(timespec='seconds')}"
    )
    await forward_event(
        "station.offline",
        {
            "station_code": station.station_code,
            "name": station.name,
            "vpn_ip": station.vpn_ip,
            "reason": reason,
        },
    )
