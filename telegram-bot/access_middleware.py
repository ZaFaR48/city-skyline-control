from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from api import BackendAPIError, api
from i18n import LANGUAGE_BY_BUTTON, all_texts, t


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
        if isinstance(event, Message) and (
            text.startswith(("/start", "/status", "/access", "/help"))
            or text in PUBLIC_TEXT
            or text in LANGUAGE_BY_BUTTON
        ):
            return await handler(event, data)
        state = data.get("state")
        state_data = await state.get_data() if state else {}
        lang = state_data.get("lang", "tj")
        try:
            registration = await api.resolve_telegram_user(event.from_user)
        except BackendAPIError:
            if isinstance(event, CallbackQuery):
                await event.answer(t(lang, "access_inactive"), show_alert=True)
            else:
                await event.answer(t(lang, "access_inactive"))
            return None
        if not registration.get("is_active"):
            if isinstance(event, CallbackQuery):
                await event.answer(t(lang, "access_inactive"), show_alert=True)
            else:
                await event.answer(t(lang, "access_inactive"))
            return None
        if state:
            await state.update_data(
                access_status="activated",
                role=registration.get("role"),
                lang=registration.get("preferred_language", lang),
            )
        return await handler(event, data)
