from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.dependencies import get_camera_service
from app.camera_models import CameraStatusResponse, CameraTestResponse, SnapshotResponse
from app.camera_service import CameraService

router = APIRouter(prefix="/camera", tags=["camera"])


@router.get("/status", response_model=CameraStatusResponse)
def camera_status(camera: CameraService = Depends(get_camera_service)) -> CameraStatusResponse:
    return CameraStatusResponse.model_validate(camera.status())


@router.post("/test", response_model=CameraTestResponse)
def camera_test(camera: CameraService = Depends(get_camera_service)) -> CameraTestResponse:
    return CameraTestResponse.model_validate(camera.test_connection())


@router.post("/snapshot", response_model=SnapshotResponse)
def camera_snapshot(camera: CameraService = Depends(get_camera_service)) -> SnapshotResponse:
    try:
        return SnapshotResponse.model_validate(camera.capture_snapshot().__dict__)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/snapshot/latest")
def latest_snapshot(camera: CameraService = Depends(get_camera_service)) -> FileResponse:
    snapshot_dir = camera.config.snapshot_dir
    candidates = sorted(snapshot_dir.glob("*.jpg"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise HTTPException(status_code=404, detail="No snapshot has been captured yet")
    path = candidates[0]
    return FileResponse(Path(path), media_type="image/jpeg")


@router.post("/reconnect", response_model=CameraTestResponse)
def camera_reconnect(camera: CameraService = Depends(get_camera_service)) -> CameraTestResponse:
    return CameraTestResponse.model_validate(camera.reconnect())
