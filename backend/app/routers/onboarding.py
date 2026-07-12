from __future__ import annotations

import csv
from datetime import datetime, timezone
from difflib import SequenceMatcher
import io
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..deps import require_roles
from ..models import (
    Alert,
    ApprovalStatus,
    DeviceType,
    Camera,
    HeadscaleNode,
    OperationalRegion,
    PingHistory,
    Role,
    Station,
    StationStatusEvent,
    User,
)
from ..schemas import (
    ActionPreviewOut,
    ApprovalCheckOut,
    DistrictApplyIn,
    DistrictAssignmentIn,
    DistrictAssignmentRow,
    DistrictPreviewIn,
    DistrictPreviewOut,
    DuplicateAlertApplyIn,
    DuplicateAlertGroup,
    DuplicateVpnActionApplyIn,
    DuplicateVpnActionPreviewIn,
    DuplicateVpnGroup,
    DuplicateVpnStation,
    OnboardingValidationError,
    StationOut,
    StationApprovalApplyIn,
    StationApprovalPreviewOut,
    StationRepairApplyIn,
    StationRepairChangeOut,
    StationRepairIn,
    StationRepairPreviewOut,
    StationLifecycleApplyIn,
    StationLifecyclePreviewOut,
    SuspectedDuplicatePairOut,
    SuspectedDuplicateStationOut,
    SuspectedDuplicateKeepBothIn,
)
from ..services.audit import add_audit
from ..services.confirmation_tokens import create_confirmation_token, verify_confirmation_token
from ..services.station_views import serialize_stations


router = APIRouter()
MAX_CSV_BYTES = 1_000_000
SUPPORTED_DISTRICT_CODES = {"ismoili-somoni", "shohmansur", "sino", "firdavsi"}


@router.get("/stations", response_model=list[StationOut])
async def station_approval_inventory(
    approval: str = "pending",
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    if approval not in {"pending", "approved", "all"}:
        raise HTTPException(422, "approval must be pending, approved, or all")
    stmt = (
        select(Station)
        .join(OperationalRegion, Station.city_id == OperationalRegion.id)
        .where(
            OperationalRegion.code == "dushanbe",
            Station.is_active.is_(True),
            Station.is_archived.is_(False),
        )
        .options(selectinload(Station.city), selectinload(Station.district))
    )
    if approval == "pending":
        stmt = stmt.where(Station.approved_at.is_(None))
    elif approval == "approved":
        stmt = stmt.where(Station.approved_at.is_not(None))
    if q and q.strip():
        like = f"%{q.strip()}%"
        node_match = select(HeadscaleNode.station_id).where(
            or_(HeadscaleNode.hostname.ilike(like), func.cast(HeadscaleNode.id, String).ilike(like))
        )
        stmt = stmt.where(
            or_(
                Station.station_code.ilike(like),
                Station.name.ilike(like),
                Station.operational_area.ilike(like),
                Station.address.ilike(like),
                Station.vpn_ip.ilike(like),
                OperationalRegion.name.ilike(like),
                Station.id.in_(node_match),
            )
        )
    stations = (await db.execute(stmt.order_by(Station.station_code))).scalars().all()
    return await serialize_stations(db, list(stations))


@router.get("/stations/by-code/{station_code}", response_model=StationOut)
async def station_by_exact_code(
    station_code: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin, Role.operator)),
):
    normalized = station_code.strip().upper()
    if not normalized:
        raise HTTPException(422, "Station code is required")
    station = (
        await db.execute(
            select(Station)
            .join(OperationalRegion, Station.city_id == OperationalRegion.id)
            .where(
                func.upper(Station.station_code) == normalized,
                OperationalRegion.code == "dushanbe",
                Station.is_active.is_(True),
                Station.is_archived.is_(False),
            )
            .options(selectinload(Station.city), selectinload(Station.district))
        )
    ).scalar_one_or_none()
    if not station:
        raise HTTPException(404, "Station not found")
    return (await serialize_stations(db, [station]))[0]


@router.post("/stations/{station_id}/approval-preview", response_model=StationApprovalPreviewOut)
async def preview_station_approval(
    station_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    station = await _onboarding_station(db, station_id)
    return await _station_approval_preview(db, station, "approve")


@router.post("/stations/{station_id}/approve", response_model=StationOut)
async def approve_station_for_production(
    station_id: int,
    data: StationApprovalApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    station = await _onboarding_station(db, station_id)
    preview = await _station_approval_preview(db, station, "approve")
    if not preview.valid or not preview.preview_token:
        raise HTTPException(422, preview.errors)
    if data.confirmation != preview.confirmation_phrase:
        raise HTTPException(422, "Explicit station confirmation is required")
    if not verify_confirmation_token(data.preview_token, "station-approval", _station_approval_payload(station, preview, "approve")):
        raise HTTPException(409, "Approval preview expired or station readiness changed; preview again")
    before = {"approved_at": station.approved_at, "approved_by": station.approved_by}
    station.approved_at = datetime.now(timezone.utc)
    station.approved_by = user.id
    add_audit(
        db,
        action="station.production_approve",
        entity_type="station",
        entity_id=station.id,
        actor=user,
        before=before,
        after={"approved_at": station.approved_at, "approved_by": station.approved_by},
        request=request,
    )
    await db.commit()
    station = await _onboarding_station(db, station_id)
    return (await serialize_stations(db, [station]))[0]


@router.post("/stations/{station_id}/revocation-preview", response_model=StationApprovalPreviewOut)
async def preview_station_revocation(
    station_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    station = await _onboarding_station(db, station_id)
    return await _station_approval_preview(db, station, "revoke")


@router.post("/stations/{station_id}/revoke", response_model=StationOut)
async def revoke_station_from_production(
    station_id: int,
    data: StationApprovalApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    station = await _onboarding_station(db, station_id)
    preview = await _station_approval_preview(db, station, "revoke")
    if not preview.valid or not preview.preview_token:
        raise HTTPException(422, preview.errors)
    if data.confirmation != preview.confirmation_phrase:
        raise HTTPException(422, "Explicit station confirmation is required")
    if not verify_confirmation_token(data.preview_token, "station-revocation", _station_approval_payload(station, preview, "revoke")):
        raise HTTPException(409, "Revocation preview expired or station changed; preview again")
    before = {"approved_at": station.approved_at, "approved_by": station.approved_by}
    station.approved_at = None
    station.approved_by = None
    add_audit(
        db,
        action="station.production_revoke",
        entity_type="station",
        entity_id=station.id,
        actor=user,
        before=before,
        after={"approved_at": None, "approved_by": None},
        request=request,
    )
    await db.commit()
    station = await _onboarding_station(db, station_id)
    return (await serialize_stations(db, [station]))[0]


@router.post("/stations/{station_id}/repair-preview", response_model=StationRepairPreviewOut)
async def preview_station_repair(
    station_id: int,
    data: StationRepairIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    station = await _onboarding_station(db, station_id)
    return await _station_repair_preview(db, station, data)


@router.post("/stations/{station_id}/repair", response_model=StationOut)
async def apply_station_repair(
    station_id: int,
    data: StationRepairApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    station = await _onboarding_station(db, station_id)
    fields = {key: value for key, value in data.model_dump(exclude_unset=True).items() if key not in {"preview_token", "confirmation"}}
    proposal = StationRepairIn(**fields)
    preview = await _station_repair_preview(db, station, proposal)
    if not preview.valid or not preview.preview_token:
        raise HTTPException(422, preview.errors)
    if data.confirmation != preview.confirmation_phrase:
        raise HTTPException(422, "Explicit repair confirmation is required")
    payload = _station_repair_payload(station, preview)
    if not verify_confirmation_token(data.preview_token, "station-repair", payload):
        raise HTTPException(409, "Repair preview expired or station data changed; preview again")
    before = {change.field: getattr(station, change.field) for change in preview.changes}
    for change in preview.changes:
        setattr(station, change.field, change.proposed)
    add_audit(
        db,
        action="station.data_repair",
        entity_type="station",
        entity_id=station.id,
        actor=user,
        before=before,
        after={change.field: change.proposed for change in preview.changes},
        request=request,
    )
    await db.commit()
    station = await _onboarding_station(db, station_id)
    return (await serialize_stations(db, [station]))[0]


@router.get("/station-inventory", response_model=list[StationOut])
async def station_inventory(
    view: str = "all",
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    allowed = {"all", "pending", "approved", "archived", "missing_headscale", "suspected_duplicate", "data_quality", "operator_created"}
    if view not in allowed:
        raise HTTPException(422, "Unknown station inventory filter")
    stations = list((await db.execute(
        select(Station)
        .join(OperationalRegion, Station.city_id == OperationalRegion.id)
        .where(OperationalRegion.code == "dushanbe")
        .options(selectinload(Station.city), selectinload(Station.district))
        .order_by(Station.station_code)
    )).scalars().all())
    rows = await serialize_stations(db, stations)
    duplicate_ids = await _suspected_duplicate_ids(db, stations) if view == "suspected_duplicate" else set()
    if view == "pending":
        rows = [row for row in rows if row.approved_at is None and not row.is_archived]
    elif view == "approved":
        rows = [row for row in rows if row.approved_at is not None and not row.is_archived]
    elif view == "archived":
        rows = [row for row in rows if row.is_archived]
    elif view == "missing_headscale":
        rows = [row for row in rows if not row.headscale_linked and not row.is_archived]
    elif view == "suspected_duplicate":
        rows = [row for row in rows if row.id in duplicate_ids]
    elif view == "data_quality":
        rows = [row for row in rows if row.data_quality_warnings]
    elif view == "operator_created":
        rows = [row for row in rows if row.created_by_role == Role.operator]
    if q and q.strip():
        needle = q.strip().casefold()
        matching_node_station_ids = set(
            (
                await db.execute(
                    select(HeadscaleNode.station_id).where(
                        HeadscaleNode.station_id.is_not(None),
                        or_(
                            HeadscaleNode.hostname.ilike(f"%{q.strip()}%"),
                            func.cast(HeadscaleNode.id, String).ilike(f"%{q.strip()}%"),
                        ),
                    )
                )
            ).scalars().all()
        )
        rows = [
            row
            for row in rows
            if row.id in matching_node_station_ids
            or needle
            in " ".join(
                str(value or "")
                for value in (
                    row.station_code,
                    row.name,
                    row.city,
                    row.district,
                    row.operational_area,
                    row.address,
                    row.vpn_ip,
                    row.headscale_hostname,
                )
            ).casefold()
        ]
    return rows


@router.post("/stations/{station_id}/archive-preview", response_model=StationLifecyclePreviewOut)
async def preview_station_archive(
    station_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    station = await _inventory_station(db, station_id)
    return await _station_lifecycle_preview(db, station, "archive")


@router.post("/stations/{station_id}/restore-preview", response_model=StationLifecyclePreviewOut)
async def preview_station_restore(
    station_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    station = await _inventory_station(db, station_id)
    return await _station_lifecycle_preview(db, station, "restore")


@router.post("/stations/{station_id}/archive", response_model=StationOut)
async def archive_inventory_station(
    station_id: int,
    data: StationLifecycleApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    return await _apply_station_lifecycle(db, station_id, data, "archive", request, user)


@router.post("/stations/{station_id}/restore", response_model=StationOut)
async def restore_inventory_station(
    station_id: int,
    data: StationLifecycleApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    return await _apply_station_lifecycle(db, station_id, data, "restore", request, user)


@router.get("/suspected-duplicates", response_model=list[SuspectedDuplicatePairOut])
async def suspected_duplicate_report(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    stations = list((await db.execute(
        select(Station)
        .join(OperationalRegion, Station.city_id == OperationalRegion.id)
        .where(OperationalRegion.code == "dushanbe", Station.is_archived.is_(False))
        .order_by(Station.station_code)
    )).scalars().all())
    return await _suspected_duplicate_pairs(db, stations)


@router.post("/suspected-duplicates/keep-both")
async def keep_both_suspected_duplicates(
    data: SuspectedDuplicateKeepBothIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    if data.left_station_id == data.right_station_id:
        raise HTTPException(422, "Select two different stations")
    stations = list((await db.execute(select(Station).where(Station.id.in_([data.left_station_id, data.right_station_id])))).scalars().all())
    if len(stations) != 2:
        raise HTTPException(404, "Station pair not found")
    reasons = _duplicate_reasons(stations[0], stations[1])
    if not reasons:
        raise HTTPException(409, "This pair is no longer in the suspected duplicate report")
    add_audit(
        db,
        action="station.duplicate_keep_both",
        entity_type="station_pair",
        entity_id=f"{min(data.left_station_id, data.right_station_id)}:{max(data.left_station_id, data.right_station_id)}",
        actor=user,
        before={"reasons": reasons},
        after={"decision": "keep_both", "changed": False},
        request=request,
    )
    await db.commit()
    return {"status": "recorded", "changed": False}


@router.get("/districts/stations", response_model=list[StationOut])
async def district_station_inventory(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    stations = (
        await db.execute(
            select(Station)
            .join(OperationalRegion, Station.city_id == OperationalRegion.id)
            .where(
                OperationalRegion.code == "dushanbe",
                Station.is_active.is_(True),
                Station.is_archived.is_(False),
            )
            .options(selectinload(Station.city), selectinload(Station.district))
            .order_by(Station.station_code)
        )
    ).scalars().all()
    return await serialize_stations(db, list(stations))


@router.post("/districts/preview", response_model=DistrictPreviewOut)
async def preview_district_assignments(
    data: DistrictPreviewIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    return await _district_preview(db, data.assignments)


@router.post("/districts/apply")
async def apply_district_assignments(
    data: DistrictApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    preview = await _district_preview(db, data.assignments)
    if not preview.valid or not preview.preview_token:
        raise HTTPException(422, {"message": "Assignments are no longer valid", "errors": [item.model_dump() for item in preview.errors]})
    payload = _district_token_payload(preview.rows)
    if not verify_confirmation_token(data.preview_token, "district-assignment", payload):
        raise HTTPException(409, "Preview expired or station data changed; run the preview again")
    changed = 0
    for row in preview.rows:
        if not row.changed:
            continue
        station = await db.get(Station, row.station_id)
        if not station:
            raise HTTPException(409, f"Station {row.station_code} changed after preview")
        before = {"district_id": station.district_id, "district": row.current_district}
        station.district_id = row.proposed_district_id
        add_audit(
            db,
            action="station.district_assign",
            entity_type="station",
            entity_id=station.id,
            actor=user,
            before=before,
            after={"district_id": row.proposed_district_id, "district": row.proposed_district},
            request=request,
        )
        changed += 1
    await db.commit()
    return {"applied": changed, "unchanged": len(preview.rows) - changed}


@router.get("/districts/template.csv")
async def export_district_template(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    stations = await district_station_inventory(db=db, _=_)
    output = io.StringIO()
    columns = [
        "station_code",
        "station_name",
        "address",
        "current_district",
        "vpn_ip",
        "headscale_hostname",
        "district",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for station in stations:
        writer.writerow(
            {
                "station_code": station.station_code,
                "station_name": station.name,
                "address": station.address,
                "current_district": station.district or "",
                "vpn_ip": station.vpn_ip or "",
                "headscale_hostname": station.headscale_hostname or "",
                "district": "",
            }
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dushanbe-district-assignment.csv"},
    )


@router.post("/districts/csv/preview", response_model=DistrictPreviewOut)
async def preview_district_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    assignments, parse_errors = await _parse_district_csv(file)
    if parse_errors:
        return DistrictPreviewOut(valid=False, rows=[], errors=parse_errors, preview_token=None)
    return await _district_preview(db, assignments)


@router.post("/districts/csv/apply")
async def apply_district_csv(
    request: Request,
    file: UploadFile = File(...),
    preview_token: str = Form(...),
    confirmation: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    if confirmation != "ASSIGN DISTRICTS":
        raise HTTPException(422, "Explicit confirmation is required")
    assignments, parse_errors = await _parse_district_csv(file)
    if parse_errors:
        raise HTTPException(422, [item.model_dump() for item in parse_errors])
    return await apply_district_assignments(
        DistrictApplyIn(
            assignments=assignments,
            preview_token=preview_token,
            confirmation="ASSIGN DISTRICTS",
        ),
        request,
        db,
        user,
    )


@router.get("/duplicate-vpn", response_model=list[DuplicateVpnGroup])
async def duplicate_vpn_report(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    duplicate_ips = (
        await db.execute(
            select(Station.vpn_ip)
            .where(Station.vpn_ip.is_not(None), Station.vpn_ip != "", Station.is_archived.is_(False))
            .group_by(Station.vpn_ip)
            .having(func.count(Station.id) > 1)
            .order_by(Station.vpn_ip)
        )
    ).scalars().all()
    if not duplicate_ips:
        return []
    stations = (
        await db.execute(
            select(Station).where(Station.vpn_ip.in_(duplicate_ips)).order_by(Station.vpn_ip, Station.station_code)
        )
    ).scalars().all()
    nodes = (
        await db.execute(select(HeadscaleNode).where(HeadscaleNode.station_id.in_([station.id for station in stations])))
    ).scalars().all()
    node_by_station = {node.station_id: node for node in nodes}
    groups = []
    for vpn_ip in duplicate_ips:
        affected = [station for station in stations if station.vpn_ip == vpn_ip]
        groups.append(
            DuplicateVpnGroup(
                vpn_ip=vpn_ip,
                stations=[
                    DuplicateVpnStation(
                        station_id=station.id,
                        station_code=station.station_code,
                        station_name=station.name,
                        status=station.status,
                        last_seen_at=station.last_seen_at,
                        linked_node_id=(node_by_station.get(station.id).id if node_by_station.get(station.id) else None),
                        linked_node_hostname=(node_by_station.get(station.id).hostname if node_by_station.get(station.id) else None),
                        linked_node_approval_status=(node_by_station.get(station.id).approval_status if node_by_station.get(station.id) else None),
                    )
                    for station in affected
                ],
                recommended_remediation="Verify the stable Headscale node identity, link the canonical station device, then clear only the stale station VPN value.",
            )
        )
    return groups


@router.post("/duplicate-vpn/action-preview", response_model=ActionPreviewOut)
async def preview_duplicate_vpn_action(
    data: DuplicateVpnActionPreviewIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    valid, description, errors, payload = await _validate_vpn_action(db, data)
    token = create_confirmation_token("duplicate-vpn-action", payload) if valid else None
    return ActionPreviewOut(valid=valid, description=description, errors=errors, preview_token=token)


@router.post("/duplicate-vpn/action-apply")
async def apply_duplicate_vpn_action(
    data: DuplicateVpnActionApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    valid, description, errors, payload = await _validate_vpn_action(db, data)
    if not valid:
        raise HTTPException(422, errors)
    if not verify_confirmation_token(data.preview_token, "duplicate-vpn-action", payload):
        raise HTTPException(409, "Preview expired or inventory changed; preview the action again")
    if data.action == "cancel":
        add_audit(
            db,
            action="duplicate_vpn.cancel",
            entity_type="vpn_ip",
            entity_id=data.vpn_ip,
            actor=user,
            before={"station_ids": payload["group_station_ids"]},
            after={"changed": False},
            request=request,
        )
        await db.commit()
        return {"applied": False, "status": "cancelled"}
    if data.action == "clear_station_vpn":
        station = await db.get(Station, data.station_id)
        before = {"vpn_ip": station.vpn_ip}
        station.vpn_ip = None
        add_audit(db, action="station.vpn_clear", entity_type="station", entity_id=station.id, actor=user, before=before, after={"vpn_ip": None}, request=request)
    elif data.action == "unlink_node":
        node = await db.get(HeadscaleNode, data.node_id)
        before = {"station_id": node.station_id, "device_type": node.device_type}
        node.station_id = None
        node.device_type = DeviceType.unknown.value
        add_audit(db, action="headscale.unlink_stale", entity_type="headscale_node", entity_id=node.id, actor=user, before=before, after={"station_id": None, "device_type": node.device_type}, request=request)
    elif data.action == "select_canonical_node":
        node = await db.get(HeadscaleNode, data.node_id)
        station = await db.get(Station, data.station_id)
        before = {"node_station_id": node.station_id, "station_vpn_ip": station.vpn_ip}
        node.station_id = station.id
        station.vpn_ip = node.vpn_ip
        add_audit(db, action="headscale.select_canonical", entity_type="headscale_node", entity_id=node.id, actor=user, before=before, after={"station_id": station.id, "station_vpn_ip": station.vpn_ip}, request=request)
        if before["station_vpn_ip"] != station.vpn_ip:
            add_audit(
                db,
                action="station.vpn_sync_headscale",
                entity_type="station",
                entity_id=station.id,
                actor=user,
                before={"vpn_ip": before["station_vpn_ip"], "headscale_node_id": node.id},
                after={"vpn_ip": station.vpn_ip, "headscale_node_id": node.id},
                request=request,
            )
    await db.commit()
    return {"applied": True, "description": description}


@router.get("/duplicate-alerts", response_model=list[DuplicateAlertGroup])
async def duplicate_alert_report(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    groups = (
        await db.execute(
            select(Alert.station_id, Alert.type)
            .where(Alert.resolved_at.is_(None), Alert.station_id.is_not(None))
            .group_by(Alert.station_id, Alert.type)
            .having(func.count(Alert.id) > 1)
        )
    ).all()
    output = []
    for station_id, alert_type in groups:
        station = await db.get(Station, station_id)
        alerts = (
            await db.execute(
                select(Alert)
                .where(Alert.station_id == station_id, Alert.type == alert_type, Alert.resolved_at.is_(None))
                .order_by(Alert.created_at, Alert.id)
            )
        ).scalars().all()
        payload = {
            "station_id": station_id,
            "alert_type": alert_type,
            "canonical_alert_id": alerts[0].id,
            "resolve_ids": [alert.id for alert in alerts[1:]],
        }
        output.append(
            DuplicateAlertGroup(
                station_id=station_id,
                station_code=station.station_code,
                station_name=station.name,
                alert_type=alert_type,
                open_alert_count=len(alerts),
                oldest_alert_at=alerts[0].created_at,
                newest_alert_at=alerts[-1].created_at,
                canonical_alert_id=alerts[0].id,
                proposed_resolve_alert_ids=[alert.id for alert in alerts[1:]],
                preview_token=create_confirmation_token("duplicate-alert-resolution", payload),
            )
        )
    return sorted(output, key=lambda item: item.station_code)


@router.post("/duplicate-alerts/apply")
async def apply_duplicate_alert_resolution(
    data: DuplicateAlertApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    alerts = (
        await db.execute(
            select(Alert)
            .where(Alert.station_id == data.station_id, Alert.type == data.alert_type.value, Alert.resolved_at.is_(None))
            .order_by(Alert.created_at, Alert.id)
        )
    ).scalars().all()
    if len(alerts) < 2:
        raise HTTPException(409, "Duplicate group no longer exists")
    payload = {
        "station_id": data.station_id,
        "alert_type": data.alert_type.value,
        "canonical_alert_id": alerts[0].id,
        "resolve_ids": [alert.id for alert in alerts[1:]],
    }
    if not verify_confirmation_token(data.preview_token, "duplicate-alert-resolution", payload):
        raise HTTPException(409, "Preview expired or alerts changed; run the dry-run again")
    now = datetime.now(timezone.utc)
    for alert in alerts[1:]:
        alert.resolved_at = now
        alert.resolved_by = user.id
    add_audit(
        db,
        action="alerts.duplicate_resolve",
        entity_type="station",
        entity_id=data.station_id,
        actor=user,
        before={"open_alert_ids": [alert.id for alert in alerts]},
        after={"canonical_alert_id": alerts[0].id, "resolved_alert_ids": [alert.id for alert in alerts[1:]]},
        request=request,
    )
    await db.commit()
    return {"canonical_alert_id": alerts[0].id, "resolved": len(alerts) - 1}


async def _onboarding_station(db: AsyncSession, station_id: int) -> Station:
    station = (
        await db.execute(
            select(Station)
            .where(Station.id == station_id)
            .options(selectinload(Station.city), selectinload(Station.district))
        )
    ).scalar_one_or_none()
    if not station or station.is_archived or not station.is_active or station.city.code != "dushanbe":
        raise HTTPException(404, "Active Dushanbe station not found")
    return station


async def _station_approval_preview(
    db: AsyncSession,
    station: Station,
    action: str,
) -> StationApprovalPreviewOut:
    node = (
        await db.execute(select(HeadscaleNode).where(HeadscaleNode.station_id == station.id))
    ).scalar_one_or_none()
    verified_district = bool(
        station.district
        and station.district.region_type == "district"
        and station.district.code in SUPPORTED_DISTRICT_CODES
        and station.district.parent_id == station.city_id
    )
    checklist = [
        ApprovalCheckOut(
            key="verified_district",
            label="Verified Dushanbe district",
            ready=verified_district,
        ),
        ApprovalCheckOut(
            key="linked_headscale_node",
            label="Headscale node linked to this station",
            ready=node is not None,
        ),
        ApprovalCheckOut(
            key="approved_station_node",
            label="Linked node approved as a station device",
            ready=bool(
                node
                and node.device_type == DeviceType.station.value
                and node.approval_status == ApprovalStatus.approved.value
            ),
        ),
        ApprovalCheckOut(
            key="one_to_one_link",
            label="Station and Headscale node have a one-to-one link",
            ready=bool(node and node.station_id == station.id),
        ),
        ApprovalCheckOut(
            key="monitoring_configured",
            label="Monitoring VPN matches the approved Headscale node",
            ready=bool(node and node.vpn_ip and station.vpn_ip == node.vpn_ip),
        ),
    ]
    monitoring_ready = all(item.ready for item in checklist)
    errors: list[str] = []
    if action == "approve":
        if station.approved_at is not None:
            errors.append("Station is already approved for production")
        errors.extend(f"Required check failed: {item.label}" for item in checklist if not item.ready)
        confirmation_phrase = f"APPROVE STATION {station.station_code}"
        purpose = "station-approval"
    else:
        if station.approved_at is None:
            errors.append("Station is not currently approved for production")
        confirmation_phrase = f"REMOVE STATION {station.station_code} FROM PRODUCTION"
        purpose = "station-revocation"
    preview = StationApprovalPreviewOut(
        station_id=station.id,
        station_code=station.station_code,
        station_name=station.name,
        district=station.district.name if station.district else None,
        address=station.address,
        vpn_ip=station.vpn_ip,
        local_ip=station.local_ip,
        headscale_hostname=node.hostname if node else None,
        headscale_approval_status=node.approval_status if node else None,
        monitoring_status=station.status,
        monitoring_ready=monitoring_ready,
        warning=(
            "The approved monitoring node is currently offline; offline status does not block approval."
            if monitoring_ready and node and not node.online
            else None
        ),
        production_approved=station.approved_at is not None,
        action=action,
        confirmation_phrase=confirmation_phrase,
        valid=not errors,
        errors=errors,
        preview_token=None,
        checklist=checklist,
    )
    if preview.valid:
        preview.preview_token = create_confirmation_token(
            purpose,
            _station_approval_payload(station, preview, action),
        )
    return preview


def _station_approval_payload(
    station: Station,
    preview: StationApprovalPreviewOut,
    action: str,
) -> dict[str, object]:
    return {
        "station_id": station.id,
        "station_code": station.station_code,
        "action": action,
        "approved_at": station.approved_at,
        "approved_by": station.approved_by,
        "district_id": station.district_id,
        "vpn_ip": station.vpn_ip,
        "headscale_hostname": preview.headscale_hostname,
        "headscale_approval_status": preview.headscale_approval_status,
        "monitoring_ready": preview.monitoring_ready,
    }


async def _station_repair_preview(
    db: AsyncSession,
    station: Station,
    data: StationRepairIn,
) -> StationRepairPreviewOut:
    changes = [
        StationRepairChangeOut(field=field, current=getattr(station, field), proposed=value)
        for field, value in data.model_dump(exclude_unset=True).items()
        if getattr(station, field) != value
    ]
    errors: list[str] = []
    proposed_name = next((item.proposed for item in changes if item.field == "name"), station.name)
    proposed_address = next((item.proposed for item in changes if item.field == "address"), station.address)
    if not isinstance(proposed_name, str) or not proposed_name.strip():
        errors.append("Station name cannot be empty")
    if not isinstance(proposed_address, str):
        errors.append("Station address cannot be null")
    final_latitude = next((item.proposed for item in changes if item.field == "latitude"), station.latitude)
    final_longitude = next((item.proposed for item in changes if item.field == "longitude"), station.longitude)
    if final_latitude is not None and not -90 <= final_latitude <= 90:
        errors.append("Latitude must be between -90 and 90")
    if final_longitude is not None and not -180 <= final_longitude <= 180:
        errors.append("Longitude must be between -180 and 180")
    node = (
        await db.execute(select(HeadscaleNode).where(HeadscaleNode.station_id == station.id))
    ).scalar_one_or_none()
    proposed_vpn = next((item.proposed for item in changes if item.field == "vpn_ip"), station.vpn_ip)
    if node and node.approval_status == ApprovalStatus.approved.value and node.device_type == DeviceType.station.value and node.vpn_ip and proposed_vpn != node.vpn_ip:
        errors.append("VPN IP must match the approved linked Headscale station node")
    final = {field: getattr(station, field) for field in ("name", "operational_area", "address", "vpn_ip", "local_ip")}
    final.update({item.field: item.proposed for item in changes})
    warnings = _repair_quality_warnings(station, final, node)
    if not changes:
        errors.append("No field changes were proposed")
    phrase = f"REPAIR STATION {station.station_code}"
    preview = StationRepairPreviewOut(
        station_id=station.id,
        station_code=station.station_code,
        changes=changes,
        warnings=warnings,
        errors=errors,
        confirmation_phrase=phrase,
        valid=not errors,
        preview_token=None,
    )
    if preview.valid:
        preview.preview_token = create_confirmation_token("station-repair", _station_repair_payload(station, preview))
    return preview


def _repair_quality_warnings(
    station: Station,
    final: dict[str, object],
    node: HeadscaleNode | None,
) -> list[str]:
    warnings: list[str] = []
    district_name = station.district.name if station.district else None
    name = str(final.get("name") or "").casefold().removeprefix("н.").strip()
    if district_name and name == district_name.casefold():
        warnings.append("Station name equals the district name")
    address = str(final.get("address") or "").strip()
    if address and len(address) <= 64 and not any(char.isdigit() for char in address):
        warnings.append("Address looks like only a landmark; verify street/building details")
    monitoring_node = bool(
        node
        and node.approval_status == ApprovalStatus.approved.value
        and node.device_type == DeviceType.station.value
    )
    if final.get("vpn_ip") and not monitoring_node:
        warnings.append("Manual VPN IP has no approved linked Headscale station node")
    if final.get("local_ip") and not monitoring_node:
        warnings.append("Local IP has no configured monitoring agent")
    return warnings


def _station_repair_payload(station: Station, preview: StationRepairPreviewOut) -> dict[str, object]:
    return {
        "station_id": station.id,
        "station_code": station.station_code,
        "changes": [item.model_dump() for item in preview.changes],
    }


async def _inventory_station(db: AsyncSession, station_id: int) -> Station:
    station = (
        await db.execute(
            select(Station)
            .where(Station.id == station_id)
            .options(selectinload(Station.city), selectinload(Station.district))
        )
    ).scalar_one_or_none()
    if not station or not station.city or station.city.code != "dushanbe":
        raise HTTPException(404, "Dushanbe station not found")
    return station


async def _station_lifecycle_preview(
    db: AsyncSession,
    station: Station,
    action: str,
) -> StationLifecyclePreviewOut:
    node_id = await db.scalar(select(HeadscaleNode.id).where(HeadscaleNode.station_id == station.id))
    active_alerts = int(await db.scalar(select(func.count()).select_from(Alert).where(Alert.station_id == station.id, Alert.resolved_at.is_(None))) or 0)
    cameras = int(await db.scalar(select(func.count()).select_from(Camera).where(Camera.station_id == station.id)) or 0)
    ping_count = int(await db.scalar(select(func.count()).select_from(PingHistory).where(PingHistory.station_id == station.id)) or 0)
    event_count = int(await db.scalar(select(func.count()).select_from(StationStatusEvent).where(StationStatusEvent.station_id == station.id)) or 0)
    history_records = ping_count + event_count
    errors = []
    if action == "archive" and station.is_archived:
        errors.append("Station is already archived")
    if action == "restore" and not station.is_archived:
        errors.append("Station is not archived")
    warnings = []
    if node_id:
        warnings.append("A Headscale node is linked; archiving does not unlink it")
    if active_alerts:
        warnings.append(f"Station has {active_alerts} active alert(s)")
    if cameras:
        warnings.append(f"Station has {cameras} camera record(s)")
    if history_records:
        warnings.append(f"Station has {history_records} monitoring/history record(s)")
    phrase = f"{action.upper()} STATION {station.station_code}"
    payload = {
        "station_id": station.id,
        "station_code": station.station_code,
        "action": action,
        "is_active": station.is_active,
        "is_archived": station.is_archived,
        "linked_node_id": node_id,
        "active_alerts": active_alerts,
        "cameras": cameras,
        "history_records": history_records,
    }
    preview = StationLifecyclePreviewOut(
        station_id=station.id,
        station_code=station.station_code,
        action=action,
        warnings=warnings,
        linked_node_id=node_id,
        active_alerts=active_alerts,
        cameras=cameras,
        history_records=history_records,
        confirmation_phrase=phrase,
        valid=not errors,
        errors=errors,
        preview_token=None,
    )
    if preview.valid:
        preview.preview_token = create_confirmation_token("station-lifecycle", payload)
    return preview


async def _apply_station_lifecycle(
    db: AsyncSession,
    station_id: int,
    data: StationLifecycleApplyIn,
    action: str,
    request: Request,
    user: User,
) -> StationOut:
    station = await _inventory_station(db, station_id)
    preview = await _station_lifecycle_preview(db, station, action)
    if not preview.valid or not preview.preview_token:
        raise HTTPException(422, preview.errors)
    if data.confirmation != preview.confirmation_phrase:
        raise HTTPException(422, "Explicit station lifecycle confirmation is required")
    payload = {
        "station_id": station.id,
        "station_code": station.station_code,
        "action": action,
        "is_active": station.is_active,
        "is_archived": station.is_archived,
        "linked_node_id": preview.linked_node_id,
        "active_alerts": preview.active_alerts,
        "cameras": preview.cameras,
        "history_records": preview.history_records,
    }
    if not verify_confirmation_token(data.preview_token, "station-lifecycle", payload):
        raise HTTPException(409, "Lifecycle preview expired or inventory changed; preview again")
    before = {"is_active": station.is_active, "is_archived": station.is_archived}
    station.is_archived = action == "archive"
    station.is_active = action == "restore"
    add_audit(
        db,
        action=f"station.{action}",
        entity_type="station",
        entity_id=station.id,
        actor=user,
        before=before,
        after={"is_active": station.is_active, "is_archived": station.is_archived},
        request=request,
    )
    await db.commit()
    station = await _inventory_station(db, station_id)
    return (await serialize_stations(db, [station]))[0]


def _normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().replace(".", " ").replace(",", " ").split())


def _distance_m(left: Station, right: Station) -> float | None:
    if None in (left.latitude, left.longitude, right.latitude, right.longitude):
        return None
    lat1, lon1, lat2, lon2 = map(radians, (left.latitude, left.longitude, right.latitude, right.longitude))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6_371_000 * 2 * asin(sqrt(value))


def _duplicate_reasons(left: Station, right: Station) -> list[str]:
    reasons = []
    left_name, right_name = _normalized(left.name), _normalized(right.name)
    if left_name and right_name:
        similarity = SequenceMatcher(None, left_name, right_name).ratio()
        if left_name == right_name:
            reasons.append("same normalized name")
        elif similarity >= 0.82:
            reasons.append(f"similar name ({similarity:.0%})")
    distance = _distance_m(left, right)
    if distance is not None and distance <= 50:
        reasons.append(f"coordinates within {distance:.0f} m")
    if _normalized(left.address) and _normalized(left.address) == _normalized(right.address):
        reasons.append("same address")
    if left.vpn_ip and left.vpn_ip == right.vpn_ip:
        reasons.append("same VPN IP")
    if _normalized(left.operational_area) and _normalized(left.operational_area) == _normalized(right.operational_area):
        reasons.append("same operational area")
    return reasons


async def _suspected_duplicate_ids(db: AsyncSession, stations: list[Station]) -> set[int]:
    pairs = await _suspected_duplicate_pairs(db, stations)
    return {item.left.station_id for item in pairs} | {item.right.station_id for item in pairs}


async def _suspected_duplicate_pairs(db: AsyncSession, stations: list[Station]) -> list[SuspectedDuplicatePairOut]:
    station_ids = [station.id for station in stations]
    nodes = list((await db.execute(select(HeadscaleNode).where(HeadscaleNode.station_id.in_(station_ids)))).scalars().all()) if station_ids else []
    node_by_station = {node.station_id: node.id for node in nodes}
    alert_counts = dict((await db.execute(select(Alert.station_id, func.count()).where(Alert.station_id.in_(station_ids), Alert.resolved_at.is_(None)).group_by(Alert.station_id))).all()) if station_ids else {}
    camera_counts = dict((await db.execute(select(Camera.station_id, func.count()).where(Camera.station_id.in_(station_ids)).group_by(Camera.station_id))).all()) if station_ids else {}
    ping_counts = dict((await db.execute(select(PingHistory.station_id, func.count()).where(PingHistory.station_id.in_(station_ids)).group_by(PingHistory.station_id))).all()) if station_ids else {}
    event_counts = dict((await db.execute(select(StationStatusEvent.station_id, func.count()).where(StationStatusEvent.station_id.in_(station_ids)).group_by(StationStatusEvent.station_id))).all()) if station_ids else {}

    def row(station: Station) -> SuspectedDuplicateStationOut:
        return SuspectedDuplicateStationOut(
            station_id=station.id,
            station_code=station.station_code,
            name=station.name,
            approval_status="approved" if station.approved_at else "pending",
            is_active=station.is_active,
            is_archived=station.is_archived,
            linked_node_id=node_by_station.get(station.id),
            active_alerts=int(alert_counts.get(station.id, 0)),
            cameras=int(camera_counts.get(station.id, 0)),
            history_records=int(ping_counts.get(station.id, 0)) + int(event_counts.get(station.id, 0)),
        )

    output = []
    for index, left in enumerate(stations):
        for right in stations[index + 1:]:
            if left.station_code == right.station_code:
                continue
            reasons = _duplicate_reasons(left, right)
            if reasons:
                output.append(SuspectedDuplicatePairOut(
                    left=row(left),
                    right=row(right),
                    reasons=reasons,
                    recommendation="Review both records. Keep both when they represent distinct physical sites; otherwise repair or explicitly archive only the obsolete record.",
                ))
    return output


async def _district_preview(db: AsyncSession, assignments: list[DistrictAssignmentIn]) -> DistrictPreviewOut:
    errors: list[OnboardingValidationError] = []
    rows: list[DistrictAssignmentRow] = []
    city = (
        await db.execute(select(OperationalRegion).where(OperationalRegion.code == "dushanbe"))
    ).scalar_one()
    districts = (
        await db.execute(
            select(OperationalRegion).where(
                OperationalRegion.parent_id == city.id,
                OperationalRegion.region_type == "district",
                OperationalRegion.is_active.is_(True),
                OperationalRegion.code.in_(SUPPORTED_DISTRICT_CODES),
            )
        )
    ).scalars().all()
    district_lookup = {
        key.casefold(): district
        for district in districts
        for key in (district.code, district.name)
    }
    normalized_codes = [item.station_code.strip() for item in assignments]
    duplicate_codes = {code for code in normalized_codes if normalized_codes.count(code) > 1}
    stations = (
        await db.execute(
            select(Station)
            .where(Station.station_code.in_(set(normalized_codes)))
            .options(selectinload(Station.district))
        )
    ).scalars().all()
    station_by_code = {station.station_code: station for station in stations}
    linked_nodes = (
        await db.execute(select(HeadscaleNode).where(HeadscaleNode.station_id.in_([station.id for station in stations])))
    ).scalars().all()
    node_by_station = {node.station_id: node for node in linked_nodes}
    for index, assignment in enumerate(assignments, start=2):
        station_code = assignment.station_code.strip()
        station = station_by_code.get(station_code)
        district = district_lookup.get(assignment.district.strip().casefold())
        if station_code in duplicate_codes:
            errors.append(OnboardingValidationError(row=index, station_code=station_code, message="Station code appears more than once"))
            continue
        if not station or station.city_id != city.id or station.is_archived or not station.is_active:
            errors.append(OnboardingValidationError(row=index, station_code=station_code, message="Active Dushanbe station not found"))
            continue
        if not district:
            errors.append(OnboardingValidationError(row=index, station_code=station_code, message="District must be Ismoili Somoni, Shohmansur, Sino, or Firdavsi"))
            continue
        node = node_by_station.get(station.id)
        rows.append(
            DistrictAssignmentRow(
                station_id=station.id,
                station_code=station.station_code,
                station_name=station.name,
                address=station.address,
                vpn_ip=station.vpn_ip,
                headscale_hostname=node.hostname if node else None,
                current_district=station.district.name if station.district else None,
                proposed_district=district.name,
                proposed_district_id=district.id,
                changed=station.district_id != district.id,
            )
        )
    token = create_confirmation_token("district-assignment", _district_token_payload(rows)) if rows and not errors else None
    return DistrictPreviewOut(valid=bool(rows) and not errors, rows=rows, errors=errors, preview_token=token)


def _district_token_payload(rows: list[DistrictAssignmentRow]) -> list[dict[str, object]]:
    return [
        {
            "station_id": row.station_id,
            "station_code": row.station_code,
            "current_district": row.current_district,
            "proposed_district_id": row.proposed_district_id,
        }
        for row in sorted(rows, key=lambda item: item.station_code)
    ]


async def _parse_district_csv(file: UploadFile) -> tuple[list[DistrictAssignmentIn], list[OnboardingValidationError]]:
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        return [], [OnboardingValidationError(row=1, station_code=None, message="CSV file exceeds 1 MB")]
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [OnboardingValidationError(row=1, station_code=None, message="CSV must be UTF-8 encoded")]
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not {"station_code", "district"}.issubset(reader.fieldnames):
        return [], [OnboardingValidationError(row=1, station_code=None, message="CSV requires station_code and district columns")]
    assignments = []
    errors = []
    for row_number, row in enumerate(reader, start=2):
        station_code = (row.get("station_code") or "").strip()
        district = (row.get("district") or "").strip()
        if not station_code or not district:
            errors.append(OnboardingValidationError(row=row_number, station_code=station_code or None, message="station_code and district are required"))
            continue
        assignments.append(DistrictAssignmentIn(station_code=station_code, district=district))
    if not assignments and not errors:
        errors.append(OnboardingValidationError(row=1, station_code=None, message="CSV contains no assignments"))
    return assignments, errors


async def _validate_vpn_action(
    db: AsyncSession,
    data: DuplicateVpnActionPreviewIn,
) -> tuple[bool, str, list[str], dict[str, object]]:
    errors: list[str] = []
    station = await db.get(Station, data.station_id) if data.station_id else None
    node = await db.get(HeadscaleNode, data.node_id) if data.node_id else None
    current_stations = (
        await db.execute(select(Station).where(Station.vpn_ip == data.vpn_ip, Station.is_archived.is_(False)))
    ).scalars().all()
    if len(current_stations) < 2:
        errors.append("VPN address is no longer duplicated")
    if data.action in {"clear_station_vpn", "select_canonical_node"} and (not station or station.vpn_ip != data.vpn_ip):
        errors.append("Selected station is not part of this duplicate group")
    if data.action in {"unlink_node", "select_canonical_node"} and not node:
        errors.append("Selected Headscale node was not found")
    if data.action == "unlink_node" and node and node.station_id is None:
        errors.append("Selected node is not linked")
    if data.action == "unlink_node" and node and node.station_id not in {item.id for item in current_stations}:
        errors.append("Selected node is not linked to this duplicate group")
    if data.action == "select_canonical_node" and node:
        if node.approval_status != ApprovalStatus.approved.value or node.device_type != DeviceType.station.value:
            errors.append("Canonical node must already be approved as a station device")
        occupied = (
            await db.execute(
                select(HeadscaleNode).where(HeadscaleNode.station_id == data.station_id, HeadscaleNode.id != node.id)
            )
        ).scalar_one_or_none()
        if occupied:
            errors.append("Station is already linked to another node")
        if node.station_id not in (None, data.station_id):
            errors.append("Node is already linked to another station")
        if node.vpn_ip != data.vpn_ip:
            errors.append("Canonical node VPN IP does not match this duplicate group")
    descriptions = {
        "unlink_node": f"Unlink Headscale node {data.node_id}; the node record remains in inventory.",
        "clear_station_vpn": f"Clear VPN IP {data.vpn_ip} from station {station.station_code if station else data.station_id}; no station is deleted.",
        "select_canonical_node": f"Link approved node {data.node_id} as the canonical device for station {station.station_code if station else data.station_id}.",
        "cancel": "Cancel without changing any data.",
    }
    payload = {
        "action": data.action,
        "vpn_ip": data.vpn_ip,
        "station_id": data.station_id,
        "node_id": data.node_id,
        "group_station_ids": sorted(item.id for item in current_stations),
        "node_station_id": node.station_id if node else None,
    }
    return not errors, descriptions[data.action], errors, payload
