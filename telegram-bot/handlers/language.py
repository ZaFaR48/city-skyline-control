from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from api import BackendAPIError, api
from i18n import LANGUAGE_BY_BUTTON, all_menu_labels, localized_error, t
from keyboards import language_keyboard, main_keyboard
from handlers.start import send_registration_result


router = Router()


@router.message(lambda message: message.text in LANGUAGE_BY_BUTTON)
async def choose_language(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    lang = LANGUAGE_BY_BUTTON[message.text]
    data = await state.get_data()
    await state.update_data(lang=lang)
    try:
        await api.set_telegram_language(message.from_user, lang)
    except BackendAPIError as exc:
        await message.answer(localized_error(lang, exc.message))
        return
    await message.answer(t(lang, "language_selected"))
    if data.get("registration_unavailable"):
        await message.answer(t(lang, "registration_unavailable"))
        return
    pending = data.get("pending_registration_result")
    if pending:
        await send_registration_result(message, state, lang, pending)
    else:
        await message.answer(t(lang, "main_menu"), reply_markup=main_keyboard(lang, role=data.get("role")))


@router.message(lambda message: message.text in all_menu_labels("change_language"))
async def change_language(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Лутфан забонро интихоб кунед · Выберите язык · Choose language",
        reply_markup=language_keyboard(),
    )
