from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from ..database import get_db
from ..deps import require_roles
from ..models import ApprovalStatus, DeviceType, HeadscaleNode, OperationalRegion, Role, Station, User
from ..schemas import (
    HeadscaleApproveConfirmIn,
    HeadscaleApproveIn,
    HeadscaleClassificationApplyIn,
    HeadscaleClassificationIn,
    HeadscaleClassificationPreviewOut,
    HeadscaleLinkIn,
    HeadscaleNodeListOut,
    HeadscaleNodeOut,
    HeadscaleReconciliationApplyIn,
    HeadscaleReconciliationPreviewIn,
    HeadscaleReconciliationPreviewOut,
    HeadscaleReconciliationRowOut,
    HeadscaleStationOptionOut,
)
from ..services.audit import add_audit
from ..services.confirmation_tokens import create_confirmation_token, verify_confirmation_token
from ..services.headscale import sync_headscale_nodes
from ..services.ping_monitor import ping_station
from ..services.performance import record_result_count


router = APIRouter()


@router.get("/station-options", response_model=list[HeadscaleStationOptionOut])
async def station_options(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    node = aliased(HeadscaleNode)
    rows = (
        await db.execute(
            select(
                Station.id,
                Station.station_code,
                Station.name,
                node.id.is_not(None).label("headscale_linked"),
            )
            .join(OperationalRegion, Station.city_id == OperationalRegion.id)
            .outerjoin(
                node,
                (node.station_id == Station.id)
                & (node.approval_status == ApprovalStatus.approved.value)
                & (node.device_type == DeviceType.station.value),
            )
            .where(
                OperationalRegion.code == "dushanbe",
                Station.is_active.is_(True),
                Station.is_archived.is_(False),
            )
            .order_by(Station.station_code, Station.id)
        )
    ).mappings().all()
    result = [HeadscaleStationOptionOut(**row) for row in rows]
    record_result_count(len(result))
    return result


@router.get("/nodes", response_model=HeadscaleNodeListOut | list[HeadscaleNodeOut])
async def list_nodes(
    q: str | None = None,
    approval_status: ApprovalStatus | None = None,
    device_type: DeviceType | None = None,
    online: bool | None = None,
    linked: bool | None = None,
    page: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    stmt = select(HeadscaleNode).outerjoin(Station, HeadscaleNode.station_id == Station.id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                cast(HeadscaleNode.id, String).ilike(like),
                HeadscaleNode.hostname.ilike(like),
                HeadscaleNode.given_name.ilike(like),
                HeadscaleNode.vpn_ip.ilike(like),
                Station.station_code.ilike(like),
                Station.name.ilike(like),
            )
        )
    if approval_status:
        stmt = stmt.where(HeadscaleNode.approval_status == approval_status.value)
    if device_type:
        stmt = stmt.where(HeadscaleNode.device_type == device_type.value)
    if online is not None:
        stmt = stmt.where(HeadscaleNode.online == online)
    if linked is not None:
        stmt = stmt.where(HeadscaleNode.station_id.is_not(None) if linked else HeadscaleNode.station_id.is_(None))
    if not page:
        nodes = (
            await db.execute(stmt.order_by(HeadscaleNode.hostname, HeadscaleNode.id))
        ).scalars().all()
        items = await _serialize_nodes(db, list(nodes))
        record_result_count(len(items))
        return items

    filtered = stmt.with_only_columns(
        HeadscaleNode.id.label("node_id"),
        HeadscaleNode.station_id.label("station_id"),
        HeadscaleNode.approval_status.label("approval_status"),
    ).order_by(None).subquery()
    counts = (await db.execute(
        select(
            func.count(filtered.c.node_id),
            func.count(filtered.c.node_id).filter(filtered.c.station_id.is_not(None)),
            func.count(filtered.c.node_id).filter(
                filtered.c.approval_status == ApprovalStatus.pending.value
            ),
        )
    )).one()
    nodes = (
        await db.execute(
            stmt.order_by(HeadscaleNode.hostname, HeadscaleNode.id).limit(limit).offset(offset)
        )
    ).scalars().all()
    items = await _serialize_nodes(db, list(nodes))
    result = HeadscaleNodeListOut(
        items=items,
        total=counts[0],
        limit=limit,
        offset=offset,
        linked_count=counts[1],
        pending_count=counts[2],
    )
    record_result_count(len(items))
    return result


@router.get("/nodes/pending", response_model=list[HeadscaleNodeOut])
async def pending_nodes(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    nodes = (
        await db.execute(
            select(HeadscaleNode)
            .where(HeadscaleNode.approval_status == ApprovalStatus.pending.value)
            .order_by(HeadscaleNode.first_seen_at)
        )
    ).scalars().all()
    return await _serialize_nodes(db, list(nodes))


@router.post("/nodes/{node_id}/approval-preview")
async def preview_node_approval(
    node_id: int,
    data: HeadscaleApproveIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    node = await _node_or_404(db, node_id)
    preview, payload = await _approval_preview(db, node, data)
    preview["preview_token"] = create_confirmation_token("headscale-approval", payload) if preview["valid"] else None
    return preview


@router.post("/nodes/{node_id}/approve", response_model=HeadscaleNodeOut)
async def approve_node(
    node_id: int,
    data: HeadscaleApproveConfirmIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    node = await _node_or_404(db, node_id)
    preview, payload = await _approval_preview(db, node, data)
    if not preview["valid"]:
        raise HTTPException(422, preview["errors"])
    if not verify_confirmation_token(data.preview_token, "headscale-approval", payload):
        raise HTTPException(409, "Approval preview expired or inventory changed; preview again")
    before = _audit_snapshot(node)
    if data.device_type == DeviceType.station:
        if data.station_id is None:
            raise HTTPException(422, "station_id is required for station devices")
        station = await db.get(Station, data.station_id)
        if not station or station.is_archived or not station.is_active:
            raise HTTPException(404, "Active station not found")
        await _assert_link_available(db, node, station)
        node.station_id = station.id
        await _sync_station_vpn_from_node(db, station, node, user, request)
    else:
        if data.station_id is not None:
            raise HTTPException(422, "Non-station devices cannot be linked to a station")
        node.station_id = None
    node.device_type = data.device_type.value
    node.approval_status = ApprovalStatus.approved.value
    node.approved_by = user.id
    node.approved_at = datetime.now(timezone.utc)
    if data.display_name:
        node.given_name = data.display_name
    add_audit(db, action="headscale.approve", entity_type="headscale_node", entity_id=node.id, actor=user, before=before, after=_audit_snapshot(node), request=request)
    await db.commit()
    await db.refresh(node)
    if node.station_id:
        await ping_station(node.station_id)
    return (await _serialize_nodes(db, [node]))[0]


@router.post("/nodes/{node_id}/reject", response_model=HeadscaleNodeOut)
async def reject_node(
    node_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    node = await _node_or_404(db, node_id)
    before = _audit_snapshot(node)
    node.station_id = None
    node.approval_status = ApprovalStatus.rejected.value
    node.approved_by = user.id
    node.approved_at = datetime.now(timezone.utc)
    add_audit(db, action="headscale.reject", entity_type="headscale_node", entity_id=node.id, actor=user, before=before, after=_audit_snapshot(node), request=request)
    await db.commit()
    await db.refresh(node)
    return (await _serialize_nodes(db, [node]))[0]


@router.post("/nodes/{node_id}/link-station", response_model=HeadscaleNodeOut)
async def link_station(
    node_id: int,
    data: HeadscaleLinkIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    node = await _node_or_404(db, node_id)
    station = await db.get(Station, data.station_id)
    if not station or station.is_archived or not station.is_active:
        raise HTTPException(404, "Active station not found")
    if node.approval_status != ApprovalStatus.approved.value:
        raise HTTPException(409, "Node must be approved before linking")
    payload = {
        "node_id": node.id,
        "station_id": station.id,
        "node_station_id": node.station_id,
        "station_existing_node_id": await _station_existing_node_id(db, station.id, node.id),
        "node_vpn_ip": node.vpn_ip,
        "station_vpn_ip": station.vpn_ip,
    }
    if not verify_confirmation_token(data.preview_token, "headscale-link", payload):
        raise HTTPException(409, "Link preview expired or inventory changed; preview again")
    await _assert_link_available(db, node, station)
    before = _audit_snapshot(node)
    node.device_type = DeviceType.station.value
    node.station_id = station.id
    await _sync_station_vpn_from_node(db, station, node, user, request)
    add_audit(db, action="headscale.link", entity_type="headscale_node", entity_id=node.id, actor=user, before=before, after=_audit_snapshot(node), request=request)
    await db.commit()
    await db.refresh(node)
    await ping_station(station.id)
    return (await _serialize_nodes(db, [node]))[0]


@router.post("/nodes/{node_id}/link-preview")
async def preview_station_link(
    node_id: int,
    station_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    node = await _node_or_404(db, node_id)
    station = await db.get(Station, station_id)
    errors = []
    if not station or station.is_archived or not station.is_active:
        errors.append("Active station not found")
    if node.approval_status != ApprovalStatus.approved.value or node.device_type != DeviceType.station.value:
        errors.append("Node must already be approved as a station device")
    existing_id = await _station_existing_node_id(db, station_id, node.id) if station else None
    if existing_id:
        errors.append("Station is already linked to another Headscale node")
    if node.station_id not in (None, station_id):
        errors.append("Headscale node is already linked to another station")
    payload = {
        "node_id": node.id,
        "station_id": station_id,
        "node_station_id": node.station_id,
        "station_existing_node_id": existing_id,
        "node_vpn_ip": node.vpn_ip,
        "station_vpn_ip": station.vpn_ip if station else None,
    }
    return {
        "valid": not errors,
        "errors": errors,
        "node_id": node.id,
        "node_hostname": node.hostname,
        "station_id": station_id,
        "station_code": station.station_code if station else None,
        "station_name": station.name if station else None,
        "node_vpn_ip": node.vpn_ip,
        "station_vpn_ip": station.vpn_ip if station else None,
        "vpn_replacement_warning": _vpn_replacement_warning(station, node),
        "preview_token": create_confirmation_token("headscale-link", payload) if not errors else None,
    }


@router.post("/nodes/{node_id}/unlink-station", response_model=HeadscaleNodeOut)
async def unlink_station(
    node_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    node = await _node_or_404(db, node_id)
    before = _audit_snapshot(node)
    node.station_id = None
    node.device_type = DeviceType.unknown.value
    add_audit(db, action="headscale.unlink", entity_type="headscale_node", entity_id=node.id, actor=user, before=before, after=_audit_snapshot(node), request=request)
    await db.commit()
    await db.refresh(node)
    return (await _serialize_nodes(db, [node]))[0]


@router.post("/nodes/{node_id}/classification-preview", response_model=HeadscaleClassificationPreviewOut)
async def preview_node_classification(
    node_id: int,
    data: HeadscaleClassificationIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    node = await _node_or_404(db, node_id)
    preview, payload = await _classification_preview(db, node, data)
    if preview.valid:
        preview.preview_token = create_confirmation_token("headscale-classification", payload)
    return preview


@router.post("/nodes/{node_id}/classification", response_model=HeadscaleNodeOut)
async def apply_node_classification(
    node_id: int,
    data: HeadscaleClassificationApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    node = await _node_or_404(db, node_id)
    preview, payload = await _classification_preview(db, node, data)
    if not preview.valid:
        raise HTTPException(422, preview.errors)
    if data.confirmation != preview.confirmation_phrase:
        raise HTTPException(422, "Explicit classification confirmation is required")
    if not verify_confirmation_token(data.preview_token, "headscale-classification", payload):
        raise HTTPException(409, "Classification preview expired or inventory changed; preview again")

    before = _audit_snapshot(node)
    station = await db.get(Station, data.station_id) if data.station_id else None
    previous_station_id = node.station_id
    if data.device_type == DeviceType.station:
        assert station is not None
        await _assert_link_available(db, node, station)
        node.station_id = station.id
        await _sync_station_vpn_from_node(db, station, node, user, request)
    else:
        node.station_id = None
    node.device_type = data.device_type.value

    if before["device_type"] != node.device_type:
        add_audit(
            db,
            action="headscale.reclassify",
            entity_type="headscale_node",
            entity_id=node.id,
            actor=user,
            before={"device_type": before["device_type"], "approval_status": before["approval_status"]},
            after={"device_type": node.device_type, "approval_status": node.approval_status},
            request=request,
        )
    if previous_station_id != node.station_id:
        add_audit(
            db,
            action="headscale.link" if node.station_id else "headscale.unlink",
            entity_type="headscale_node",
            entity_id=node.id,
            actor=user,
            before={"station_id": previous_station_id},
            after={"station_id": node.station_id},
            request=request,
        )
    await db.commit()
    await db.refresh(node)
    if node.station_id:
        await ping_station(node.station_id)
    return (await _serialize_nodes(db, [node]))[0]


@router.post("/sync")
async def sync_now(_: User = Depends(require_roles(Role.admin))):
    try:
        added = await sync_headscale_nodes()
    except Exception as exc:
        raise HTTPException(502, "Headscale synchronization failed") from exc
    return {"added": added}


@router.get("/ip-reconciliation", response_model=list[HeadscaleReconciliationRowOut])
async def ip_reconciliation(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    return await _reconciliation_rows(db)


@router.post(
    "/stations/{station_id}/reconciliation-preview",
    response_model=HeadscaleReconciliationPreviewOut,
)
async def preview_ip_reconciliation(
    station_id: int,
    data: HeadscaleReconciliationPreviewIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    preview, payload = await _reconciliation_preview(db, station_id, data)
    if preview.valid:
        preview.preview_token = create_confirmation_token("headscale-reconciliation", payload)
    return preview


@router.post("/stations/{station_id}/reconcile", response_model=HeadscaleReconciliationRowOut)
async def apply_ip_reconciliation(
    station_id: int,
    data: HeadscaleReconciliationApplyIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    station = await db.scalar(select(Station).where(Station.id == station_id).with_for_update())
    if not station:
        raise HTTPException(404, "Station not found")
    old_node = await db.scalar(
        select(HeadscaleNode).where(HeadscaleNode.station_id == station.id).with_for_update()
    )
    new_node = None
    if data.candidate_node_id is not None:
        new_node = await db.scalar(
            select(HeadscaleNode).where(HeadscaleNode.id == data.candidate_node_id).with_for_update()
        )
    preview, payload = await _reconciliation_preview(db, station_id, data)
    if not preview.valid:
        raise HTTPException(422, preview.errors)
    if data.confirmation != preview.confirmation_phrase:
        raise HTTPException(422, "Typed reconciliation confirmation is required")
    if not verify_confirmation_token(data.preview_token, "headscale-reconciliation", payload):
        raise HTTPException(409, "Reconciliation preview expired or inventory changed; preview again")

    previous_vpn = station.vpn_ip
    if data.action == "refresh_vpn":
        assert old_node is not None
        await _sync_station_vpn_from_node(db, station, old_node, user, request)
    elif data.action == "remove_stale_link":
        assert old_node is not None
        node_before = _audit_snapshot(old_node)
        old_node.station_id = None
        station.vpn_ip = None
        add_audit(db, action="headscale.unlink", entity_type="headscale_node", entity_id=old_node.id,
                  actor=user, before=node_before, after=_audit_snapshot(old_node), request=request)
        if previous_vpn:
            add_audit(db, action="station.vpn_clear_headscale_unlink", entity_type="station",
                      entity_id=station.id, actor=user,
                      before={"vpn_ip": previous_vpn, "headscale_node_id": old_node.id},
                      after={"vpn_ip": None, "headscale_node_id": None}, request=request)
    else:
        assert new_node is not None
        if data.action == "replace_node":
            assert old_node is not None
            old_before = _audit_snapshot(old_node)
            old_node.station_id = None
            add_audit(db, action="headscale.replace.unlink_old", entity_type="headscale_node",
                      entity_id=old_node.id, actor=user, before=old_before,
                      after=_audit_snapshot(old_node), request=request)
        await _assert_link_available(db, new_node, station)
        new_before = _audit_snapshot(new_node)
        new_node.station_id = station.id
        await _sync_station_vpn_from_node(db, station, new_node, user, request)
        add_audit(db, action="headscale.replace.link_new" if data.action == "replace_node" else "headscale.link",
                  entity_type="headscale_node", entity_id=new_node.id, actor=user,
                  before=new_before, after=_audit_snapshot(new_node), request=request)
    await db.commit()
    rows = await _reconciliation_rows(db)
    return next(row for row in rows if row.station_id == station.id)


async def _reconciliation_rows(db: AsyncSession) -> list[HeadscaleReconciliationRowOut]:
    stations = list((await db.execute(
        select(Station).where(Station.is_active.is_(True), Station.is_archived.is_(False))
        .order_by(Station.station_code, Station.id)
    )).scalars().all())
    nodes = list((await db.execute(select(HeadscaleNode))).scalars().all())
    linked = {node.station_id: node for node in nodes if node.station_id is not None}
    vpn_stations: dict[str, list[Station]] = {}
    for station in stations:
        if station.vpn_ip and station.vpn_ip.strip():
            vpn_stations.setdefault(station.vpn_ip.strip(), []).append(station)
    output = []
    for station in stations:
        node = linked.get(station.id)
        candidates = [
            candidate for candidate in nodes
            if candidate.station_id is None
            and candidate.device_type == DeviceType.station.value
            and candidate.approval_status == ApprovalStatus.approved.value
            and (
                (bool(station.vpn_ip and station.vpn_ip.strip()) and candidate.vpn_ip == station.vpn_ip.strip())
                or (candidate.hostname or "").casefold() == station.station_code.casefold()
                or (candidate.given_name or "").casefold() == station.station_code.casefold()
            )
        ]
        duplicate_rows = vpn_stations.get((station.vpn_ip or "").strip(), []) if station.vpn_ip else []
        conflict = None
        if len(duplicate_rows) > 1:
            status, action = "vpn_ip_duplicated", "Resolve the VPN conflict one station at a time"
            conflict = "Stored VPN also belongs to: " + ", ".join(s.station_code for s in duplicate_rows if s.id != station.id)
        elif node is None and len(candidates) > 1:
            status, action = "several_candidate_nodes", "Review candidates and choose one node"
        elif node is None:
            status, action = "station_has_no_linked_node", "Link an approved station node"
        elif node.device_type != DeviceType.station.value:
            status, action = "device_type_is_not_station", "Correct classification or remove stale link"
        elif node.approval_status != ApprovalStatus.approved.value:
            status, action = "approval_missing", "Approve the node or remove stale link"
        elif not node.vpn_ip:
            status, action = "linked_node_missing", "Review the linked node inventory"
        elif station.vpn_ip != node.vpn_ip:
            other_station, other_node = await _vpn_conflict_ids(db, node.vpn_ip, station.id, node.id)
            if other_station or other_node:
                status, action = "vpn_ip_duplicated", "Resolve the VPN conflict before refresh"
                conflict = f"Authoritative VPN conflicts with station {other_station or '—'} / node {other_node or '—'}"
            else:
                status, action = "linked_node_changed_ip", "Refresh VPN from linked node"
        else:
            status, action = "OK", "No action"
        output.append(HeadscaleReconciliationRowOut(
            station_id=station.id, station_code=station.station_code,
            station_vpn_ip=station.vpn_ip or None, linked_node_id=node.id if node else None,
            linked_node_hostname=node.hostname if node else None,
            authoritative_node_vpn_ip=node.vpn_ip if node else None,
            node_online=node.online if node else None, node_last_seen_at=node.last_seen_at if node else None,
            status=status, conflict_status=conflict, recommended_action=action,
            candidate_node_ids=[candidate.id for candidate in candidates],
        ))
    return output


async def _reconciliation_preview(
    db: AsyncSession, station_id: int, data: HeadscaleReconciliationPreviewIn,
) -> tuple[HeadscaleReconciliationPreviewOut, dict[str, object]]:
    station = await db.get(Station, station_id)
    if not station or station.is_archived or not station.is_active:
        raise HTTPException(404, "Active station not found")
    old_node = await db.scalar(select(HeadscaleNode).where(HeadscaleNode.station_id == station.id))
    new_node = await db.get(HeadscaleNode, data.candidate_node_id) if data.candidate_node_id else None
    errors: list[str] = []
    if data.action in {"refresh_vpn", "remove_stale_link", "replace_node"} and old_node is None:
        errors.append("Station has no linked node")
    if data.action in {"link_node", "replace_node"}:
        if new_node is None:
            errors.append("Select one candidate node")
        elif new_node.station_id is not None:
            errors.append("Candidate node is already linked")
        elif new_node.device_type != DeviceType.station.value or new_node.approval_status != ApprovalStatus.approved.value:
            errors.append("Candidate must be approved as a station device")
        elif not new_node.vpn_ip:
            errors.append("Candidate node has no authoritative VPN IP")
        else:
            station_conflict, node_conflict = await _vpn_conflict_ids(db, new_node.vpn_ip, station.id, new_node.id)
            if station_conflict or node_conflict:
                errors.append("Candidate VPN conflicts with another active station")
    if data.action == "link_node" and old_node is not None:
        errors.append("Station is already linked; use replace_node")
    if data.action == "replace_node" and new_node and old_node and new_node.id == old_node.id:
        errors.append("Replacement node must be different")
    if data.action == "refresh_vpn" and old_node:
        if old_node.device_type != DeviceType.station.value or old_node.approval_status != ApprovalStatus.approved.value:
            errors.append("Linked node is not an approved station device")
        elif not old_node.vpn_ip:
            errors.append("Linked node has no authoritative VPN IP")
        else:
            station_conflict, node_conflict = await _vpn_conflict_ids(db, old_node.vpn_ip, station.id, old_node.id)
            if station_conflict or node_conflict:
                errors.append("Authoritative VPN conflicts with another active station")
    phrases = {
        "refresh_vpn": f"REFRESH VPN STATION {station.station_code}",
        "remove_stale_link": f"REMOVE STALE LINK STATION {station.station_code}",
        "link_node": f"LINK NODE {new_node.id if new_node else '?'} TO STATION {station.station_code}",
        "replace_node": f"REPLACE NODE {old_node.id if old_node else '?'} WITH {new_node.id if new_node else '?'} FOR STATION {station.station_code}",
    }
    phrase = phrases[data.action]
    payload = {
        "action": data.action, "station_id": station.id, "station_code": station.station_code,
        "station_vpn_ip": station.vpn_ip, "old_node_id": old_node.id if old_node else None,
        "old_node_vpn_ip": old_node.vpn_ip if old_node else None,
        "new_node_id": new_node.id if new_node else None, "new_node_vpn_ip": new_node.vpn_ip if new_node else None,
        "new_node_station_id": new_node.station_id if new_node else None,
        "confirmation_phrase": phrase,
    }
    preview = HeadscaleReconciliationPreviewOut(
        valid=not errors, errors=errors, action=data.action, station_id=station.id,
        station_code=station.station_code, old_node_id=old_node.id if old_node else None,
        old_node_hostname=old_node.hostname if old_node else None,
        old_node_vpn_ip=old_node.vpn_ip if old_node else station.vpn_ip,
        new_node_id=new_node.id if new_node else (old_node.id if old_node else None),
        new_node_hostname=new_node.hostname if new_node else (old_node.hostname if old_node else None),
        new_node_vpn_ip=new_node.vpn_ip if new_node else (old_node.vpn_ip if old_node else None),
        new_node_operating_system=new_node.operating_system if new_node else (old_node.operating_system if old_node else None),
        new_node_last_seen_at=new_node.last_seen_at if new_node else (old_node.last_seen_at if old_node else None),
        confirmation_phrase=phrase, preview_token=None,
    )
    return preview, payload


async def _node_or_404(db: AsyncSession, node_id: int) -> HeadscaleNode:
    node = await db.get(HeadscaleNode, node_id)
    if not node:
        raise HTTPException(404, "Headscale node not found")
    return node


async def _assert_link_available(db: AsyncSession, node: HeadscaleNode, station: Station) -> None:
    station_link = (
        await db.execute(
            select(HeadscaleNode).where(
                HeadscaleNode.station_id == station.id,
                HeadscaleNode.id != node.id,
            )
        )
    ).scalar_one_or_none()
    if station_link:
        raise HTTPException(409, "Station is already linked to another Headscale node")
    if node.station_id is not None and node.station_id != station.id:
        raise HTTPException(409, "Headscale node is already linked to another station")
    station_conflict, node_conflict = await _vpn_conflict_ids(db, node.vpn_ip, station.id, node.id)
    if station_conflict or node_conflict:
        raise HTTPException(409, "Headscale VPN conflicts with another active station")


def _audit_snapshot(node: HeadscaleNode) -> dict[str, object]:
    return {
        "device_type": node.device_type,
        "approval_status": node.approval_status,
        "station_id": node.station_id,
        "given_name": node.given_name,
    }


def _vpn_replacement_warning(station: Station | None, node: HeadscaleNode) -> str | None:
    if station and station.vpn_ip and node.vpn_ip and station.vpn_ip != node.vpn_ip:
        return f"Station VPN will change from {station.vpn_ip} to Headscale VPN {node.vpn_ip}"
    return None


async def _sync_station_vpn_from_node(
    db: AsyncSession,
    station: Station,
    node: HeadscaleNode,
    actor: User,
    request: Request,
) -> None:
    if not node.vpn_ip or station.vpn_ip == node.vpn_ip:
        return
    station_conflict, node_conflict = await _vpn_conflict_ids(db, node.vpn_ip, station.id, node.id)
    if station_conflict or node_conflict:
        raise HTTPException(409, "Headscale VPN conflicts with another active station")
    previous = station.vpn_ip
    station.vpn_ip = node.vpn_ip
    add_audit(
        db,
        action="station.vpn_sync_headscale",
        entity_type="station",
        entity_id=station.id,
        actor=actor,
        before={"vpn_ip": previous, "headscale_node_id": node.id},
        after={"vpn_ip": node.vpn_ip, "headscale_node_id": node.id},
        request=request,
    )


async def _vpn_conflict_ids(
    db: AsyncSession, vpn_ip: str | None, station_id: int, node_id: int,
) -> tuple[int | None, int | None]:
    if not vpn_ip:
        return None, None
    station_conflict = await db.scalar(
        select(Station.id).where(
            Station.id != station_id, Station.is_active.is_(True), Station.is_archived.is_(False),
            Station.vpn_ip == vpn_ip,
        ).limit(1)
    )
    node_conflict = await db.scalar(
        select(HeadscaleNode.id).join(Station, Station.id == HeadscaleNode.station_id).where(
            HeadscaleNode.id != node_id, HeadscaleNode.vpn_ip == vpn_ip,
            HeadscaleNode.device_type == DeviceType.station.value,
            HeadscaleNode.approval_status == ApprovalStatus.approved.value,
            Station.id != station_id, Station.is_active.is_(True), Station.is_archived.is_(False),
        ).limit(1)
    )
    return station_conflict, node_conflict


async def _approval_preview(db: AsyncSession, node: HeadscaleNode, data: HeadscaleApproveIn):
    errors: list[str] = []
    station = (
        (
            await db.execute(
                select(Station)
                .where(Station.id == data.station_id)
                .options(selectinload(Station.district))
            )
        ).scalar_one_or_none()
        if data.station_id
        else None
    )
    existing_id = None
    if node.approval_status != ApprovalStatus.pending.value:
        errors.append("Only pending nodes can use the approval workflow")
    if data.device_type == DeviceType.station:
        if not station or station.is_archived or not station.is_active:
            errors.append("An active station is required for station devices")
        else:
            existing_id = await _station_existing_node_id(db, station.id, node.id)
            if existing_id:
                errors.append("Station is already linked to another Headscale node")
            if node.station_id not in (None, station.id):
                errors.append("Headscale node is already linked to another station")
    elif data.station_id is not None:
        errors.append("Phones, PCs, and servers cannot be linked to stations")
    district = station.district.name if station and station.district else None
    payload = {
        "node_id": node.id,
        "approval_status": node.approval_status,
        "device_type": data.device_type.value,
        "display_name": data.display_name,
        "station_id": data.station_id,
        "node_existing_station_id": node.station_id,
        "station_existing_node_id": existing_id,
        "vpn_ip": node.vpn_ip,
        "station_vpn_ip": station.vpn_ip if station else None,
    }
    preview = {
        "node_id": node.id,
        "node_hostname": node.hostname,
        "node_given_name": data.display_name or node.given_name,
        "vpn_ip": node.vpn_ip,
        "device_type": data.device_type,
        "station_id": data.station_id,
        "station_code": station.station_code if station else None,
        "station_name": station.name if station else None,
        "district": district,
        "node_existing_station_id": node.station_id,
        "station_existing_node_id": existing_id,
        "vpn_replacement_warning": _vpn_replacement_warning(station, node),
        "valid": not errors,
        "errors": errors,
    }
    return preview, payload


async def _classification_preview(
    db: AsyncSession,
    node: HeadscaleNode,
    data: HeadscaleClassificationIn,
) -> tuple[HeadscaleClassificationPreviewOut, dict[str, object]]:
    errors: list[str] = []
    if node.approval_status != ApprovalStatus.approved.value:
        errors.append("Only approved nodes can use classification editing")
    current_station = await db.get(Station, node.station_id) if node.station_id else None
    station = await db.get(Station, data.station_id) if data.station_id else None
    existing_node_id = None
    if data.device_type == DeviceType.station:
        if not station or station.is_archived or not station.is_active:
            errors.append("Select exactly one active station")
        else:
            existing_node_id = await _station_existing_node_id(db, station.id, node.id)
            if existing_node_id:
                errors.append("Station is already linked to another Headscale node")
            if node.station_id not in (None, station.id):
                errors.append("Unlink this node from its current station before selecting another station")
    elif data.station_id is not None:
        errors.append("Non-station device classifications cannot have a station link")

    station_code = station.station_code if station else None
    if data.device_type == DeviceType.station and station_code:
        phrase = f"LINK NODE {node.id} TO STATION {station_code}"
    elif node.station_id is not None:
        phrase = f"UNLINK NODE {node.id} AND RECLASSIFY AS {data.device_type.value.upper()}"
    else:
        phrase = f"RECLASSIFY NODE {node.id} AS {data.device_type.value.upper()}"
    replacement = _vpn_replacement_warning(station, node)
    preview = HeadscaleClassificationPreviewOut(
        node_id=node.id,
        hostname=node.hostname,
        vpn_ip=node.vpn_ip,
        online=node.online,
        approval_status=ApprovalStatus(node.approval_status),
        current_device_type=DeviceType(node.device_type),
        current_station_id=node.station_id,
        current_station_code=current_station.station_code if current_station else None,
        proposed_device_type=data.device_type,
        proposed_station_id=data.station_id,
        proposed_station_code=station_code,
        station_vpn_ip=station.vpn_ip if station else None,
        proposed_station_vpn_ip=node.vpn_ip if station and node.vpn_ip else station.vpn_ip if station else None,
        vpn_replacement_warning=replacement,
        confirmation_phrase=phrase,
        valid=not errors,
        errors=errors,
        preview_token=None,
    )
    payload = {
        "node_id": node.id,
        "approval_status": node.approval_status,
        "current_device_type": node.device_type,
        "current_station_id": node.station_id,
        "node_vpn_ip": node.vpn_ip,
        "proposed_device_type": data.device_type.value,
        "proposed_station_id": data.station_id,
        "station_existing_node_id": existing_node_id,
        "station_vpn_ip": station.vpn_ip if station else None,
        "confirmation_phrase": phrase,
    }
    return preview, payload


async def _station_existing_node_id(db: AsyncSession, station_id: int, excluding_node_id: int) -> int | None:
    return (
        await db.execute(
            select(HeadscaleNode.id).where(
                HeadscaleNode.station_id == station_id,
                HeadscaleNode.id != excluding_node_id,
            )
        )
    ).scalar_one_or_none()


async def _serialize_nodes(db: AsyncSession, nodes: list[HeadscaleNode]) -> list[HeadscaleNodeOut]:
    if not nodes:
        return []
    station_ids = {node.station_id for node in nodes if node.station_id}
    stations = (
        await db.execute(select(Station).where(Station.id.in_(station_ids)))
    ).scalars().all() if station_ids else []
    station_by_id = {station.id: station for station in stations}
    vpn_ips = {node.vpn_ip for node in nodes if node.vpn_ip}
    all_nodes = (
        await db.execute(select(HeadscaleNode).where(HeadscaleNode.vpn_ip.in_(vpn_ips)))
    ).scalars().all() if vpn_ips else []
    station_vpn_counts = dict(
        (
            await db.execute(
                select(Station.vpn_ip, func.count(Station.id))
                .where(Station.vpn_ip.in_(vpn_ips), Station.is_archived.is_(False))
                .group_by(Station.vpn_ip)
            )
        ).all()
    ) if vpn_ips else {}
    nodes_by_vpn: dict[str, list[HeadscaleNode]] = {}
    for item in all_nodes:
        if item.vpn_ip:
            nodes_by_vpn.setdefault(item.vpn_ip, []).append(item)
    output = []
    for node in nodes:
        station = station_by_id.get(node.station_id)
        duplicates = nodes_by_vpn.get(node.vpn_ip or "", [])
        output.append(
            HeadscaleNodeOut.model_validate(node).model_copy(
                update={
                    "linked_station_code": station.station_code if station else None,
                    "linked_station_name": station.name if station else None,
                    "duplicate_vpn_ip": len(duplicates) > 1 or station_vpn_counts.get(node.vpn_ip, 0) > 1,
                    "duplicate_vpn_node_ids": [item.id for item in duplicates if item.id != node.id],
                }
            )
        )
    return output
