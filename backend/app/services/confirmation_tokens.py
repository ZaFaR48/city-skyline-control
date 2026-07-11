from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

from ..config import settings


TOKEN_TTL_SECONDS = 15 * 60


def create_confirmation_token(purpose: str, payload: Any) -> str:
    expires_at = int(time.time()) + TOKEN_TTL_SECONDS
    signature = _signature(purpose, expires_at, payload)
    return f"{expires_at}.{signature}"


def verify_confirmation_token(token: str, purpose: str, payload: Any) -> bool:
    try:
        expires_raw, supplied = token.split(".", 1)
        expires_at = int(expires_raw)
    except (TypeError, ValueError):
        return False
    if expires_at < int(time.time()):
        return False
    expected = _signature(purpose, expires_at, payload)
    return hmac.compare_digest(supplied, expected)


def _signature(purpose: str, expires_at: int, payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    message = f"{purpose}|{expires_at}|{canonical}".encode()
    return hmac.new(settings.JWT_SECRET.encode(), message, hashlib.sha256).hexdigest()
