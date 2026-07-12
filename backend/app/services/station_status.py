from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import (
    Alert,
    AlertSeverity,
    AlertType,
    ApprovalStatus,
    DeviceType,
    EventSource,
    HeadscaleNode,
    Station,
    StationStatus,
    StationStatusEvent,
)


@dataclass(frozen=True)
class StatusResolution:
    previous_status: str
    new_status: str
    transitioned: bool
    reason: str


class StationStatusResolver:
    """The single authority for persisted station state transitions."""

    @staticmethod
    async def resolve_ping(
        db: AsyncSession,
        station: Station,
        *,
        success: bool,
        latency_ms: float | None,
        checked_at: datetime | None = None,
        error_type: str | None = None,
    ) -> StatusResolution:
        now = checked_at or datetime.now(timezone.utc)
        node = (
            await db.execute(
                select(HeadscaleNode).where(
                    HeadscaleNode.station_id == station.id,
                    HeadscaleNode.approval_status == ApprovalStatus.approved.value,
                    HeadscaleNode.device_type == DeviceType.station.value,
                )
            )
        ).scalar_one_or_none()

        station.last_ping_at = now
        station.last_ping_ms = round(latency_ms) if success and latency_ms is not None else None

        if not station.vpn_ip or not node:
            station.consecutive_ping_failures = 0 if success else station.consecutive_ping_failures
            new_status = StationStatus.unknown.value
            reason = "MONITORING_NOT_CONFIGURED"
        elif success:
            station.consecutive_ping_failures = 0
            station.last_seen_at = now
            if not node.online:
                new_status = StationStatus.degraded.value
                reason = "HEADSCALE_OFFLINE"
            elif latency_ms is not None and latency_ms > settings.DEGRADED_LATENCY_MS:
                new_status = StationStatus.degraded.value
                reason = f"PING_HIGH_LATENCY: {round(latency_ms)} ms"
            else:
                new_status = StationStatus.online.value
                reason = "HEALTHY"
        else:
            station.consecutive_ping_failures += 1
            node_stale = (
                not node.online
                and (
                    node.last_seen_at is None
                    or (now - node.last_seen_at).total_seconds() >= settings.OFFLINE_AFTER_SECONDS
                )
            )
            confirmed = station.consecutive_ping_failures >= settings.PING_FAIL_THRESHOLD or node_stale
            if confirmed:
                new_status = StationStatus.offline.value
                reason = f"PING_TIMEOUT: {error_type or 'connectivity failure'}"
            else:
                new_status = StationStatus.degraded.value
                reason = f"PING_TIMEOUT: {error_type or 'temporary connectivity failure'} {station.consecutive_ping_failures}/{settings.PING_FAIL_THRESHOLD}"

        return await StationStatusResolver.transition(
            db,
            station,
            new_status=new_status,
            source=EventSource.ping,
            reason=reason,
            occurred_at=now,
        )

    @staticmethod
    async def transition(
        db: AsyncSession,
        station: Station,
        *,
        new_status: StationStatus | str,
        source: EventSource | str,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> StatusResolution:
        now = occurred_at or datetime.now(timezone.utc)
        status_value = new_status.value if isinstance(new_status, StationStatus) else new_status
        source_value = source.value if isinstance(source, EventSource) else source
        previous = station.status or StationStatus.unknown.value

        if previous == status_value:
            if station.status_reason != reason:
                logging.getLogger(__name__).info(
                    "station_status_reason_changed station_id=%s station_code=%s status=%s reason=%s",
                    station.id,
                    station.station_code,
                    status_value,
                    reason,
                )
            station.status_reason = reason
            return StatusResolution(previous, status_value, False, reason)

        open_events = (
            await db.execute(
                select(StationStatusEvent).where(
                    StationStatusEvent.station_id == station.id,
                    StationStatusEvent.ended_at.is_(None),
                )
            )
        ).scalars().all()
        for event in open_events:
            event.ended_at = now
            event.duration_seconds = max(0, int((now - event.started_at).total_seconds()))

        db.add(
            StationStatusEvent(
                station_id=station.id,
                previous_status=previous,
                new_status=status_value,
                source=source_value,
                reason=reason,
                started_at=now,
            )
        )
        station.status = status_value
        station.status_reason = reason
        logging.getLogger(__name__).info(
            "station_status_transition station_id=%s station_code=%s previous=%s current=%s source=%s reason=%s",
            station.id,
            station.station_code,
            previous,
            status_value,
            source_value,
            reason,
        )

        if status_value == StationStatus.offline.value:
            station.offline_since = station.offline_since or now
            existing = (
                await db.execute(
                    select(Alert).where(
                        Alert.station_id == station.id,
                        Alert.type == AlertType.offline_station.value,
                        Alert.resolved_at.is_(None),
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if not existing:
                db.add(
                    Alert(
                        station_id=station.id,
                        type=AlertType.offline_station.value,
                        severity=AlertSeverity.critical.value,
                        message=f"Station {station.station_code} is offline",
                    )
                )
        elif previous == StationStatus.offline.value:
            station.offline_since = None
            if status_value in {StationStatus.online.value, StationStatus.degraded.value}:
                active_alerts = (
                    await db.execute(
                        select(Alert).where(
                            Alert.station_id == station.id,
                            Alert.type == AlertType.offline_station.value,
                            Alert.resolved_at.is_(None),
                        )
                    )
                ).scalars().all()
                for alert in active_alerts:
                    alert.resolved_at = now

        return StatusResolution(previous, status_value, True, reason)
