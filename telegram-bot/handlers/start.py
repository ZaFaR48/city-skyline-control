from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api import BackendAPIError, api
from i18n import all_texts, t
from keyboards import language_keyboard, main_keyboard, registration_review_keyboard


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user is None:
        return
    result = await _registration(message)
    if result is None:
        return
    status = result.get("status")
    await state.update_data(access_status=status, role=result.get("role"))
    if status == "activated":
        is_admin = result.get("role") == "admin"
        await message.answer(
            f"Welcome, {result.get('username') or message.from_user.first_name}.",
            reply_markup=main_keyboard("tj", is_admin=is_admin),
        )
        return
    if status == "approved" and result.get("activation_code"):
        await message.answer(
            f"System username: {result.get('username')}\n"
            f"Role: {result.get('role') or 'viewer'}\n"
            f"Activation URL: {result.get('activation_url')}\n"
            "Use this exact username on the login page after activation. The link is single-use."
        )
        return
    if status == "pending":
        await message.answer("Your registration request has been sent to the administrator.")
    elif status == "rejected":
        await message.answer("Your registration request was rejected. Contact a City Parking administrator.")
    elif status == "clarification_requested":
        await message.answer("The administrator requested clarification. Contact City Parking support.")
    else:
        await message.answer("Your account is awaiting activation.")


@router.message(Command("status"))
@router.message(Command("access"))
@router.message(lambda message: message.text in all_texts("my_access"))
async def my_status(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    result = await _registration(message)
    if result is not None:
        await state.update_data(access_status=result.get("status"), role=result.get("role"))
        lang = (await state.get_data()).get("lang", "tj")
        await message.answer(_access_text(lang, result))


@router.message(lambda message: message.text in all_texts("request_access"))
async def request_access(message: Message) -> None:
    if message.from_user is None:
        return
    result = await _registration(message)
    if result and result.get("status") == "pending":
        await message.answer("Your registration request has been sent to the administrator.")


@router.message(Command("help"))
@router.message(lambda message: message.text in all_texts("help_access"))
async def access_help(message: Message) -> None:
    await message.answer("Use /start to register, My status to check access, or contact a City Parking administrator.")


@router.message(lambda message: message.text in all_texts("pending_users"))
async def pending_users(message: Message) -> None:
    if not await _is_admin(message):
        await message.answer("Administrator access required.")
        return
    try:
        rows = await api.pending_registrations()
    except BackendAPIError as exc:
        await message.answer(f"Registration service unavailable: {exc.message}")
        return
    if not rows:
        await message.answer("No pending registration requests.")
        return
    for row in rows:
        name = " ".join(filter(None, [row.get("first_name"), row.get("last_name")])) or "—"
        username = f"@{row['telegram_username']}" if row.get("telegram_username") else "—"
        await message.answer(
            f"Pending user\nTelegram ID: {row['telegram_user_id']}\nName: {name}\nUsername: {username}",
            reply_markup=registration_review_keyboard(int(row["id"])),
        )


@router.callback_query(F.data.startswith("reg:"))
async def registration_callback(callback: CallbackQuery) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer("Invalid callback", show_alert=True)
        return
    if not await _is_admin(callback.message, callback.from_user):
        await callback.answer("Administrator access required", show_alert=True)
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 4 or parts[1] not in {"approve", "reject"} or not parts[2].isdigit():
        await callback.answer("Invalid callback", show_alert=True)
        return
    action, registration_id, role = parts[1], int(parts[2]), parts[3]
    if action == "approve" and role not in {"admin", "operator", "viewer"}:
        await callback.answer("Invalid role", show_alert=True)
        return
    try:
        await api.review_registration(registration_id, action, role if action == "approve" else None)
    except BackendAPIError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Registration reviewed")


async def _registration(message: Message) -> dict | None:
    try:
        return await api.registration_start(message.from_user)
    except BackendAPIError:
        await message.answer("Registration service is temporarily unavailable. Please try again later.")
        return None


async def _is_admin(message: Message, user=None) -> bool:
    telegram_user = user or message.from_user
    if telegram_user is None:
        return False
    try:
        result = await api.registration_start(telegram_user)
    except BackendAPIError:
        return False
    return result.get("status") == "activated" and result.get("role") == "admin"


def _access_text(lang: str, result: dict) -> str:
    role = str(result.get("role") or "viewer")
    activation = t(lang, "activation_required") if result.get("activation_required") else t(lang, "activation_not_required")
    return "\n".join(
        [
            t(lang, "access_title"),
            f"{t(lang, 'access_username')}: {result.get('username') or '—'}",
            f"{t(lang, 'access_role')}: {t(lang, f'role_{role}')}",
            f"{t(lang, 'access_status')}: {str(result.get('status', 'pending')).replace('_', ' ')}",
            f"{t(lang, 'access_activation')}: {activation}",
            t(lang, "username_login_hint"),
        ]
    )
