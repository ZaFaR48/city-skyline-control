from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_repository
from app.database.repositories import EdgeRepository
from app.ptz.models import PatrolPlanRead, PatrolPlanWrite, PatrolSimulation
from app.ptz.patrol_service import simulate_patrol
from app.ptz.validators import validate_patrol_plan

router = APIRouter(prefix="/patrol", tags=["patrol"])


@router.get("", response_model=PatrolPlanRead | None)
def get_patrol(repository: EdgeRepository = Depends(get_repository)) -> PatrolPlanRead | None:
    plan = repository.get_patrol_plan()
    return PatrolPlanRead.model_validate(plan) if plan else None


@router.put("", response_model=PatrolPlanRead)
def put_patrol(
    payload: PatrolPlanWrite,
    repository: EdgeRepository = Depends(get_repository),
) -> PatrolPlanRead:
    try:
        validate_patrol_plan(payload)
        return PatrolPlanRead.model_validate(repository.put_patrol_plan(payload.model_dump(mode="json")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/simulate", response_model=PatrolSimulation)
def simulate(repository: EdgeRepository = Depends(get_repository)) -> PatrolSimulation:
    plan = repository.get_patrol_plan()
    if plan is None:
        raise HTTPException(status_code=404, detail="Patrol plan not configured")
    return simulate_patrol(PatrolPlanRead.model_validate(plan))
