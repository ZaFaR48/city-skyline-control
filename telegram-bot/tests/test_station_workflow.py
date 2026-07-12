from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from handlers.station import (
    _build_create,
    _save_update,
    back_station,
    register_address,
    register_area,
    register_code,
    register_gps,
    register_name,
    station_callback,
    update_text_value,
)
from states import RegisterStation, UpdateStation


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
    def __init__(self, text="", *, location=None, chat_id=10):
        self.text = text
        self.location = location
        self.chat = SimpleNamespace(id=chat_id)
        self.from_user = SimpleNamespace(id=10, username="operator", first_name="Operator", last_name=None)
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs.get("reply_markup")))
        return SimpleNamespace(message_id=len(self.answers))


class FakeCallback:
    def __init__(self, data, message=None):
        self.data = data
        self.message = message or FakeMessage()
        self.from_user = SimpleNamespace(id=10, username="operator", first_name="Operator", last_name=None)
        self.answers = []

    async def answer(self, text=None, **kwargs):
        self.answers.append((text, kwargs))


def existing_station(**overrides):
    return {
        "id": 42,
        "station_code": "10002",
        "name": "Current name",
        "city_id": 1,
        "city": "Dushanbe",
        "district_id": 2,
        "district": "Shohmansur",
        "operational_area": "Customs",
        "address": "Current address",
        "latitude": 38.5,
        "longitude": 68.7,
        "approved_at": None,
        **overrides,
    }


@pytest.mark.asyncio
async def test_existing_code_cannot_silently_enter_creation(monkeypatch):
    monkeypatch.setattr("handlers.station.api.station_by_code", lambda code: _async(existing_station()))
    state = FakeState({"lang": "en", "nonce": "abcd", "version": 0}, RegisterStation.code.state)
    message = FakeMessage("10002")
    await register_code(message, state)
    assert state.current == RegisterStation.existing_offer.state
    assert "Creation has stopped" in message.answers[0][0]


@pytest.mark.asyncio
async def test_open_existing_update_is_explicit_callback(monkeypatch):
    async def resolved(_user):
        return {"user_id": 1, "username": "operator", "is_active": True, "role": "operator"}

    monkeypatch.setattr("handlers.station.api.resolve_telegram_user", resolved)
    state = FakeState(
        {"lang": "en", "nonce": "abcd", "version": 1, "existing": existing_station(), "existing_station_id": 42},
        RegisterStation.existing_offer.state,
    )
    callback = FakeCallback("st:abcd:1:open_update:-")
    await station_callback(callback, state)
    assert state.current == UpdateStation.menu.state


@pytest.mark.asyncio
async def test_update_edits_only_selected_field():
    current = existing_station()
    state = FakeState(
        {"lang": "en", "nonce": "abcd", "version": 2, "existing": current, "selected_field": "address"},
        UpdateStation.text_value.state,
    )
    await update_text_value(FakeMessage("New exact address"), state)
    assert state.data["patch"] == {"address": "New exact address"}
    assert "name" not in state.data["patch"] and "operational_area" not in state.data["patch"]


@pytest.mark.asyncio
async def test_back_from_step_6_returns_to_step_5():
    state = FakeState({"lang": "en", "nonce": "abcd", "version": 4}, RegisterStation.name.state)
    message = FakeMessage("⬅️ Back")
    await back_station(message, state)
    assert state.current == RegisterStation.address.state
    assert "Step 5/7" in message.answers[0][0]


@pytest.mark.asyncio
async def test_back_from_step_5_returns_to_step_4():
    state = FakeState({"lang": "en", "nonce": "abcd", "version": 4}, RegisterStation.address.state)
    message = FakeMessage("⬅️ Back")
    await back_station(message, state)
    assert state.current == RegisterStation.operational_area.state
    assert "Step 4/7" in message.answers[0][0]


@pytest.mark.asyncio
async def test_operational_area_and_address_never_shift():
    state = FakeState({"lang": "en", "nonce": "abcd", "version": 3}, RegisterStation.operational_area.state)
    await register_area(FakeMessage("Customs", chat_id=20), state)
    assert state.data["operational_area"] == "Customs"
    assert "address" not in state.data
    await register_address(FakeMessage("Rudaki 10", chat_id=20), state)
    assert state.data["address"] == "Rudaki 10"
    assert "name" not in state.data


@pytest.mark.asyncio
async def test_gps_then_late_text_cannot_overwrite_name():
    state = FakeState(
        {
            "lang": "en", "nonce": "abcd", "version": 6, "code": "10998",
            "city_name": "Dushanbe", "district_name": "Sino", "operational_area": "Customs",
            "address": "Rudaki 10", "name": "Chosen name",
        },
        RegisterStation.gps.state,
    )
    location = SimpleNamespace(latitude=38.5, longitude=68.7)
    await register_gps(FakeMessage(location=location, chat_id=30), state)
    assert state.current == RegisterStation.confirm.state
    await register_name(FakeMessage("Late text", chat_id=30), state)
    assert state.data["name"] == "Chosen name"


@pytest.mark.asyncio
async def test_rapid_messages_do_not_populate_next_field():
    state = FakeState({"lang": "en", "nonce": "abcd", "version": 3}, RegisterStation.operational_area.state)
    await asyncio.gather(
        register_area(FakeMessage("First area", chat_id=40), state),
        register_area(FakeMessage("Late area", chat_id=40), state),
    )
    assert state.data["operational_area"] in {"First area", "Late area"}
    assert "address" not in state.data
    assert state.current == RegisterStation.address.state


@pytest.mark.asyncio
async def test_stale_callback_version_is_rejected():
    state = FakeState({"lang": "en", "nonce": "abcd", "version": 7}, UpdateStation.menu.state)
    callback = FakeCallback("st:abcd:6:update_field:name")
    await station_callback(callback, state)
    assert state.current == UpdateStation.menu.state
    assert callback.answers[0][1]["show_alert"] is True


@pytest.mark.asyncio
async def test_duplicate_update_is_idempotent(monkeypatch):
    calls = 0
    current = existing_station(address="Already applied")

    async def lookup(code):
        return current

    async def update(station_id, patch):
        nonlocal calls
        calls += 1

    monkeypatch.setattr("handlers.station.api.station_by_code", lookup)
    monkeypatch.setattr("handlers.station.api.update_station", update)
    state = FakeState(
        {
            "lang": "en", "nonce": "abcd", "version": 8, "saving": False,
            "code": "10002", "existing_station_id": 42, "patch": {"address": "Already applied"},
        },
        UpdateStation.confirm.state,
    )
    callback = FakeCallback("st:abcd:8:update_confirm:save")
    await _save_update(callback, state, "en")
    assert calls == 0


def test_create_payload_has_no_approval_or_operational_defaults():
    payload = _build_create(
        {"code": "10999", "name": "Display", "address": "Rudaki 10", "operational_area": None},
        1,
        2,
    )
    assert "approved_at" not in payload and "approved_by" not in payload
    assert "vpn_ip" not in payload and "local_ip" not in payload


async def _async(value):
    return value
