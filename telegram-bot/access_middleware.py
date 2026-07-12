from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from api import BackendAPIError, api
from i18n import all_texts


PUBLIC_TEXT = all_texts("my_access") | all_texts("request_access") | all_texts("help_access")


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)) or event.from_user is None:
            return await handler(event, data)
        text = (event.text or "").strip() if isinstance(event, Message) else ""
        if isinstance(event, Message) and (text.startswith(("/start", "/status", "/access", "/help")) or text in PUBLIC_TEXT):
            return await handler(event, data)
        try:
            registration = await api.resolve_telegram_user(event.from_user)
        except BackendAPIError:
            if isinstance(event, CallbackQuery):
                await event.answer("Access is not active. Use /start or My access.", show_alert=True)
            else:
                await event.answer("Access is not active. Use /start or My access.")
            return None
        if not registration.get("is_active"):
            if isinstance(event, CallbackQuery):
                await event.answer("Access is not active.", show_alert=True)
            else:
                await event.answer("Access is not active.")
            return None
        state = data.get("state")
        if state:
            await state.update_data(access_status="activated", role=registration.get("role"))
        return await handler(event, data)
