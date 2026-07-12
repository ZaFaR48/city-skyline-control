from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
import logging
from typing import Awaitable, Callable

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import SessionLocal
from ..models import AuditLog, AuditSource, HeadscaleNode, Station, StationStatus, StationStatusEvent
from .telegram import send_telegram
from .station_visibility import production_station_filter


SUMMARY_ACTION = "telegram.operations_summary"
RELEVANT_ACTIONS = {
    "station.create": "new",
    "station.update": "updated",
    "station.data_repair": "updated",
    "station.district_assign": "updated",
    "station.production_approve": "published",
    "station.production_revoke": "updated",
    "station.archive": "lifecycle",
    "station.restore": "lifecycle",
    "headscale.link": "headscale",
    "headscale.unlink": "headscale",
    "headscale.reclassify": "headscale",
    "station.vpn_sync_headscale": "headscale",
}
SECTION_TITLES = {
    "new": "➕ Newly created stations",
    "updated": "✏️ Updated stations",
    "published": "✅ Published / approved stations",
    "lifecycle": "🗄 Archived / restored stations",
    "headscale": "🌐 Headscale operations",
}
SUMMARY_SAFE_DIFF_FIELDS = {
    "station_code", "name", "city_id", "district_id", "operational_area", "address",
    "latitude", "longitude", "vpn_ip", "local_ip", "is_active", "is_archived",
    "approval_status", "device_type", "station_id",
}


async def deliver_operations_summary(
    db: AsyncSession,
    sender: Callable[[str], Awaitable[bool]] = send_telegram,
    *,
    now: datetime | None = None,
) -> int:
    events = await _pending_events(db, now=now)
    status_events = await _pending_status_events(db, now=now)
    if not events and not status_events:
        return 0
    messages = await format_operations_summary(db, events, status_events)
    for message in messages:
        if not await sender(message):
            logging.getLogger(__name__).warning(
                "telegram_operations_summary_delivery_failed audit_events=%s status_events=%s",
                len(events),
                len(status_events),
            )
            await db.rollback()
            return 0
    cursor = await _summary_cursor(db)
    max_id = max((event.id for event in events), default=int((cursor.after_data or {}).get("max_audit_id", 0)) if cursor else 0)
    max_status_event_id = max((event.id for event in status_events), default=int((cursor.after_data or {}).get("max_status_event_id", 0)) if cursor else 0)
    db.add(
        AuditLog(
            action=SUMMARY_ACTION,
            entity_type="telegram_batch",
            entity_id=str(max_id),
            after_data={"max_audit_id": max_id, "max_status_event_id": max_status_event_id, "event_count": len(events), "status_event_count": len(status_events)},
            source=AuditSource.system.value,
        )
    )
    await db.commit()
    logging.getLogger(__name__).info(
        "telegram_operations_summary_delivered audit_events=%s status_events=%s",
        len(events),
        len(status_events),
    )
    return len(events) + len(status_events)


async def run_operations_summary_job() -> int:
    async with SessionLocal() as db:
        locked = bool(await db.scalar(text("select pg_try_advisory_xact_lock(73421010)")))
        if not locked:
            return 0
        return await deliver_operations_summary(db)


async def _pending_events(db: AsyncSession, *, now: datetime | None = None) -> list[AuditLog]:
    cursor_row = await _summary_cursor(db)
    stmt = select(AuditLog).where(AuditLog.action.in_(RELEVANT_ACTIONS)).order_by(AuditLog.id)
    if cursor_row and cursor_row.after_data and cursor_row.after_data.get("max_audit_id"):
        stmt = stmt.where(AuditLog.id > int(cursor_row.after_data["max_audit_id"]))
    else:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=10)
        stmt = stmt.where(AuditLog.timestamp >= cutoff)
    return list((await db.execute(stmt)).scalars().all())


async def _pending_status_events(db: AsyncSession, *, now: datetime | None = None) -> list[StationStatusEvent]:
    cursor = await _summary_cursor(db)
    stmt = (
        select(StationStatusEvent)
        .join(Station, Station.id == StationStatusEvent.station_id)
        .where(production_station_filter())
        .order_by(StationStatusEvent.id)
    )
    cursor_id = int((cursor.after_data or {}).get("max_status_event_id", 0)) if cursor else 0
    if cursor_id:
        stmt = stmt.where(StationStatusEvent.id > cursor_id)
    else:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=10)
        stmt = stmt.where(StationStatusEvent.started_at >= cutoff)
    return list((await db.execute(stmt)).scalars().all())


async def _summary_cursor(db: AsyncSession) -> AuditLog | None:
    return (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.action == SUMMARY_ACTION)
            .order_by(AuditLog.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def format_operations_summary(
    db: AsyncSession,
    events: list[AuditLog],
    status_events: list[StationStatusEvent] | None = None,
) -> list[str]:
    status_events = status_events or []
    station_ids: set[int] = set()
    node_ids: set[int] = set()
    for event in events:
        if event.entity_type == "station" and event.entity_id and event.entity_id.isdigit():
            station_ids.add(int(event.entity_id))
        elif event.entity_type == "headscale_node" and event.entity_id and event.entity_id.isdigit():
            node_ids.add(int(event.entity_id))
    station_ids.update(event.station_id for event in status_events)
    nodes = list((await db.execute(select(HeadscaleNode).where(HeadscaleNode.id.in_(node_ids)))).scalars().all()) if node_ids else []
    node_by_id = {node.id: node for node in nodes}
    station_ids.update(node.station_id for node in nodes if node.station_id)
    stations = list(
        (
            await db.execute(
                select(Station)
                .where(Station.id.in_(station_ids))
                .options(selectinload(Station.city), selectinload(Station.district))
            )
        ).scalars().all()
    ) if station_ids else []
    station_by_id = {station.id: station for station in stations}
    linked_nodes = list((await db.execute(select(HeadscaleNode).where(HeadscaleNode.station_id.in_(station_ids)))).scalars().all()) if station_ids else []
    node_by_station = {node.station_id: node for node in linked_nodes}

    operation_lines: list[str] = []
    for event in events:
        station = None
        node = None
        if event.entity_type == "station" and event.entity_id and event.entity_id.isdigit():
            station = station_by_id.get(int(event.entity_id))
            node = node_by_station.get(station.id) if station else None
        elif event.entity_type == "headscale_node" and event.entity_id and event.entity_id.isdigit():
            node = node_by_id.get(int(event.entity_id))
            station = station_by_id.get(node.station_id) if node and node.station_id else None
        operation_lines.append(_event_text(event, station, node))

    status_groups: dict[str, list[str]] = defaultdict(list)
    for event in status_events:
        station = station_by_id.get(event.station_id)
        if not station or station.approved_at is None or not station.is_active or station.is_archived:
            continue
        if event.new_status == StationStatus.online.value:
            category = "recovered"
        elif event.new_status == StationStatus.degraded.value:
            category = "degraded"
        elif event.new_status == StationStatus.offline.value:
            category = "offline"
        else:
            category = "unknown"
        local_time = event.started_at.astimezone(timezone(timedelta(hours=5))).strftime("%H:%M")
        status_groups[category].append(
            f"{escape(station.station_code)} — {_status_reason_tj(event.reason)} · {local_time}"
        )

    lines = ["<b>📊 Тағйирот дар 10 дақиқа</b>"]
    for category, title in (
        ("recovered", "🟢 Барқарор шуд"),
        ("degraded", "⚠️ Мушкил пайдо шуд"),
        ("offline", "🔴 Хомӯш шуд"),
        ("unknown", "⚪ Ҳолат номаълум шуд"),
    ):
        if status_groups.get(category):
            lines.extend(["", f"<b>{title}:</b>", *status_groups[category]])
    if operation_lines:
        lines.extend(["", "<b>📝 Амалиёти стансия:</b>", *operation_lines])
    return _chunk_lines(lines)


def _event_text(event: AuditLog, station: Station | None, node: HeadscaleNode | None) -> str:
    diff = _diff_text(event.before_data or {}, event.after_data or {})
    if station:
        actor = ""
        if event.action == "station.create" and event.source == AuditSource.telegram.value:
            values = event.after_data or {}
            display_name = escape(str(values.get("operator_display_name") or values.get("operator_username") or "—"))
            username = escape(str(values.get("operator_username") or "—"))
            telegram_username = values.get("telegram_username")
            telegram_id = escape(str(values.get("telegram_user_id") or "—"))
            telegram_label = f"@{escape(str(telegram_username))}" if telegram_username else "—"
            actor = f" · илова кард: {display_name} / {username} / {telegram_label} / Telegram ID {telegram_id}"
        return f"• <b>{escape(station.station_code)}</b> — {escape(event.action)}{diff}{actor}"
    node_label = f"#{node.id} {node.hostname}" if node else f"node {event.entity_id or '—'}"
    return f"• {escape(node_label)} · {escape(event.action)}{diff}"


def _status_reason_tj(reason: str | None) -> str:
    value = reason or ""
    if value.startswith("HEALTHY") or "healthy" in value.casefold():
        return "алоқа барқарор шуд"
    if value.startswith("PING_TIMEOUT") or value in {"unreachable", "ping_error"}:
        return "бо стансия алоқа нест"
    if value.startswith("PING_HIGH_LATENCY") or "latency exceeds" in value.casefold():
        return "таъхири алоқа баланд аст"
    if value.startswith("HEADSCALE_OFFLINE"):
        return "Headscale хомӯш аст"
    if value.startswith("CAMERA_OFFLINE"):
        return "стансия онлайн, камера хомӯш"
    if value.startswith("MONITORING_NOT_CONFIGURED") or "not configured" in value.casefold():
        return "мониторинг танзим нашудааст"
    return "сабаби дақиқ муайян нашуд"


def _diff_text(before: dict, after: dict) -> str:
    changes = []
    for key in sorted((set(before) | set(after)) & SUMMARY_SAFE_DIFF_FIELDS):
        old, new = before.get(key), after.get(key)
        if old != new:
            changes.append(f"{key}: {old or '—'} → {new or '—'}")
    return f" ({'; '.join(changes[:6])})" if changes else ""


def _chunk_lines(lines: list[str], limit: int = 3900) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if current and len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
