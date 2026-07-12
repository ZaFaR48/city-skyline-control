from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import BackendAPIError, api
from i18n import all_texts, localized_error, t
from keyboards import language_keyboard, main_keyboard, registration_review_keyboard


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user is None:
        return
    result = await _registration(message)
    await state.update_data(
        access_status=(result or {}).get("status"),
        role=(result or {}).get("role"),
        pending_registration_result=result,
        lang=(result or {}).get("preferred_language", "tj"),
        registration_unavailable=result is None,
    )
    await message.answer(
        "Лутфан забонро интихоб кунед · Выберите язык · Choose language",
        reply_markup=language_keyboard(),
    )


@router.message(Command("status"))
@router.message(Command("access"))
@router.message(lambda message: message.text in all_texts("my_access"))
async def my_status(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    result = await _registration(message)
    if result is not None:
        lang = result.get("preferred_language") or (await state.get_data()).get("lang", "tj")
        await state.update_data(access_status=result.get("status"), role=result.get("role"), lang=lang)
        await message.answer(_access_text(lang, result))


@router.message(lambda message: message.text in all_texts("request_access"))
async def request_access(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    result = await _registration(message)
    if result and result.get("status") == "pending":
        lang = result.get("preferred_language") or (await state.get_data()).get("lang", "tj")
        await message.answer(t(lang, "registration_pending"))


@router.message(Command("help"))
@router.message(lambda message: message.text in all_texts("help_access"))
async def access_help(message: Message, state: FSMContext) -> None:
    result = await _registration(message) if message.from_user else None
    lang = (result or {}).get("preferred_language") or (await state.get_data()).get("lang", "tj")
    await state.update_data(lang=lang)
    await message.answer(t(lang, "access_help_text"))


@router.message(lambda message: message.text in all_texts("pending_users"))
async def pending_users(message: Message, state: FSMContext) -> None:
    lang = (await state.get_data()).get("lang", "tj")
    if not await _is_admin(message):
        await message.answer(t(lang, "admin_required"))
        return
    try:
        rows = await api.pending_registrations()
    except BackendAPIError as exc:
        await message.answer(t(lang, "registration_unavailable"))
        return
    if not rows:
        await message.answer(t(lang, "pending_none"))
        return
    for row in rows:
        name = " ".join(filter(None, [row.get("first_name"), row.get("last_name")])) or "—"
        username = f"@{row['telegram_username']}" if row.get("telegram_username") else "—"
        await message.answer(
            f"{t(lang, 'pending_user_label')}\nTelegram ID: {row['telegram_user_id']}\n{t(lang, 'label_name')}: {name}\n{t(lang, 'label_telegram_username')}: {username}",
            reply_markup=registration_review_keyboard(int(row["id"]), lang),
        )


@router.callback_query(F.data.startswith("reg:"))
async def registration_callback(callback: CallbackQuery, state: FSMContext) -> None:
    lang = (await state.get_data()).get("lang", "tj")
    if callback.message is None or callback.from_user is None:
        await callback.answer(t(lang, "invalid_callback"), show_alert=True)
        return
    if not await _is_admin(callback.message, callback.from_user):
        await callback.answer(t(lang, "admin_required"), show_alert=True)
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 4 or parts[1] not in {"approve", "reject"} or not parts[2].isdigit():
        await callback.answer(t(lang, "invalid_callback"), show_alert=True)
        return
    action, registration_id, role = parts[1], int(parts[2]), parts[3]
    if action == "approve" and role not in {"admin", "operator", "viewer"}:
        await callback.answer(t(lang, "invalid_callback"), show_alert=True)
        return
    try:
        await api.review_registration(registration_id, action, role if action == "approve" else None)
    except BackendAPIError as exc:
        await callback.answer(localized_error(lang, exc.message), show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(t(lang, "registration_reviewed"))


async def _registration(message: Message) -> dict | None:
    try:
        return await api.registration_start(message.from_user)
    except BackendAPIError:
        return None


async def send_registration_result(message: Message, state: FSMContext, lang: str, result: dict) -> None:
    status = result.get("status")
    role = result.get("role") or "viewer"
    if status == "activated":
        await message.answer(
            t(lang, "activated_welcome").format(username=result.get("username") or message.from_user.first_name),
            reply_markup=main_keyboard(lang, role=role),
        )
    elif status == "approved" and result.get("activation_code"):
        await message.answer(t(lang, "activation_details").format(
            username=result.get("username") or "—",
            role=t(lang, f"role_{role}"),
            url=result.get("activation_url") or "—",
        ))
    elif status == "pending":
        await message.answer(t(lang, "registration_pending"))
    elif status == "rejected":
        await message.answer(t(lang, "registration_rejected"))
    elif status == "clarification_requested":
        await message.answer(t(lang, "registration_clarification"))
    else:
        await message.answer(t(lang, "registration_awaiting"))
    await state.update_data(pending_registration_result=None)


async def _is_admin(message: Message, user=None) -> bool:
    telegram_user = user or message.from_user
    if telegram_user is None:
        return False
    try:
        result = await api.resolve_telegram_user(telegram_user)
    except BackendAPIError:
        return False
    return result.get("is_active") and result.get("role") == "admin"


def _access_text(lang: str, result: dict) -> str:
    role = str(result.get("role") or "viewer")
    activation = t(lang, "activation_required") if result.get("activation_required") else t(lang, "activation_not_required")
    return "\n".join(
        [
            t(lang, "access_title"),
            f"{t(lang, 'access_username')}: {result.get('username') or '—'}",
            f"{t(lang, 'access_role')}: {t(lang, f'role_{role}')}",
            f"{t(lang, 'access_status')}: {t(lang, 'registration_status_' + str(result.get('status', 'pending')))}",
            f"{t(lang, 'access_activation')}: {activation}",
            t(lang, "username_login_hint"),
        ]
    )
