from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models import PingHistory, User
from ..schemas import PingPoint

router = APIRouter()


@router.get("/{station_id}", response_model=list[PingPoint])
async def history(station_id: int,
                  limit: int = Query(200, le=2000),
                  db: AsyncSession = Depends(get_db),
                  _: User = Depends(get_current_user)):
    stmt = (select(PingHistory)
            .where(PingHistory.station_id == station_id)
            .order_by(PingHistory.checked_at.desc())
            .limit(limit))
    return (await db.execute(stmt)).scalars().all()
