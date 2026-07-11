from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from api import BackendAPIError, api


PUBLIC_TEXT = {"My status", "Request access", "Help"}


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)
        text = (event.text or "").strip()
        if text.startswith(("/start", "/status", "/help")) or text in PUBLIC_TEXT:
            return await handler(event, data)
        try:
            registration = await api.registration_start(event.from_user)
        except BackendAPIError:
            await event.answer("Registration service is temporarily unavailable. Please try again later.")
            return None
        if registration.get("status") != "activated":
            await event.answer("Access is not active. Use /start or My status.")
            return None
        state = data.get("state")
        if state:
            await state.update_data(access_status="activated", role=registration.get("role"))
        return await handler(event, data)
