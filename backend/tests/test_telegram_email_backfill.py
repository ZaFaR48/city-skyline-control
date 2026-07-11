from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user
from app.main import app
from app.models import User, UserRegistrationRequest
from app.schemas import UserOut
from app.services.registration import create_activation
from scripts.backfill_telegram_emails import backfill_telegram_emails


@pytest.mark.asyncio
async def test_telegram_created_user_validates_and_user_endpoints_return_200(db):
    registration = UserRegistrationRequest(telegram_user_id=880001, telegram_username="validmail", status="pending", assigned_role="admin")
    db.add(registration)
    await db.flush()
    user, _, _ = await create_activation(db, registration)
    await db.flush()
    assert user.email == "validmail@telegram.cityparking.tj"
    assert UserOut.model_validate(user).email == user.email

    async def current_user_override():
        return user

    async def db_override():
        yield db

    app.dependency_overrides[get_current_user] = current_user_override
    app.dependency_overrides[get_db] = db_override
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            me = await client.get("/api/auth/me")
            users = await client.get("/api/users")
            registrations = await client.get("/api/registrations")
        assert me.status_code == users.status_code == registrations.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_backfill_dry_run_and_apply_preserve_password_role_and_identity_fields(db):
    user = User(username="legacytelegram", email="legacytelegram@telegram.invalid", hashed_password="same-hash", role="viewer", is_active=True)
    db.add(user)
    await db.flush()
    original = (user.hashed_password, user.role, user.username)
    dry = await backfill_telegram_emails(db, apply=False)
    await db.refresh(user)
    assert dry[0].status == "would_apply"
    assert user.email.endswith("@telegram.invalid")
    applied = await backfill_telegram_emails(db, apply=True)
    await db.refresh(user)
    assert applied[0].status == "applied"
    assert user.email == "legacytelegram@telegram.cityparking.tj"
    assert (user.hashed_password, user.role, user.username) == original


@pytest.mark.asyncio
async def test_backfill_skips_duplicate_target_email(db):
    legacy = User(username="collision", email="collision@telegram.invalid", hashed_password="a", role="viewer", is_active=True)
    existing = User(username="other", email="collision@telegram.cityparking.tj", hashed_password="b", role="operator", is_active=True)
    db.add_all([legacy, existing])
    await db.flush()
    result = await backfill_telegram_emails(db, apply=True)
    await db.refresh(legacy)
    assert result[0].status == "skipped"
    assert legacy.email == "collision@telegram.invalid"
