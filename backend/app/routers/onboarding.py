from __future__ import annotations

import csv
from datetime import datetime, timezone
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..deps import require_roles
from ..models import (
    Alert,
    ApprovalStatus,
    DeviceType,
    HeadscaleNode,
    OperationalRegion,
    Role,
    Station,
    User,
)
from ..schemas import (
    ActionPreviewOut,
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
)
from ..services.audit import add_audit
from ..services.confirmation_tokens import create_confirmation_token, verify_confirmation_token
from ..services.station_views import serialize_stations


router = APIRouter()
MAX_CSV_BYTES = 1_000_000
SUPPORTED_DISTRICT_CODES = {"ismoili-somoni", "shohmansur", "sino", "firdavsi"}


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
