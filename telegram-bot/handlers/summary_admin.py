from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from api import BackendAPIError, api
from authorization import require_telegram_roles
from i18n import all_menu_labels, localized_error, t
from keyboards import main_keyboard


router = Router()


@router.message(Command("autosummary"))
async def automatic_summary_command(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=1)
    action = parts[1].strip().lower() if len(parts) > 1 else "status"
    if action not in {"enable", "disable", "status"}:
        action = "status"
    await _control(message, state, action)


@router.message(lambda message: message.text in all_menu_labels("summary_enable"))
async def automatic_summary_enable(message: Message, state: FSMContext) -> None:
    await _control(message, state, "enable")


@router.message(lambda message: message.text in all_menu_labels("summary_disable"))
async def automatic_summary_disable(message: Message, state: FSMContext) -> None:
    await _control(message, state, "disable")


@router.message(lambda message: message.text in all_menu_labels("summary_status"))
async def automatic_summary_status(message: Message, state: FSMContext) -> None:
    await _control(message, state, "status")


async def _control(message: Message, state: FSMContext, action: str) -> None:
    lang = (await state.get_data()).get("lang", "tj")
    if not await require_telegram_roles(message, state, "admin"):
        await message.answer(t(lang, "permission_denied"))
        return
    try:
        result = await api.automatic_summary_control(message.from_user, action)
    except BackendAPIError as exc:
        await message.answer(localized_error(lang, exc.message))
        return
    state_label = t(lang, "summary_enabled" if result.get("enabled") else "summary_disabled")
    text = t(lang, "summary_control_status").format(
        state=state_label,
        interval=result.get("interval_minutes", 10),
        recipients=result.get("recipient_count", 0),
        caller=t(lang, "yes" if result.get("caller_is_recipient") else "no"),
    )
    await message.answer(text, reply_markup=main_keyboard(lang, role="admin"))
