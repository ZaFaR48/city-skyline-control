from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (
    AuditSource,
    RegistrationStatus,
    Role,
    TelegramIdentity,
    User,
    UserActivationToken,
    UserRegistrationRequest,
)
from ..schemas import (
    ActivationIn,
    RegistrationOut,
    RegistrationPreApproveIn,
    RegistrationReviewIn,
    RegistrationStatusOut,
    RegistrationUpsertIn,
)
from ..security import hash_password
from ..services.audit import add_audit
from ..services.registration import create_activation, hash_activation_code
from ..services.telegram import send_telegram_to


router = APIRouter()


@router.post("/telegram/start", response_model=RegistrationStatusOut)
async def telegram_start(
    data: RegistrationUpsertIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    identity = (
        await db.execute(
            select(TelegramIdentity).where(TelegramIdentity.telegram_user_id == data.telegram_user_id)
        )
    ).scalar_one_or_none()
    if identity:
        user = await db.get(User, identity.user_id)
        return RegistrationStatusOut(
            status=RegistrationStatus.activated if user and user.is_active else RegistrationStatus.approved,
            username=user.username if user else None,
            role=user.role if user else None,
        )

    registration = (
        await db.execute(
            select(UserRegistrationRequest).where(
                UserRegistrationRequest.telegram_user_id == data.telegram_user_id
            )
        )
    ).scalar_one_or_none()
    if registration is None:
        registration = UserRegistrationRequest(
            **data.model_dump(),
            status=RegistrationStatus.pending.value,
        )
        db.add(registration)
        await db.commit()
        return RegistrationStatusOut(status=RegistrationStatus.pending)

    registration.telegram_username = data.telegram_username
    registration.first_name = data.first_name
    registration.last_name = data.last_name
    if registration.status == RegistrationStatus.pre_approved.value:
        user, code, expires_at = await create_activation(db, registration)
        add_audit(
            db,
            action="registration.preapproved_started",
            entity_type="user_registration_request",
            entity_id=registration.id,
            after={"user_id": user.id, "role": user.role},
            source=AuditSource.telegram,
        )
        await db.commit()
        return RegistrationStatusOut(status=RegistrationStatus.approved, username=user.username, role=user.role, activation_code=code, expires_at=expires_at)
    await db.commit()
    return RegistrationStatusOut(status=registration.status)


@router.get("", response_model=list[RegistrationOut])
async def list_registrations(
    status: RegistrationStatus | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    stmt = select(UserRegistrationRequest)
    if status:
        stmt = stmt.where(UserRegistrationRequest.status == status.value)
    return (await db.execute(stmt.order_by(UserRegistrationRequest.requested_at.desc()))).scalars().all()


@router.post("/preapprove", response_model=RegistrationOut, status_code=201)
async def preapprove(
    data: RegistrationPreApproveIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    existing = (
        await db.execute(
            select(UserRegistrationRequest).where(
                UserRegistrationRequest.telegram_user_id == data.telegram_user_id
            )
        )
    ).scalar_one_or_none()
    if existing and existing.status == RegistrationStatus.activated.value:
        raise HTTPException(409, "Telegram user is already registered")
    registration = existing or UserRegistrationRequest(telegram_user_id=data.telegram_user_id)
    registration.telegram_username = data.telegram_username
    registration.display_name = data.display_name
    registration.assigned_role = data.role.value
    registration.status = RegistrationStatus.pre_approved.value
    if not existing:
        db.add(registration)
    await db.flush()
    add_audit(db, action="registration.preapprove", entity_type="user_registration_request", entity_id=registration.id, actor=user, after={"telegram_user_id": data.telegram_user_id, "role": data.role.value}, request=request)
    await db.commit()
    await db.refresh(registration)
    return registration


@router.post("/{registration_id}/review", response_model=RegistrationStatusOut)
async def review_registration(
    registration_id: int,
    data: RegistrationReviewIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(Role.admin)),
):
    registration = await db.get(UserRegistrationRequest, registration_id)
    if not registration:
        raise HTTPException(404, "Registration request not found")
    own_identity = (
        await db.execute(
            select(TelegramIdentity).where(
                TelegramIdentity.user_id == actor.id,
                TelegramIdentity.telegram_user_id == registration.telegram_user_id,
            )
        )
    ).scalar_one_or_none()
    if own_identity:
        raise HTTPException(403, "An administrator cannot approve their own registration request")
    before = {"status": registration.status, "assigned_role": registration.assigned_role}
    registration.reviewed_by = actor.id
    registration.reviewed_at = datetime.now(timezone.utc)

    if data.action == "reject":
        registration.status = RegistrationStatus.rejected.value
        action = "registration.reject"
        result = RegistrationStatusOut(status=RegistrationStatus.rejected)
    elif data.action == "clarification":
        registration.status = RegistrationStatus.clarification_requested.value
        registration.clarification = data.clarification
        action = "registration.clarification"
        result = RegistrationStatusOut(status=RegistrationStatus.clarification_requested)
    else:
        if data.role is None:
            raise HTTPException(422, "role is required when approving")
        registration.assigned_role = data.role.value
        user, code, expires_at = await create_activation(db, registration)
        action = "registration.approve"
        result = RegistrationStatusOut(status=RegistrationStatus.approved, username=user.username, activation_code=code, expires_at=expires_at)

    add_audit(db, action=action, entity_type="user_registration_request", entity_id=registration.id, actor=actor, before=before, after={"status": registration.status, "assigned_role": registration.assigned_role}, request=request)
    await db.commit()
    if data.action == "approve" and result.activation_code:
        await send_telegram_to(
            registration.telegram_user_id,
            f"City Parking access approved.\nUsername: {result.username}\n"
            f"Activation: {settings.PUBLIC_WEB_URL}/activate?code={result.activation_code}\n"
            f"This single-use code expires in {settings.ACTIVATION_TOKEN_TTL_MINUTES} minutes.",
        )
    return result


@router.post("/activate")
async def activate_account(data: ActivationIn, db: AsyncSession = Depends(get_db)):
    token = (
        await db.execute(
            select(UserActivationToken).where(
                UserActivationToken.token_hash == hash_activation_code(data.code)
            )
        )
    ).scalar_one_or_none()
    if token is None:
        raise HTTPException(400, "Invalid activation code")
    token.attempt_count += 1
    now = datetime.now(timezone.utc)
    if token.used_at is not None:
        await db.commit()
        raise HTTPException(400, "Activation code has already been used")
    if token.expires_at <= now:
        await db.commit()
        raise HTTPException(400, "Activation code has expired")
    user = await db.get(User, token.user_id)
    if not user:
        raise HTTPException(400, "Activation account no longer exists")
    user.hashed_password = hash_password(data.password)
    user.is_active = True
    token.used_at = now
    registration = (
        await db.execute(
            select(UserRegistrationRequest).where(UserRegistrationRequest.user_id == user.id)
        )
    ).scalar_one_or_none()
    if registration:
        registration.status = RegistrationStatus.activated.value
    add_audit(db, action="user.activate", entity_type="user", entity_id=user.id, actor=None, after={"is_active": True}, source=AuditSource.web)
    await db.commit()
    return {"status": "activated", "username": user.username}
