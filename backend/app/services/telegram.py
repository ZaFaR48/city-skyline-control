from __future__ import annotations

import httpx

from ..config import settings


async def send_telegram(text: str) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json={
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        })
        return r.status_code == 200
