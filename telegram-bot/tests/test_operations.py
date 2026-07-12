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
    return {
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
        "approved_at": None,
        "is_active": True,
        "is_archived": False,
        "headscale_hostname": "station-10042",
        **overrides,
    }


async def activated(_user):
    return {"status": "activated", "role": "operator"}


@pytest.mark.asyncio
async def test_exact_station_lookup_returns_full_details(monkeypatch):
    monkeypatch.setattr("handlers.operations.api.registration_start", activated)

    async def rows(view, query=None):
        assert view == "all" and query == "10042"
        return [station()]

    monkeypatch.setattr("handlers.operations.api.operational_stations", rows)
    state = FakeState({"lang": "en"}, OperationsLookup.code.state)
    message = FakeMessage("10042")
    await operations_code_input(message, state)
    text = "\n".join(item[0] for item in message.answers)
    assert "10042 · Sino Customs" in text
    assert "Customs" in text and "Rudaki 10" in text
    assert "station-10042" in text and "100.64.0.42" in text


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
    chunks = chunk_station_messages(rows, "en", limit=700)
    assert len(chunks) > 1
    assert all(len(chunk) <= 700 for chunk in chunks)
    assert "10000" in chunks[0]


def test_station_summary_localizes_labels():
    russian = format_station_summary(station(), "ru")
    tajik = format_station_summary(station(), "tj")
    assert "Город:" in russian and "Район:" in russian
    assert "Шаҳр:" in tajik and "Ноҳия:" in tajik


@pytest.mark.asyncio
async def test_viewer_is_denied_operational_summaries(monkeypatch):
    async def viewer(_user):
        return {"status": "activated", "role": "viewer"}

    monkeypatch.setattr("handlers.operations.api.registration_start", viewer)
    state = FakeState({"lang": "en"})
    message = FakeMessage("📋 Station summaries")
    await operations_menu(message, state)
    assert "only to administrators and operators" in message.answers[0][0]
