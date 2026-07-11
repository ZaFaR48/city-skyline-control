from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from i18n import LANGUAGE_BY_BUTTON, menu_label, t


def language_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in LANGUAGE_BY_BUTTON]],
        resize_keyboard=True,
    )


def main_keyboard(lang: str = "tj", is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        ["new_station", "search_station"],
        ["scan_qr", "rustdesk"],
        ["vpn", "ping"],
        ["camera", "network_status"],
        ["alerts", "reports"],
        ["settings"],
    ]
    if is_admin:
        rows.append(["pending_users"])
    rows.extend([["my_access", "request_access"], ["help_access"]])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, key) if key in {"pending_users", "my_access", "request_access", "help_access"} else menu_label(lang, key)) for key in row]
            for row in rows
        ],
        resize_keyboard=True,
    )


def registration_review_keyboard(registration_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Approve ADMIN", callback_data=f"reg:approve:{registration_id}:admin"),
            InlineKeyboardButton(text="Approve OPERATOR", callback_data=f"reg:approve:{registration_id}:operator"),
        ],
        [
            InlineKeyboardButton(text="Approve VIEWER", callback_data=f"reg:approve:{registration_id}:viewer"),
            InlineKeyboardButton(text="Reject", callback_data=f"reg:reject:{registration_id}:none"),
        ],
    ])


def skip_keyboard(lang: str = "tj") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "skip"))],
            [KeyboardButton(text=t(lang, "cancel"))],
        ],
        resize_keyboard=True,
    )


def location_keyboard(lang: str = "tj") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "send_location"), request_location=True)],
            [KeyboardButton(text=t(lang, "skip"))],
            [KeyboardButton(text=t(lang, "cancel"))],
        ],
        resize_keyboard=True,
    )


def confirm_keyboard(lang: str = "tj") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "save"))],
            [KeyboardButton(text=t(lang, "cancel"))],
        ],
        resize_keyboard=True,
    )


def approved_update_keyboard(lang: str = "tj") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "confirm_approved_update"))],
            [KeyboardButton(text=t(lang, "cancel"))],
        ],
        resize_keyboard=True,
    )
