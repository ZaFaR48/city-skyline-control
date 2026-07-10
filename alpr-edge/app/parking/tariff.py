from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.parking.validators import ensure_utc


@dataclass(frozen=True)
class TariffConfig:
    timezone_name: str = "Asia/Dushanbe"
    start_time: str = "07:00"
    end_time: str = "22:00"
    free_minutes: int = 10
    rate_tjs_per_hour: float = 3.0
    rounding_mode: str = "exact_minute"

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def start_local_time(self) -> time:
        hour, minute = [int(part) for part in self.start_time.split(":", 1)]
        return time(hour, minute)

    @property
    def end_local_time(self) -> time:
        hour, minute = [int(part) for part in self.end_time.split(":", 1)]
        return time(hour, minute)


class TariffEngine:
    def __init__(self, config: TariffConfig) -> None:
        self.config = config

    def is_within_paid_hours(self, moment: datetime) -> bool:
        local = ensure_utc(moment).astimezone(self.config.zone)
        start = self.config.start_local_time
        end = self.config.end_local_time
        if start <= end:
            return start <= local.time() < end
        return local.time() >= start or local.time() < end

    def free_until(self, first_seen_at: datetime) -> datetime:
        return ensure_utc(first_seen_at) + timedelta(minutes=self.config.free_minutes)

    def billable_seconds(self, first_seen_at: datetime, until: datetime) -> int:
        start = max(self.free_until(first_seen_at), ensure_utc(first_seen_at))
        end = ensure_utc(until)
        if end <= start:
            return 0
        return int(self._paid_overlap_seconds(start, end))

    def amount_tjs(self, first_seen_at: datetime, until: datetime) -> float:
        seconds = self.billable_seconds(first_seen_at, until)
        rounded_seconds = self._round_seconds(seconds)
        return round((rounded_seconds / 3600) * self.config.rate_tjs_per_hour, 2)

    def _round_seconds(self, seconds: int) -> int:
        mode = self.config.rounding_mode
        if seconds <= 0:
            return 0
        if mode == "exact_minute":
            return int(math.ceil(seconds / 60) * 60)
        if mode == "started_hour":
            return int(math.ceil(seconds / 3600) * 3600)
        if mode == "completed_hour":
            return int(math.floor(seconds / 3600) * 3600)
        raise ValueError(f"Unsupported rounding mode: {mode}")

    def _paid_overlap_seconds(self, start_utc: datetime, end_utc: datetime) -> float:
        zone = self.config.zone
        start_local = start_utc.astimezone(zone)
        end_local = end_utc.astimezone(zone)
        current_day = start_local.date()
        final_day = end_local.date()
        total = 0.0
        while current_day <= final_day:
            window_start, window_end = self._window_for_day(current_day)
            overlap_start = max(start_utc, window_start)
            overlap_end = min(end_utc, window_end)
            if overlap_end > overlap_start:
                total += (overlap_end - overlap_start).total_seconds()
            current_day += timedelta(days=1)
        return total

    def _window_for_day(self, local_day: date) -> tuple[datetime, datetime]:
        zone = self.config.zone
        start_local = datetime.combine(local_day, self.config.start_local_time, tzinfo=zone)
        end_local = datetime.combine(local_day, self.config.end_local_time, tzinfo=zone)
        if end_local <= start_local:
            end_local += timedelta(days=1)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
