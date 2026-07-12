from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models import TelegramIdentity, TelegramSummarySetting, User
from app.routers.activity import telegram_summary_control
from app.schemas import TelegramSummaryControlIn


def service_admin() -> User:
    return User(id=9900, username="summary-service", email="summary-service@test.invalid", hashed_password="x", role="admin", is_active=True)


async def actor(db, suffix: str, role: str, *, active: bool = True):
    user = User(username=f"summary-control-{suffix}", email=f"summary-control-{suffix}@test.invalid", hashed_password="x", role=role, is_active=active)
    db.add(user)
    await db.flush()
    identity = TelegramIdentity(user_id=user.id, telegram_user_id=9500000 + user.id, preferred_language="en")
    db.add(identity)
    await db.flush()
    return user, identity


@pytest.mark.asyncio
async def test_admin_can_disable_enable_and_inspect_automatic_summary(db):
    _, identity = await actor(db, "admin", "admin")
    payload = lambda action: TelegramSummaryControlIn(telegram_user_id=identity.telegram_user_id, action=action)
    disabled = await telegram_summary_control(payload("disable"), db, service_admin())
    assert disabled.enabled is False
    enabled = await telegram_summary_control(payload("enable"), db, service_admin())
    assert enabled.enabled is True and enabled.caller_is_recipient is True
    status = await telegram_summary_control(payload("status"), db, service_admin())
    assert status.enabled is True and status.interval_minutes == 10
    assert status.recipient_count >= 1
    setting = await db.get(TelegramSummarySetting, 1)
    assert setting is not None and setting.enabled is True


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["operator", "viewer"])
async def test_non_admin_cannot_change_automatic_summary(db, role):
    _, identity = await actor(db, role, role)
    with pytest.raises(HTTPException) as exc:
        await telegram_summary_control(
            TelegramSummaryControlIn(telegram_user_id=identity.telegram_user_id, action="disable"),
            db,
            service_admin(),
        )
    assert exc.value.status_code == 403
