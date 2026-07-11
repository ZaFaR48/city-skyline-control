from __future__ import annotations

import pytest

from handlers.start import _access_text
from handlers.station import _save_station, _summary
from states import AddStation


def payload(code: str = "10002") -> dict:
    return {
        "station_code": code,
        "name": "Station",
        "city_id": 1,
        "district_id": 2,
        "address": "Address",
        "vpn_ip": "100.64.0.2",
        "local_ip": "192.168.1.2",
        "rustdesk_id": "123",
        "latitude": 38.5,
        "longitude": 68.7,
    }


@pytest.mark.asyncio
async def test_existing_pending_station_updates_without_post_create(monkeypatch):
    calls = {"create": 0, "update": 0}

    async def lookup(code):
        return {"id": 42, "station_code": code, "approved_at": None}

    async def create(data):
        calls["create"] += 1
        return data

    async def update(station_id, data):
        calls["update"] += 1
        return {"id": station_id, **data, "approved_at": None}

    monkeypatch.setattr("handlers.station.api.station_by_code", lookup)
    monkeypatch.setattr("handlers.station.api.create_station", create)
    monkeypatch.setattr("handlers.station.api.update_station", update)
    saved, outcome = await _save_station(payload())
    assert saved["id"] == 42 and outcome == "saved_existing_pending"
    assert calls == {"create": 0, "update": 1}


@pytest.mark.asyncio
async def test_new_station_create_payload_is_pending_and_duplicate_click_is_idempotent(monkeypatch):
    stored = None
    calls = {"create": 0, "update": 0}

    async def lookup(code):
        return stored

    async def create(data):
        nonlocal stored
        calls["create"] += 1
        assert "approved_at" not in data and "approved_by" not in data
        stored = {"id": 50, **data, "approved_at": None}
        return stored

    async def update(station_id, data):
        calls["update"] += 1
        assert "approved_at" not in data and "approved_by" not in data
        return {"id": station_id, **data, "approved_at": None}

    monkeypatch.setattr("handlers.station.api.station_by_code", lookup)
    monkeypatch.setattr("handlers.station.api.create_station", create)
    monkeypatch.setattr("handlers.station.api.update_station", update)
    first, first_outcome = await _save_station(payload("10050"))
    second, second_outcome = await _save_station(payload("10050"))
    assert first["id"] == second["id"] == 50
    assert first_outcome == "saved_new_pending" and second_outcome == "saved_existing_pending"
    assert calls == {"create": 1, "update": 1}


@pytest.mark.asyncio
async def test_approved_station_update_preserves_approval_payload(monkeypatch):
    async def lookup(code):
        return {"id": 60, "station_code": code, "approved_at": "2026-01-01T00:00:00Z"}

    async def update(station_id, data):
        assert "approved_at" not in data and "approved_by" not in data
        return {"id": station_id, **data, "approved_at": "2026-01-01T00:00:00Z"}

    monkeypatch.setattr("handlers.station.api.station_by_code", lookup)
    monkeypatch.setattr("handlers.station.api.update_station", update)
    _, outcome = await _save_station(payload("10060"), allow_approved=True)
    assert outcome == "saved_approved"


def test_removed_wizard_fields_are_absent_from_states_and_summary():
    for field in ("camera_ip", "rtsp_url", "qr", "nfc"):
        assert not hasattr(AddStation, field)
    summary = _summary(
        "ru",
        {
            "code": "10002",
            "name": "Station",
            "region": "Sino",
            "address": "Address",
            "vpn_ip": None,
            "local_ip": None,
            "rustdesk_id": None,
            "lat": None,
            "lng": None,
            "existing_station_id": 1,
            "existing_approved": False,
        },
    )
    for removed in ("Camera", "RTSP", "QR", "NFC"):
        assert removed not in summary
    assert "Код:" in summary and "Район:" in summary


def test_my_access_contains_only_safe_identity_status():
    text = _access_text(
        "ru",
        {"username": "telegram-user", "role": "operator", "status": "activated", "activation_required": False},
    )
    assert "telegram-user" in text
    assert "Оператор" in text
    assert "activated" in text
    for secret in ("password", "token", "hash", "code"):
        assert secret not in text.lower()
