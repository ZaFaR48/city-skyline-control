from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from i18n import LANGUAGE_BY_BUTTON, t
from keyboards import main_keyboard


router = Router()


@router.message(lambda message: message.text in LANGUAGE_BY_BUTTON)
async def choose_language(message: Message, state: FSMContext) -> None:
    lang = LANGUAGE_BY_BUTTON[message.text]
    data = await state.get_data()
    await state.update_data(lang=lang)
    await message.answer(t(lang, "language_selected"), reply_markup=main_keyboard(lang, is_admin=data.get("role") == "admin"))
