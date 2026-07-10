from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import AppConfig


@dataclass(frozen=True)
class ALPRConfig:
    vehicle_detector_enabled: bool
    vehicle_detector_model_path: Path | None
    vehicle_detector_confidence: float
    vehicle_detector_input_size: int | None
    vehicle_classes: tuple[str, ...]
    plate_detector_backend: str
    plate_detector_model_path: Path | None
    plate_detector_confidence: float
    plate_min_aspect_ratio: float
    plate_max_aspect_ratio: float
    plate_min_width_pixels: int
    plate_max_candidates_per_vehicle: int
    ocr_backend: str
    ocr_min_confidence: float
    ocr_max_variants: int
    ocr_allowed_characters: str
    ocr_model_dir: Path
    alpr_dedup_window_seconds: int
    alpr_same_plate_max_distance: int
    alpr_reprocess_interval_seconds: int
    pilot_fixed_preset_id: str | None
    save_full_frame: bool
    save_vehicle_crop: bool
    save_plate_crop: bool
    save_rejected_candidates: bool
    media_retention_days: int
    review_media_retention_days: int
    dataset_collection_enabled: bool
    dataset_collection_require_review: bool
    model_manifest_path: Path | None
    model_pack_dir: Path


def alpr_config_from_app(config: AppConfig) -> ALPRConfig:
    return ALPRConfig(
        vehicle_detector_enabled=config.vehicle_detector_enabled,
        vehicle_detector_model_path=config.vehicle_detector_model_path,
        vehicle_detector_confidence=config.vehicle_detector_confidence,
        vehicle_detector_input_size=config.vehicle_detector_input_size,
        vehicle_classes=tuple(config.vehicle_classes),
        plate_detector_backend=config.plate_detector_backend,
        plate_detector_model_path=config.plate_detector_model_path,
        plate_detector_confidence=config.plate_detector_confidence,
        plate_min_aspect_ratio=config.plate_min_aspect_ratio,
        plate_max_aspect_ratio=config.plate_max_aspect_ratio,
        plate_min_width_pixels=config.plate_min_width_pixels,
        plate_max_candidates_per_vehicle=config.plate_max_candidates_per_vehicle,
        ocr_backend=config.ocr_backend,
        ocr_min_confidence=config.ocr_min_confidence,
        ocr_max_variants=config.ocr_max_variants,
        ocr_allowed_characters=config.ocr_allowed_characters,
        ocr_model_dir=config.ocr_model_dir,
        alpr_dedup_window_seconds=config.alpr_dedup_window_seconds,
        alpr_same_plate_max_distance=config.alpr_same_plate_max_distance,
        alpr_reprocess_interval_seconds=config.alpr_reprocess_interval_seconds,
        pilot_fixed_preset_id=config.pilot_fixed_preset_id,
        save_full_frame=config.alpr_save_full_frame,
        save_vehicle_crop=config.alpr_save_vehicle_crop,
        save_plate_crop=config.alpr_save_plate_crop,
        save_rejected_candidates=config.alpr_save_rejected_candidates,
        media_retention_days=config.alpr_media_retention_days,
        review_media_retention_days=config.alpr_review_media_retention_days,
        dataset_collection_enabled=config.dataset_collection_enabled,
        dataset_collection_require_review=config.dataset_collection_require_review,
        model_manifest_path=config.model_manifest_path,
        model_pack_dir=config.model_pack_dir,
    )
