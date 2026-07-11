from __future__ import annotations

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from api import BackendAPIError, api
from i18n import all_menu_labels, all_texts, t
from keyboards import (
    approved_update_keyboard,
    confirm_keyboard,
    location_keyboard,
    main_keyboard,
    skip_keyboard,
)
from states import AddStation
from validators import clean_text, is_skip, is_valid_ip, is_valid_station_code, normalize_station_code


router = Router()


async def _lang(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("lang", "tj")


async def _clear_keep_lang(state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.update_data(lang=lang)


@router.message(StateFilter(AddStation), lambda message: message.text in all_texts("cancel"))
async def cancel_station(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    await _clear_keep_lang(state, lang)
    await message.answer(t(lang, "cancelled"), reply_markup=main_keyboard(lang))


@router.message(lambda message: message.text in all_menu_labels("new_station"))
async def station_start(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    await _clear_keep_lang(state, lang)
    await state.set_state(AddStation.code)
    await message.answer(t(lang, "enter_code"))


@router.message(AddStation.code)
async def station_code(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = normalize_station_code(message.text)
    if not value or is_skip(value) or not is_valid_station_code(value):
        await message.answer(t(lang, "invalid_station_code"))
        return
    try:
        existing = await api.station_by_code(value)
    except BackendAPIError as exc:
        await message.answer(f"{t(lang, 'api_error')} {exc.message}")
        return
    await state.update_data(
        code=value,
        existing_station_id=existing.get("id") if existing else None,
        existing_station=existing,
        existing_approved=bool(existing and existing.get("approved_at")),
    )
    if existing:
        key = "station_exists_approved" if existing.get("approved_at") else "station_exists_pending"
        await message.answer(f"{t(lang, key).format(code=value)}\n\n{_existing_station_text(lang, existing)}")
    await state.set_state(AddStation.name)
    await message.answer(t(lang, "enter_name"))


@router.message(AddStation.name)
async def station_name(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    if not value or is_skip(value):
        await message.answer(t(lang, "invalid_required"))
        return
    await state.update_data(name=value)
    await state.set_state(AddStation.region)
    await message.answer(t(lang, "enter_region"))


@router.message(AddStation.region)
async def station_region(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    if not value or is_skip(value):
        await message.answer(t(lang, "invalid_required"))
        return
    canonical = _canonical_district(value)
    if canonical is None:
        await message.answer(t(lang, "district_error"))
        return
    await state.update_data(region=canonical)
    await state.set_state(AddStation.address)
    await message.answer(t(lang, "enter_address"))


@router.message(AddStation.address)
async def station_address(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    if not value or is_skip(value):
        await message.answer(t(lang, "invalid_required"))
        return
    await state.update_data(address=value)
    await state.set_state(AddStation.vpn_ip)
    await message.answer(t(lang, "enter_vpn"), reply_markup=skip_keyboard(lang))


@router.message(AddStation.vpn_ip)
async def station_vpn_ip(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    if is_skip(value):
        await state.update_data(vpn_ip=None)
    else:
        if not is_valid_ip(value):
            await message.answer(t(lang, "invalid_ip"), reply_markup=skip_keyboard(lang))
            return
        await state.update_data(vpn_ip=value)
    await state.set_state(AddStation.local_ip)
    await message.answer(t(lang, "enter_local"), reply_markup=skip_keyboard(lang))


@router.message(AddStation.local_ip)
async def station_local_ip(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    if is_skip(value):
        await state.update_data(local_ip=None)
    else:
        if not is_valid_ip(value):
            await message.answer(t(lang, "invalid_ip"), reply_markup=skip_keyboard(lang))
            return
        await state.update_data(local_ip=value)
    await state.set_state(AddStation.rustdesk_id)
    await message.answer(t(lang, "enter_rustdesk"), reply_markup=skip_keyboard(lang))


@router.message(AddStation.rustdesk_id)
async def station_rustdesk(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    await state.update_data(rustdesk_id=None if is_skip(value) else value)
    await state.set_state(AddStation.gps)
    await message.answer(t(lang, "enter_location"), reply_markup=location_keyboard(lang))


@router.message(AddStation.gps)
async def station_gps(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if message.location:
        await state.update_data(lat=message.location.latitude, lng=message.location.longitude)
    elif is_skip(message.text):
        await state.update_data(lat=None, lng=None)
    else:
        await message.answer(t(lang, "invalid_location"), reply_markup=location_keyboard(lang))
        return
    await state.set_state(AddStation.confirm)
    data = await state.get_data()
    keyboard = approved_update_keyboard(lang) if data.get("existing_approved") else confirm_keyboard(lang)
    await message.answer(_summary(lang, data), reply_markup=keyboard)


@router.message(AddStation.confirm)
async def station_confirm(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    data = await state.get_data()
    try:
        current = await api.station_by_code(str(data.get("code", "")))
    except BackendAPIError as exc:
        await message.answer(f"{t(lang, 'api_error')} {exc.message}")
        return
    if current and current.get("approved_at") and not data.get("existing_approved"):
        await state.update_data(existing_station_id=current.get("id"), existing_station=current, existing_approved=True)
        data = await state.get_data()
        await message.answer(
            f"{t(lang, 'station_exists_approved').format(code=data['code'])}\n\n{_summary(lang, data)}",
            reply_markup=approved_update_keyboard(lang),
        )
        return
    required = t(lang, "confirm_approved_update") if data.get("existing_approved") else None
    accepted = clean_text(message.text) == required if required else clean_text(message.text) in all_texts("save")
    keyboard = approved_update_keyboard(lang) if data.get("existing_approved") else confirm_keyboard(lang)
    if not accepted:
        await message.answer(_summary(lang, data), reply_markup=keyboard)
        return
    missing = _missing_backend_fields(data)
    if missing:
        await message.answer(
            f"{t(lang, 'missing_backend')}\n\n{t(lang, 'missing_fields')} {', '.join(missing)}",
            reply_markup=keyboard,
        )
        return

    try:
        regions = await api.regions()
    except BackendAPIError as exc:
        await message.answer(f"{t(lang, 'api_error')} {exc.message}", reply_markup=keyboard)
        return
    city = next((region for region in regions if region.get("code") == "dushanbe"), None)
    district = next((region for region in regions if str(region.get("name", "")).casefold() == str(data["region"]).casefold()), None)
    if not city or not district:
        await message.answer(t(lang, "district_error"), reply_markup=keyboard)
        return

    station_payload = {
        "station_code": data["code"],
        "name": data["name"],
        "city_id": city["id"],
        "district_id": district["id"],
        "address": data["address"],
        "vpn_ip": data["vpn_ip"],
        "local_ip": data["local_ip"],
        "rustdesk_id": data.get("rustdesk_id"),
        "latitude": data["lat"],
        "longitude": data["lng"],
    }

    try:
        saved, outcome = await _save_station(station_payload, allow_approved=bool(data.get("existing_approved")))
    except BackendAPIError as exc:
        await message.answer(f"{t(lang, 'api_error')} {exc.message}", reply_markup=keyboard)
        return
    station_id = saved.get("id")
    rustdesk_id = data.get("rustdesk_id")
    if station_id and rustdesk_id:
        try:
            await api.update_rustdesk(station_id, rustdesk_id)
        except BackendAPIError as exc:
            await message.answer(f"{t(lang, 'api_error')} RustDesk: {exc.message}")

    await _clear_keep_lang(state, lang)
    await message.answer(t(lang, outcome), reply_markup=main_keyboard(lang))


def _missing_backend_fields(data: dict) -> list[str]:
    missing = []
    if not data.get("region"):
        missing.append("District")
    return missing


def _summary(lang: str, data: dict) -> str:
    gps = "-"
    if data.get("lat") is not None and data.get("lng") is not None:
        gps = f"{data['lat']:.6f}, {data['lng']:.6f}"

    rows = [
        t(lang, "summary_title"),
        "",
        f"{t(lang, 'label_code')}: {data.get('code', '-')}",
        f"{t(lang, 'label_name')}: {data.get('name', '-')}",
        f"{t(lang, 'label_district')}: {_localized_district(lang, data.get('region'))}",
        f"{t(lang, 'label_address')}: {data.get('address', '-')}",
        f"{t(lang, 'label_vpn')}: {data.get('vpn_ip') or '-'}",
        f"{t(lang, 'label_local')}: {data.get('local_ip') or '-'}",
        f"{t(lang, 'label_rustdesk')}: {data.get('rustdesk_id') or '-'}",
        f"{t(lang, 'label_gps')}: {gps}",
        f"{t(lang, 'label_record_status')}: {t(lang, 'record_existing') if data.get('existing_station_id') else t(lang, 'record_new')}",
        f"{t(lang, 'label_approval')}: {t(lang, 'approval_approved') if data.get('existing_approved') else t(lang, 'approval_pending')}",
    ]
    missing = _missing_backend_fields(data)
    if missing:
        rows.extend(["", t(lang, "missing_backend"), f"{t(lang, 'missing_fields')} {', '.join(missing)}"])
    return "\n".join(rows)


async def _save_station(payload: dict, *, allow_approved: bool = False) -> tuple[dict, str]:
    existing = await api.station_by_code(str(payload["station_code"]))
    if existing:
        if existing.get("approved_at") and not allow_approved:
            raise BackendAPIError("Approved station update requires explicit confirmation", 409)
        update_payload = {key: value for key, value in payload.items() if key != "station_code"}
        saved = await api.update_station(int(existing["id"]), update_payload)
        outcome = "saved_approved" if existing.get("approved_at") else "saved_existing_pending"
        return saved, outcome
    try:
        created = await api.create_station(payload)
        return created, "saved_new_pending"
    except BackendAPIError as exc:
        if exc.status_code != 409:
            raise
        existing = await api.station_by_code(str(payload["station_code"]))
        if not existing:
            raise BackendAPIError("Station inventory changed; try again", 409) from exc
        if existing.get("approved_at") and not allow_approved:
            raise BackendAPIError("Approved station update requires explicit confirmation", 409) from exc
        update_payload = {key: value for key, value in payload.items() if key != "station_code"}
        saved = await api.update_station(int(existing["id"]), update_payload)
        outcome = "saved_approved" if existing.get("approved_at") else "saved_existing_pending"
        return saved, outcome


def _canonical_district(value: str) -> str | None:
    aliases = {
        "ismoili somoni": "Ismoili Somoni", "исмоили сомони": "Ismoili Somoni", "исмоили сомонӣ": "Ismoili Somoni",
        "shohmansur": "Shohmansur", "шохмансур": "Shohmansur", "шоҳмансур": "Shohmansur",
        "sino": "Sino", "сино": "Sino",
        "firdavsi": "Firdavsi", "фирдавси": "Firdavsi", "фирдавсӣ": "Firdavsi",
    }
    return aliases.get(value.strip().casefold())


def _existing_station_text(lang: str, station: dict) -> str:
    rows = [
        f"{t(lang, 'label_name')}: {station.get('name') or '-'}",
        f"{t(lang, 'label_district')}: {_localized_district(lang, station.get('district'))}",
        f"{t(lang, 'label_address')}: {station.get('address') or '-'}",
        f"{t(lang, 'label_vpn')}: {station.get('vpn_ip') or '-'}",
        f"{t(lang, 'label_local')}: {station.get('local_ip') or '-'}",
        f"{t(lang, 'label_rustdesk')}: {station.get('rustdesk_id') or '-'}",
        f"{t(lang, 'label_approval')}: {t(lang, 'approval_approved') if station.get('approved_at') else t(lang, 'approval_pending')}",
    ]
    return "\n".join(rows)


def _localized_district(lang: str, value: str | None) -> str:
    canonical = _canonical_district(value or "") or value or "-"
    labels = {
        "ru": {"Ismoili Somoni": "Исмоили Сомони", "Shohmansur": "Шохмансур", "Sino": "Сино", "Firdavsi": "Фирдавси"},
        "tj": {"Ismoili Somoni": "Исмоили Сомонӣ", "Shohmansur": "Шоҳмансур", "Sino": "Сино", "Firdavsi": "Фирдавсӣ"},
    }
    return labels.get(lang, {}).get(canonical, canonical)
