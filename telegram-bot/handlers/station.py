from __future__ import annotations

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from api import BackendAPIError, api
from i18n import all_menu_labels, all_texts, t
from keyboards import (
    confirm_keyboard,
    location_keyboard,
    main_keyboard,
    nfc_keyboard,
    qr_keyboard,
    skip_keyboard,
)
from states import AddStation
from validators import clean_text, is_skip, is_valid_ip, mask_url_credentials


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
    value = clean_text(message.text)
    if not value or is_skip(value):
        await message.answer(t(lang, "invalid_required"))
        return
    await state.update_data(code=value)
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
    await state.update_data(region=value)
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
    await state.set_state(AddStation.camera_ip)
    await message.answer(t(lang, "enter_camera_ip"), reply_markup=skip_keyboard(lang))


@router.message(AddStation.camera_ip)
async def station_camera_ip(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    if is_skip(value):
        await state.update_data(camera_ip=None)
    else:
        if not is_valid_ip(value):
            await message.answer(t(lang, "invalid_ip"), reply_markup=skip_keyboard(lang))
            return
        await state.update_data(camera_ip=value)
    await state.set_state(AddStation.rtsp_url)
    await message.answer(t(lang, "enter_rtsp"), reply_markup=skip_keyboard(lang))


@router.message(AddStation.rtsp_url)
async def station_rtsp_url(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    await state.update_data(rtsp_url=None if is_skip(value) else value)
    await state.set_state(AddStation.qr)
    await message.answer(t(lang, "enter_qr"), reply_markup=qr_keyboard(lang))


@router.message(AddStation.qr)
async def station_qr(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    await state.update_data(qr_requested=value == t(lang, "generate_qr"))
    await state.set_state(AddStation.nfc)
    await message.answer(t(lang, "enter_nfc"), reply_markup=nfc_keyboard(lang))


@router.message(AddStation.nfc)
async def station_nfc(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    value = clean_text(message.text)
    await state.update_data(nfc_requested=value == t(lang, "assign_nfc"))
    await state.set_state(AddStation.confirm)
    data = await state.get_data()
    await message.answer(_summary(lang, data), reply_markup=confirm_keyboard(lang))


@router.message(AddStation.confirm)
async def station_confirm(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    if clean_text(message.text) not in all_texts("save"):
        data = await state.get_data()
        await message.answer(_summary(lang, data), reply_markup=confirm_keyboard(lang))
        return

    data = await state.get_data()
    missing = _missing_backend_fields(data)
    if missing:
        await message.answer(
            f"{t(lang, 'missing_backend')}\n\n{t(lang, 'missing_fields')} {', '.join(missing)}",
            reply_markup=confirm_keyboard(lang),
        )
        return

    station_payload = {
        "code": data["code"],
        "name": data["name"],
        "region": data["region"],
        "address": data["address"],
        "vpn_ip": data["vpn_ip"],
        "local_ip": data["local_ip"],
        "rustdesk_id": data.get("rustdesk_id"),
        "lat": data["lat"],
        "lng": data["lng"],
    }

    try:
        created = await api.create_station(station_payload)
    except BackendAPIError as exc:
        await message.answer(f"{t(lang, 'api_error')} {exc.message}", reply_markup=confirm_keyboard(lang))
        return

    followups = []
    station_id = created.get("id")
    camera_ip = data.get("camera_ip")
    rtsp_url = data.get("rtsp_url")
    if station_id and camera_ip and rtsp_url:
        try:
            await api.create_camera({
                "station_id": station_id,
                "name": f"{data['code']} Camera",
                "ip": camera_ip,
                "rtsp_url": rtsp_url,
                "ptz": False,
                "resolution": "1920x1080",
                "fps": 25,
            })
            followups.append(t(lang, "station_created_camera"))
        except BackendAPIError as exc:
            followups.append(f"{t(lang, 'api_error')} camera: {exc.message}")
    else:
        followups.append(t(lang, "station_created_no_camera"))

    rustdesk_id = data.get("rustdesk_id")
    if station_id and rustdesk_id:
        try:
            await api.update_rustdesk(station_id, rustdesk_id)
        except BackendAPIError as exc:
            followups.append(f"{t(lang, 'api_error')} RustDesk: {exc.message}")

    await _clear_keep_lang(state, lang)
    details = "\n".join(followups)
    await message.answer(f"{t(lang, 'saved')}\n{details}", reply_markup=main_keyboard(lang))


def _missing_backend_fields(data: dict) -> list[str]:
    missing = []
    if not data.get("vpn_ip"):
        missing.append("VPN IP")
    if not data.get("local_ip"):
        missing.append("Local IP")
    if data.get("lat") is None or data.get("lng") is None:
        missing.append("GPS")
    return missing


def _summary(lang: str, data: dict) -> str:
    gps = "-"
    if data.get("lat") is not None and data.get("lng") is not None:
        gps = f"{data['lat']:.6f}, {data['lng']:.6f}"

    rows = [
        t(lang, "summary_title"),
        "",
        f"Code: {data.get('code', '-')}",
        f"Name: {data.get('name', '-')}",
        f"Region: {data.get('region', '-')}",
        f"Address: {data.get('address', '-')}",
        f"VPN IP: {data.get('vpn_ip') or '-'}",
        f"Local IP: {data.get('local_ip') or '-'}",
        f"RustDesk ID: {data.get('rustdesk_id') or '-'}",
        f"GPS: {gps}",
        f"Camera IP: {data.get('camera_ip') or '-'}",
        f"RTSP URL: {mask_url_credentials(data.get('rtsp_url'))}",
        f"QR: {'requested' if data.get('qr_requested') else 'skipped'}",
        f"NFC: {'requested' if data.get('nfc_requested') else 'skipped'}",
    ]
    missing = _missing_backend_fields(data)
    if missing:
        rows.extend(["", t(lang, "missing_backend"), f"{t(lang, 'missing_fields')} {', '.join(missing)}"])
    return "\n".join(rows)
