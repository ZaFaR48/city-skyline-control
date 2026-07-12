from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import AuditLog, RegistrationStatus, TelegramIdentity, User, UserActivationToken, UserRegistrationRequest
from app.routers.registrations import (
    activate_account,
    initiate_password_reset,
    link_registration_to_existing_user,
    preview_password_reset,
    preview_existing_user_link,
    set_telegram_language,
    telegram_start,
)
from app.schemas import ActivationIn, PasswordResetApplyIn, RegistrationUpsertIn, TelegramLanguageIn, TelegramLinkApplyIn, TelegramLinkPreviewIn
from app.routers.auth import login
from app.schemas import LoginIn
from app.security import hash_password
from app.services.registration import create_activation
from starlette.requests import Request


def admin() -> User:
    return User(id=9000, username="admin-test", email="admin@test.invalid", hashed_password="x", role="admin", is_active=True)


def request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1)})


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
    assert result.status == "activated"
    assert result.username == user.username
    assert result.role == "operator"
    assert result.is_active is True
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


@pytest.mark.asyncio
async def test_language_preference_persists_for_pending_and_activated_users(db):
    pending_id = 700006
    await set_telegram_language(TelegramLanguageIn(telegram_user_id=pending_id, language="ru"), db, admin())
    pending = await telegram_start(RegistrationUpsertIn(telegram_user_id=pending_id), db, admin())
    assert pending.preferred_language == "ru"

    user = User(username="language-user", email="language-user@test.invalid", hashed_password="x", role="operator", is_active=True)
    db.add(user)
    await db.flush()
    identity = TelegramIdentity(user_id=user.id, telegram_user_id=700007, preferred_language="tj")
    db.add(identity)
    await db.flush()
    await set_telegram_language(TelegramLanguageIn(telegram_user_id=700007, language="en"), db, admin())
    db.expire_all()
    activated = await telegram_start(RegistrationUpsertIn(telegram_user_id=700007), db, admin())
    assert activated.preferred_language == "en"


@pytest.mark.asyncio
async def test_existing_user_link_preserves_user_and_password_and_writes_audit(db, monkeypatch):
    actor = User(username="link-admin", email="link-admin@test.invalid", hashed_password="admin-hash", role="admin", is_active=True)
    target = User(username="existing-user", email="existing-user@test.invalid", hashed_password="original-password-hash", role="operator", is_active=True)
    registration = UserRegistrationRequest(telegram_user_id=1361661042, telegram_username="pending", status="pending")
    db.add_all([actor, target, registration])
    await db.flush()
    users_before = await db.scalar(select(func.count()).select_from(User))
    monkeypatch.setattr("app.routers.registrations.send_telegram_to", lambda *args, **kwargs: _true())

    preview = await preview_existing_user_link(registration.id, TelegramLinkPreviewIn(user_id=target.id), db, actor)
    result = await link_registration_to_existing_user(
        registration.id,
        TelegramLinkApplyIn(user_id=target.id, preview_token=preview.preview_token or "", confirmation=preview.confirmation_phrase),
        request(),
        db,
        actor,
    )
    await db.refresh(target)
    await db.refresh(registration)
    identity = (await db.execute(select(TelegramIdentity).where(TelegramIdentity.telegram_user_id == 1361661042))).scalar_one()
    assert result["status"] == "activated"
    assert identity.user_id == target.id and registration.user_id == target.id
    assert target.hashed_password == "original-password-hash"
    assert target.role == "operator"
    assert await db.scalar(select(func.count()).select_from(User)) == users_before
    assert await db.scalar(select(func.count()).select_from(UserActivationToken).where(UserActivationToken.user_id == target.id)) == 0
    audit = (await db.execute(select(AuditLog).where(AuditLog.action == "registration.link_existing_user"))).scalar_one()
    assert audit.actor_user_id == actor.id


@pytest.mark.asyncio
async def test_duplicate_existing_user_telegram_link_is_rejected(db):
    actor = User(username="duplicate-admin", email="duplicate-admin@test.invalid", hashed_password="x", role="admin", is_active=True)
    target = User(username="already-linked", email="already-linked@test.invalid", hashed_password="x", role="viewer", is_active=True)
    first = UserRegistrationRequest(telegram_user_id=700010, status="activated")
    second = UserRegistrationRequest(telegram_user_id=700011, status="pending")
    db.add_all([actor, target, first, second])
    await db.flush()
    db.add(TelegramIdentity(user_id=target.id, telegram_user_id=first.telegram_user_id))
    await db.flush()
    preview = await preview_existing_user_link(second.id, TelegramLinkPreviewIn(user_id=target.id), db, actor)
    assert not preview.valid
    assert "already has a Telegram identity" in " ".join(preview.errors)


@pytest.mark.asyncio
async def test_telegram_id_cannot_be_linked_to_a_second_user(db):
    actor = User(username="telegram-id-admin", email="telegram-id-admin@test.invalid", hashed_password="x", role="admin", is_active=True)
    linked = User(username="telegram-owner", email="telegram-owner@test.invalid", hashed_password="x", role="viewer", is_active=True)
    target = User(username="telegram-target", email="telegram-target@test.invalid", hashed_password="x", role="viewer", is_active=True)
    registration = UserRegistrationRequest(telegram_user_id=700012, status="pending")
    db.add_all([actor, linked, target, registration])
    await db.flush()
    db.add(TelegramIdentity(user_id=linked.id, telegram_user_id=registration.telegram_user_id))
    await db.flush()
    preview = await preview_existing_user_link(registration.id, TelegramLinkPreviewIn(user_id=target.id), db, actor)
    assert not preview.valid
    assert "Telegram ID is already linked" in " ".join(preview.errors)


@pytest.mark.asyncio
async def test_login_still_requires_exact_username_and_valid_password(db):
    user = User(
        username="telegram-exact-user",
        email="telegram-login@test.invalid",
        hashed_password=hash_password("Correct-password-123"),
        role="operator",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    tokens = await login(LoginIn(username=user.username, password="Correct-password-123"), db)
    assert tokens.access_token
    with pytest.raises(HTTPException):
        await login(LoginIn(username="admin", password="Correct-password-123"), db)


@pytest.mark.asyncio
async def test_admin_password_reset_creates_single_use_token_without_changing_password(db, monkeypatch):
    actor = User(username="reset-admin", email="reset-admin@test.invalid", hashed_password="x", role="admin", is_active=True)
    target = User(username="reset-target", email="reset-target@test.invalid", hashed_password="original-hash", role="viewer", is_active=True)
    registration = UserRegistrationRequest(telegram_user_id=700020, status="activated")
    db.add_all([actor, target, registration])
    await db.flush()
    registration.user_id = target.id
    db.add(TelegramIdentity(user_id=target.id, telegram_user_id=registration.telegram_user_id))
    await db.flush()
    monkeypatch.setattr("app.routers.registrations.send_telegram_to", lambda *args, **kwargs: _true())
    preview = await preview_password_reset(registration.id, db, actor)
    result = await initiate_password_reset(
        registration.id,
        PasswordResetApplyIn(preview_token=preview.preview_token or "", confirmation=preview.confirmation_phrase),
        request(),
        db,
        actor,
    )
    await db.refresh(target)
    assert result["status"] == "sent"
    assert target.hashed_password == "original-hash"
    assert await db.scalar(select(func.count()).select_from(UserActivationToken).where(UserActivationToken.user_id == target.id)) == 1


async def _true() -> bool:
    return True
