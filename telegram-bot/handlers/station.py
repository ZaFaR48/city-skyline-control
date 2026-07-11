from __future__ import annotations

import secrets

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import BackendAPIError, api
from i18n import all_menu_labels, all_texts, t
from keyboards import location_keyboard, main_keyboard, navigation_keyboard, wizard_inline
from states import AddStation
from validators import clean_text, is_valid_station_code, normalize_station_code


router = Router()
DISTRICTS = {
    "ismoili-somoni": "Ismoili Somoni",
    "shohmansur": "Shohmansur",
    "sino": "Sino",
    "firdavsi": "Firdavsi",
}
DISTRICT_LABELS = {
    "ru": {"ismoili-somoni": "Исмоили Сомони", "shohmansur": "Шохмансур", "sino": "Сино", "firdavsi": "Фирдавси"},
    "tj": {"ismoili-somoni": "Исмоили Сомонӣ", "shohmansur": "Шоҳмансур", "sino": "Сино", "firdavsi": "Фирдавсӣ"},
    "en": DISTRICTS,
}


async def _lang(state: FSMContext) -> str:
    return (await state.get_data()).get("lang", "tj")


async def _finish(state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.update_data(lang=lang)


def _step(lang: str, number: int, text: str) -> str:
    return f"{t(lang, 'wizard_step').format(step=number)} — {text}"


def _cb(nonce: str, step: str, value: str) -> str:
    return f"sw:{nonce}:{step}:{value}"


@router.message(StateFilter(AddStation), lambda message: message.text in all_texts("cancel"))
async def cancel_station(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    await _finish(state, lang)
    await message.answer(t(lang, "cancelled"), reply_markup=main_keyboard(lang))


@router.message(StateFilter(AddStation), lambda message: message.text in all_texts("back"))
async def back_station(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    current = await state.get_state()
    if current == AddStation.operational_area.state:
        await _prompt_district(message, state, lang)
    elif current == AddStation.address.state:
        await _prompt_area(message, state, lang)
    elif current == AddStation.name.state:
        await _prompt_name_choice(message, state, lang)
    elif current == AddStation.gps.state:
        await _prompt_name_choice(message, state, lang)
    elif current == AddStation.code.state:
        await _finish(state, lang)
        await message.answer(t(lang, "cancelled"), reply_markup=main_keyboard(lang))
    else:
        await state.set_state(AddStation.code)
        await message.answer(_step(lang, 1, t(lang, "enter_code")), reply_markup=navigation_keyboard(lang))


@router.message(lambda message: message.text in all_menu_labels("new_station"))
async def station_start(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    await _finish(state, lang)
    await state.update_data(nonce=secrets.token_hex(4), saving=False)
    await state.set_state(AddStation.code)
    await message.answer(_step(lang, 1, t(lang, "enter_code")), reply_markup=navigation_keyboard(lang))


@router.message(AddStation.code)
async def station_code(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    code = normalize_station_code(message.text)
    if not is_valid_station_code(code):
        await message.answer(t(lang, "invalid_station_code"))
        return
    try:
        existing = await api.station_by_code(code)
    except BackendAPIError as exc:
        await message.answer(f"{t(lang, 'api_error')} {exc.message}")
        return
    await state.update_data(code=code, existing_station_id=existing.get("id") if existing else None, existing=existing)
    if existing:
        await state.set_state(AddStation.existing_action)
        nonce = (await state.get_data())["nonce"]
        notice = t(lang, "station_exists_approved") if existing.get("approved_at") else t(lang, "existing_edit_notice")
        await message.answer(
            f"{notice.format(code=code)}\n\n{_current_station(lang, existing)}",
            reply_markup=wizard_inline([
                [(t(lang, "keep_current"), _cb(nonce, "existing", "keep"))],
                [(t(lang, "edit_station"), _cb(nonce, "existing", "edit"))],
                [(t(lang, "cancel"), _cb(nonce, "existing", "cancel"))],
            ]),
        )
    else:
        await _prompt_city(message, state, lang)


@router.callback_query(F.data.startswith("sw:"))
async def station_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return
    lang = await _lang(state)
    parts = (callback.data or "").split(":", 3)
    if len(parts) != 4:
        await callback.answer(t(lang, "stale_action"), show_alert=True)
        return
    _, nonce, step, value = parts
    data = await state.get_data()
    if nonce != data.get("nonce"):
        await callback.answer(t(lang, "stale_action"), show_alert=True)
        return
    if value == "cancel":
        await _finish(state, lang)
        await callback.message.answer(t(lang, "cancelled"), reply_markup=main_keyboard(lang))
        await callback.answer()
        return
    expected = {
        "existing": AddStation.existing_action.state,
        "city": AddStation.city.state,
        "district": AddStation.district.state,
        "name": AddStation.name_choice.state,
        "confirm": AddStation.confirm.state,
    }.get(step)
    if expected is None or await state.get_state() != expected:
        await callback.answer(t(lang, "stale_action"), show_alert=True)
        return

    if step == "existing":
        if value == "keep":
            await _finish(state, lang)
            await callback.message.answer(t(lang, "no_changes"), reply_markup=main_keyboard(lang))
        elif value == "edit":
            await _prompt_city(callback.message, state, lang)
    elif step == "city":
        if value == "back":
            await _prompt_existing_action(callback.message, state, lang)
        elif value == "dushanbe":
            await state.update_data(city_code="dushanbe", city_name="Dushanbe")
            await _prompt_district(callback.message, state, lang)
    elif step == "district":
        if value == "back":
            await _prompt_city(callback.message, state, lang)
        elif value in DISTRICTS:
            await state.update_data(district_code=value, district_name=DISTRICTS[value])
            await _prompt_area(callback.message, state, lang)
    elif step == "name":
        if value == "back":
            await _prompt_address(callback.message, state, lang)
        elif value == "keep":
            await state.update_data(name_changed=False)
            await _prompt_gps(callback.message, state, lang)
        elif value == "suggested":
            await state.update_data(name=(await state.get_data()).get("suggested_name"), name_changed=True)
            await _prompt_gps(callback.message, state, lang)
        elif value == "change":
            await state.set_state(AddStation.name)
            await callback.message.answer(_step(lang, 6, t(lang, "name_prompt")), reply_markup=navigation_keyboard(lang))
    elif step == "confirm":
        if value == "back":
            await _prompt_gps(callback.message, state, lang)
        elif value == "save":
            await _save(callback, state, lang)
            return
    await callback.answer()


async def _prompt_existing_action(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    existing = data.get("existing")
    if not existing:
        await state.set_state(AddStation.code)
        await message.answer(_step(lang, 1, t(lang, "enter_code")), reply_markup=navigation_keyboard(lang))
        return
    await state.set_state(AddStation.existing_action)
    nonce = data["nonce"]
    await message.answer(
        f"{t(lang, 'existing_edit_notice').format(code=data['code'])}\n\n{_current_station(lang, existing)}",
        reply_markup=wizard_inline([
            [(t(lang, "keep_current"), _cb(nonce, "existing", "keep"))],
            [(t(lang, "edit_station"), _cb(nonce, "existing", "edit"))],
            [(t(lang, "cancel"), _cb(nonce, "existing", "cancel"))],
        ]),
    )


async def _prompt_city(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(AddStation.city)
    data = await state.get_data()
    back = "back"
    await message.answer(
        _step(lang, 2, t(lang, "select_city")),
        reply_markup=wizard_inline([
            [(t(lang, "city_dushanbe"), _cb(data["nonce"], "city", "dushanbe"))],
            [(t(lang, "back"), _cb(data["nonce"], "city", back)), (t(lang, "cancel"), _cb(data["nonce"], "city", "cancel"))],
        ]),
    )


async def _prompt_district(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(AddStation.district)
    nonce = (await state.get_data())["nonce"]
    rows = [[(DISTRICT_LABELS[lang][code], _cb(nonce, "district", code))] for code in DISTRICTS]
    rows.append([(t(lang, "back"), _cb(nonce, "district", "back")), (t(lang, "cancel"), _cb(nonce, "district", "cancel"))])
    await message.answer(_step(lang, 3, t(lang, "select_district")), reply_markup=wizard_inline(rows))


async def _prompt_area(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(AddStation.operational_area)
    existing = (await state.get_data()).get("existing")
    current = f"\n{t(lang, 'label_operational_area')}: {existing.get('operational_area') or '—'}" if existing else ""
    await message.answer(_step(lang, 4, t(lang, "area_prompt")) + current, reply_markup=navigation_keyboard(lang, allow_skip=True, keep_existing=bool(existing)))


@router.message(AddStation.operational_area)
async def station_area(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    if value in all_texts("keep_existing_field") or value in all_texts("skip_now"):
        await state.update_data(operational_area_changed=False)
    elif not value:
        await message.answer(t(lang, "invalid_required"))
        return
    else:
        await state.update_data(operational_area=value, operational_area_changed=True)
    await _prompt_address(message, state, lang)


async def _prompt_address(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(AddStation.address)
    existing = (await state.get_data()).get("existing")
    current = f"\n{t(lang, 'label_address')}: {existing.get('address') or '—'}" if existing else ""
    await message.answer(_step(lang, 5, t(lang, "address_prompt")) + current, reply_markup=navigation_keyboard(lang, allow_skip=bool(existing), keep_existing=True))


@router.message(AddStation.address)
async def station_address(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    existing = (await state.get_data()).get("existing")
    if value in all_texts("keep_existing_field") and existing:
        await state.update_data(address_changed=False)
    elif not value:
        await message.answer(t(lang, "invalid_required"))
        return
    else:
        await state.update_data(address=value, address_changed=True)
    data = await state.get_data()
    suggestion = _suggest_name(data)
    await state.update_data(suggested_name=suggestion)
    await _prompt_name_choice(message, state, lang)


async def _prompt_name_choice(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(AddStation.name_choice)
    data = await state.get_data()
    nonce = data["nonce"]
    existing = data.get("existing")
    rows = []
    if existing:
        rows.extend([
            [(t(lang, "keep_station_name"), _cb(nonce, "name", "keep"))],
            [(t(lang, "change_station_name"), _cb(nonce, "name", "change"))],
        ])
        text = f"{_step(lang, 6, t(lang, 'name_prompt'))}\n{t(lang, 'label_name')}: {existing.get('name')}"
    else:
        rows.extend([
            [(t(lang, "use_suggested_name"), _cb(nonce, "name", "suggested"))],
            [(t(lang, "change_station_name"), _cb(nonce, "name", "change"))],
        ])
        text = f"{_step(lang, 6, t(lang, 'name_prompt'))}\n{t(lang, 'suggested_name').format(name=data.get('suggested_name'))}"
    rows.append([(t(lang, "back"), _cb(nonce, "name", "back")), (t(lang, "cancel"), _cb(nonce, "name", "cancel"))])
    await message.answer(text, reply_markup=wizard_inline(rows))


@router.message(AddStation.name)
async def station_name(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    if not value:
        await message.answer(t(lang, "invalid_required"))
        return
    await state.update_data(name=value, name_changed=True)
    await _prompt_gps(message, state, lang)


async def _prompt_gps(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(AddStation.gps)
    await message.answer(_step(lang, 7, t(lang, "gps_prompt")), reply_markup=location_keyboard(lang))


@router.message(AddStation.gps)
async def station_gps(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if message.location:
        lat, lng = message.location.latitude, message.location.longitude
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            await message.answer(t(lang, "invalid_location"), reply_markup=location_keyboard(lang))
            return
        await state.update_data(latitude=lat, longitude=lng, gps_changed=True)
    elif clean_text(message.text) in all_texts("skip_now"):
        await state.update_data(gps_changed=False)
    else:
        await message.answer(t(lang, "invalid_location"), reply_markup=location_keyboard(lang))
        return
    await _prompt_confirm(message, state, lang)


async def _prompt_confirm(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    try:
        current = await api.station_by_code(data["code"])
    except BackendAPIError as exc:
        await message.answer(f"{t(lang, 'api_error')} {exc.message}")
        return
    if data.get("existing_station_id") and (not current or current.get("id") != data["existing_station_id"]):
        await message.answer(t(lang, "stale_action"))
        return
    if not data.get("existing_station_id") and current:
        await message.answer(t(lang, "stale_action"))
        return
    if current:
        await state.update_data(existing=current)
    try:
        regions = await api.regions()
    except BackendAPIError as exc:
        await message.answer(f"{t(lang, 'api_error')} {exc.message}")
        return
    city = next((item for item in regions if item.get("code") == data.get("city_code")), None)
    district = next((item for item in regions if item.get("code") == data.get("district_code")), None)
    if not city or not district:
        await message.answer(t(lang, "stale_action"))
        return
    await state.update_data(city_id=city["id"], district_id=district["id"])
    data = await state.get_data()
    await state.set_state(AddStation.confirm)
    nonce = data["nonce"]
    action_label = t(lang, "save_changes") if current else t(lang, "create_station")
    await message.answer(
        _summary(lang, data),
        reply_markup=wizard_inline([
            [(action_label, _cb(nonce, "confirm", "save"))],
            [(t(lang, "back"), _cb(nonce, "confirm", "back")), (t(lang, "cancel"), _cb(nonce, "confirm", "cancel"))],
        ]),
    )


async def _save(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    if data.get("saving"):
        await callback.answer(t(lang, "saving"), show_alert=True)
        return
    await state.update_data(saving=True)
    try:
        regions = await api.regions()
        city = next((item for item in regions if item.get("code") == data["city_code"]), None)
        district = next((item for item in regions if item.get("code") == data["district_code"]), None)
        if not city or not district:
            raise BackendAPIError("Canonical region data is unavailable", 409)
        current = await api.station_by_code(data["code"])
        if data.get("existing_station_id"):
            if not current or current.get("id") != data["existing_station_id"]:
                raise BackendAPIError("Station changed; restart the wizard", 409)
            patch, _ = _build_patch(current, data, city["id"], district["id"])
            if patch:
                await api.update_station(int(current["id"]), patch)
            message = t(lang, "saved_approved") if current.get("approved_at") else t(lang, "saved_existing_pending").format(code=data["code"])
        else:
            if current:
                raise BackendAPIError("Station code now exists; restart the wizard", 409)
            payload = _build_create(data, city["id"], district["id"])
            await api.create_station(payload)
            message = t(lang, "saved_new_pending")
    except BackendAPIError as exc:
        await state.update_data(saving=False)
        await callback.answer(exc.message, show_alert=True)
        return
    await _finish(state, lang)
    await callback.message.answer(message, reply_markup=main_keyboard(lang))
    await callback.answer()


def _build_patch(existing: dict, data: dict, city_id: int, district_id: int) -> tuple[dict, list[tuple[str, object, object]]]:
    proposed: dict[str, object] = {"city_id": city_id, "district_id": district_id}
    if data.get("operational_area_changed"):
        proposed["operational_area"] = data.get("operational_area")
    if data.get("address_changed"):
        proposed["address"] = data.get("address")
    if data.get("name_changed"):
        proposed["name"] = data.get("name")
    if data.get("gps_changed"):
        proposed["latitude"] = data.get("latitude")
        proposed["longitude"] = data.get("longitude")
    current_values = {**existing, "city_id": existing.get("city_id"), "district_id": existing.get("district_id")}
    patch = {key: value for key, value in proposed.items() if current_values.get(key) != value}
    diffs = [(key, current_values.get(key), value) for key, value in patch.items()]
    return patch, diffs


def _build_create(data: dict, city_id: int, district_id: int) -> dict:
    return {
        "station_code": data["code"], "name": data["name"], "city_id": city_id,
        "district_id": district_id, "operational_area": data.get("operational_area"),
        "address": data["address"], "latitude": data.get("latitude"), "longitude": data.get("longitude"),
    }


def _summary(lang: str, data: dict) -> str:
    existing = data.get("existing")
    if existing:
        _, diffs = _build_patch(existing, data, data.get("city_id", existing.get("city_id")), data.get("district_id", existing.get("district_id")))
        rows = [t(lang, "diff_title")]
        rows.extend(f"{key}: {old if old not in (None, '') else '—'} → {new if new not in (None, '') else '—'}" for key, old, new in diffs)
        if not diffs:
            rows.append(t(lang, "no_field_changes"))
        rows.append(f"{t(lang, 'label_approval')}: {t(lang, 'approval_approved') if existing.get('approved_at') else t(lang, 'approval_pending')}")
        return "\n".join(rows)
    gps = f"{data['latitude']:.6f}, {data['longitude']:.6f}" if data.get("gps_changed") else "—"
    return "\n".join([
        t(lang, "summary_title"), f"{t(lang, 'label_code')}: {data.get('code')}",
        f"{t(lang, 'label_name')}: {data.get('name')}", f"{t(lang, 'label_district')}: {data.get('district_name')}",
        f"{t(lang, 'label_operational_area')}: {data.get('operational_area') or '—'}", f"{t(lang, 'label_address')}: {data.get('address')}",
        f"{t(lang, 'label_gps')}: {gps}", f"{t(lang, 'label_approval')}: {t(lang, 'approval_pending')}",
    ])


def _suggest_name(data: dict) -> str:
    area = clean_text(data.get("operational_area"))
    address = clean_text(data.get("address"))
    district = data.get("district_name") or "Station"
    detail = area or address[:48] or data["code"]
    return f"{district} — {detail}"[:128]


def _current_station(lang: str, station: dict) -> str:
    return "\n".join([
        f"{t(lang, 'label_code')}: {station.get('station_code')}", f"{t(lang, 'label_name')}: {station.get('name')}",
        f"{t(lang, 'label_city')}: {station.get('city') or '—'}", f"{t(lang, 'label_district')}: {station.get('district') or '—'}",
        f"{t(lang, 'label_operational_area')}: {station.get('operational_area') or '—'}",
        f"{t(lang, 'label_address')}: {station.get('address') or '—'}", f"{t(lang, 'label_vpn')}: {station.get('vpn_ip') or '—'}",
        f"{t(lang, 'label_local')}: {station.get('local_ip') or '—'}", f"{t(lang, 'label_rustdesk')}: {station.get('rustdesk_id') or '—'}",
        f"{t(lang, 'label_gps')}: {station.get('latitude') or '—'}, {station.get('longitude') or '—'}",
        f"{t(lang, 'label_approval')}: {t(lang, 'approval_approved') if station.get('approved_at') else t(lang, 'approval_pending')}",
    ])
