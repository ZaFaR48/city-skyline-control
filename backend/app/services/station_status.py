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


def _reset_hysteresis(station: Station) -> None:
    station.consecutive_ping_failures = 0
    station.consecutive_ping_successes = 0
    station.consecutive_high_latency = 0
    station.consecutive_low_latency = 0
    station.recovery_started_at = None


def _recovery_confirmed(station: Station, now: datetime) -> bool:
    return bool(
        station.consecutive_ping_successes >= settings.PING_SUCCESS_THRESHOLD
        and station.recovery_started_at
        and (now - station.recovery_started_at).total_seconds() >= settings.RECOVERY_STABLE_SECONDS
    )


def _suppressed(station: Station, reason: str) -> StatusResolution:
    status = station.status or StationStatus.unknown.value
    if 1 in {
        int(station.consecutive_ping_failures or 0),
        int(station.consecutive_ping_successes or 0),
        int(station.consecutive_high_latency or 0),
        int(station.consecutive_low_latency or 0),
    }:
        logging.getLogger(__name__).info(
            "station_status_transition_suppressed station_id=%s station_code=%s status=%s reason=%s failures=%s successes=%s high_latency=%s low_latency=%s",
            station.id,
            station.station_code,
            status,
            reason,
            station.consecutive_ping_failures,
            station.consecutive_ping_successes,
            station.consecutive_high_latency,
            station.consecutive_low_latency,
        )
    return StatusResolution(status, status, False, reason)


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
        previous = station.status or StationStatus.unknown.value

        if not station.vpn_ip or not node:
            _reset_hysteresis(station)
            return await StationStatusResolver.transition(
                db,
                station,
                new_status=StationStatus.unknown,
                source=EventSource.ping,
                reason="MONITORING_NOT_CONFIGURED",
                occurred_at=now,
            )

        if not success:
            station.consecutive_ping_failures = int(station.consecutive_ping_failures or 0) + 1
            station.consecutive_ping_successes = 0
            station.consecutive_high_latency = 0
            station.consecutive_low_latency = 0
            station.recovery_started_at = None
            if station.consecutive_ping_failures < settings.PING_FAIL_THRESHOLD:
                return _suppressed(station, "connectivity failure below confirmation threshold")
            return await StationStatusResolver.transition(
                db,
                station,
                new_status=StationStatus.offline,
                source=EventSource.ping,
                reason=f"PING_TIMEOUT: {error_type or 'connectivity failure'}",
                occurred_at=now,
            )

        station.consecutive_ping_failures = 0
        station.consecutive_ping_successes = int(station.consecutive_ping_successes or 0) + 1
        station.last_seen_at = now

        latency = latency_ms or 0.0
        if latency >= settings.DEGRADED_ENTER_MS:
            station.consecutive_high_latency = int(station.consecutive_high_latency or 0) + 1
            station.consecutive_low_latency = 0
            if previous == StationStatus.offline.value:
                station.recovery_started_at = station.recovery_started_at or now
                if not _recovery_confirmed(station, now):
                    return _suppressed(station, "offline recovery not yet stable")
            else:
                station.recovery_started_at = None
            if (
                previous != StationStatus.degraded.value
                and station.consecutive_high_latency < settings.DEGRADED_CONSECUTIVE_CHECKS
            ):
                return _suppressed(station, "high latency below confirmation threshold")
            return await StationStatusResolver.transition(
                db,
                station,
                new_status=StationStatus.degraded,
                source=EventSource.ping,
                reason=f"PING_HIGH_LATENCY: {round(latency)} ms",
                occurred_at=now,
            )

        if latency <= settings.DEGRADED_EXIT_MS:
            station.consecutive_low_latency = int(station.consecutive_low_latency or 0) + 1
            station.consecutive_high_latency = 0
            if previous != StationStatus.online.value:
                station.recovery_started_at = station.recovery_started_at or now
                if (
                    station.consecutive_low_latency < settings.DEGRADED_EXIT_CONSECUTIVE_CHECKS
                    or not _recovery_confirmed(station, now)
                ):
                    return _suppressed(station, "healthy recovery not yet stable")
            else:
                station.recovery_started_at = None
        else:
            station.consecutive_high_latency = 0
            station.consecutive_low_latency = 0
            if previous == StationStatus.degraded.value:
                station.recovery_started_at = None
                return _suppressed(station, "latency remains inside hysteresis band")
            if previous == StationStatus.offline.value:
                station.recovery_started_at = station.recovery_started_at or now
                if not _recovery_confirmed(station, now):
                    return _suppressed(station, "offline recovery not yet stable")

        if not node.online:
            new_status, reason = StationStatus.degraded, "HEADSCALE_OFFLINE"
        else:
            new_status, reason = StationStatus.online, "HEALTHY"
        result = await StationStatusResolver.transition(
            db,
            station,
            new_status=new_status,
            source=EventSource.ping,
            reason=reason,
            occurred_at=now,
        )
        if result.transitioned:
            station.recovery_started_at = None
        return result

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
