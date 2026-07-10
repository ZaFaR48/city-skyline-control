from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.config import AppConfig
from app.parking.validators import ensure_utc


@dataclass(frozen=True)
class WorkingHoursStatus:
    timezone: str
    local_time: str
    is_working_hours: bool
    start_time: str
    end_time: str


class OperatingSchedule:
    def __init__(self, config: AppConfig) -> None:
        self.timezone_name = config.parking_timezone
        self.zone = ZoneInfo(config.parking_timezone)
        self.start_time = self._parse_time(config.parking_start_time)
        self.end_time = self._parse_time(config.parking_end_time)

    def is_working_time(self, moment: datetime) -> bool:
        local = ensure_utc(moment).astimezone(self.zone)
        if self.start_time <= self.end_time:
            return self.start_time <= local.time() < self.end_time
        return local.time() >= self.start_time or local.time() < self.end_time

    def status(self, moment: datetime) -> WorkingHoursStatus:
        local = ensure_utc(moment).astimezone(self.zone)
        return WorkingHoursStatus(
            timezone=self.timezone_name,
            local_time=local.isoformat(),
            is_working_hours=self.is_working_time(moment),
            start_time=self.start_time.strftime("%H:%M"),
            end_time=self.end_time.strftime("%H:%M"),
        )

    def _parse_time(self, value: str) -> time:
        hour, minute = [int(part) for part in value.split(":", 1)]
        return time(hour, minute)
