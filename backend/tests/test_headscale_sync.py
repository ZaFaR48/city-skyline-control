from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.config import settings
from app.services import headscale


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"nodes": [{"id": "stable-duplicate-vpn", "name": "device", "ipAddresses": ["100.64.0.4"], "online": True}]}


class Client:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        return Response()


@pytest.mark.asyncio
async def test_duplicate_station_vpn_does_not_break_inventory_sync(monkeypatch):
    monkeypatch.setattr(settings, "HEADSCALE_URL", "http://headscale.test")
    monkeypatch.setattr(settings, "HEADSCALE_API_KEY", "test-only")
    monkeypatch.setattr(headscale.httpx, "AsyncClient", Client)
    assert await headscale.sync_headscale_nodes() in {0, 1}
