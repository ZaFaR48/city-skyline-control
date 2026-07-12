from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import BackendAPIError, api
from i18n import all_menu_labels, t
from keyboards import main_keyboard, wizard_inline
from states import OperationsLookup
from validators import clean_text, normalize_station_code


router = Router()
DISTRICTS = {
    "ismoili-somoni": "Ismoili Somoni",
    "shohmansur": "Shohmansur",
    "sino": "Sino",
    "firdavsi": "Firdavsi",
}


async def _lang(state: FSMContext) -> str:
    return (await state.get_data()).get("lang", "tj")


async def _authorized(user, state: FSMContext) -> bool:
    if user is None:
        return False
    try:
        registration = await api.registration_start(user)
    except BackendAPIError:
        return False
    allowed = registration.get("status") == "activated" and registration.get("role") in {"admin", "operator"}
    if allowed:
        await state.update_data(role=registration.get("role"), access_status="activated")
    return allowed


@router.message(Command("stations"))
@router.message(lambda message: message.text in all_menu_labels("station_summary"))
async def operations_menu(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if not await _authorized(message.from_user, state):
        await message.answer(t(lang, "ops_denied"))
        return
    await message.answer(
        t(lang, "ops_title"),
        reply_markup=wizard_inline([
            [(t(lang, "ops_all"), "ops:all")],
            [(t(lang, "ops_code"), "ops:code")],
            [(t(lang, "ops_district"), "ops:district")],
            [(t(lang, "ops_state"), "ops:state")],
        ]),
    )


@router.message(Command("station"))
async def station_command(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if not await _authorized(message.from_user, state):
        await message.answer(t(lang, "ops_denied"))
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 1:
        await state.set_state(OperationsLookup.code)
        await message.answer(t(lang, "ops_enter_code"))
        return
    await _send_exact_code(message, state, parts[1])


@router.message(Command("district"))
async def district_command(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if not await _authorized(message.from_user, state):
        await message.answer(t(lang, "ops_denied"))
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip() in DISTRICTS:
        await _send_district(message, state, parts[1].strip())
    else:
        await _district_menu(message, lang)


@router.message(Command("state"))
async def state_command(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if not await _authorized(message.from_user, state):
        await message.answer(t(lang, "ops_denied"))
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip() in {"pending", "approved", "archived"}:
        await _send_state(message, state, parts[1].strip())
    else:
        await _state_menu(message, lang)


@router.callback_query(F.data.startswith("ops:"))
async def operations_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or not await _authorized(callback.from_user, state):
        await callback.answer(t(await _lang(state), "ops_denied"), show_alert=True)
        return
    lang = await _lang(state)
    action = (callback.data or "").split(":", 1)[1]
    if action == "all":
        await _send_view(callback.message, state, "all", active_only=True)
    elif action == "code":
        await state.set_state(OperationsLookup.code)
        await callback.message.answer(t(lang, "ops_enter_code"))
    elif action == "district":
        await _district_menu(callback.message, lang)
    elif action == "state":
        await _state_menu(callback.message, lang)
    elif action.startswith("district-"):
        await _send_district(callback.message, state, action.removeprefix("district-"))
    elif action.startswith("state-"):
        await _send_state(callback.message, state, action.removeprefix("state-"))
    else:
        await callback.answer("Invalid action", show_alert=True)
        return
    await callback.answer()


@router.message(OperationsLookup.code)
async def operations_code_input(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if not await _authorized(message.from_user, state):
        await message.answer(t(lang, "ops_denied"))
        return
    await _send_exact_code(message, state, clean_text(message.text) or "")


async def _district_menu(message: Message, lang: str) -> None:
    await message.answer(
        t(lang, "ops_choose_district"),
        reply_markup=wizard_inline([[(name, f"ops:district-{code}")] for code, name in DISTRICTS.items()]),
    )


async def _state_menu(message: Message, lang: str) -> None:
    await message.answer(
        t(lang, "ops_choose_state"),
        reply_markup=wizard_inline([
            [(t(lang, "approval_pending"), "ops:state-pending")],
            [(t(lang, "approval_approved"), "ops:state-approved")],
            [("Archived", "ops:state-archived")],
        ]),
    )


async def _send_exact_code(message: Message, state: FSMContext, raw_code: str) -> None:
    code = normalize_station_code(raw_code)
    try:
        rows = await api.operational_stations("all", code)
    except BackendAPIError as exc:
        await message.answer(f"{t(await _lang(state), 'api_error')} {exc.message}")
        return
    exact = [row for row in rows if str(row.get("station_code", "")).casefold() == code.casefold()]
    await _send_rows(message, state, exact)


async def _send_district(message: Message, state: FSMContext, code: str) -> None:
    try:
        rows = await api.operational_stations("all", DISTRICTS[code])
    except BackendAPIError as exc:
        await message.answer(f"{t(await _lang(state), 'api_error')} {exc.message}")
        return
    await _send_rows(message, state, [row for row in rows if row.get("district") == DISTRICTS[code]])


async def _send_state(message: Message, state: FSMContext, production_state: str) -> None:
    await _send_view(message, state, production_state)


async def _send_view(message: Message, state: FSMContext, view: str, *, active_only: bool = False) -> None:
    try:
        rows = await api.operational_stations(view)
    except BackendAPIError as exc:
        await message.answer(f"{t(await _lang(state), 'api_error')} {exc.message}")
        return
    if active_only:
        rows = [row for row in rows if row.get("is_active") and not row.get("is_archived")]
    await _send_rows(message, state, rows)


async def _send_rows(message: Message, state: FSMContext, rows: list[dict]) -> None:
    lang = await _lang(state)
    await state.set_state(None)
    if not rows:
        await message.answer(t(lang, "ops_empty"), reply_markup=main_keyboard(lang))
        return
    for chunk in chunk_station_messages(rows, lang):
        await message.answer(chunk)
    await message.answer(t(lang, "main_menu"), reply_markup=main_keyboard(lang))


def format_station_summary(station: dict, lang: str) -> str:
    gps = "—"
    if station.get("latitude") is not None and station.get("longitude") is not None:
        gps = f"{station['latitude']}, {station['longitude']}"
    approval = t(lang, "approval_approved") if station.get("approved_at") else t(lang, "approval_pending")
    record = "archived" if station.get("is_archived") else "active" if station.get("is_active") else "inactive"
    node = station.get("headscale_hostname") or "—"
    return "\n".join([
        f"{station.get('station_code', '—')} · {station.get('name', '—')}",
        f"{t(lang, 'label_city')}: {station.get('city') or '—'}",
        f"{t(lang, 'label_district')}: {station.get('district') or '—'}",
        f"{t(lang, 'ops_area')}: {station.get('operational_area') or '—'}",
        f"{t(lang, 'label_address')}: {station.get('address') or '—'}",
        f"{t(lang, 'label_vpn')}: {station.get('vpn_ip') or '—'} · {t(lang, 'label_local')}: {station.get('local_ip') or '—'}",
        f"{t(lang, 'label_gps')}: {gps}",
        f"{t(lang, 'ops_approval')}: {approval} · {t(lang, 'ops_record')}: {record}",
        f"{t(lang, 'ops_linked')}: {node}",
    ])


def chunk_station_messages(rows: list[dict], lang: str, limit: int = 3500) -> list[str]:
    blocks = [format_station_summary(row, lang) for row in rows]
    chunks: list[str] = []
    current = t(lang, "ops_title")
    for block in blocks:
        candidate = f"{current}\n\n{block}"
        if len(candidate) > limit and current != t(lang, "ops_title"):
            chunks.append(current)
            current = f"{t(lang, 'ops_title')}\n\n{block}"
        else:
            current = candidate
    chunks.append(current)
    return chunks
