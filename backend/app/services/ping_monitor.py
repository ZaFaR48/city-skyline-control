"""Async ping monitor.

Every PING_INTERVAL_SEC the scheduler invokes ping_all_stations(), which
pings each station's VPN IP, persists a ping_history row, updates the
station's status/latency and raises Telegram + n8n alerts after
PING_FAIL_THRESHOLD consecutive failures.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from icmplib import async_ping
from sqlalchemy import select

from ..config import settings
from ..database import SessionLocal
from ..models import Alert, AlertSeverity, AlertType, PingHistory, Station, StationStatus
from .n8n import forward_event
from .telegram import send_telegram

_consecutive_failures: dict[int, int] = {}


async def _ping_one(station: Station) -> tuple[float, float, bool]:
    try:
        host = await async_ping(station.vpn_ip, count=3, timeout=settings.PING_TIMEOUT_SEC,
                                privileged=True)
        return host.avg_rtt, host.packet_loss * 100, host.is_alive
    except Exception:
        return 0.0, 100.0, False


def _status_from(latency: float, success: bool) -> StationStatus:
    if not success: return StationStatus.offline
    if latency > 150: return StationStatus.warning
    return StationStatus.online


async def ping_all_stations() -> None:
    async with SessionLocal() as db:
        stations = (await db.execute(select(Station))).scalars().all()
        results = await asyncio.gather(*(_ping_one(s) for s in stations))

        for s, (latency, loss, success) in zip(stations, results):
            db.add(PingHistory(station_id=s.id, latency_ms=latency,
                               packet_loss=loss, success=success))
            new_status = _status_from(latency, success)
            s.last_ping_ms = int(latency)
            s.status = new_status
            if success: s.last_seen = datetime.now(timezone.utc)

            if not success:
                _consecutive_failures[s.id] = _consecutive_failures.get(s.id, 0) + 1
                if _consecutive_failures[s.id] == settings.PING_FAIL_THRESHOLD:
                    db.add(Alert(
                        station_id=s.id, type=AlertType.offline_station,
                        severity=AlertSeverity.critical,
                        message=f"Station {s.name} unreachable at {s.vpn_ip}",
                    ))
                    await send_telegram(
                        f"🚨 Station Offline\nStation: {s.name}\nVPN: {s.vpn_ip}\n"
                        f"Region: {s.region}\nTime: {datetime.utcnow():%H:%M:%S}"
                    )
                    await forward_event("station.offline", {
                        "id": s.code, "name": s.name, "region": s.region, "vpn_ip": s.vpn_ip,
                    })
            else:
                _consecutive_failures.pop(s.id, None)

        await db.commit()
