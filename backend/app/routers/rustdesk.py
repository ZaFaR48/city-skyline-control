from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Role, RustdeskDevice, Station, User
from ..services.station_visibility import production_station_filter

router = APIRouter()


@router.get("")
async def list_devices(db: AsyncSession = Depends(get_db),
                       _: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(RustdeskDevice, Station)
        .join(Station, RustdeskDevice.station_id == Station.id)
        .where(production_station_filter())
    )).all()
    return [{
        "station_code": s.station_code, "station": s.name, "district_id": s.district_id, "vpn_ip": s.vpn_ip,
        "rustdesk_id": d.rustdesk_id,
    } for d, s in rows]


@router.put("/{station_id}",
            dependencies=[Depends(require_roles(Role.admin, Role.operator))])
async def upsert_device(station_id: int, rustdesk_id: str,
                        db: AsyncSession = Depends(get_db)):
    s = await db.get(Station, station_id)
    if not s: raise HTTPException(404, "Station not found")
    d = (await db.execute(
        select(RustdeskDevice).where(RustdeskDevice.station_id == station_id)
    )).scalar_one_or_none()
    if d:
        d.rustdesk_id = rustdesk_id
    else:
        db.add(RustdeskDevice(station_id=station_id, rustdesk_id=rustdesk_id))
    s.rustdesk_id = rustdesk_id
    await db.commit()
    return {"ok": True}
