from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers.start import _access_text
from handlers.station import DISTRICTS, _build_create, _build_patch, _summary, back_station, station_callback, station_code
from states import AddStation


class FakeState:
    def __init__(self, data=None, current=None):
        self.data = dict(data or {})
        self.current = current

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, state):
        self.current = state.state if hasattr(state, "state") else state

    async def get_state(self):
        return self.current

    async def clear(self):
        self.data.clear()
        self.current = None


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.location = None
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs.get("reply_markup")))


class FakeCallback:
    def __init__(self, data):
        self.data = data
        self.message = FakeMessage()
        self.answers = []

    async def answer(self, text=None, **kwargs):
        self.answers.append((text, kwargs))


def existing_station(**overrides):
    return {
        "id": 42, "station_code": "10002", "name": "Current name", "city_id": 1,
        "city": "Dushanbe", "district_id": 2, "district": "Shohmansur",
        "operational_area": None, "address": "Current address", "vpn_ip": "100.64.0.23",
        "local_ip": "192.168.1.111", "rustdesk_id": None, "latitude": 38.5,
        "longitude": 68.7, "approved_at": None, **overrides,
    }


@pytest.mark.asyncio
async def test_existing_station_code_enters_update_mode_without_create(monkeypatch):
    async def lookup(code):
        assert code == "10002"
        return existing_station()

    monkeypatch.setattr("handlers.station.api.station_by_code", lookup)
    state = FakeState({"lang": "en", "nonce": "abcd"}, AddStation.code.state)
    message = FakeMessage(" 10002 ")
    await station_code(message, state)
    assert state.current == AddStation.existing_action.state
    assert state.data["existing_station_id"] == 42
    assert "edit the existing record" in message.answers[0][0]


def test_canonical_button_values_and_separate_operational_fields():
    assert set(DISTRICTS) == {"ismoili-somoni", "shohmansur", "sino", "firdavsi"}
    created = _build_create(
        {"code": "10050", "name": "Display", "operational_area": "Customs", "address": "Rudaki 10", "latitude": None, "longitude": None},
        1,
        2,
    )
    assert created["operational_area"] == "Customs"
    assert created["address"] == "Rudaki 10"
    assert "approved_at" not in created and "approved_by" not in created


def test_district_and_skips_do_not_overwrite_existing_fields():
    current = existing_station()
    data = {
        "district_name": "Sino", "name_changed": False, "operational_area_changed": False,
        "address_changed": False, "gps_changed": False,
    }
    patch, _ = _build_patch(current, data, city_id=1, district_id=3)
    assert patch == {"district_id": 3}
    assert "name" not in patch and "address" not in patch and "operational_area" not in patch
    assert "vpn_ip" not in patch and "local_ip" not in patch and "rustdesk_id" not in patch


def test_removed_default_fields_and_summary():
    for field in ("vpn_ip", "local_ip", "rustdesk_id", "camera_ip", "rtsp_url", "qr", "nfc"):
        assert not hasattr(AddStation, field)
    summary = _summary(
        "ru",
        {
            "code": "10050", "name": "Сино — Таможня", "district_name": "Sino",
            "operational_area": "Таможня", "address": "Рудаки 10", "gps_changed": False,
        },
    )
    for removed in ("VPN", "Local IP", "RustDesk", "Camera", "RTSP", "QR", "NFC"):
        assert removed not in summary


@pytest.mark.asyncio
async def test_back_navigation_restores_previous_state():
    state = FakeState({"lang": "en", "nonce": "abcd"}, AddStation.operational_area.state)
    message = FakeMessage("⬅️ Back")
    await back_station(message, state)
    assert state.current == AddStation.district.state
    assert message.answers


@pytest.mark.asyncio
async def test_stale_callback_nonce_is_rejected_without_state_change():
    state = FakeState({"lang": "en", "nonce": "newnonce"}, AddStation.city.state)
    callback = FakeCallback("sw:oldnonce:city:dushanbe")
    await station_callback(callback, state)
    assert state.current == AddStation.city.state
    assert callback.answers[0][1]["show_alert"] is True


@pytest.mark.asyncio
async def test_double_save_callback_is_blocked_before_api_calls(monkeypatch):
    calls = 0

    async def regions():
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr("handlers.station.api.regions", regions)
    state = FakeState({"lang": "en", "nonce": "abcd", "saving": True}, AddStation.confirm.state)
    callback = FakeCallback("sw:abcd:confirm:save")
    await station_callback(callback, state)
    assert calls == 0
    assert any(answer[1].get("show_alert") for answer in callback.answers)


def test_approved_update_patch_never_changes_approval():
    patch, _ = _build_patch(
        existing_station(approved_at="2026-01-01T00:00:00Z"),
        {"name_changed": True, "name": "New", "operational_area_changed": False, "address_changed": False, "gps_changed": False},
        1,
        2,
    )
    assert patch == {"name": "New"}
    assert "approved_at" not in patch and "approved_by" not in patch


def test_my_access_contains_only_safe_identity_status():
    text = _access_text("ru", {"username": "telegram-user", "role": "operator", "status": "activated", "activation_required": False})
    assert "telegram-user" in text and "Оператор" in text and "activated" in text
    assert all(secret not in text.lower() for secret in ("password", "token", "hash", "code"))
