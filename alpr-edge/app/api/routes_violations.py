from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.dependencies import get_violation_service
from app.api.serializers import with_local_times
from app.violations.service import ViolationService

router = APIRouter(prefix="/violations", tags=["violations"])


class ModerationRequest(BaseModel):
    moderator_id: str | None = None
    note: str | None = None


@router.get("")
def list_violations(request: Request, service: ViolationService = Depends(get_violation_service)) -> list[dict]:
    timezone_name = request.app.state.config.parking_timezone
    return [with_local_times(candidate, timezone_name) for candidate in service.list_candidates()]


@router.get("/{violation_id}")
def get_violation(
    violation_id: str,
    request: Request,
    service: ViolationService = Depends(get_violation_service),
) -> dict:
    candidate = service.get_candidate(violation_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Violation candidate not found")
    return with_local_times(candidate, request.app.state.config.parking_timezone)


@router.post("/{violation_id}/confirm")
def confirm_violation(
    violation_id: str,
    request: Request,
    payload: ModerationRequest | None = None,
    service: ViolationService = Depends(get_violation_service),
) -> dict:
    candidate = service.confirm(violation_id, payload.moderator_id if payload else None, payload.note if payload else None)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Violation candidate not found")
    return with_local_times(candidate, request.app.state.config.parking_timezone)


@router.post("/{violation_id}/reject")
def reject_violation(
    violation_id: str,
    request: Request,
    payload: ModerationRequest | None = None,
    service: ViolationService = Depends(get_violation_service),
) -> dict:
    candidate = service.reject(violation_id, payload.moderator_id if payload else None, payload.note if payload else None)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Violation candidate not found")
    return with_local_times(candidate, request.app.state.config.parking_timezone)
