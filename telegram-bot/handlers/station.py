from __future__ import annotations

import asyncio
import secrets
from types import SimpleNamespace
from uuid import uuid4

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import BackendAPIError, api
from authorization import require_telegram_roles
from i18n import all_menu_labels, all_texts, localized_error, t
from keyboards import finished_workflow_keyboard, location_keyboard, main_keyboard, navigation_keyboard, wizard_inline
from states import RegisterStation, UpdateStation
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
_LOCKS: dict[int, asyncio.Lock] = {}


async def _lang(state: FSMContext) -> str:
    return (await state.get_data()).get("lang", "tj")


def _lock(message: Message) -> asyncio.Lock:
    chat_id = getattr(getattr(message, "chat", None), "id", 0)
    return _LOCKS.setdefault(chat_id, asyncio.Lock())


async def _finish(state: FSMContext) -> None:
    lang = await _lang(state)
    await state.clear()
    await state.update_data(lang=lang)


async def _disable_prompt(message: Message, message_id: int | None) -> None:
    bot = getattr(message, "bot", None)
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if not bot or not chat_id or not message_id:
        return
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    except Exception:
        pass


async def cancel_active_station_workflow(message: Message, state: FSMContext) -> tuple[str, str | None]:
    data = await state.get_data()
    lang = data.get("lang", "tj")
    role = data.get("role")
    await _disable_prompt(message, data.get("prompt_message_id"))
    if data.get("workflow_id") and data.get("telegram_user_id"):
        await _track(state, "telegram.station_workflow.cancelled", "cancelled", status="cancelled")
    await state.clear()
    await state.update_data(lang=lang, role=role)
    return lang, role


async def _start(state: FSMContext, mode: str, user, message: Message) -> str:
    previous = await state.get_data()
    lang = previous.get("lang", "tj")
    role = previous.get("role")
    await cancel_active_station_workflow(message, state)
    await state.clear()
    workflow_id = str(uuid4())
    await state.update_data(
        lang=lang,
        mode=mode,
        nonce=workflow_id.replace("-", "")[:10],
        version=0,
        saving=False,
        workflow_id=workflow_id,
        correlation_id=secrets.token_hex(12),
        telegram_user_id=user.id,
        telegram_username=user.username,
        chat_id=getattr(getattr(message, "chat", None), "id", None),
        role=role,
        user_id=previous.get("user_id"),
    )
    return lang


def _actor(data: dict):
    return SimpleNamespace(id=data["telegram_user_id"], username=data.get("telegram_username"))


async def _track(state: FSMContext, action: str, step: str, *, status: str = "in_progress", **extra) -> dict | None:
    data = await state.get_data()
    if not data.get("workflow_id"):
        return None
    extra.setdefault("version", int(data.get("version", 0)))
    extra.setdefault("active_prompt_message_id", data.get("prompt_message_id"))
    try:
        return await api.station_workflow_event(
            _actor(data),
            data["workflow_id"],
            {"action": action, "status": status, "current_step": step, **extra},
        )
    except BackendAPIError:
        return None


def _cb(data: dict, action: str, value: str = "-") -> str:
    return f"st:{data['nonce']}:{data['version']}:{action}:{value}"


async def _advance(state: FSMContext, target) -> dict:
    data = await state.get_data()
    await state.update_data(version=int(data.get("version", 0)) + 1)
    await state.set_state(target)
    return await state.get_data()


async def _prompt(message: Message, state: FSMContext, text: str, *, reply_markup=None) -> None:
    data = await state.get_data()
    old_id = data.get("prompt_message_id")
    bot = getattr(message, "bot", None)
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    if old_id and bot and chat_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=old_id, text=text, reply_markup=reply_markup)
            await state.update_data(prompt_message_id=old_id)
            current_state = (await state.get_state()) or "prompt"
            await _track(state, "telegram.station_prompt.activated", str(current_state).rsplit(":", 1)[-1])
            return
        except Exception:
            await _disable_prompt(message, old_id)
    sent = await message.answer(text, reply_markup=reply_markup)
    message_id = getattr(sent, "message_id", None)
    if message_id is not None:
        await state.update_data(prompt_message_id=message_id)
        current_state = (await state.get_state()) or "prompt"
        await _track(state, "telegram.station_prompt.activated", str(current_state).rsplit(":", 1)[-1])


async def _finish_old_callback(callback: CallbackQuery, lang: str) -> None:
    try:
        await callback.message.edit_text(t(lang, "workflow_finished"), reply_markup=finished_workflow_keyboard(lang))
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=finished_workflow_keyboard(lang))
        except Exception:
            pass


@router.callback_query(F.data == "menu:current")
async def current_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    lang = data.get("lang", "tj")
    await callback.message.answer(t(lang, "main_menu"), reply_markup=main_keyboard(lang, role=data.get("role")))


@router.message(StateFilter(RegisterStation, UpdateStation), lambda message: message.text in all_texts("cancel"))
@router.message(Command("cancel"))
async def cancel_station(message: Message, state: FSMContext) -> None:
    lang, role = await cancel_active_station_workflow(message, state)
    await message.answer(t(lang, "cancelled"), reply_markup=main_keyboard(lang, role=role))


@router.message(lambda message: message.text in all_menu_labels("register_station"))
async def register_start(message: Message, state: FSMContext) -> None:
    if not await require_telegram_roles(message, state, "admin", "operator"):
        await message.answer(t(await _lang(state), "ops_denied"))
        return
    lang = await _start(state, "create", message.from_user, message)
    await state.set_state(RegisterStation.code)
    data = await state.get_data()
    try:
        result = await api.start_station_workflow(
            message.from_user,
            workflow_id=data["workflow_id"],
            workflow_type="registration",
            mode="create",
            station_code=None,
            current_step="station_code",
            correlation_id=data["correlation_id"],
        )
        for message_id in result.get("cancelled_prompt_message_ids", []):
            await _disable_prompt(message, message_id)
    except BackendAPIError as exc:
        await state.clear()
        await message.answer(localized_error(lang, exc.message))
        return
    await _prompt(message, state, t(lang, "register_code"), reply_markup=navigation_keyboard(lang))


@router.message(lambda message: message.text in all_menu_labels("update_station"))
async def update_start(message: Message, state: FSMContext) -> None:
    if not await require_telegram_roles(message, state, "admin", "operator"):
        await message.answer(t(await _lang(state), "ops_denied"))
        return
    lang = await _start(state, "update", message.from_user, message)
    await state.set_state(UpdateStation.code)
    data = await state.get_data()
    try:
        result = await api.start_station_workflow(
            message.from_user,
            workflow_id=data["workflow_id"],
            workflow_type="update",
            mode="update",
            station_code=None,
            current_step="station_code",
            correlation_id=data["correlation_id"],
        )
        for message_id in result.get("cancelled_prompt_message_ids", []):
            await _disable_prompt(message, message_id)
    except BackendAPIError as exc:
        await state.clear()
        await message.answer(localized_error(lang, exc.message))
        return
    await _prompt(message, state, t(lang, "update_code"), reply_markup=navigation_keyboard(lang))


@router.message(RegisterStation.code)
async def register_code(message: Message, state: FSMContext) -> None:
    async with _lock(message):
        if await state.get_state() != RegisterStation.code.state:
            return
        lang = await _lang(state)
        code = normalize_station_code(message.text)
        if not is_valid_station_code(code):
            await _track(state, "telegram.validation_failed", "station_code", failure_reason="invalid station code")
            await message.answer(t(lang, "invalid_station_code"))
            return
        try:
            existing = await api.station_by_code(code)
        except BackendAPIError as exc:
            await message.answer(localized_error(lang, exc.message))
            return
        await state.update_data(code=code)
        await _track(state, "telegram.station_field.changed", "station_code", station_code=code, changed_fields=["station_code"], after_data={"station_code": code})
        if existing:
            await state.update_data(existing=existing, existing_station_id=existing["id"])
            data = await _advance(state, RegisterStation.existing_offer)
            await _track(state, "telegram.duplicate_station.detected", "existing_station", station_id=existing["id"], station_code=code)
            await _prompt(
                message,
                state,
                f"{t(lang, 'existing_create_blocked').format(code=code)}\n\n{_current_station(lang, existing)}",
                reply_markup=wizard_inline([
                    [(t(lang, "open_existing_update"), _cb(data, "open_update"))],
                    [(t(lang, "open_station_info"), _cb(data, "open_info"))],
                    [(t(lang, "cancel"), _cb(data, "cancel"))],
                ]),
            )
            return
        await _show_create_city(message, state, lang)


@router.message(UpdateStation.code)
async def update_code(message: Message, state: FSMContext) -> None:
    async with _lock(message):
        if await state.get_state() != UpdateStation.code.state:
            return
        lang = await _lang(state)
        code = normalize_station_code(message.text)
        if not is_valid_station_code(code):
            await _track(state, "telegram.validation_failed", "station_code", failure_reason="invalid station code")
            await message.answer(t(lang, "invalid_station_code"))
            return
        try:
            existing = await api.station_by_code(code)
        except BackendAPIError as exc:
            await message.answer(localized_error(lang, exc.message))
            return
        if not existing:
            await _track(state, "telegram.validation_failed", "station_code", failure_reason="station not found")
            await message.answer(t(lang, "update_not_found"))
            return
        await state.update_data(code=code, existing=existing, existing_station_id=existing["id"])
        await _track(state, "telegram.station_update.started", "field_selection", station_id=existing["id"], station_code=code)
        await _show_update_menu(message, state, lang)


@router.callback_query(F.data.startswith("st:"))
async def station_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.answer()
    async with _lock(callback.message):
        lang = await _lang(state)
        parts = (callback.data or "").split(":", 4)
        data = await state.get_data()
        active_prompt = data.get("prompt_message_id")
        callback_prompt = getattr(callback.message, "message_id", None)
        actor_ok = callback.from_user and callback.from_user.id == data.get("telegram_user_id")
        if (len(parts) != 5 or parts[1] != data.get("nonce") or not parts[2].isdigit()
                or int(parts[2]) != data.get("version") or not actor_ok
                or (active_prompt is not None and callback_prompt != active_prompt)):
            await _finish_old_callback(callback, lang)
            return
        action, value = parts[3], parts[4]
        if action == "cancel":
            role = data.get("role")
            await _track(state, "telegram.station_workflow.cancelled", "cancelled", status="cancelled")
            await _disable_prompt(callback.message, data.get("prompt_message_id"))
            await state.clear()
            await callback.message.answer(t(lang, "cancelled"), reply_markup=main_keyboard(lang, role=role))
            return
        if not await require_telegram_roles(callback, state, "admin", "operator"):
            await _track(state, "telegram.permission_denied", "authorization", status="failed", failure_reason="role changed")
            await state.clear()
            return
        if action == "open_update" and await state.get_state() == RegisterStation.existing_offer.state:
            existing = data["existing"]
            role, user_id = data.get("role"), data.get("user_id")
            await _track(state, "telegram.station_workflow.cancelled", "cancelled", status="cancelled")
            await _disable_prompt(callback.message, data.get("prompt_message_id"))
            await state.clear()
            await state.update_data(lang=lang, role=role, user_id=user_id)
            await _start(state, "update", callback.from_user, callback.message)
            new_data = await state.get_data()
            try:
                await api.start_station_workflow(
                    callback.from_user, workflow_id=new_data["workflow_id"], workflow_type="update",
                    mode="update", station_code=existing["station_code"], current_step="field_selection",
                    correlation_id=new_data["correlation_id"],
                )
            except BackendAPIError as exc:
                await state.clear()
                await callback.message.answer(localized_error(lang, exc.message), reply_markup=main_keyboard(lang, role=role))
                return
            await state.update_data(code=existing["station_code"], existing=existing, existing_station_id=existing["id"])
            await _show_update_menu(callback.message, state, lang)
        elif action == "open_info" and await state.get_state() == RegisterStation.existing_offer.state:
            await _track(state, "telegram.station_workflow.cancelled", "cancelled", status="cancelled")
            role = data.get("role")
            await _disable_prompt(callback.message, data.get("prompt_message_id"))
            await _finish(state)
            await callback.message.answer(_current_station(lang, data["existing"]), reply_markup=main_keyboard(lang, role=role))
        elif action == "create_city" and await state.get_state() == RegisterStation.city.state:
            if value == "back":
                await _advance(state, RegisterStation.code)
                await _prompt(callback.message, state, t(lang, "register_code"), reply_markup=navigation_keyboard(lang))
            else:
                await state.update_data(city_code="dushanbe", city_name="Dushanbe")
                await _track(state, "telegram.station_field.changed", "city", changed_fields=["city_id"])
                await _show_create_district(callback.message, state, lang)
        elif action == "create_district" and await state.get_state() == RegisterStation.district.state:
            if value == "back":
                await _show_create_city(callback.message, state, lang)
            elif value in DISTRICTS:
                await state.update_data(district_code=value, district_name=DISTRICTS[value])
                await _track(state, "telegram.station_field.changed", "district", changed_fields=["district_id"])
                await _prompt_create_text(callback.message, state, lang, RegisterStation.operational_area, 4, "area_prompt")
        elif action == "create_name_default" and await state.get_state() == RegisterStation.name.state:
            if value == "back":
                await _prompt_create_text(callback.message, state, lang, RegisterStation.address, 5, "address_prompt")
            else:
                await state.update_data(name=data["suggested_name"])
                await _track(state, "telegram.station_field.changed", "name", changed_fields=["name"], after_data={"name": data["suggested_name"]})
                await _prompt_create_gps(callback.message, state, lang)
        elif action == "create_save" and await state.get_state() == RegisterStation.confirm.state:
            if value == "back":
                await _prompt_create_gps(callback.message, state, lang)
            elif value == data.get("preview_hash"):
                await _save_create(callback, state, lang)
                return
        elif action == "update_field" and await state.get_state() == UpdateStation.menu.state:
            await _select_update_field(callback.message, state, lang, value)
        elif action == "update_city" and await state.get_state() == UpdateStation.city.state:
            if value == "back":
                await _show_update_menu(callback.message, state, lang)
            else:
                await _prepare_region_patch(callback.message, state, lang, city_code="dushanbe")
        elif action == "update_district" and await state.get_state() == UpdateStation.district.state:
            if value == "back":
                await _show_update_menu(callback.message, state, lang)
            elif value in DISTRICTS:
                await _prepare_region_patch(callback.message, state, lang, district_code=value)
        elif action == "update_confirm" and await state.get_state() == UpdateStation.confirm.state:
            if value == "back":
                await _show_update_menu(callback.message, state, lang)
            elif value == data.get("preview_hash"):
                await _save_update(callback, state, lang)
                return
        elif action == "choose_field" and await state.get_state() == UpdateStation.confirm.state:
            await _show_update_menu(callback.message, state, lang)
        else:
            await _finish_old_callback(callback, lang)
            return


async def _show_create_city(message: Message, state: FSMContext, lang: str) -> None:
    data = await _advance(state, RegisterStation.city)
    await _prompt(
        message,
        state,
        f"{t(lang, 'wizard_step').format(step=2)} — {t(lang, 'select_city')}",
        reply_markup=wizard_inline([
            [(t(lang, "city_dushanbe"), _cb(data, "create_city", "dushanbe"))],
            [(t(lang, "back"), _cb(data, "create_city", "back")), (t(lang, "cancel"), _cb(data, "cancel"))],
        ]),
    )


async def _show_create_district(message: Message, state: FSMContext, lang: str) -> None:
    data = await _advance(state, RegisterStation.district)
    rows = [[(DISTRICT_LABELS[lang][code], _cb(data, "create_district", code))] for code in DISTRICTS]
    rows.append([(t(lang, "back"), _cb(data, "create_district", "back")), (t(lang, "cancel"), _cb(data, "cancel"))])
    await _prompt(message, state, f"{t(lang, 'wizard_step').format(step=3)} — {t(lang, 'select_district')}", reply_markup=wizard_inline(rows))


async def _prompt_create_text(message: Message, state: FSMContext, lang: str, target, step: int, key: str, *, allow_skip: bool = False) -> None:
    await _advance(state, target)
    await _prompt(message, state, f"{t(lang, 'wizard_step').format(step=step)} — {t(lang, key)}", reply_markup=navigation_keyboard(lang, allow_skip=allow_skip))


@router.message(RegisterStation.operational_area)
async def register_area(message: Message, state: FSMContext) -> None:
    async with _lock(message):
        if await state.get_state() != RegisterStation.operational_area.state:
            return
        lang = await _lang(state)
        value = clean_text(message.text)
        if not value or value in all_texts("skip_now"):
            await _track(state, "telegram.validation_failed", "operational_area", failure_reason="required value missing")
            await message.answer(t(lang, "invalid_required"))
            return
        await state.update_data(operational_area=value)
        await _track(state, "telegram.station_field.changed", "operational_area", changed_fields=["operational_area"], after_data={"operational_area": value})
        await _prompt_create_text(message, state, lang, RegisterStation.address, 5, "address_prompt")


@router.message(RegisterStation.address)
async def register_address(message: Message, state: FSMContext) -> None:
    async with _lock(message):
        if await state.get_state() != RegisterStation.address.state:
            return
        lang = await _lang(state)
        value = clean_text(message.text)
        if not value:
            await _track(state, "telegram.validation_failed", "address", failure_reason="required value missing")
            await message.answer(t(lang, "invalid_required"))
            return
        await state.update_data(address=value)
        await _track(state, "telegram.station_field.changed", "address", changed_fields=["address"], after_data={"address": value})
        suggested = f"{(await state.get_data()).get('code')} — {value}"
        await _advance(state, RegisterStation.name)
        await state.update_data(suggested_name=suggested)
        data = await state.get_data()
        await _prompt(
            message, state,
            f"{t(lang, 'wizard_step').format(step=6)} — {t(lang, 'name_prompt')}\n{t(lang, 'suggested_name').format(name=suggested)}",
            reply_markup=wizard_inline([
                [(t(lang, "use_suggested_name"), _cb(data, "create_name_default", "use"))],
                [(t(lang, "back"), _cb(data, "create_name_default", "back")), (t(lang, "cancel"), _cb(data, "cancel"))],
            ]),
        )


@router.message(RegisterStation.name)
async def register_name(message: Message, state: FSMContext) -> None:
    async with _lock(message):
        if await state.get_state() != RegisterStation.name.state:
            return
        lang = await _lang(state)
        value = clean_text(message.text)
        if not value:
            await _track(state, "telegram.validation_failed", "name", failure_reason="required value missing")
            await message.answer(t(lang, "invalid_required"))
            return
        await state.update_data(name=value)
        await _track(state, "telegram.station_field.changed", "name", changed_fields=["name"], after_data={"name": value})
        await _prompt_create_gps(message, state, lang)


async def _prompt_create_gps(message: Message, state: FSMContext, lang: str) -> None:
    await _advance(state, RegisterStation.gps)
    await _prompt(message, state, f"{t(lang, 'wizard_step').format(step=7)} — {t(lang, 'gps_prompt')}", reply_markup=location_keyboard(lang))


@router.message(RegisterStation.gps)
async def register_gps(message: Message, state: FSMContext) -> None:
    async with _lock(message):
        if await state.get_state() != RegisterStation.gps.state:
            return
        lang = await _lang(state)
        data = await state.get_data()
        message_id = getattr(message, "message_id", None)
        if message_id is not None and data.get("accepted_location_message_id") == message_id:
            return
        if (data.get("telegram_user_id") != getattr(getattr(message, "from_user", None), "id", None)
                or data.get("chat_id") != getattr(getattr(message, "chat", None), "id", None)
                or not data.get("prompt_message_id")):
            return
        if message.location:
            await state.update_data(latitude=message.location.latitude, longitude=message.location.longitude, accepted_location_message_id=message_id)
            await _track(state, "telegram.station_field.changed", "gps", telegram_update_id=message_id, changed_fields=["latitude", "longitude"], after_data={"latitude": message.location.latitude, "longitude": message.location.longitude})
        elif clean_text(message.text) in all_texts("skip_now"):
            await state.update_data(latitude=None, longitude=None)
        else:
            await _track(state, "telegram.validation_failed", "gps", failure_reason="invalid location input")
            await message.answer(t(lang, "invalid_location"), reply_markup=location_keyboard(lang))
            return
        await _show_create_confirm(message, state, lang)


async def _show_create_confirm(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    try:
        regions = await api.regions()
        city = next((item for item in regions if item.get("code") == data["city_code"]), None)
        district = next((item for item in regions if item.get("code") == data["district_code"]), None)
        if not city or not district:
            raise BackendAPIError(t(lang, "canonical_region_unavailable"), 409)
    except BackendAPIError as exc:
        await message.answer(localized_error(lang, exc.message))
        return
    await state.update_data(city_id=city["id"], district_id=district["id"])
    data = await _advance(state, RegisterStation.confirm)
    preview = await _track(state, "telegram.station_preview.generated", "confirmation", station_code=data.get("code"), after_data=_build_preview_data(data))
    preview_hash = (preview or {}).get("preview_hash") or secrets.token_urlsafe(12)
    await state.update_data(preview_hash=preview_hash)
    data = await state.get_data()
    await _prompt(
        message,
        state,
        _create_summary(lang, data),
        reply_markup=wizard_inline([
            [(t(lang, "create_station"), _cb(data, "create_save", preview_hash))],
            [(t(lang, "back"), _cb(data, "create_save", "back")), (t(lang, "cancel"), _cb(data, "cancel"))],
        ]),
    )


async def _show_update_menu(message: Message, state: FSMContext, lang: str) -> None:
    data = await _advance(state, UpdateStation.menu)
    rows = [
        [(t(lang, "field_city"), _cb(data, "update_field", "city")), (t(lang, "field_district"), _cb(data, "update_field", "district"))],
        [(t(lang, "field_area"), _cb(data, "update_field", "operational_area")), (t(lang, "field_address"), _cb(data, "update_field", "address"))],
        [(t(lang, "field_name"), _cb(data, "update_field", "name")), (t(lang, "field_gps"), _cb(data, "update_field", "gps"))],
        [(t(lang, "cancel"), _cb(data, "cancel"))],
    ]
    production_warning = f"\n\n{t(lang, 'approved_update_warning')}" if data["existing"].get("approved_at") else ""
    await _prompt(message, state, f"{_current_station(lang, data['existing'])}{production_warning}\n\n{t(lang, 'update_fields')}", reply_markup=wizard_inline(rows))


async def _select_update_field(message: Message, state: FSMContext, lang: str, field: str) -> None:
    await state.update_data(selected_field=field, patch=None)
    if field == "city":
        data = await _advance(state, UpdateStation.city)
        await _prompt(message, state, t(lang, "select_city"), reply_markup=wizard_inline([
            [(t(lang, "city_dushanbe"), _cb(data, "update_city", "dushanbe"))],
            [(t(lang, "back"), _cb(data, "update_city", "back")), (t(lang, "cancel"), _cb(data, "cancel"))],
        ]))
    elif field == "district":
        data = await _advance(state, UpdateStation.district)
        rows = [[(DISTRICT_LABELS[lang][code], _cb(data, "update_district", code))] for code in DISTRICTS]
        rows.append([(t(lang, "back"), _cb(data, "update_district", "back")), (t(lang, "cancel"), _cb(data, "cancel"))])
        await _prompt(message, state, t(lang, "select_district"), reply_markup=wizard_inline(rows))
    elif field == "gps":
        await _advance(state, UpdateStation.gps)
        await _prompt(message, state, t(lang, "gps_prompt"), reply_markup=location_keyboard(lang))
    else:
        await _advance(state, UpdateStation.text_value)
        await _prompt(message, state, t(lang, "enter_new_value").format(field=t(lang, f"field_{'area' if field == 'operational_area' else field}")), reply_markup=navigation_keyboard(lang))


@router.message(UpdateStation.text_value)
async def update_text_value(message: Message, state: FSMContext) -> None:
    async with _lock(message):
        if await state.get_state() != UpdateStation.text_value.state:
            return
        lang = await _lang(state)
        data = await state.get_data()
        value = clean_text(message.text)
        if not value:
            await message.answer(t(lang, "invalid_required"))
            return
        await _show_update_confirm(message, state, lang, {data["selected_field"]: value})


@router.message(UpdateStation.gps)
async def update_gps(message: Message, state: FSMContext) -> None:
    async with _lock(message):
        if await state.get_state() != UpdateStation.gps.state:
            return
        lang = await _lang(state)
        data = await state.get_data()
        message_id = getattr(message, "message_id", None)
        if message_id is not None and data.get("accepted_location_message_id") == message_id:
            return
        if (data.get("telegram_user_id") != getattr(getattr(message, "from_user", None), "id", None)
                or data.get("chat_id") != getattr(getattr(message, "chat", None), "id", None)
                or not data.get("prompt_message_id")):
            return
        if not message.location:
            await message.answer(t(lang, "invalid_location"), reply_markup=location_keyboard(lang))
            return
        await state.update_data(accepted_location_message_id=message_id)
        await _show_update_confirm(message, state, lang, {"latitude": message.location.latitude, "longitude": message.location.longitude}, telegram_update_id=message_id)


async def _prepare_region_patch(message: Message, state: FSMContext, lang: str, *, city_code: str | None = None, district_code: str | None = None) -> None:
    try:
        regions = await api.regions()
    except BackendAPIError as exc:
        await message.answer(localized_error(lang, exc.message))
        return
    code = city_code or district_code
    region = next((item for item in regions if item.get("code") == code), None)
    if not region:
        await message.answer(t(lang, "stale_action"))
        return
    await state.update_data(patch_display=region.get("name") or region.get("code"))
    await _show_update_confirm(message, state, lang, {"city_id" if city_code else "district_id": region["id"]})


async def _show_update_confirm(message: Message, state: FSMContext, lang: str, patch: dict, *, telegram_update_id: int | None = None) -> None:
    data = await state.get_data()
    current = data["existing"]
    selected = data.get("selected_field")
    allowed = {"gps": {"latitude", "longitude"}, "city": {"city_id"}, "district": {"district_id"}}
    expected_keys = allowed.get(selected, {selected})
    if set(patch) != expected_keys:
        await _track(state, "telegram.validation_failed", "confirmation", failure_reason="selected field mismatch")
        return
    diffs = [(field, current.get(field), value) for field, value in patch.items() if current.get(field) != value]
    await state.update_data(patch=patch, diffs=diffs)
    data = await _advance(state, UpdateStation.confirm)
    preview = await _track(
        state,
        "telegram.station_preview.generated",
        "confirmation",
        station_id=data.get("existing_station_id", current.get("id")),
        station_code=data.get("code", current.get("station_code")),
        changed_fields=list(patch),
        before_data={field: current.get(field) for field in patch},
        after_data=patch,
        telegram_update_id=telegram_update_id,
    )
    preview_hash = (preview or {}).get("preview_hash") or secrets.token_urlsafe(12)
    await state.update_data(preview_hash=preview_hash)
    data = await state.get_data()
    rows = [t(lang, "diff_title")]
    rows.extend(_localized_diff_rows(lang, diffs, data))
    if not diffs:
        rows.append(t(lang, "no_field_changes"))
        buttons = [
            [(t(lang, "choose_another_field"), _cb(data, "choose_field"))],
            [(t(lang, "cancel"), _cb(data, "cancel"))],
        ]
    else:
        buttons = [
            [(t(lang, "save_changes"), _cb(data, "update_confirm", preview_hash))],
            [(t(lang, "back"), _cb(data, "update_confirm", "back")), (t(lang, "cancel"), _cb(data, "cancel"))],
        ]
    await _prompt(message, state, "\n".join(rows), reply_markup=wizard_inline(buttons))


async def _save_update(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    role = data.get("role")
    if data.get("saving"):
        return
    await state.update_data(saving=True)
    if not await require_telegram_roles(callback, state, "admin", "operator"):
        await state.update_data(saving=False)
        return
    try:
        current = await api.station_by_code(data["code"])
        if not current or current.get("id") != data["existing_station_id"]:
            raise BackendAPIError(t(lang, "station_changed_restart"), 409)
        original = data.get("existing") or {}
        raw_patch = data.get("patch") or {}
        if any(current.get(field) != original.get(field) for field in raw_patch):
            raise BackendAPIError("STATION_CHANGED_AFTER_PREVIEW", 409)
        patch = {field: value for field, value in raw_patch.items() if current.get(field) != value}
        if patch:
            await _track(state, "telegram.station_save.confirmed", "save", station_id=current["id"], station_code=data["code"], changed_fields=list(patch))
            current = await api.update_station_as_telegram_user(
                callback.from_user, data["workflow_id"], current["id"], data["version"],
                data["preview_hash"], {field: original.get(field) for field in raw_patch}, patch,
            )
        else:
            await _track(state, "telegram.station_update.completed", "completed", status="completed", station_id=current["id"], station_code=data["code"])
    except BackendAPIError as exc:
        await _track(state, "telegram.validation_failed", "save", failure_reason=exc.message)
        await state.update_data(saving=False)
        await callback.message.answer(localized_error(lang, exc.message))
        return
    await _disable_prompt(callback.message, data.get("prompt_message_id"))
    await _finish(state)
    await callback.message.answer(t(lang, "field_saved"), reply_markup=main_keyboard(lang, role=role))


async def _save_create(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    role = data.get("role")
    if data.get("saving"):
        return
    await state.update_data(saving=True)
    if not await require_telegram_roles(callback, state, "admin", "operator"):
        await state.update_data(saving=False)
        return
    try:
        if await api.station_by_code(data["code"]):
            raise BackendAPIError(t(lang, "station_code_conflict"), 409)
        await _track(state, "telegram.station_save.confirmed", "save", station_code=data["code"])
        await api.create_station_as_telegram_user(
            callback.from_user, data["workflow_id"], data["version"], data["preview_hash"],
            _build_create(data, data["city_id"], data["district_id"]),
        )
    except BackendAPIError as exc:
        await _track(state, "telegram.validation_failed", "save", failure_reason=exc.message)
        await state.update_data(saving=False)
        await callback.message.answer(localized_error(lang, exc.message))
        return
    await _disable_prompt(callback.message, data.get("prompt_message_id"))
    await _finish(state)
    await callback.message.answer(t(lang, "registered_pending").format(code=data["code"]), reply_markup=main_keyboard(lang, role=role))


@router.message(StateFilter(RegisterStation, UpdateStation), lambda message: message.text in all_texts("back"))
async def back_station(message: Message, state: FSMContext) -> None:
    async with _lock(message):
        lang = await _lang(state)
        current = await state.get_state()
        if current == RegisterStation.operational_area.state:
            await _show_create_district(message, state, lang)
        elif current == RegisterStation.address.state:
            await _prompt_create_text(message, state, lang, RegisterStation.operational_area, 4, "area_prompt")
        elif current == RegisterStation.name.state:
            await _prompt_create_text(message, state, lang, RegisterStation.address, 5, "address_prompt")
        elif current == RegisterStation.gps.state:
            await _prompt_create_text(message, state, lang, RegisterStation.name, 6, "name_prompt")
        elif current in {UpdateStation.text_value.state, UpdateStation.gps.state}:
            await _show_update_menu(message, state, lang)
        else:
            await state.clear()
            await message.answer(t(lang, "cancelled"), reply_markup=main_keyboard(lang))


def _build_create(data: dict, city_id: int, district_id: int) -> dict:
    return {
        "station_code": data["code"], "name": data["name"], "city_id": city_id,
        "district_id": district_id, "operational_area": data.get("operational_area"),
        "address": data["address"], "latitude": data.get("latitude"), "longitude": data.get("longitude"),
    }


def _build_preview_data(data: dict) -> dict:
    return {
        "station_code": data.get("code"), "name": data.get("name"),
        "city_id": data.get("city_id"), "district_id": data.get("district_id"),
        "operational_area": data.get("operational_area"), "address": data.get("address"),
        "latitude": data.get("latitude"), "longitude": data.get("longitude"),
    }


def _localized_diff_rows(lang: str, diffs: list[tuple[str, object, object]], data: dict) -> list[str]:
    by_field = {field: (old, new) for field, old, new in diffs}
    if "latitude" in by_field or "longitude" in by_field:
        old = data["existing"]
        old_gps = f"{_value(old.get('latitude'))}, {_value(old.get('longitude'))}"
        patch = data.get("patch") or {}
        new_gps = f"{_value(patch.get('latitude'))}, {_value(patch.get('longitude'))}"
        return [f"{t(lang, 'field_gps')}: {old_gps} → {new_gps}"]
    labels = {
        "city_id": "field_city", "district_id": "field_district",
        "operational_area": "field_area", "address": "field_address", "name": "field_name",
    }
    rows = []
    for field, old, new in diffs:
        if field == "city_id":
            old, new = data["existing"].get("city"), data.get("patch_display", new)
        elif field == "district_id":
            old, new = data["existing"].get("district"), data.get("patch_display", new)
        rows.append(f"{t(lang, labels[field])}: {_value(old)} → {_value(new)}")
    return rows


def _create_summary(lang: str, data: dict) -> str:
    gps = f"{data['latitude']:.6f}, {data['longitude']:.6f}" if data.get("latitude") is not None else "—"
    return "\n".join([
        t(lang, "summary_title"), f"{t(lang, 'label_code')}: {data['code']}",
        f"{t(lang, 'label_city')}: {data['city_name']}", f"{t(lang, 'label_district')}: {data['district_name']}",
        f"{t(lang, 'label_operational_area')}: {_value(data.get('operational_area'))}",
        f"{t(lang, 'label_address')}: {data['address']}", f"{t(lang, 'label_name')}: {data['name']}",
        f"{t(lang, 'label_gps')}: {gps}", f"{t(lang, 'label_approval')}: {t(lang, 'approval_pending')}",
    ])


def _value(value: object) -> str:
    return "—" if value in (None, "") else str(value)


def _current_station(lang: str, station: dict) -> str:
    return "\n".join([
        f"{t(lang, 'label_code')}: {station.get('station_code')}", f"{t(lang, 'label_name')}: {station.get('name')}",
        f"{t(lang, 'label_city')}: {_value(station.get('city'))}", f"{t(lang, 'label_district')}: {_value(station.get('district'))}",
        f"{t(lang, 'label_operational_area')}: {_value(station.get('operational_area'))}",
        f"{t(lang, 'label_address')}: {_value(station.get('address'))}",
        f"{t(lang, 'label_gps')}: {_value(station.get('latitude'))}, {_value(station.get('longitude'))}",
        f"{t(lang, 'label_approval')}: {t(lang, 'approval_approved') if station.get('approved_at') else t(lang, 'approval_pending')}",
    ])
