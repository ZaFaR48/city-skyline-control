from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..deps import require_roles
from ..models import ApprovalStatus, DeviceType, HeadscaleNode, Role, Station, User
from ..schemas import (
    HeadscaleApproveConfirmIn,
    HeadscaleApproveIn,
    HeadscaleClassificationApplyIn,
    HeadscaleClassificationIn,
    HeadscaleClassificationPreviewOut,
    HeadscaleLinkIn,
    HeadscaleNodeOut,
)
from ..services.audit import add_audit
from ..services.confirmation_tokens import create_confirmation_token, verify_confirmation_token
from ..services.headscale import sync_headscale_nodes
from ..services.ping_monitor import ping_station


router = APIRouter()


@router.get("/nodes", response_model=list[HeadscaleNodeOut])
async def list_nodes(
    approval_status: ApprovalStatus | None = None,
    device_type: DeviceType | None = None,
    online: bool | None = None,
    linked: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    stmt = select(HeadscaleNode)
    if approval_status:
        stmt = stmt.where(HeadscaleNode.approval_status == approval_status.value)
    if device_type:
        stmt = stmt.where(HeadscaleNode.device_type == device_type.value)
    if online is not None:
        stmt = stmt.where(HeadscaleNode.online == online)
    if linked is not None:
        stmt = stmt.where(HeadscaleNode.station_id.is_not(None) if linked else HeadscaleNode.station_id.is_(None))
    nodes = (await db.execute(stmt.order_by(HeadscaleNode.hostname))).scalars().all()
    return await _serialize_nodes(db, list(nodes))


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
        _sync_station_vpn_from_node(db, station, node, user, request)
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
    _sync_station_vpn_from_node(db, station, node, user, request)
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
        _sync_station_vpn_from_node(db, station, node, user, request)
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


def _sync_station_vpn_from_node(
    db: AsyncSession,
    station: Station,
    node: HeadscaleNode,
    actor: User,
    request: Request,
) -> None:
    if not node.vpn_ip or station.vpn_ip == node.vpn_ip:
        return
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
