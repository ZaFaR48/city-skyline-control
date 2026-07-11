from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, AuditSource, User


SENSITIVE_PARTS = ("password", "token", "secret", "authorization", "database_url", "api_key")


def sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if any(part in str(key).lower() for part in SENSITIVE_PARTS) else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def add_audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    actor: User | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    source: AuditSource | str = AuditSource.api,
    request: Request | None = None,
) -> None:
    source_value = source.value if isinstance(source, AuditSource) else source
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before_data=sanitize(before),
            after_data=sanitize(after),
            source=source_value,
            ip_address=request.client.host if request and request.client else None,
        )
    )
