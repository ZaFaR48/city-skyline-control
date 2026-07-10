from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_repository
from app.database.repositories import EdgeRepository
from app.version import __version__

router = APIRouter(tags=["health"])


@router.get("")
@router.get("/")
def api_index() -> dict:
    return {
        "service": "City Skyline Edge",
        "module": "PTZ Zone Designer",
        "status": "ok",
        "version": __version__,
    }


@router.get("/health")
def health(repository: EdgeRepository = Depends(get_repository)) -> dict:
    plan = repository.get_patrol_plan()
    return {
        "service": "City Skyline Edge",
        "module": "PTZ Zone Designer",
        "status": "ok",
        "version": __version__,
        "patrol_configured": plan is not None,
    }
