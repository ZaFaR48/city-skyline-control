from __future__ import annotations

from aiogram.fsm.context import FSMContext

from api import BackendAPIError, api


async def require_telegram_roles(event, state: FSMContext, *roles: str) -> dict | None:
    user = getattr(event, "from_user", None)
    if user is None:
        return None
    try:
        resolved = await api.resolve_telegram_user(user)
    except BackendAPIError:
        return None
    if not resolved.get("is_active") or resolved.get("role") not in roles:
        return None
    await state.update_data(
        access_status="activated",
        role=resolved.get("role"),
        user_id=resolved.get("user_id"),
        system_username=resolved.get("username"),
    )
    return resolved
