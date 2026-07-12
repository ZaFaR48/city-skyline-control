from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import String, asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (
    Alert,
    ApprovalStatus,
    AuditLog,
    Camera,
    DeviceType,
    HeadscaleNode,
    OperationalRegion,
    PingHistory,
    Role,
    Station,
    StationStatus,
    StationStatusEvent,
    User,
)
from ..schemas import StationCreate, StationDetailOut, StationListOut, StationOut, StationUpdate
from ..services.audit import add_audit
from ..services.ping_monitor import ping_station
from ..services.station_views import serialize_stations
from ..services.station_permissions import enforce_station_create_policy, enforce_station_update_policy
from ..services.operator_activity import add_activity_event, touch_presence
from ..services.station_visibility import production_station_filter


router = APIRouter()


@router.get("", response_model=StationListOut)
async def list_stations(
    q: str | None = None,
    city_id: int | None = None,
    city_code: str | None = "dushanbe",
    district_id: int | None = None,
    status: StationStatus | None = None,
    monitoring_configured: bool | None = None,
    headscale_linked: bool | None = None,
    active: bool | None = True,
    archived: bool | None = False,
    sort: str = Query("station_code", pattern=r"^(station_code|name|district|status|ping|offline_duration|last_seen)$"),
    direction: str = Query("asc", pattern=r"^(asc|desc)$"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    approval: str = Query("approved", pattern=r"^(pending|approved|all)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    district = aliased(OperationalRegion)
    city = aliased(OperationalRegion)
    node = aliased(HeadscaleNode)
    stmt = (
        select(Station)
        .join(city, Station.city_id == city.id)
        .outerjoin(district, Station.district_id == district.id)
        .outerjoin(
            node,
            (node.station_id == Station.id)
            & (node.approval_status == ApprovalStatus.approved.value)
            & (node.device_type == DeviceType.station.value),
        )
        .options(selectinload(Station.city), selectinload(Station.district))
    )
    filters = []
    if user.role != Role.admin.value and approval != "approved":
        raise HTTPException(403, "Only administrators may view pending stations")
    if approval == "approved":
        filters.append(production_station_filter())
    elif approval == "pending":
        filters.append(Station.approved_at.is_(None))
    if q and q.strip():
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                Station.station_code.ilike(like),
                Station.name.ilike(like),
                city.name.ilike(like),
                district.name.ilike(like),
                Station.operational_area.ilike(like),
                Station.address.ilike(like),
                Station.vpn_ip.ilike(like),
                Station.local_ip.ilike(like),
                node.hostname.ilike(like),
                func.cast(node.id, String).ilike(like),
            )
        )
    if city_id is not None:
        filters.append(Station.city_id == city_id)
    elif city_code:
        filters.append(city.code == city_code)
    if district_id is not None:
        filters.append(Station.district_id == district_id)
    if status is not None:
        filters.append(Station.status == status.value)
    if active is not None:
        filters.append(Station.is_active == active)
    if archived is not None:
        filters.append(Station.is_archived == archived)
    linked_condition = node.id.is_not(None)
    if headscale_linked is not None:
        filters.append(linked_condition if headscale_linked else node.id.is_(None))
    if monitoring_configured is not None:
        configured = Station.vpn_ip.is_not(None) & linked_condition
        filters.append(configured if monitoring_configured else ~configured)
    stmt = stmt.where(*filters)

    count_stmt = select(func.count()).select_from(
        stmt.with_only_columns(Station.id).order_by(None).distinct().subquery()
    )
    total = (await db.execute(count_stmt)).scalar_one()

    sort_columns = {
        "station_code": Station.station_code,
        "name": Station.name,
        "district": district.name,
        "status": Station.status,
        "ping": Station.last_ping_ms,
        "offline_duration": Station.offline_since,
        "last_seen": Station.last_seen_at,
    }
    ordering = desc(sort_columns[sort]) if direction == "desc" else asc(sort_columns[sort])
    stations = (await db.execute(stmt.order_by(ordering, Station.id).limit(limit).offset(offset))).scalars().unique().all()
    items = await serialize_stations(db, list(stations))
    return StationListOut(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=StationOut, status_code=201)
async def create_station(
    data: StationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin, Role.operator)),
):
    values = data.model_dump()
    enforce_station_create_policy(user, values)
    await _validate_regions(db, data.city_id, data.district_id)
    station = Station(**values, is_active=True, is_archived=False, approved_at=None, approved_by=None)
    db.add(station)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Station code must be unique") from exc
    add_audit(
        db,
        action="station.create",
        entity_type="station",
        entity_id=station.id,
        actor=user,
        after={"station_code": station.station_code, "name": station.name, "city_id": station.city_id, "district_id": station.district_id},
        request=request,
    )
    add_activity_event(
        db,
        user=user,
        action="station.created",
        source="api",
        station_id=station.id,
        station_code=station.station_code,
        status="completed",
        changed_fields=["station_code", "name", "city_id", "district_id", "operational_area", "address", "latitude", "longitude"],
        after=values,
    )
    await touch_presence(db, user, "api")
    await db.commit()
    station = await _load_station(db, station.id)
    return (await serialize_stations(db, [station]))[0]


@router.get("/{station_id}", response_model=StationDetailOut)
async def get_station(
    station_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    station = await _load_station(db, station_id)
    if user.role != Role.admin.value and not (
        station.approved_at is not None and station.is_active and not station.is_archived
    ):
        raise HTTPException(404, "Station not found")
    base = (await serialize_stations(db, [station]))[0]
    node = (
        await db.execute(select(HeadscaleNode).where(HeadscaleNode.station_id == station_id))
    ).scalar_one_or_none()
    cameras = (await db.execute(select(Camera).where(Camera.station_id == station_id).order_by(Camera.id))).scalars().all()
    pings = (
        await db.execute(
            select(PingHistory).where(PingHistory.station_id == station_id).order_by(PingHistory.checked_at.desc()).limit(100)
        )
    ).scalars().all()
    alerts = (
        await db.execute(
            select(Alert).where(Alert.station_id == station_id, Alert.resolved_at.is_(None)).order_by(Alert.created_at.desc())
        )
    ).scalars().all()
    timeline = (
        await db.execute(
            select(StationStatusEvent).where(StationStatusEvent.station_id == station_id).order_by(StationStatusEvent.started_at.desc()).limit(200)
        )
    ).scalars().all()
    audits = (
        await db.execute(
            select(AuditLog).where(AuditLog.entity_type == "station", AuditLog.entity_id == str(station_id)).order_by(AuditLog.timestamp.desc()).limit(100)
        )
    ).scalars().all()
    return StationDetailOut(
        **base.model_dump(),
        headscale_node=node,
        cameras=list(cameras),
        ping_history=list(pings),
        open_alerts=list(alerts),
        status_timeline=list(timeline),
        audit_history=list(audits),
    )


@router.patch("/{station_id}", response_model=StationOut)
async def update_station(
    station_id: int,
    data: StationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin, Role.operator)),
):
    station = await _load_station(db, station_id)
    changes = data.model_dump(exclude_unset=True)
    enforce_station_update_policy(user, changes)
    city_id = changes.get("city_id", station.city_id)
    district_id = changes.get("district_id", station.district_id)
    await _validate_regions(db, city_id, district_id)
    if "vpn_ip" in changes:
        approved_node = (
            await db.execute(
                select(HeadscaleNode).where(
                    HeadscaleNode.station_id == station.id,
                    HeadscaleNode.approval_status == ApprovalStatus.approved.value,
                    HeadscaleNode.device_type == DeviceType.station.value,
                )
            )
        ).scalar_one_or_none()
        if approved_node and approved_node.vpn_ip and changes["vpn_ip"] != approved_node.vpn_ip:
            raise HTTPException(409, "VPN IP is controlled by the approved linked Headscale station node")
    before = {key: getattr(station, key) for key in changes}
    for key, value in changes.items():
        setattr(station, key, value)
    add_audit(
        db,
        action="station.archive" if changes.get("is_archived") else "station.update",
        entity_type="station",
        entity_id=station.id,
        actor=user,
        before=before,
        after=changes,
        request=request,
    )
    add_activity_event(
        db,
        user=user,
        action="station.updated",
        source="api",
        station_id=station.id,
        station_code=station.station_code,
        status="completed",
        changed_fields=sorted(changes),
        before=before,
        after=changes,
    )
    await touch_presence(db, user, "api")
    await db.commit()
    station = await _load_station(db, station_id)
    return (await serialize_stations(db, [station]))[0]


@router.delete("/{station_id}", status_code=204)
async def archive_station(
    station_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    await _load_station(db, station_id)
    raise HTTPException(
        409,
        "Use the Onboarding station inventory archive preview and typed confirmation workflow",
    )


@router.post("/{station_id}/check", status_code=202)
async def run_monitoring_check(
    station_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin, Role.operator)),
):
    await _load_station(db, station_id)
    await ping_station(station_id)
    return {"status": "completed"}


async def _load_station(db: AsyncSession, station_id: int) -> Station:
    station = (
        await db.execute(
            select(Station)
            .where(Station.id == station_id)
            .options(selectinload(Station.city), selectinload(Station.district))
        )
    ).scalar_one_or_none()
    if not station:
        raise HTTPException(404, "Station not found")
    return station


async def _validate_regions(db: AsyncSession, city_id: int, district_id: int | None) -> None:
    city = await db.get(OperationalRegion, city_id)
    if not city or city.region_type != "city":
        raise HTTPException(422, "city_id must reference a city")
    if district_id is not None:
        district = await db.get(OperationalRegion, district_id)
        if not district or district.region_type != "district" or district.parent_id != city_id:
            raise HTTPException(422, "district_id must reference a district belonging to the selected city")
