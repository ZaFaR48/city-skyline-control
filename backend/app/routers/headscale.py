from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import HeadscaleNode, Role, User
from ..schemas import HeadscaleNodeOut
from ..services.headscale import sync_headscale_nodes

router = APIRouter()


@router.get("/nodes", response_model=list[HeadscaleNodeOut])
async def list_nodes(db: AsyncSession = Depends(get_db),
                     _: User = Depends(get_current_user)):
    return (await db.execute(select(HeadscaleNode).order_by(HeadscaleNode.hostname))).scalars().all()


@router.post("/sync", dependencies=[Depends(require_roles(Role.admin))])
async def sync_now():
    added = await sync_headscale_nodes()
    return {"added": added}
