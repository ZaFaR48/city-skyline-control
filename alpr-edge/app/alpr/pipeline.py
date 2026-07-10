from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from app.alpr.config import ALPRConfig
from app.alpr.deduplicator import TemporalDeduplicator
from app.alpr.metrics import ALPRMetrics
from app.alpr.models import ALPRObservation, ALPRStatus, BoundingBox, SlotContext
from app.alpr.observation_service import ALPRObservationService
from app.alpr.ocr_engine import RapidOCREngine
from app.alpr.perspective import crop_bbox
from app.alpr.plate_detector import HybridPlateDetector
from app.alpr.tajik_normalizer import TajikPlateNormalizer
from app.alpr.tajik_validator import TajikPlateValidator
from app.alpr.vehicle_detector import DisabledVehicleDetector, ONNXVehicleDetector, VehicleDetectorError
from app.database.repositories import EdgeRepository
from app.parking.session_engine import ParkingSessionEngine


class ALPRPipeline:
    def __init__(
        self,
        config: ALPRConfig,
        edge_repository: EdgeRepository,
        observation_service: ALPRObservationService,
        media_dir: Path,
    ) -> None:
        self.config = config
        self.edge_repository = edge_repository
        self.observation_service = observation_service
        self.media_dir = media_dir
        self.metrics = ALPRMetrics()
        self.vehicle_detector = (
            ONNXVehicleDetector(
                config.vehicle_detector_model_path,
                config.vehicle_detector_confidence,
                config.vehicle_classes,
                config.vehicle_detector_input_size,
            )
            if config.vehicle_detector_enabled
            else DisabledVehicleDetector()
        )
        self.plate_detector = HybridPlateDetector(
            config.plate_min_aspect_ratio,
            config.plate_max_aspect_ratio,
            config.plate_min_width_pixels,
            config.plate_max_candidates_per_vehicle,
            config.plate_detector_confidence,
        )
        self.ocr_engine = RapidOCREngine(
            config.ocr_model_dir,
            config.ocr_min_confidence,
            config.ocr_max_variants,
            config.ocr_allowed_characters,
        )
        self.normalizer = TajikPlateNormalizer()
        self.validator = TajikPlateValidator()
        self.deduplicator = TemporalDeduplicator(
            config.alpr_dedup_window_seconds,
            config.alpr_reprocess_interval_seconds,
        )

    def load_models(self) -> None:
        if self.config.vehicle_detector_enabled:
            self.vehicle_detector.load()
        self.ocr_engine.load()

    def status(self) -> dict:
        vehicle_status = self.vehicle_detector.status()
        ocr_status = self.ocr_engine.status()
        return {
            "ready": vehicle_status.get("ready", False) and ocr_status.get("ready", False),
            "vehicle_model": vehicle_status,
            "ocr_model": ocr_status,
            "plate_detector": {"backend": self.config.plate_detector_backend, "version": self.plate_detector.model_version},
            "current_preset": self.config.pilot_fixed_preset_id,
            "metrics": self.metrics.as_dict(),
            "warnings": self._configuration_warnings(),
        }

    def process_frame(
        self,
        frame: np.ndarray,
        observed_at: datetime | None = None,
        frame_path: str | None = None,
        create_sessions: bool = True,
    ) -> list[dict]:
        started = time.perf_counter()
        observed_at = observed_at or datetime.now(timezone.utc)
        h, w = frame.shape[:2]
        frame_hash = hashlib.sha256(frame.tobytes()).hexdigest()
        slots = self._slot_contexts(w, h)
        if not slots:
            self.metrics.warnings.append("No fixed preset or enabled slot polygons configured; ALPR skipped")
            return []
        observations: list[dict] = []
        for slot in slots:
            slot_crop, offset = self._crop_slot(frame, slot)
            if slot_crop.size == 0:
                continue
            try:
                vehicle_detections = self.vehicle_detector.detect(slot_crop)
            except VehicleDetectorError as exc:
                self.metrics.warnings.append(str(exc))
                return []
            if not vehicle_detections:
                vehicle_detections = []
            for vehicle in vehicle_detections:
                vehicle_crop = crop_bbox(slot_crop, vehicle.bbox)
                plate_candidates = self.plate_detector.detect(vehicle_crop)
                if not plate_candidates:
                    self.metrics.rejected_candidates += 1
                    continue
                for plate in plate_candidates:
                    ocr = self.ocr_engine.recognize(plate.corrected_crop)
                    if ocr is None or not ocr.text:
                        self.metrics.rejected_candidates += 1
                        continue
                    normalized = self.normalizer.normalize(ocr.text)
                    validation = self.validator.validate(normalized.canonical_text)
                    status = self._status_for(ocr.confidence, validation.status)
                    global_vehicle_bbox = self._global_bbox(vehicle.bbox, offset)
                    global_plate_bbox = self._global_bbox(
                        BoundingBox(
                            vehicle.bbox.x + plate.bbox.x,
                            vehicle.bbox.y + plate.bbox.y,
                            plate.bbox.width,
                            plate.bbox.height,
                        ),
                        offset,
                    )
                    if self.deduplicator.should_skip(
                        normalized.canonical_text,
                        slot.slot_id,
                        slot.preset_id,
                        frame_hash,
                        global_vehicle_bbox,
                        observed_at,
                    ):
                        continue
                    media_paths = self._save_media(
                        observed_at,
                        frame,
                        vehicle_crop,
                        plate.crop,
                        plate.corrected_crop,
                        normalized.canonical_text,
                        status,
                    )
                    observation = ALPRObservation(
                        observation_id=str(uuid4()),
                        station_code=self.edge_repository_station_code,
                        camera_id=self.edge_repository_camera_id,
                        preset_id=slot.preset_id,
                        zone_id=slot.zone_id,
                        slot_id=slot.slot_id,
                        slot_code=slot.slot_code,
                        observed_at=observed_at,
                        plate_raw=normalized.raw_text,
                        plate_canonical=normalized.canonical_text,
                        plate_display=normalized.display_text,
                        plate_format=validation.plate_format,
                        plate_confidence=ocr.confidence,
                        vehicle_class=vehicle.vehicle_class,
                        vehicle_confidence=vehicle.confidence,
                        vehicle_bbox=global_vehicle_bbox.as_dict(),
                        plate_bbox=global_plate_bbox.as_dict(),
                        frame_path=frame_path if frame_path else media_paths.get("frame"),
                        vehicle_crop_path=media_paths.get("vehicle"),
                        plate_crop_path=media_paths.get("plate"),
                        corrected_plate_path=media_paths.get("corrected_plate"),
                        frame_hash=frame_hash,
                        model_versions={
                            "vehicle": getattr(self.vehicle_detector, "model_version", "unknown"),
                            "plate": self.plate_detector.model_version,
                            "ocr": self.ocr_engine.model_version,
                        },
                        processing_time_ms=(time.perf_counter() - started) * 1000,
                        status=status,
                        review_reason=";".join(validation.warnings) if validation.warnings else None,
                    )
                    saved = self.observation_service.save_and_maybe_feed_session(observation, create_session=create_sessions)
                    observations.append(saved)
                    if status == "accepted":
                        self.metrics.accepted_observations += 1
                    elif status == "needs_review":
                        self.metrics.needs_review_observations += 1
        self.metrics.processed_frames += 1
        self.metrics.last_processing_time_ms = (time.perf_counter() - started) * 1000
        self.observation_service.repository.save_metrics(self.metrics.as_dict())
        return observations

    @property
    def edge_repository_station_code(self) -> str:
        # The repository owns geometry; station metadata comes from AppConfig in production wrappers.
        return getattr(self, "station_code", "STATION-001")

    @property
    def edge_repository_camera_id(self) -> str:
        return getattr(self, "camera_id", "CAM-001")

    def set_station_context(self, station_code: str, camera_id: str) -> None:
        self.station_code = station_code
        self.camera_id = camera_id

    def _configuration_warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.config.pilot_fixed_preset_id and not self.config.vehicle_detector_enabled:
            warnings.append("PILOT_FIXED_PRESET_ID is not configured; slot-based sessions will not be created")
        if self.config.vehicle_detector_enabled and not self.config.vehicle_detector_model_path:
            warnings.append("VEHICLE_DETECTOR_MODEL_PATH is not configured")
        return warnings + self.metrics.warnings[-10:]

    def _slot_contexts(self, frame_w: int, frame_h: int) -> list[SlotContext]:
        if not self.config.pilot_fixed_preset_id:
            return []
        slots = self.edge_repository.list_slots(preset_id=self.config.pilot_fixed_preset_id)
        zones = {zone["id"]: zone for zone in self.edge_repository.list_zones(preset_id=self.config.pilot_fixed_preset_id)}
        contexts: list[SlotContext] = []
        for slot in slots:
            if not slot.get("enabled", True):
                continue
            zone = zones.get(slot["zone_id"])
            if zone is None:
                continue
            contexts.append(
                SlotContext(
                    preset_id=slot["preset_id"],
                    zone_id=slot["zone_id"],
                    slot_id=slot["id"],
                    slot_code=slot["slot_code"],
                    zone_type=zone.get("zone_type", "paid_parking"),
                    polygon_points=[
                        {"x": point["x"] * frame_w, "y": point["y"] * frame_h} for point in slot["polygon_points"]
                    ],
                    overlap_group=slot.get("overlap_group"),
                )
            )
        return contexts

    def _crop_slot(self, frame: np.ndarray, slot: SlotContext) -> tuple[np.ndarray, tuple[int, int]]:
        points = np.array([[point["x"], point["y"]] for point in slot.polygon_points], dtype=np.int32)
        h, w = frame.shape[:2]
        x, y, bw, bh = cv2.boundingRect(points)
        bbox = BoundingBox(x, y, bw, bh).clipped(w, h)
        crop = crop_bbox(frame, bbox)
        return crop, (bbox.x, bbox.y)

    def _global_bbox(self, bbox: BoundingBox, offset: tuple[int, int]) -> BoundingBox:
        return BoundingBox(bbox.x + offset[0], bbox.y + offset[1], bbox.width, bbox.height)

    def _status_for(self, ocr_confidence: float, validation_status: str) -> str:
        if ocr_confidence < self.config.ocr_min_confidence:
            return ALPRStatus.REJECTED.value
        if validation_status != "accepted":
            return ALPRStatus.NEEDS_REVIEW.value
        return ALPRStatus.ACCEPTED.value

    def _save_media(
        self,
        observed_at: datetime,
        frame: np.ndarray,
        vehicle_crop: np.ndarray,
        plate_crop: np.ndarray,
        corrected_plate: np.ndarray,
        canonical: str,
        status: str,
    ) -> dict[str, str]:
        if status == "rejected" and not self.config.save_rejected_candidates:
            return {}
        date_dir = observed_at.strftime("%Y%m%d")
        output_dir = self.media_dir / "alpr" / date_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = observed_at.strftime("%H%M%S%f")
        prefix = f"{stamp}_{canonical}"
        paths: dict[str, str] = {}
        if self.config.save_full_frame:
            paths["frame"] = self._write_image(output_dir / f"{prefix}_frame.jpg", frame)
        if self.config.save_vehicle_crop:
            paths["vehicle"] = self._write_image(output_dir / f"{prefix}_vehicle.jpg", vehicle_crop)
        if self.config.save_plate_crop:
            paths["plate"] = self._write_image(output_dir / f"{prefix}_plate_raw.jpg", plate_crop)
            paths["corrected_plate"] = self._write_image(output_dir / f"{prefix}_plate_corrected.jpg", corrected_plate)
        return paths

    def _write_image(self, path: Path, image: np.ndarray) -> str:
        ok = cv2.imwrite(str(path), image)
        if not ok:
            raise OSError(f"Could not save ALPR media: {path.name}")
        try:
            return str(path.relative_to(self.media_dir.parent))
        except ValueError:
            return path.name


def build_pipeline(config, edge_repository: EdgeRepository, session_engine: ParkingSessionEngine) -> ALPRPipeline:
    from app.alpr.config import alpr_config_from_app

    observation_service = ALPRObservationService(config.edge_database_path, session_engine)
    pipeline = ALPRPipeline(alpr_config_from_app(config), edge_repository, observation_service, config.snapshot_dir)
    pipeline.set_station_context(config.station_code, config.camera_id)
    return pipeline
