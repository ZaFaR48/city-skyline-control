from __future__ import annotations

import pytest
from fastapi import HTTPException
import httpx

from app.database import get_db
from app.deps import require_roles
from app.deps import get_current_user
from app.main import app
from app.models import Role, User


def user(role: str) -> User:
    return User(id=1, username=role, email=f"{role}@test.invalid", hashed_password="x", role=role, is_active=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "allowed"),
    [("admin", True), ("operator", False), ("viewer", False)],
)
async def test_admin_only_permissions(role, allowed):
    dependency = require_roles(Role.admin)
    if allowed:
        assert await dependency(user(role))
    else:
        with pytest.raises(HTTPException) as exc:
            await dependency(user(role))
        assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "allowed"),
    [("admin", True), ("operator", True), ("viewer", False)],
)
async def test_operator_write_and_viewer_read_only(role, allowed):
    dependency = require_roles(Role.admin, Role.operator)
    if allowed:
        assert await dependency(user(role))
    else:
        with pytest.raises(HTTPException) as exc:
            await dependency(user(role))
        assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "method", "path", "json"),
    [
        ("viewer", "POST", "/api/stations", {}),
        ("viewer", "PATCH", "/api/stations/1", {}),
        ("viewer", "DELETE", "/api/stations/1", None),
        ("viewer", "POST", "/api/cameras", {}),
        ("viewer", "POST", "/api/alerts/1/ack", None),
        ("operator", "POST", "/api/alerts/1/resolve", None),
        ("operator", "GET", "/api/headscale/nodes/pending", None),
        ("operator", "POST", "/api/headscale/nodes/1/approve", {"device_type": "phone"}),
        ("operator", "POST", "/api/headscale/nodes/1/approval-preview", {"device_type": "phone"}),
        ("operator", "POST", "/api/headscale/nodes/1/reject", None),
        ("operator", "POST", "/api/headscale/nodes/1/link-station", {"station_id": 1}),
        ("operator", "POST", "/api/headscale/nodes/1/unlink-station", None),
        ("operator", "POST", "/api/headscale/sync", None),
        ("operator", "POST", "/api/regions", {}),
        ("operator", "GET", "/api/reports/uptime.csv?start=2026-01-01T00:00:00Z&end=2026-01-02T00:00:00Z", None),
        ("operator", "GET", "/api/registrations", None),
        ("operator", "POST", "/api/registrations/preapprove", {}),
        ("operator", "POST", "/api/registrations/1/review", {"action": "reject"}),
        ("operator", "GET", "/api/users", None),
        ("operator", "PATCH", "/api/users/1/role", {"role": "viewer"}),
        ("operator", "GET", "/api/audit", None),
        ("operator", "GET", "/api/onboarding/districts/stations", None),
        ("operator", "POST", "/api/onboarding/districts/preview", {"assignments": []}),
        ("operator", "POST", "/api/onboarding/districts/apply", {"assignments": [], "preview_token": "x", "confirmation": "ASSIGN DISTRICTS"}),
        ("operator", "GET", "/api/onboarding/duplicate-vpn", None),
        ("operator", "GET", "/api/onboarding/duplicate-alerts", None),
        ("operator", "POST", "/api/onboarding/duplicate-vpn/action-preview", {}),
        ("operator", "POST", "/api/onboarding/duplicate-vpn/action-apply", {"action": "cancel", "vpn_ip": "100.64.0.1", "preview_token": "x", "confirmation": "APPLY VPN ACTION"}),
        ("viewer", "POST", "/api/webhooks/n8n/test", None),
    ],
)
async def test_sensitive_endpoints_reject_unauthorized_roles(role, method, path, json):
    async def current_user_override():
        return user(role)

    async def db_override():
        yield object()

    app.dependency_overrides[get_current_user] = current_user_override
    app.dependency_overrides[get_db] = db_override
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.request(method, path, json=json)
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
