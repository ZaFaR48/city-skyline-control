from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from api import BackendAPI
from app import build_dispatcher
from keyboards import main_keyboard, registration_review_keyboard


ROOT = Path(__file__).resolve().parents[1]


def test_admin_keyboard_exposes_pending_users_only_for_admins():
    admin_text = [button.text for row in main_keyboard("en", is_admin=True).keyboard for button in row]
    viewer_text = [button.text for row in main_keyboard("en", is_admin=False).keyboard for button in row]
    assert "Pending users" in admin_text
    assert "Pending users" not in viewer_text
    assert {"👤 My access", "Request access", "Help"}.issubset(admin_text)


def test_registration_callbacks_are_narrow_and_role_explicit():
    keyboard = registration_review_keyboard(42)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert callbacks == [
        "reg:approve:42:admin",
        "reg:approve:42:operator",
        "reg:approve:42:viewer",
        "reg:reject:42:none",
    ]


def test_dispatcher_has_access_middleware_and_existing_bot_routers():
    dispatcher = build_dispatcher()
    assert dispatcher.sub_routers
    assert dispatcher.message.outer_middleware


def test_production_settings_and_systemd_startup_are_valid():
    from config import settings

    settings.validate()
    unit = (ROOT / "deployment" / "city-telegram-bot.service").read_text()
    assert "WorkingDirectory=/opt/city-skyline-control/telegram-bot" in unit
    assert "EnvironmentFile=/opt/city-skyline-control/telegram-bot/.env" in unit
    assert "ExecStart=/opt/city-skyline-control/telegram-bot/venv/bin/python" in unit
    assert "Restart=always" in unit
    assert "RestartSec=5" in unit
    assert "After=network-online.target city-backend.service" in unit
    assert "User=city-telegram" in unit


@pytest.mark.asyncio
async def test_registration_start_sends_only_telegram_identity(monkeypatch):
    client = BackendAPI()
    captured = {}

    async def request(method, path, **kwargs):
        captured.update(method=method, path=path, payload=kwargs.get("json"))
        return {"status": "pending"}

    monkeypatch.setattr(client, "_request", request)
    result = await client.registration_start(
        SimpleNamespace(id=1234, username="operator", first_name="Test", last_name="User")
    )
    assert result["status"] == "pending"
    assert captured["path"] == "/api/registrations/telegram/start"
    assert set(captured["payload"]) == {
        "telegram_user_id",
        "telegram_username",
        "first_name",
        "last_name",
    }
