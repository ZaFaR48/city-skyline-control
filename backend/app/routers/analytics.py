from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models import Alert, Camera, HeadscaleNode, Station, StationStatus, User
from ..schemas import SummaryOut

router = APIRouter()


@router.get("/summary", response_model=SummaryOut)
async def summary(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    async def cnt(stmt):
        return (await db.execute(stmt)).scalar_one() or 0

    return SummaryOut(
        stations_total   = await cnt(select(func.count(Station.id))),
        stations_online  = await cnt(select(func.count(Station.id)).where(Station.status == StationStatus.online)),
        stations_warning = await cnt(select(func.count(Station.id)).where(Station.status == StationStatus.warning)),
        stations_offline = await cnt(select(func.count(Station.id)).where(Station.status == StationStatus.offline)),
        cameras_total    = await cnt(select(func.count(Camera.id))),
        cameras_online   = await cnt(select(func.count(Camera.id)).where(Camera.status == StationStatus.online)),
        alerts_active    = await cnt(select(func.count(Alert.id)).where(Alert.acknowledged == False)),  # noqa: E712
        vpn_nodes        = await cnt(select(func.count(HeadscaleNode.id))),
    )
