from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.api.dependencies import get_camera_service
from app.api.dependencies import get_repository
from app.camera_service import CameraService
from app.database.repositories import EdgeRepository
from app.ptz.controller import PTZController
from app.ptz.models import PTZActionResult, PTZPresetCreate, PTZPresetPatch, PTZPresetRead
from app.ptz.preset_service import enforce_home_defaults

router = APIRouter(prefix="/ptz", tags=["ptz"])


def _as_preset(data: dict | None) -> PTZPresetRead:
    if data is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    return PTZPresetRead.model_validate(data)


@router.get("/presets", response_model=list[PTZPresetRead])
def list_presets(repository: EdgeRepository = Depends(get_repository)) -> list[PTZPresetRead]:
    return [PTZPresetRead.model_validate(item) for item in repository.list_presets()]


@router.post("/presets", response_model=PTZPresetRead, status_code=201)
def create_preset(
    payload: PTZPresetCreate,
    repository: EdgeRepository = Depends(get_repository),
) -> PTZPresetRead:
    enforce_home_defaults(payload)
    try:
        return PTZPresetRead.model_validate(repository.create_preset(payload))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/presets/{preset_id}", response_model=PTZPresetRead)
def get_preset(preset_id: str, repository: EdgeRepository = Depends(get_repository)) -> PTZPresetRead:
    return _as_preset(repository.get_preset(preset_id))


@router.patch("/presets/{preset_id}", response_model=PTZPresetRead)
def update_preset(
    preset_id: str,
    payload: PTZPresetPatch,
    repository: EdgeRepository = Depends(get_repository),
) -> PTZPresetRead:
    enforce_home_defaults(payload)
    try:
        return _as_preset(repository.update_preset(preset_id, payload))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/presets/{preset_id}", status_code=204)
def delete_preset(preset_id: str, repository: EdgeRepository = Depends(get_repository)) -> None:
    if not repository.delete_preset(preset_id):
        raise HTTPException(status_code=404, detail="Preset not found")


@router.post("/presets/{preset_id}/set-home", response_model=PTZPresetRead)
def set_home_preset(preset_id: str, repository: EdgeRepository = Depends(get_repository)) -> PTZPresetRead:
    return _as_preset(repository.set_home_preset(preset_id))


@router.post("/presets/{preset_id}/goto", response_model=PTZActionResult)
def goto_preset(
    preset_id: str,
    request: Request,
    repository: EdgeRepository = Depends(get_repository),
) -> PTZActionResult:
    preset = _as_preset(repository.get_preset(preset_id))
    controller = PTZController(dry_run=request.app.state.config.ptz_dry_run)
    return controller.goto_preset(preset)


@router.post("/presets/{preset_id}/snapshot")
def snapshot_preset(
    preset_id: str,
    request: Request,
    source: str = "upload",
    file: UploadFile | None = File(default=None),
    repository: EdgeRepository = Depends(get_repository),
    camera: CameraService = Depends(get_camera_service),
) -> dict:
    preset = _as_preset(repository.get_preset(preset_id))
    snapshot_dir = request.app.state.config.snapshot_dir
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    if source == "upload":
        if file is None:
            raise HTTPException(status_code=400, detail="JPEG or PNG upload is required")
        content_type = file.content_type or ""
        if content_type not in {"image/jpeg", "image/png"}:
            raise HTTPException(status_code=400, detail="Only JPEG and PNG snapshots are allowed")
        suffix = ".jpg" if content_type == "image/jpeg" else ".png"
        path = snapshot_dir / f"{preset.id}{suffix}"
        with path.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        width, height = _read_image_size(path)
    elif source == "capture":
        try:
            metadata = camera.capture_snapshot(snapshot_dir)
            path = Path(metadata.snapshot_path)
            width = metadata.frame_width
            height = metadata.frame_height
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=400, detail="source must be 'upload' or 'capture'")

    updated = repository.update_preset(
        preset_id,
        PTZPresetPatch(
            reference_snapshot_path=str(path),
            snapshot_width=width,
            snapshot_height=height,
            calibration_version=preset.calibration_version + 1,
        ),
    )
    return {
        "preset": _as_preset(updated),
        "snapshot_path": str(path),
        "snapshot_width": width,
        "snapshot_height": height,
    }


def _read_image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        import cv2

        image = cv2.imread(str(path))
        if image is None:
            return None, None
        height, width = image.shape[:2]
        return width, height
    except Exception:
        return None, None
