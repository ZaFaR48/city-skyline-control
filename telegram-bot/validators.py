from __future__ import annotations

import ipaddress
import re


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def is_skip(value: str | None) -> bool:
    return clean_text(value).casefold() in {
        "⏭ skip".casefold(),
        "⏭ пропустить".casefold(),
        "⏭ гузариш".casefold(),
    }


def normalize_station_code(value: str | None) -> str:
    return clean_text(value).upper()


def is_valid_station_code(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9_-]{1,32}", value))


def is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True
