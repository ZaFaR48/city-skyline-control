from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import require_roles
from ..models import Role, User
from ..schemas import UserOut
from ..services.audit import add_audit


router = APIRouter()


class RoleUpdate(BaseModel):
    role: Role


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db), _: User = Depends(require_roles(Role.admin))):
    return (await db.execute(select(User).order_by(User.username))).scalars().all()


@router.patch("/{user_id}/role", response_model=UserOut)
async def update_role(
    user_id: int,
    data: RoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(Role.admin)),
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == actor.id and data.role != Role.admin:
        raise HTTPException(409, "Administrators cannot demote themselves")
    before = target.role
    target.role = data.role.value
    add_audit(db, action="user.role_change", entity_type="user", entity_id=target.id, actor=actor, before={"role": before}, after={"role": target.role}, request=request)
    await db.commit()
    await db.refresh(target)
    return target
