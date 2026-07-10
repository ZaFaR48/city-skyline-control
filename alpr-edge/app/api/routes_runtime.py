from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_runtime_status_service
from app.runtime.lifecycle import RuntimeStatusService

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/status")
def runtime_status(request: Request, service: RuntimeStatusService = Depends(get_runtime_status_service)) -> dict:
    return service.status(embedded_worker_running=request.app.state.runtime_controller.running)


@router.post("/start")
def runtime_start(request: Request) -> dict:
    result = request.app.state.runtime_controller.start()
    return result


@router.post("/stop")
def runtime_stop(request: Request) -> dict:
    return request.app.state.runtime_controller.stop()
