from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import (
    RegistrationStatus,
    TelegramIdentity,
    User,
    UserActivationToken,
    UserRegistrationRequest,
)


def hash_activation_code(code: str) -> str:
    return sha256(code.encode("utf-8")).hexdigest()


async def create_activation(
    db: AsyncSession,
    registration: UserRegistrationRequest,
) -> tuple[User, str, datetime]:
    if registration.user_id:
        user = await db.get(User, registration.user_id)
        if user is None:
            raise RuntimeError("Registration references a missing user")
    else:
        username = await _unique_username(db, registration)
        user = User(
            username=username,
            email=f"{username}@telegram.cityparking.tj",
            hashed_password="!activation-required!",
            role=registration.assigned_role or "viewer",
            is_active=False,
        )
        db.add(user)
        await db.flush()
        registration.user_id = user.id

    identity = (
        await db.execute(
            select(TelegramIdentity).where(
                TelegramIdentity.telegram_user_id == registration.telegram_user_id
            )
        )
    ).scalar_one_or_none()
    if identity is None:
        db.add(
            TelegramIdentity(
                user_id=user.id,
                telegram_user_id=registration.telegram_user_id,
                telegram_username=registration.telegram_username,
                first_name=registration.first_name,
                last_name=registration.last_name,
            )
        )

    code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACTIVATION_TOKEN_TTL_MINUTES)
    db.add(
        UserActivationToken(
            user_id=user.id,
            token_hash=hash_activation_code(code),
            expires_at=expires_at,
        )
    )
    registration.status = RegistrationStatus.approved.value
    return user, code, expires_at


def create_user_reset_token(db: AsyncSession, user: User) -> tuple[str, datetime]:
    code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACTIVATION_TOKEN_TTL_MINUTES)
    db.add(
        UserActivationToken(
            user_id=user.id,
            token_hash=hash_activation_code(code),
            expires_at=expires_at,
        )
    )
    return code, expires_at


async def _unique_username(db: AsyncSession, registration: UserRegistrationRequest) -> str:
    raw = (registration.telegram_username or f"telegram_{registration.telegram_user_id}").lower()
    base = "".join(char for char in raw if char.isalnum() or char in "_-")[:48] or f"telegram_{registration.telegram_user_id}"
    candidate = base
    suffix = 1
    while (
        await db.execute(select(User.id).where(User.username == candidate))
    ).scalar_one_or_none() is not None:
        suffix += 1
        candidate = f"{base[:55]}_{suffix}"
    return candidate
