from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.alpr.observation_service import ALPRObservationRepository
from app.api.dependencies import get_alpr_pipeline, get_repository
from app.database.repositories import EdgeRepository

router = APIRouter(prefix="/alpr", tags=["alpr"])


@router.get("/status")
def alpr_status(pipeline=Depends(get_alpr_pipeline)) -> dict:
    return pipeline.status()


@router.get("/models")
def alpr_models(pipeline=Depends(get_alpr_pipeline)) -> dict:
    status = pipeline.status()
    return {
        "vehicle_model": status["vehicle_model"],
        "ocr_model": status["ocr_model"],
        "plate_detector": status["plate_detector"],
        "warnings": status["warnings"],
    }


@router.post("/test-snapshot")
async def test_snapshot(
    file: UploadFile = File(...),
    create_session: bool = Query(default=False),
    pipeline=Depends(get_alpr_pipeline),
) -> dict:
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename or "snapshot.jpg").suffix or ".jpg") as handle:
        handle.write(content)
        handle.flush()
        frame = cv2.imread(handle.name)
    if frame is None:
        raise HTTPException(status_code=400, detail="Uploaded image could not be decoded")
    try:
        observations = pipeline.process_frame(frame, frame_path=None, create_sessions=create_session)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"created_sessions": create_session, "observations": observations, "metrics": pipeline.metrics.as_dict()}


@router.post("/process-latest-snapshot")
def process_latest_snapshot(
    create_session: bool = Query(default=True),
    pipeline=Depends(get_alpr_pipeline),
) -> dict:
    snapshot_dir = pipeline.media_dir
    candidates = sorted(snapshot_dir.glob("*.jpg"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise HTTPException(status_code=404, detail="No snapshot has been captured yet")
    frame = cv2.imread(str(candidates[0]))
    if frame is None:
        raise HTTPException(status_code=400, detail="Latest snapshot could not be decoded")
    observations = pipeline.process_frame(frame, frame_path=str(candidates[0].name), create_sessions=create_session)
    return {"snapshot": candidates[0].name, "observations": observations, "metrics": pipeline.metrics.as_dict()}


@router.get("/observations")
def list_observations(repository: EdgeRepository = Depends(get_repository)) -> list[dict]:
    return ALPRObservationRepository(repository.database_path).list_observations()


@router.get("/observations/{observation_id}")
def get_observation(observation_id: str, repository: EdgeRepository = Depends(get_repository)) -> dict:
    observation = ALPRObservationRepository(repository.database_path).get_observation(observation_id)
    if observation is None:
        raise HTTPException(status_code=404, detail="ALPR observation not found")
    return observation


@router.get("/review")
def review_queue(repository: EdgeRepository = Depends(get_repository)) -> list[dict]:
    return ALPRObservationRepository(repository.database_path).list_review()


@router.post("/review/{observation_id}/confirm")
def confirm_observation(observation_id: str, repository: EdgeRepository = Depends(get_repository)) -> dict:
    observation = ALPRObservationRepository(repository.database_path).update_review(observation_id, "accepted")
    if observation is None:
        raise HTTPException(status_code=404, detail="ALPR observation not found")
    return observation


@router.post("/review/{observation_id}/correct")
def correct_observation(
    observation_id: str,
    corrected_plate: str = Query(..., min_length=1),
    repository: EdgeRepository = Depends(get_repository),
) -> dict:
    observation = ALPRObservationRepository(repository.database_path).update_review(
        observation_id, "accepted", corrected_plate=corrected_plate
    )
    if observation is None:
        raise HTTPException(status_code=404, detail="ALPR observation not found")
    return observation


@router.post("/review/{observation_id}/reject")
def reject_observation(observation_id: str, repository: EdgeRepository = Depends(get_repository)) -> dict:
    observation = ALPRObservationRepository(repository.database_path).update_review(observation_id, "rejected")
    if observation is None:
        raise HTTPException(status_code=404, detail="ALPR observation not found")
    return observation


@router.get("/metrics")
def alpr_metrics(repository: EdgeRepository = Depends(get_repository)) -> dict:
    return ALPRObservationRepository(repository.database_path).latest_metrics()
