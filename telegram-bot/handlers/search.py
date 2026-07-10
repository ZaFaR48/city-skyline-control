from __future__ import annotations

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from api import BackendAPIError, api
from i18n import all_menu_labels, all_texts, t
from keyboards import main_keyboard
from states import SearchStation
from validators import clean_text


router = Router()


async def _lang(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("lang", "tj")


@router.message(StateFilter(SearchStation), lambda message: message.text in all_texts("cancel"))
async def cancel_search(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    await state.clear()
    await state.update_data(lang=lang)
    await message.answer(t(lang, "cancelled"), reply_markup=main_keyboard(lang))


@router.message(lambda message: message.text in all_menu_labels("search_station"))
async def search_start(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    await state.set_state(SearchStation.query)
    await message.answer(t(lang, "search_prompt"))


@router.message(SearchStation.query)
async def search_query(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    query = clean_text(message.text)
    if not query:
        await message.answer(t(lang, "search_empty"))
        return

    try:
        rows = await api.search_stations(query)
    except BackendAPIError as exc:
        await message.answer(f"{t(lang, 'api_error')} {exc.message}", reply_markup=main_keyboard(lang))
        await state.clear()
        await state.update_data(lang=lang)
        return

    await state.clear()
    await state.update_data(lang=lang)

    if not rows:
        await message.answer(t(lang, "search_no_results"), reply_markup=main_keyboard(lang))
        return

    lines = [t(lang, "search_results"), ""]
    for station in rows[:10]:
        lines.append(
            "\n".join([
                f"{station.get('code', '-')}: {station.get('name', '-')}",
                f"Region: {station.get('region', '-')}",
                f"Address: {station.get('address', '-')}",
                f"VPN IP: {station.get('vpn_ip', '-')}",
                f"Status: {station.get('status', '-')}",
            ])
        )
        lines.append("")

    await message.answer("\n".join(lines).strip(), reply_markup=main_keyboard(lang))
