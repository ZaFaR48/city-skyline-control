from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit, urlunsplit


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def is_skip(value: str | None) -> bool:
    return clean_text(value).casefold() == "⏭ skip".casefold()


def is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def mask_url_credentials(value: str | None) -> str:
    url = clean_text(value)
    if not url:
        return "-"
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.username and not parts.password:
        return url

    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    masked_netloc = f"***:***@{host}" if host else "***:***"
    return urlunsplit((parts.scheme, masked_netloc, parts.path, parts.query, parts.fragment))
