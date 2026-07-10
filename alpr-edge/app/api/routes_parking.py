from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import get_parking_repository
from app.api.serializers import with_local_times
from app.parking.repositories import ParkingRepository
router = APIRouter(prefix="/parking", tags=["parking"])


@router.get("/sessions")
def list_sessions(request: Request, repository: ParkingRepository = Depends(get_parking_repository)) -> list[dict]:
    timezone_name = request.app.state.config.parking_timezone
    return [with_local_times(session, timezone_name) for session in repository.list_sessions()]


@router.get("/sessions/active")
def list_active_sessions(request: Request, repository: ParkingRepository = Depends(get_parking_repository)) -> list[dict]:
    timezone_name = request.app.state.config.parking_timezone
    return [with_local_times(session, timezone_name) for session in repository.list_active_sessions()]


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    request: Request,
    repository: ParkingRepository = Depends(get_parking_repository),
) -> dict:
    session = repository.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Parking session not found")
    return with_local_times(session, request.app.state.config.parking_timezone)

