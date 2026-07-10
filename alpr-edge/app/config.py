from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser()


def _optional_int(value: str | None) -> int | None:
    if not value:
        return None
    return int(value)


def _csv_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class AppConfig:
    rtsp_url: str
    rtsp_transport: str
    rtsp_connect_timeout_seconds: float
    rtsp_read_timeout_seconds: float
    rtsp_reconnect_delay_seconds: float
    rtsp_max_reconnect_delay_seconds: float
    rtsp_low_latency: bool
    camera_id: str
    camera_name: str
    camera_vendor: str
    camera_local_ip: str | None
    station_code: str
    snapshot_jpeg_quality: int
    preview_refresh_seconds: float
    onvif_host: str | None
    onvif_port: int
    onvif_username: str | None
    onvif_password: str | None
    sample_interval_seconds: float
    frame_output_dir: Path
    queue_dir: Path
    central_api_url: str | None
    central_api_token: str | None
    upload_timeout_seconds: float
    retry_interval_seconds: float
    detector_model_path: Path | None
    ocr_model_path: Path | None
    direction: str
    zone_type: str
    log_level: str
    ptz_dry_run: bool
    edge_api_host: str
    edge_api_port: int
    edge_database_path: Path
    snapshot_dir: Path
    parking_timezone: str
    parking_start_time: str
    parking_end_time: str
    parking_free_minutes: int
    parking_rate_tjs_per_hour: float
    parking_rounding_mode: str
    session_confirmation_observations: int
    session_confirmation_window_seconds: int
    session_exit_misses: int
    session_exit_timeout_seconds: int
    ptz_auto_patrol: bool
    ptz_patrol_require_approval: bool
    ptz_patrol_approved: bool
    vehicle_detector_enabled: bool
    vehicle_detector_model_path: Path | None
    vehicle_detector_confidence: float
    vehicle_detector_input_size: int | None
    vehicle_classes: list[str]
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
    alpr_save_full_frame: bool
    alpr_save_vehicle_crop: bool
    alpr_save_plate_crop: bool
    alpr_save_rejected_candidates: bool
    alpr_media_retention_days: int
    alpr_review_media_retention_days: int
    dataset_collection_enabled: bool
    dataset_collection_require_review: bool
    model_pack_dir: Path
    model_manifest_path: Path | None

    @property
    def model_configured(self) -> bool:
        return self.detector_model_path is not None and self.ocr_model_path is not None


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> AppConfig:
    load_dotenv()

    return AppConfig(
        rtsp_url=os.getenv("RTSP_URL", "").strip(),
        rtsp_transport=os.getenv("RTSP_TRANSPORT", "tcp").strip().lower(),
        rtsp_connect_timeout_seconds=float(os.getenv("RTSP_CONNECT_TIMEOUT_SECONDS", "10")),
        rtsp_read_timeout_seconds=float(os.getenv("RTSP_READ_TIMEOUT_SECONDS", "10")),
        rtsp_reconnect_delay_seconds=float(os.getenv("RTSP_RECONNECT_DELAY_SECONDS", "3")),
        rtsp_max_reconnect_delay_seconds=float(os.getenv("RTSP_MAX_RECONNECT_DELAY_SECONDS", "30")),
        rtsp_low_latency=_bool_env("RTSP_LOW_LATENCY", True),
        camera_id=os.getenv("CAMERA_ID", "CAM-001").strip(),
        camera_name=os.getenv("CAMERA_NAME", "").strip(),
        camera_vendor=os.getenv("CAMERA_VENDOR", "generic").strip(),
        camera_local_ip=os.getenv("CAMERA_LOCAL_IP") or None,
        station_code=os.getenv("STATION_CODE", "STATION-001").strip(),
        snapshot_jpeg_quality=int(os.getenv("SNAPSHOT_JPEG_QUALITY", "90")),
        preview_refresh_seconds=float(os.getenv("PREVIEW_REFRESH_SECONDS", "2")),
        onvif_host=os.getenv("ONVIF_HOST") or None,
        onvif_port=int(os.getenv("ONVIF_PORT", "80")),
        onvif_username=os.getenv("ONVIF_USERNAME") or None,
        onvif_password=os.getenv("ONVIF_PASSWORD") or None,
        sample_interval_seconds=float(os.getenv("SAMPLE_INTERVAL_SECONDS", "5")),
        frame_output_dir=Path(os.getenv("FRAME_OUTPUT_DIR", "data/frames")),
        queue_dir=Path(os.getenv("QUEUE_DIR", "data/queue")),
        central_api_url=os.getenv("CENTRAL_API_URL") or None,
        central_api_token=os.getenv("CENTRAL_API_TOKEN") or None,
        upload_timeout_seconds=float(os.getenv("UPLOAD_TIMEOUT_SECONDS", "5")),
        retry_interval_seconds=float(os.getenv("RETRY_INTERVAL_SECONDS", "30")),
        detector_model_path=_optional_path(os.getenv("PLATE_DETECTOR_MODEL_PATH")),
        ocr_model_path=_optional_path(os.getenv("PLATE_OCR_MODEL_PATH")),
        direction=os.getenv("DIRECTION", "unknown").strip(),
        zone_type=os.getenv("ZONE_TYPE", "paid_parking").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        ptz_dry_run=_bool_env("PTZ_DRY_RUN", True),
        edge_api_host=os.getenv("EDGE_API_HOST", "127.0.0.1").strip(),
        edge_api_port=int(os.getenv("EDGE_API_PORT", "18080")),
        edge_database_path=Path(os.getenv("EDGE_DATABASE_PATH", "data/sqlite/edge_config.db")),
        snapshot_dir=Path(os.getenv("SNAPSHOT_DIR", "data/snapshots")),
        parking_timezone=os.getenv("PARKING_TIMEZONE", "Asia/Dushanbe").strip(),
        parking_start_time=os.getenv("PARKING_START_TIME", "07:00").strip(),
        parking_end_time=os.getenv("PARKING_END_TIME", "22:00").strip(),
        parking_free_minutes=int(os.getenv("PARKING_FREE_MINUTES", "10")),
        parking_rate_tjs_per_hour=float(os.getenv("PARKING_RATE_TJS_PER_HOUR", "3.00")),
        parking_rounding_mode=os.getenv("PARKING_ROUNDING_MODE", "exact_minute").strip(),
        session_confirmation_observations=int(os.getenv("SESSION_CONFIRMATION_OBSERVATIONS", "2")),
        session_confirmation_window_seconds=int(os.getenv("SESSION_CONFIRMATION_WINDOW_SECONDS", "120")),
        session_exit_misses=int(os.getenv("SESSION_EXIT_MISSES", "2")),
        session_exit_timeout_seconds=int(os.getenv("SESSION_EXIT_TIMEOUT_SECONDS", "180")),
        ptz_auto_patrol=_bool_env("PTZ_AUTO_PATROL", False),
        ptz_patrol_require_approval=_bool_env("PTZ_PATROL_REQUIRE_APPROVAL", True),
        ptz_patrol_approved=_bool_env("PTZ_PATROL_APPROVED", False),
        vehicle_detector_enabled=_bool_env("VEHICLE_DETECTOR_ENABLED", True),
        vehicle_detector_model_path=_optional_path(os.getenv("VEHICLE_DETECTOR_MODEL_PATH")),
        vehicle_detector_confidence=float(os.getenv("VEHICLE_DETECTOR_CONFIDENCE", "0.40")),
        vehicle_detector_input_size=_optional_int(os.getenv("VEHICLE_DETECTOR_INPUT_SIZE")),
        vehicle_classes=_csv_env("VEHICLE_CLASSES", "car,bus,truck,motorcycle"),
        plate_detector_backend=os.getenv("PLATE_DETECTOR_BACKEND", "hybrid").strip(),
        plate_detector_model_path=_optional_path(os.getenv("PLATE_DETECTOR_MODEL_PATH")),
        plate_detector_confidence=float(os.getenv("PLATE_DETECTOR_CONFIDENCE", "0.35")),
        plate_min_aspect_ratio=float(os.getenv("PLATE_MIN_ASPECT_RATIO", "1.5")),
        plate_max_aspect_ratio=float(os.getenv("PLATE_MAX_ASPECT_RATIO", "7.5")),
        plate_min_width_pixels=int(os.getenv("PLATE_MIN_WIDTH_PIXELS", "50")),
        plate_max_candidates_per_vehicle=int(os.getenv("PLATE_MAX_CANDIDATES_PER_VEHICLE", "5")),
        ocr_backend=os.getenv("OCR_BACKEND", "rapidocr").strip(),
        ocr_min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.45")),
        ocr_max_variants=int(os.getenv("OCR_MAX_VARIANTS", "5")),
        ocr_allowed_characters=os.getenv("OCR_ALLOWED_CHARACTERS", "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ").strip(),
        ocr_model_dir=Path(os.getenv("OCR_MODEL_DIR", "/var/lib/city-skyline-edge/models/ocr")),
        alpr_dedup_window_seconds=int(os.getenv("ALPR_DEDUP_WINDOW_SECONDS", "30")),
        alpr_same_plate_max_distance=int(os.getenv("ALPR_SAME_PLATE_MAX_DISTANCE", "1")),
        alpr_reprocess_interval_seconds=int(os.getenv("ALPR_REPROCESS_INTERVAL_SECONDS", "10")),
        pilot_fixed_preset_id=os.getenv("PILOT_FIXED_PRESET_ID") or None,
        alpr_save_full_frame=_bool_env("ALPR_SAVE_FULL_FRAME", False),
        alpr_save_vehicle_crop=_bool_env("ALPR_SAVE_VEHICLE_CROP", True),
        alpr_save_plate_crop=_bool_env("ALPR_SAVE_PLATE_CROP", True),
        alpr_save_rejected_candidates=_bool_env("ALPR_SAVE_REJECTED_CANDIDATES", False),
        alpr_media_retention_days=int(os.getenv("ALPR_MEDIA_RETENTION_DAYS", "30")),
        alpr_review_media_retention_days=int(os.getenv("ALPR_REVIEW_MEDIA_RETENTION_DAYS", "90")),
        dataset_collection_enabled=_bool_env("DATASET_COLLECTION_ENABLED", True),
        dataset_collection_require_review=_bool_env("DATASET_COLLECTION_REQUIRE_REVIEW", True),
        model_pack_dir=Path(os.getenv("MODEL_PACK_DIR", "/var/lib/city-skyline-edge/models")),
        model_manifest_path=_optional_path(os.getenv("MODEL_MANIFEST_PATH", "/var/lib/city-skyline-edge/models/manifest.json")),
    )
