from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
import logging
from typing import Awaitable, Callable

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..database import SessionLocal
from ..models import (
    AuditLog,
    AuditSource,
    HeadscaleNode,
    Role,
    Station,
    StationStatus,
    StationStatusEvent,
    TelegramIdentity,
    TelegramSummarySetting,
    User,
)
from .telegram import send_telegram_to
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


@dataclass(frozen=True)
class ReducedStatus:
    station_id: int
    station_code: str
    category: str
    reason_code: str
    transition_count: int
    current_duration_seconds: int | None
    longest_problem_seconds: int
    occurred_at: datetime
    start_status: str
    end_status: str


@dataclass(frozen=True)
class ReductionResult:
    stations: list[ReducedStatus]
    raw_transition_count: int
    suppressed_transient_count: int


async def deliver_operations_summary(
    db: AsyncSession,
    sender: Callable[[str], Awaitable[bool]] | None = None,
    *,
    now: datetime | None = None,
) -> int:
    current = now or datetime.now(timezone.utc)
    recipients: list[tuple[TelegramIdentity, User]] = []
    setting = await db.get(TelegramSummarySetting, 1)
    if sender is None:
        if not setting or not setting.enabled:
            return 0
        recipients = list((await db.execute(
            select(TelegramIdentity, User)
            .join(User, User.id == TelegramIdentity.user_id)
            .where(
                TelegramIdentity.automatic_summary_recipient.is_(True),
                User.is_active.is_(True),
                User.role.in_((Role.admin.value, Role.operator.value)),
            )
        )).all())
        if not recipients:
            return 0
    events = await _pending_events(db, now=now)
    status_events = await _pending_status_events(db, now=now)
    if not events and not status_events:
        return 0
    reduction = await reduce_status_events(db, status_events, now=current)
    languages = ["tj"] if sender is not None else sorted({identity.preferred_language for identity, _ in recipients})
    messages_by_language = {
        language: await format_operations_summary(db, events, status_events, language=language, reduction=reduction)
        for language in languages
    }
    meaningful = any(messages_by_language.values())
    if sender is not None:
        delivery_targets = [(None, "tj", sender)]
    else:
        delivery_targets = [
            (
                identity.telegram_user_id,
                identity.preferred_language,
                lambda message, chat_id=identity.telegram_user_id: send_telegram_to(chat_id, message),
            )
            for identity, _ in recipients
        ]
    for chat_id, language, target_sender in delivery_targets:
        for message in messages_by_language[language]:
            try:
                delivered = await target_sender(message)
            except Exception:
                logging.getLogger(__name__).exception(
                    "telegram_operations_summary_delivery_failed chat_id=%s language=%s audit_events=%s status_events=%s",
                    chat_id,
                    language,
                    len(events),
                    len(status_events),
                )
                await db.rollback()
                return 0
            if delivered:
                continue
            logging.getLogger(__name__).warning(
                "telegram_operations_summary_delivery_failed chat_id=%s language=%s audit_events=%s status_events=%s",
                chat_id,
                language,
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
            after_data={
                "max_audit_id": max_id,
                "max_status_event_id": max_status_event_id,
                "event_count": len(events),
                "status_event_count": len(status_events),
                "raw_transition_count": reduction.raw_transition_count,
                "reduced_station_count": len(reduction.stations),
                "suppressed_transient_count": reduction.suppressed_transient_count,
                "recipient_count": len(delivery_targets) if meaningful else 0,
                "cursor_before": int((cursor.after_data or {}).get("max_status_event_id", 0)) if cursor else 0,
                "cursor_after": max_status_event_id,
            },
            source=AuditSource.system.value,
        )
    )
    await db.commit()
    logging.getLogger(__name__).info(
        "telegram_operations_summary_delivered audit_events=%s raw_transitions=%s reduced_stations=%s suppressed=%s recipients=%s meaningful=%s cursor_after=%s",
        len(events),
        reduction.raw_transition_count,
        len(reduction.stations),
        reduction.suppressed_transient_count,
        len(delivery_targets) if meaningful else 0,
        meaningful,
        max_status_event_id,
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


async def snapshot_summary_cursor(db: AsyncSession, *, reason: str) -> None:
    max_audit_id = int(await db.scalar(
        select(func.max(AuditLog.id)).where(AuditLog.action.in_(RELEVANT_ACTIONS))
    ) or 0)
    max_status_event_id = int(await db.scalar(
        select(func.max(StationStatusEvent.id))
        .join(Station, Station.id == StationStatusEvent.station_id)
        .where(production_station_filter())
    ) or 0)
    db.add(AuditLog(
        action=SUMMARY_ACTION,
        entity_type="telegram_batch",
        entity_id=str(max_audit_id),
        after_data={
            "max_audit_id": max_audit_id,
            "max_status_event_id": max_status_event_id,
            "event_count": 0,
            "status_event_count": 0,
            "recipient_count": 0,
            "cursor_snapshot_reason": reason,
        },
        source=AuditSource.system.value,
    ))


async def reduce_status_events(
    db: AsyncSession,
    events: list[StationStatusEvent],
    *,
    now: datetime,
) -> ReductionResult:
    grouped: dict[int, list[StationStatusEvent]] = defaultdict(list)
    for event in sorted(events, key=lambda item: (item.station_id, item.started_at, item.id)):
        grouped[event.station_id].append(event)
    stations = {
        station.id: station
        for station in (
            await db.execute(select(Station).where(Station.id.in_(list(grouped))))
        ).scalars().all()
    } if grouped else {}
    reduced: list[ReducedStatus] = []
    suppressed = 0
    for station_id, station_events in grouped.items():
        station = stations.get(station_id)
        if not station:
            continue
        final = station_events[-1]
        problem_events = [event for event in station_events if event.new_status != StationStatus.online.value]
        prior_problem = None
        if final.new_status == StationStatus.online.value and not problem_events:
            prior_problem = (
                await db.execute(
                    select(StationStatusEvent)
                    .where(
                        StationStatusEvent.station_id == station_id,
                        StationStatusEvent.id < final.id,
                        StationStatusEvent.new_status != StationStatus.online.value,
                    )
                    .order_by(StationStatusEvent.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        durations = [
            max(0, int(((event.ended_at or now) - event.started_at).total_seconds()))
            for event in problem_events
        ]
        if prior_problem:
            durations.append(max(0, int(((prior_problem.ended_at or final.started_at) - prior_problem.started_at).total_seconds())))
        longest = max(durations, default=0)
        transition_count = len(station_events)
        is_latency_flapping = (
            transition_count >= settings.SUMMARY_FLAPPING_THRESHOLD
            and all(event.new_status in {StationStatus.online.value, StationStatus.degraded.value} for event in station_events)
            and any((event.reason or "").startswith("PING_HIGH_LATENCY") for event in station_events)
        )
        if is_latency_flapping:
            category = "ongoing"
            reason_code = "UNSTABLE_LATENCY"
            duration = max(0, int((now - final.started_at).total_seconds())) if final.new_status != StationStatus.online.value else None
            logging.getLogger(__name__).warning(
                "telegram_summary_flapping_detected station_id=%s station_code=%s transitions=%s start=%s end=%s",
                station.id,
                station.station_code,
                transition_count,
                station_events[0].previous_status,
                final.new_status,
            )
        elif final.new_status == StationStatus.offline.value:
            category, reason_code = "offline", _reason_code(final.reason)
            duration = max(0, int((now - final.started_at).total_seconds()))
        elif final.new_status in {StationStatus.degraded.value, StationStatus.unknown.value}:
            category, reason_code = "ongoing", _reason_code(final.reason)
            duration = max(0, int((now - final.started_at).total_seconds()))
        elif longest >= settings.SUMMARY_TRANSIENT_MIN_SECONDS:
            category, reason_code, duration = "recovered", "HEALTHY", longest
        else:
            suppressed += 1
            logging.getLogger(__name__).info(
                "telegram_summary_transient_suppressed station_id=%s station_code=%s transitions=%s longest_problem_seconds=%s",
                station.id,
                station.station_code,
                transition_count,
                longest,
            )
            continue
        reduced.append(
            ReducedStatus(
                station_id=station.id,
                station_code=station.station_code,
                category=category,
                reason_code=reason_code,
                transition_count=transition_count,
                current_duration_seconds=duration,
                longest_problem_seconds=longest,
                occurred_at=final.started_at,
                start_status=station_events[0].previous_status,
                end_status=final.new_status,
            )
        )
        logging.getLogger(__name__).info(
            "telegram_summary_station_reduced station_id=%s station_code=%s raw_transitions=%s category=%s start=%s end=%s longest_problem_seconds=%s",
            station.id,
            station.station_code,
            transition_count,
            category,
            station_events[0].previous_status,
            final.new_status,
            longest,
        )
    reduced.sort(key=lambda item: (0, int(item.station_code)) if item.station_code.isdigit() else (1, item.station_code.casefold()))
    return ReductionResult(
        stations=reduced,
        raw_transition_count=len(events),
        suppressed_transient_count=suppressed,
    )


async def format_operations_summary(
    db: AsyncSession,
    events: list[AuditLog],
    status_events: list[StationStatusEvent] | None = None,
    *,
    language: str = "tj",
    reduction: ReductionResult | None = None,
) -> list[str]:
    status_events = status_events or []
    reduction = reduction or await reduce_status_events(db, status_events, now=datetime.now(timezone.utc))
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

    latest_operations: dict[str, tuple[AuditLog, Station | None, HeadscaleNode | None]] = {}
    reduced_station_ids = {item.station_id for item in reduction.stations}
    for event in events:
        station = None
        node = None
        if event.entity_type == "station" and event.entity_id and event.entity_id.isdigit():
            station = station_by_id.get(int(event.entity_id))
            node = node_by_station.get(station.id) if station else None
        elif event.entity_type == "headscale_node" and event.entity_id and event.entity_id.isdigit():
            node = node_by_id.get(int(event.entity_id))
            station = station_by_id.get(node.station_id) if node and node.station_id else None
        if station and station.id in reduced_station_ids:
            continue
        key = f"station:{station.id}" if station else f"node:{node.id if node else event.entity_id}"
        latest_operations[key] = (event, station, node)

    status_groups: dict[str, list[str]] = defaultdict(list)
    for item in reduction.stations:
        status_groups[item.category].append(_reduced_line(item, language))
    operation_lines = [
        _event_text(event, station, node, language)
        for event, station, node in sorted(latest_operations.values(), key=lambda value: value[0].id)
    ]
    if not status_groups and not operation_lines:
        return []
    title = f"<b>{_summary_text(language, 'title')}</b>"
    sections: list[list[str]] = []
    for category in ("offline", "ongoing", "recovered"):
        if status_groups.get(category):
            sections.append([f"<b>{_summary_text(language, category)}:</b>", *status_groups[category]])
    if operation_lines:
        sections.append([f"<b>{_summary_text(language, 'operations')}:</b>", *operation_lines])
    return _chunk_sections(title, sections)


def _event_text(event: AuditLog, station: Station | None, node: HeadscaleNode | None, language: str) -> str:
    diff = _diff_text(event.before_data or {}, event.after_data or {}, language)
    if station:
        actor = ""
        if event.action == "station.create" and event.source == AuditSource.telegram.value:
            values = event.after_data or {}
            display_name = escape(str(values.get("operator_display_name") or values.get("operator_username") or "—"))
            username = escape(str(values.get("operator_username") or "—"))
            telegram_username = values.get("telegram_username")
            telegram_id = escape(str(values.get("telegram_user_id") or "—"))
            telegram_label = f"@{escape(str(telegram_username))}" if telegram_username else "—"
            actor = f" · {_summary_text(language, 'added_by')}: {display_name} / {username} / {telegram_label} / Telegram ID {telegram_id}"
        return f"• <b>{escape(station.station_code)}</b> — {_operation_label(event.action, language)}{diff}{actor}"
    node_label = f"#{node.id} {node.hostname}" if node else f"node {event.entity_id or '—'}"
    return f"• {escape(node_label)} · {_operation_label(event.action, language)}{diff}"


def _reason_code(reason: str | None) -> str:
    value = reason or ""
    for code in (
        "HEALTHY", "PING_TIMEOUT", "PING_HIGH_LATENCY", "HEADSCALE_OFFLINE",
        "CAMERA_OFFLINE", "MONITORING_NOT_CONFIGURED", "INSUFFICIENT_FRESH_DATA",
    ):
        if value.startswith(code):
            return code
    if value in {"unreachable", "ping_error"}:
        return "PING_TIMEOUT"
    return "EXACT_CAUSE_UNKNOWN"


def _reduced_line(item: ReducedStatus, language: str) -> str:
    if item.reason_code == "UNSTABLE_LATENCY":
        return f"{escape(item.station_code)} — {_reason_label(item.reason_code, language)} · {_changes(item.transition_count, language)}"
    if item.category == "recovered":
        local_time = item.occurred_at.astimezone(timezone(timedelta(hours=5))).strftime("%H:%M")
        return f"{escape(item.station_code)} — {_recovered(item.current_duration_seconds or 0, language)} · {local_time}"
    duration = _duration(item.current_duration_seconds, language)
    return f"{escape(item.station_code)} — {_reason_label(item.reason_code, language)}" + (f" · {duration}" if duration else "")


def _summary_text(language: str, key: str) -> str:
    values = {
        "tj": {"title": "📊 Тағйирот дар 10 дақиқа", "offline": "🔴 Хомӯш шуд", "ongoing": "⚠️ Мушкил идома дорад", "recovered": "🟢 Барқарор шуд", "operations": "📝 Амалиёти стансия", "added_by": "илова кард"},
        "ru": {"title": "📊 Изменения за 10 минут", "offline": "🔴 Отключились", "ongoing": "⚠️ Проблема продолжается", "recovered": "🟢 Восстановились", "operations": "📝 Операции со станциями", "added_by": "добавил"},
        "en": {"title": "📊 Changes in the last 10 minutes", "offline": "🔴 Went offline", "ongoing": "⚠️ Ongoing problems", "recovered": "🟢 Recovered", "operations": "📝 Station operations", "added_by": "added by"},
    }
    return values.get(language, values["tj"])[key]


def _reason_label(code: str, language: str) -> str:
    values = {
        "tj": {"PING_TIMEOUT": "бо стансия алоқа нест", "PING_HIGH_LATENCY": "таъхири алоқа баланд аст", "UNSTABLE_LATENCY": "таъхири алоқа ноустувор", "HEADSCALE_OFFLINE": "Headscale хомӯш аст", "CAMERA_OFFLINE": "стансия онлайн, камера хомӯш", "MONITORING_NOT_CONFIGURED": "мониторинг танзим нашудааст", "INSUFFICIENT_FRESH_DATA": "маълумоти нави ченшуда нест", "EXACT_CAUSE_UNKNOWN": "сабаби дақиқ муайян нашуд"},
        "ru": {"PING_TIMEOUT": "станция недоступна", "PING_HIGH_LATENCY": "высокая задержка", "UNSTABLE_LATENCY": "нестабильная задержка", "HEADSCALE_OFFLINE": "Headscale офлайн", "CAMERA_OFFLINE": "станция онлайн, камера офлайн", "MONITORING_NOT_CONFIGURED": "мониторинг не настроен", "INSUFFICIENT_FRESH_DATA": "нет свежих измеренных данных", "EXACT_CAUSE_UNKNOWN": "причина точно не определена"},
        "en": {"PING_TIMEOUT": "station unreachable", "PING_HIGH_LATENCY": "high network latency", "UNSTABLE_LATENCY": "unstable network latency", "HEADSCALE_OFFLINE": "Headscale offline", "CAMERA_OFFLINE": "station online, camera offline", "MONITORING_NOT_CONFIGURED": "monitoring not configured", "INSUFFICIENT_FRESH_DATA": "insufficient fresh measured data", "EXACT_CAUSE_UNKNOWN": "exact cause is not determined"},
    }
    return values.get(language, values["tj"]).get(code, values.get(language, values["tj"])["EXACT_CAUSE_UNKNOWN"])


def _duration(seconds: int | None, language: str) -> str:
    if seconds is None:
        return ""
    minutes = max(0, seconds) // 60
    hours, minutes = divmod(minutes, 60)
    if language == "ru":
        return f"{hours} ч {minutes} мин" if hours else f"{minutes} мин"
    if language == "en":
        return f"{hours} h {minutes} min" if hours else f"{minutes} min"
    return f"{hours} соат {minutes} дақ" if hours else f"{minutes} дақ"


def _changes(count: int, language: str) -> str:
    if language == "ru":
        ending = "изменения" if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14} else "изменений"
        return f"{count} {ending} за 10 мин"
    if language == "en":
        return f"{count} {'change' if count == 1 else 'changes'} in 10 min"
    return f"{count} тағйирот дар 10 дақ"


def _recovered(seconds: int, language: str) -> str:
    duration = _duration(seconds, language)
    return {
        "tj": f"баъди {duration} барқарор шуд",
        "ru": f"восстановлена после {duration}",
        "en": f"recovered after {duration}",
    }.get(language, f"баъди {duration} барқарор шуд")


def _operation_label(action: str, language: str) -> str:
    category = RELEVANT_ACTIONS.get(action, "updated")
    values = {
        "tj": {"new": "стансия сабт шуд", "updated": "маълумот нав шуд", "published": "ба production иҷозат гирифт", "lifecycle": "ҳолати сабт тағйир ёфт", "headscale": "амалиёти Headscale"},
        "ru": {"new": "станция зарегистрирована", "updated": "данные обновлены", "published": "допущена в production", "lifecycle": "состояние записи изменено", "headscale": "операция Headscale"},
        "en": {"new": "station registered", "updated": "data updated", "published": "approved for production", "lifecycle": "record state changed", "headscale": "Headscale operation"},
    }
    return values.get(language, values["tj"])[category]


def _diff_text(before: dict, after: dict, language: str) -> str:
    field_labels = {
        "tj": {"station_code": "код", "name": "ном", "city_id": "шаҳр", "district_id": "ноҳия", "operational_area": "минтақа", "address": "суроға", "latitude": "арз", "longitude": "тӯл", "vpn_ip": "VPN IP", "local_ip": "Local IP", "is_active": "фаъол", "is_archived": "бойгонӣ", "approval_status": "тасдиқ", "device_type": "навъи дастгоҳ", "station_id": "стансия"},
        "ru": {"station_code": "код", "name": "название", "city_id": "город", "district_id": "район", "operational_area": "зона", "address": "адрес", "latitude": "широта", "longitude": "долгота", "vpn_ip": "VPN IP", "local_ip": "Local IP", "is_active": "активна", "is_archived": "архив", "approval_status": "допуск", "device_type": "тип устройства", "station_id": "станция"},
        "en": {"station_code": "code", "name": "name", "city_id": "city", "district_id": "district", "operational_area": "area", "address": "address", "latitude": "latitude", "longitude": "longitude", "vpn_ip": "VPN IP", "local_ip": "Local IP", "is_active": "active", "is_archived": "archived", "approval_status": "approval", "device_type": "device type", "station_id": "station"},
    }
    labels = field_labels.get(language, field_labels["tj"])
    changes = []
    for key in sorted((set(before) | set(after)) & SUMMARY_SAFE_DIFF_FIELDS):
        old, new = before.get(key), after.get(key)
        if old != new:
            changes.append(f"{labels[key]}: {old if old not in (None, '') else '—'} → {new if new not in (None, '') else '—'}")
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


def _chunk_sections(title: str, sections: list[list[str]], limit: int = 3900) -> list[str]:
    chunks: list[str] = []
    current = title
    for section in sections:
        block = "\n".join(section)
        candidate = f"{current}\n\n{block}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current != title:
            chunks.append(current)
            current = f"{title}\n\n{block}"
        else:
            current = candidate
        if len(current) > limit:
            chunks.extend(_chunk_lines(current.splitlines(), limit=limit)[:-1])
            current = _chunk_lines(current.splitlines(), limit=limit)[-1]
    if current != title:
        chunks.append(current)
    return chunks
