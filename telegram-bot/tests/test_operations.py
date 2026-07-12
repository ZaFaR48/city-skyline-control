from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers.operations import (
    _send_district,
    chunk_station_messages,
    format_station_summary,
    operations_code_input,
    operations_menu,
)
from states import OperationsLookup


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


class FakeMessage:
    def __init__(self, text="", user_id=10):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id, username="operator", first_name="Operator", last_name=None)
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs.get("reply_markup")))


def station(**overrides):
    row = {
        "id": 1,
        "station_code": "10042",
        "name": "Sino Customs",
        "city": "Dushanbe",
        "district": "Sino",
        "operational_area": "Customs",
        "address": "Rudaki 10",
        "vpn_ip": "100.64.0.42",
        "local_ip": "192.168.1.42",
        "latitude": 38.55,
        "longitude": 68.77,
        "approved_at": "2026-07-12T12:00:00Z",
        "is_active": True,
        "is_archived": False,
        "headscale_hostname": "station-10042",
        "health": {
            "overall_status": "online",
            "overall_reason_code": "HEALTHY",
            "current_state_duration_seconds": 600,
            "connectivity_status": "online",
            "headscale_status": "online",
            "agent_status": "not_configured",
            "camera_status": "not_configured",
            "internet_status": "not_configured",
            "local_service_status": "not_configured",
            "observed_at": "2026-07-12T12:00:00+00:00",
        },
    }
    row.update(overrides)
    return row


async def activated(_user):
    return {"user_id": 1, "username": "operator", "is_active": True, "role": "operator"}


@pytest.mark.asyncio
async def test_exact_station_lookup_returns_full_details(monkeypatch):
    monkeypatch.setattr("handlers.operations.api.resolve_telegram_user", activated)

    async def rows(view, query=None):
        assert view == "all" and query == "10042"
        return [station()]

    monkeypatch.setattr("handlers.operations.api.operational_stations", rows)
    state = FakeState({"lang": "en"}, OperationsLookup.code.state)
    message = FakeMessage("10042")
    await operations_code_input(message, state)
    text = "\n".join(item[0] for item in message.answers)
    assert "10042 · Sino Customs" in text
    assert "Status: Online" in text
    assert "Station connectivity: online" in text and "Headscale: online" in text


@pytest.mark.asyncio
async def test_district_lookup_filters_exact_canonical_district(monkeypatch):
    async def rows(view, query=None):
        return [station(), station(id=2, station_code="10043", district="Shohmansur")]

    monkeypatch.setattr("handlers.operations.api.operational_stations", rows)
    state = FakeState({"lang": "en"})
    message = FakeMessage()
    await _send_district(message, state, "sino")
    text = "\n".join(item[0] for item in message.answers)
    assert "10042" in text and "10043" not in text


def test_long_station_results_are_chunked_safely():
    rows = [station(id=index, station_code=f"1{index:04d}", name="X" * 80) for index in range(80)]
    chunks = chunk_station_messages(rows, "en", limit=250)
    assert len(chunks) > 1
    assert all(len(chunk) <= 250 for chunk in chunks)
    assert "10000" in chunks[0]


def test_station_summary_localizes_labels():
    russian = format_station_summary(station(), "ru")
    tajik = format_station_summary(station(), "tj")
    assert "Статус:" in russian and "Связь со станцией:" in russian
    assert "Ҳолат:" in tajik and "Алоқа бо стансия:" in tajik


def test_concise_summary_has_healthy_ids_only_and_measured_problem_reason():
    degraded_health = {
        **station()["health"],
        "overall_status": "degraded",
        "overall_reason_code": "CAMERA_OFFLINE",
        "current_state_duration_seconds": 18 * 60,
        "camera_status": "offline",
    }
    text = "\n".join(chunk_station_messages([
        station(station_code="10002", name="Secret healthy name"),
        station(id=2, station_code="10008", health=degraded_health),
    ], "tj"))
    assert "10002" in text and "Secret healthy name" not in text
    assert "10008 — стансия онлайн, камера хомӯш · 18 дақ" in text
    assert "Rudaki" not in text and "100.64" not in text


@pytest.mark.asyncio
async def test_viewer_can_use_read_only_operational_summaries(monkeypatch):
    async def viewer(_user):
        return {"user_id": 2, "username": "viewer", "is_active": True, "role": "viewer"}

    monkeypatch.setattr("handlers.operations.api.resolve_telegram_user", viewer)
    state = FakeState({"lang": "en"})
    message = FakeMessage("📋 Station summaries")
    await operations_menu(message, state)
    assert "Station operations" in message.answers[0][0]
