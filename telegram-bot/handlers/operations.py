from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import BackendAPIError, api
from authorization import require_telegram_roles
from i18n import all_menu_labels, localized_error, t
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
    return bool(await require_telegram_roles(SimpleEvent(user), state, "admin", "operator", "viewer"))


class SimpleEvent:
    def __init__(self, user):
        self.from_user = user


@router.message(Command("stations"))
@router.message(lambda message: message.text in all_menu_labels("station_summary"))
async def operations_menu(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if not await _authorized(message.from_user, state):
        await message.answer(t(lang, "ops_denied"))
        return
    await _send_view(message, state, "all", active_only=True)


@router.message(lambda message: message.text in all_menu_labels("district_stations"))
async def district_menu_action(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if not await _authorized(message.from_user, state):
        await message.answer(t(lang, "ops_denied"))
        return
    await _district_menu(message, lang)


@router.message(lambda message: message.text in all_menu_labels("station_status"))
async def state_menu_action(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if not await _authorized(message.from_user, state):
        await message.answer(t(lang, "ops_denied"))
        return
    await _state_menu(message, lang)


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
    if len(parts) > 1 and parts[1].strip() in {"online", "degraded", "offline", "unknown", "pending", "approved", "archived"}:
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
        await callback.answer(t(lang, "invalid_callback"), show_alert=True)
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
            [(t(lang, "state_online"), "ops:state-online")],
            [(t(lang, "state_degraded"), "ops:state-degraded")],
            [(t(lang, "state_offline"), "ops:state-offline")],
            [(t(lang, "state_unknown"), "ops:state-unknown")],
            [(t(lang, "approval_pending"), "ops:state-pending")],
            [(t(lang, "approval_approved"), "ops:state-approved")],
            [(t(lang, "state_archived"), "ops:state-archived")],
        ]),
    )


async def _send_exact_code(message: Message, state: FSMContext, raw_code: str) -> None:
    code = normalize_station_code(raw_code)
    try:
        rows = await api.operational_stations("all", code)
    except BackendAPIError as exc:
        lang = await _lang(state)
        await message.answer(localized_error(lang, exc.message))
        return
    exact = [row for row in rows if str(row.get("station_code", "")).casefold() == code.casefold()]
    await _send_rows(message, state, exact, detailed=True)


async def _send_district(message: Message, state: FSMContext, code: str) -> None:
    try:
        rows = await api.operational_stations("all", DISTRICTS[code])
    except BackendAPIError as exc:
        lang = await _lang(state)
        await message.answer(localized_error(lang, exc.message))
        return
    await _send_rows(message, state, [row for row in rows if row.get("district") == DISTRICTS[code] and _is_production(row)])


async def _send_state(message: Message, state: FSMContext, production_state: str) -> None:
    if production_state in {"online", "degraded", "offline", "unknown"}:
        try:
            rows = await api.operational_stations("all")
        except BackendAPIError as exc:
            lang = await _lang(state)
            await message.answer(localized_error(lang, exc.message))
            return
        await _send_rows(message, state, [row for row in rows if _is_production(row) and _health_status(row) == production_state])
    else:
        await _send_view(message, state, production_state)


async def _send_view(message: Message, state: FSMContext, view: str, *, active_only: bool = False) -> None:
    try:
        rows = await api.operational_stations(view)
    except BackendAPIError as exc:
        lang = await _lang(state)
        await message.answer(localized_error(lang, exc.message))
        return
    if active_only:
        rows = [row for row in rows if _is_production(row)]
    await _send_rows(message, state, rows)


async def _send_rows(message: Message, state: FSMContext, rows: list[dict], *, detailed: bool = False) -> None:
    lang = await _lang(state)
    role = (await state.get_data()).get("role")
    await state.set_state(None)
    if not rows:
        await message.answer(t(lang, "ops_empty"), reply_markup=main_keyboard(lang, role=role))
        return
    chunks = [format_station_summary(rows[0], lang)] if detailed else chunk_station_messages(rows, lang)
    for chunk in chunks:
        await message.answer(chunk)
    await message.answer(t(lang, "main_menu"), reply_markup=main_keyboard(lang, role=role))


def format_station_summary(station: dict, lang: str) -> str:
    health = station.get("health") or {}
    status = _health_status(station)
    reason_code = health.get("overall_reason_code") or "CONFLICTING_TELEMETRY"
    return "\n".join([
        f"{station.get('station_code', '—')} · {station.get('name', '—')}",
        f"{t(lang, 'health_status')}: {t(lang, f'state_{status}')}",
        f"{t(lang, 'health_reason')}: {t(lang, f'reason_{reason_code}')}",
        f"{t(lang, 'health_duration')}: {_duration(health.get('current_state_duration_seconds'), lang)}",
        f"{t(lang, 'health_connectivity')}: {_component(health.get('connectivity_status'), lang)}",
        f"{t(lang, 'health_headscale')}: {_component(health.get('headscale_status'), lang)}",
        f"{t(lang, 'health_agent')}: {_component(health.get('agent_status'), lang)}",
        f"{t(lang, 'health_camera')}: {_component(health.get('camera_status'), lang)}",
        f"{t(lang, 'health_internet')}: {_component(health.get('internet_status'), lang)}",
        f"{t(lang, 'health_service')}: {_component(health.get('local_service_status'), lang)}",
        f"{t(lang, 'health_observed')}: {_observed(health.get('observed_at'))}",
    ])


def chunk_station_messages(rows: list[dict], lang: str, limit: int = 3500) -> list[str]:
    ordered = sorted(rows, key=lambda row: _natural_code(str(row.get("station_code") or "")))
    grouped = {status: [row for row in ordered if _health_status(row) == status] for status in ("online", "degraded", "offline", "unknown")}
    title = f"{t(lang, 'ops_title')} · {t(lang, 'health_total')}: {len(rows)}"
    max_section = max(100, limit - len(title) - 2)
    healthy = [str(row.get("station_code") or "—") for row in grouped["online"]]
    sections = _section_blocks(t(lang, "health_healthy"), healthy, max_section, comma_separated=True)
    for status, key in (("degraded", "health_degraded"), ("offline", "health_offline"), ("unknown", "health_unknown")):
        entries = []
        for row in grouped[status]:
            health = row.get("health") or {}
            reason = t(lang, f"reason_{health.get('overall_reason_code') or 'CONFLICTING_TELEMETRY'}")
            duration = _duration(health.get("current_state_duration_seconds"), lang)
            suffix = f" · {duration}" if health.get("current_state_duration_seconds") is not None else ""
            entries.append(f"{row.get('station_code', '—')} — {reason}{suffix}")
        sections.extend(_section_blocks(t(lang, key), entries, max_section))
    chunks, current = [], title
    for section in sections:
        candidate = f"{current}\n\n{section}"
        if len(candidate) > limit and current != title:
            chunks.append(current)
            current = f"{title}\n\n{section}"
        else:
            current = candidate
    chunks.append(current)
    return chunks


def _section_blocks(label: str, entries: list[str], limit: int, *, comma_separated: bool = False) -> list[str]:
    values = entries or ["—"]
    header = f"{label} ({len(entries)}):"
    blocks: list[str] = []
    current = header
    for value in values:
        separator = "\n" if current == header or not comma_separated else ", "
        candidate = f"{current}{separator}{value}"
        if len(candidate) > limit and current != header:
            blocks.append(current)
            current = f"{header}\n{value}"
        else:
            current = candidate
    blocks.append(current)
    return blocks


def _is_production(row: dict) -> bool:
    return bool(row.get("approved_at") and row.get("is_active") and not row.get("is_archived"))


def _health_status(row: dict) -> str:
    return str((row.get("health") or {}).get("overall_status") or row.get("status") or "unknown")


def _natural_code(code: str) -> tuple[int, int | str]:
    return (0, int(code)) if code.isdigit() else (1, code.casefold())


def _duration(seconds: int | None, lang: str) -> str:
    if seconds is None:
        return "—"
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes = remainder // 60
    if lang == "ru":
        return f"{hours} ч {minutes} мин" if hours else f"{minutes} мин"
    if lang == "tj":
        return f"{hours} соат {minutes} дақ" if hours else f"{minutes} дақ"
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def _component(value: str | None, lang: str) -> str:
    labels = {
        "ru": {"online": "онлайн", "degraded": "с проблемами", "offline": "офлайн", "unknown": "неизвестно", "stale": "данные устарели", "not_configured": "не настроено"},
        "tj": {"online": "онлайн", "degraded": "мушкилдор", "offline": "хомӯш", "unknown": "номаълум", "stale": "маълумот кӯҳна", "not_configured": "танзим нашудааст"},
        "en": {"online": "online", "degraded": "degraded", "offline": "offline", "unknown": "unknown", "stale": "stale", "not_configured": "not configured"},
    }
    return labels.get(lang, labels["tj"]).get(value or "unknown", value or "—")


def _observed(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Dushanbe")).isoformat(timespec="seconds")
    except ValueError:
        return "—"
