from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from i18n import LANGUAGE_BY_BUTTON, menu_label, t


def language_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in LANGUAGE_BY_BUTTON]],
        resize_keyboard=True,
    )


def main_keyboard(lang: str = "tj") -> ReplyKeyboardMarkup:
    rows = [
        ["new_station", "search_station"],
        ["scan_qr", "rustdesk"],
        ["vpn", "ping"],
        ["camera", "network_status"],
        ["alerts", "reports"],
        ["settings"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=menu_label(lang, key)) for key in row]
            for row in rows
        ],
        resize_keyboard=True,
    )


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


def qr_keyboard(lang: str = "tj") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "generate_qr"))],
            [KeyboardButton(text=t(lang, "skip"))],
            [KeyboardButton(text=t(lang, "cancel"))],
        ],
        resize_keyboard=True,
    )


def nfc_keyboard(lang: str = "tj") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "assign_nfc"))],
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
