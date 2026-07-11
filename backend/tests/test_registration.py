from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import RegistrationStatus, User, UserActivationToken, UserRegistrationRequest
from app.routers.registrations import activate_account, telegram_start
from app.schemas import ActivationIn, RegistrationUpsertIn
from app.services.registration import create_activation


def admin() -> User:
    return User(id=9000, username="admin-test", email="admin@test.invalid", hashed_password="x", role="admin", is_active=True)


@pytest.mark.asyncio
async def test_unknown_telegram_user_becomes_pending(db):
    result = await telegram_start(RegistrationUpsertIn(telegram_user_id=700001, first_name="New"), db, admin())
    assert result.status == RegistrationStatus.pending


@pytest.mark.asyncio
async def test_preapproved_user_receives_activation_flow(db):
    row = UserRegistrationRequest(telegram_user_id=700002, display_name="Approved", status="pre_approved", assigned_role="viewer")
    db.add(row)
    await db.commit()
    result = await telegram_start(RegistrationUpsertIn(telegram_user_id=700002, first_name="Approved"), db, admin())
    assert result.status == RegistrationStatus.approved
    assert result.activation_code and result.username


@pytest.mark.asyncio
async def test_activation_token_expires_and_is_single_use(db):
    row = UserRegistrationRequest(telegram_user_id=700003, status="pending", assigned_role="operator")
    db.add(row)
    await db.flush()
    user, code, _ = await create_activation(db, row)
    await db.commit()
    result = await activate_account(ActivationIn(code=code, password="A-secure-password-123"), db)
    assert result["status"] == "activated"
    with pytest.raises(HTTPException):
        await activate_account(ActivationIn(code=code, password="A-secure-password-123"), db)

    expired_row = UserRegistrationRequest(telegram_user_id=700004, status="pending", assigned_role="viewer")
    db.add(expired_row)
    await db.flush()
    _, expired_code, _ = await create_activation(db, expired_row)
    token = (await db.execute(select(UserActivationToken).order_by(UserActivationToken.id.desc()).limit(1))).scalar_one()
    token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await activate_account(ActivationIn(code=expired_code, password="A-secure-password-123"), db)
    assert "expired" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_rejected_user_cannot_register(db):
    row = UserRegistrationRequest(telegram_user_id=700005, status="rejected")
    db.add(row)
    await db.commit()
    result = await telegram_start(RegistrationUpsertIn(telegram_user_id=700005), db, admin())
    assert result.status == RegistrationStatus.rejected
