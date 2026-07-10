from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


TIME_FIELDS = {"first_seen_at", "confirmed_at", "last_seen_at", "exited_at", "free_until", "created_at", "updated_at", "reviewed_at"}


def with_local_times(record: dict, timezone_name: str) -> dict:
    zone = ZoneInfo(timezone_name)
    output = dict(record)
    for field in TIME_FIELDS:
        value = record.get(field)
        if not value:
            continue
        output[f"{field}_local"] = datetime.fromisoformat(value).astimezone(zone).isoformat()
    return output
