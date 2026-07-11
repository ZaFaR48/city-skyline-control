from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
    TelegramLinkApplyIn,
    TelegramLinkPreviewIn,
    TelegramLinkPreviewOut,
)
from ..security import hash_password
from ..services.audit import add_audit
from ..services.registration import create_activation, hash_activation_code
from ..services.confirmation_tokens import create_confirmation_token, verify_confirmation_token
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


@router.post("/{registration_id}/link-preview", response_model=TelegramLinkPreviewOut)
async def preview_existing_user_link(
    registration_id: int,
    data: TelegramLinkPreviewIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    registration = await _registration_or_404(db, registration_id)
    return await _existing_user_link_preview(db, registration, data.user_id)


@router.post("/{registration_id}/link-existing")
async def link_registration_to_existing_user(
    registration_id: int,
    data: TelegramLinkApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(Role.admin)),
):
    registration = await _registration_or_404(db, registration_id)
    preview = await _existing_user_link_preview(db, registration, data.user_id)
    if not preview.valid or not preview.preview_token:
        raise HTTPException(422, preview.errors)
    if data.confirmation != preview.confirmation_phrase:
        raise HTTPException(422, "Explicit Telegram link confirmation is required")
    payload = _existing_user_link_payload(registration, preview)
    if not verify_confirmation_token(data.preview_token, "telegram-existing-user-link", payload):
        raise HTTPException(409, "Link preview expired or account state changed; preview again")

    before = {"status": registration.status, "user_id": registration.user_id}
    db.add(
        TelegramIdentity(
            user_id=preview.user_id,
            telegram_user_id=registration.telegram_user_id,
            telegram_username=registration.telegram_username,
            first_name=registration.first_name,
            last_name=registration.last_name,
        )
    )
    registration.user_id = preview.user_id
    registration.status = RegistrationStatus.activated.value
    registration.reviewed_by = actor.id
    registration.reviewed_at = datetime.now(timezone.utc)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Telegram ID or system user is already linked") from exc
    add_audit(
        db,
        action="registration.link_existing_user",
        entity_type="user_registration_request",
        entity_id=registration.id,
        actor=actor,
        before=before,
        after={
            "status": registration.status,
            "user_id": preview.user_id,
            "telegram_user_id": registration.telegram_user_id,
            "role": preview.role.value,
        },
        request=request,
    )
    await db.commit()
    try:
        notification_sent = await send_telegram_to(
            registration.telegram_user_id,
            "Your Telegram account is now linked to City Parking.",
        )
    except Exception:
        notification_sent = False
    return {"status": "activated", "user_id": preview.user_id, "notification_sent": notification_sent}


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


async def _registration_or_404(db: AsyncSession, registration_id: int) -> UserRegistrationRequest:
    registration = await db.get(UserRegistrationRequest, registration_id)
    if not registration:
        raise HTTPException(404, "Registration request not found")
    return registration


async def _existing_user_link_preview(
    db: AsyncSession,
    registration: UserRegistrationRequest,
    user_id: int,
) -> TelegramLinkPreviewOut:
    user = await db.get(User, user_id)
    errors: list[str] = []
    if registration.status != RegistrationStatus.pending.value:
        errors.append("Only pending Telegram registrations can be linked")
    if not user:
        errors.append("System user not found")
    telegram_identity = (
        await db.execute(
            select(TelegramIdentity).where(
                TelegramIdentity.telegram_user_id == registration.telegram_user_id
            )
        )
    ).scalar_one_or_none()
    user_identity = (
        await db.execute(select(TelegramIdentity).where(TelegramIdentity.user_id == user_id))
    ).scalar_one_or_none()
    if telegram_identity:
        errors.append("Telegram ID is already linked to a system user")
    if user_identity:
        errors.append("System user already has a Telegram identity")

    username = user.username if user else "unknown"
    is_active = bool(user and user.is_active)
    warning = None if is_active else "Warning: the selected system user is inactive. Linking does not activate the user."
    confirmation_phrase = (
        f"LINK TELEGRAM {registration.telegram_user_id} TO {username}"
        if is_active
        else f"LINK TELEGRAM {registration.telegram_user_id} TO INACTIVE USER {username}"
    )
    preview = TelegramLinkPreviewOut(
        registration_id=registration.id,
        telegram_user_id=registration.telegram_user_id,
        telegram_username=registration.telegram_username,
        user_id=user_id,
        username=username,
        role=user.role if user else Role.viewer,
        is_active=is_active,
        warning=warning,
        confirmation_phrase=confirmation_phrase,
        valid=not errors,
        errors=errors,
        preview_token=None,
    )
    if preview.valid:
        preview.preview_token = create_confirmation_token(
            "telegram-existing-user-link",
            _existing_user_link_payload(registration, preview),
        )
    return preview


def _existing_user_link_payload(
    registration: UserRegistrationRequest,
    preview: TelegramLinkPreviewOut,
) -> dict[str, object]:
    return {
        "registration_id": registration.id,
        "registration_status": registration.status,
        "registration_user_id": registration.user_id,
        "telegram_user_id": registration.telegram_user_id,
        "user_id": preview.user_id,
        "username": preview.username,
        "role": preview.role.value,
        "is_active": preview.is_active,
    }
