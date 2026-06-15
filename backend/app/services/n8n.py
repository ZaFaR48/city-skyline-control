from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import settings


async def forward_event(event: str, payload: dict[str, Any]) -> bool:
    if not settings.N8N_WEBHOOK_URL:
        return False
    body = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(settings.N8N_WEBHOOK_URL, json=body)
        return 200 <= r.status_code < 300
