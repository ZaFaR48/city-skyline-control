from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Role, Station, StationStatus, User
from ..schemas import StationCreate, StationOut, StationUpdate

router = APIRouter()


@router.get("", response_model=list[StationOut])
async def list_stations(
    q: str | None = None,
    region: str | None = None,
    status: StationStatus | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Station)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            (Station.name.ilike(like)) | (Station.code.ilike(like)) |
            (Station.vpn_ip.ilike(like)) | (Station.address.ilike(like))
        )
    if region:
        stmt = stmt.where(Station.region == region)
    if status:
        stmt = stmt.where(Station.status == status)
    stmt = stmt.order_by(Station.name).limit(limit).offset(offset)
    return (await db.execute(stmt)).scalars().all()


@router.post("", response_model=StationOut, status_code=201,
             dependencies=[Depends(require_roles(Role.admin))])
async def create_station(data: StationCreate, db: AsyncSession = Depends(get_db)):
    s = Station(**data.model_dump())
    db.add(s); await db.commit(); await db.refresh(s)
    return s


@router.get("/{station_id}", response_model=StationOut)
async def get_station(station_id: int, db: AsyncSession = Depends(get_db),
                      _: User = Depends(get_current_user)):
    s = await db.get(Station, station_id)
    if not s: raise HTTPException(404, "Station not found")
    return s


@router.patch("/{station_id}", response_model=StationOut,
              dependencies=[Depends(require_roles(Role.admin, Role.operator))])
async def update_station(station_id: int, data: StationUpdate, db: AsyncSession = Depends(get_db)):
    s = await db.get(Station, station_id)
    if not s: raise HTTPException(404, "Station not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.commit(); await db.refresh(s)
    return s


@router.delete("/{station_id}", status_code=204,
               dependencies=[Depends(require_roles(Role.admin))])
async def delete_station(station_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(Station, station_id)
    if not s: raise HTTPException(404, "Station not found")
    await db.delete(s); await db.commit()
