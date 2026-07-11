from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import OperationalRegion, Role, User
from ..schemas import RegionCreate, RegionOut
from ..services.audit import add_audit


router = APIRouter()


@router.get("", response_model=list[RegionOut])
async def list_regions(
    active: bool | None = None,
    region_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(OperationalRegion)
    if active is not None:
        stmt = stmt.where(OperationalRegion.is_active == active)
    if region_type:
        stmt = stmt.where(OperationalRegion.region_type == region_type)
    return (await db.execute(stmt.order_by(OperationalRegion.sort_order, OperationalRegion.name))).scalars().all()


@router.post("", response_model=RegionOut, status_code=201)
async def create_region(
    data: RegionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    if data.parent_id and not await db.get(OperationalRegion, data.parent_id):
        raise HTTPException(422, "Parent region not found")
    region = OperationalRegion(**data.model_dump())
    db.add(region)
    await db.flush()
    add_audit(db, action="region.create", entity_type="operational_region", entity_id=region.id, actor=user, after=data.model_dump(), request=request)
    await db.commit()
    await db.refresh(region)
    return region
