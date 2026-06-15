from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Camera, Role, User
from ..schemas import CameraCreate, CameraOut

router = APIRouter()


@router.get("", response_model=list[CameraOut])
async def list_cameras(station_id: int | None = None,
                       db: AsyncSession = Depends(get_db),
                       _: User = Depends(get_current_user)):
    stmt = select(Camera)
    if station_id:
        stmt = stmt.where(Camera.station_id == station_id)
    return (await db.execute(stmt.order_by(Camera.id))).scalars().all()


@router.post("", response_model=CameraOut, status_code=201,
             dependencies=[Depends(require_roles(Role.admin))])
async def create_camera(data: CameraCreate, db: AsyncSession = Depends(get_db)):
    c = Camera(**data.model_dump())
    db.add(c); await db.commit(); await db.refresh(c)
    return c


@router.delete("/{camera_id}", status_code=204,
               dependencies=[Depends(require_roles(Role.admin))])
async def delete_camera(camera_id: int, db: AsyncSession = Depends(get_db)):
    c = await db.get(Camera, camera_id)
    if not c: raise HTTPException(404, "Camera not found")
    await db.delete(c); await db.commit()
