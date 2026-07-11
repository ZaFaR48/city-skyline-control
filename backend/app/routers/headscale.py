from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import ApprovalStatus, DeviceType, HeadscaleNode, Role, Station, User
from ..schemas import HeadscaleApproveIn, HeadscaleLinkIn, HeadscaleNodeOut
from ..services.audit import add_audit
from ..services.headscale import sync_headscale_nodes
from ..services.ping_monitor import ping_station


router = APIRouter()


@router.get("/nodes", response_model=list[HeadscaleNodeOut])
async def list_nodes(
    approval_status: ApprovalStatus | None = None,
    device_type: DeviceType | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(HeadscaleNode)
    if approval_status:
        stmt = stmt.where(HeadscaleNode.approval_status == approval_status.value)
    if device_type:
        stmt = stmt.where(HeadscaleNode.device_type == device_type.value)
    return (await db.execute(stmt.order_by(HeadscaleNode.hostname))).scalars().all()


@router.get("/nodes/pending", response_model=list[HeadscaleNodeOut])
async def pending_nodes(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.admin)),
):
    return (
        await db.execute(
            select(HeadscaleNode)
            .where(HeadscaleNode.approval_status == ApprovalStatus.pending.value)
            .order_by(HeadscaleNode.first_seen_at)
        )
    ).scalars().all()


@router.post("/nodes/{node_id}/approve", response_model=HeadscaleNodeOut)
async def approve_node(
    node_id: int,
    data: HeadscaleApproveIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.admin)),
):
    node = await _node_or_404(db, node_id)
    before = _audit_snapshot(node)
    if data.device_type == DeviceType.station:
        if data.station_id is None:
            raise HTTPException(422, "station_id is required for station devices")
        station = await db.get(Station, data.station_id)
        if not station or station.is_archived or not station.is_active:
            raise HTTPException(404, "Active station not found")
        await _assert_link_available(db, node, station)
        node.station_id = station.id
        station.vpn_ip = node.vpn_ip or station.vpn_ip
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
    return node


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
    return node


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
    await _assert_link_available(db, node, station)
    before = _audit_snapshot(node)
    node.device_type = DeviceType.station.value
    node.station_id = station.id
    station.vpn_ip = node.vpn_ip or station.vpn_ip
    add_audit(db, action="headscale.link", entity_type="headscale_node", entity_id=node.id, actor=user, before=before, after=_audit_snapshot(node), request=request)
    await db.commit()
    await db.refresh(node)
    await ping_station(station.id)
    return node


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
    return node


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
