from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.camera_service import CameraService, redact_url
from app.config import AppConfig
from app.ptz.models import PTZPresetPatch
from app.zones.models import PolygonZoneCreate
from app.database.repositories import EdgeRepository
from app.ptz.models import PTZPresetCreate


class MockAdapter:
    def __init__(self, frame=None, fail: Exception | None = None) -> None:
        self.frame = frame
        self.fail = fail
        self.closed = False

    def open(self) -> None:
        if self.fail:
            raise self.fail

    def read(self):
        if self.fail:
            raise self.fail
        return self.frame

    def close(self) -> None:
        self.closed = True

    def is_open(self) -> bool:
        return not self.closed


def make_config(tmp_path: Path, rtsp_url: str = "rtsp://USERNAME:PASSWORD@192.0.2.10:8554/stream") -> AppConfig:
    return AppConfig(
        rtsp_url=rtsp_url,
        rtsp_transport="tcp",
        rtsp_connect_timeout_seconds=0.01,
        rtsp_read_timeout_seconds=0.01,
        rtsp_reconnect_delay_seconds=0,
        rtsp_max_reconnect_delay_seconds=0,
        rtsp_low_latency=True,
        camera_id="CAM-001",
        camera_name="Parking PTZ",
        camera_vendor="generic",
        camera_local_ip="192.0.2.10",
        station_code="STATION-001",
        snapshot_jpeg_quality=90,
        preview_refresh_seconds=2,
        onvif_host=None,
        onvif_port=80,
        onvif_username=None,
        onvif_password=None,
        sample_interval_seconds=5,
        frame_output_dir=tmp_path / "frames",
        queue_dir=tmp_path / "queue",
        central_api_url=None,
        central_api_token=None,
        upload_timeout_seconds=5,
        retry_interval_seconds=30,
        detector_model_path=None,
        ocr_model_path=None,
        direction="unknown",
        zone_type="paid_parking",
        log_level="INFO",
        ptz_dry_run=True,
        edge_api_host="127.0.0.1",
        edge_api_port=18080,
        edge_database_path=tmp_path / "edge.db",
        snapshot_dir=tmp_path / "snapshots",
        parking_timezone="Asia/Dushanbe",
        parking_start_time="07:00",
        parking_end_time="22:00",
        parking_free_minutes=10,
        parking_rate_tjs_per_hour=3.0,
        parking_rounding_mode="exact_minute",
        session_confirmation_observations=2,
        session_confirmation_window_seconds=120,
        session_exit_misses=2,
        session_exit_timeout_seconds=180,
        ptz_auto_patrol=False,
        ptz_patrol_require_approval=True,
        ptz_patrol_approved=False,
        model_pack_dir=tmp_path / "models",
        model_manifest_path=tmp_path / "models" / "manifest.json",
        vehicle_detector_enabled=False,
        vehicle_detector_model_path=None,
        vehicle_detector_confidence=0.4,
        vehicle_detector_input_size=None,
        vehicle_classes=["car", "bus", "truck", "motorcycle"],
        plate_detector_backend="hybrid",
        plate_detector_model_path=None,
        plate_detector_confidence=0.35,
        plate_min_aspect_ratio=1.5,
        plate_max_aspect_ratio=7.5,
        plate_min_width_pixels=50,
        plate_max_candidates_per_vehicle=5,
        ocr_backend="rapidocr",
        ocr_min_confidence=0.45,
        ocr_max_variants=5,
        ocr_allowed_characters="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        ocr_model_dir=tmp_path / "models" / "ocr",
        alpr_dedup_window_seconds=30,
        alpr_same_plate_max_distance=1,
        alpr_reprocess_interval_seconds=10,
        pilot_fixed_preset_id=None,
        alpr_save_full_frame=False,
        alpr_save_vehicle_crop=True,
        alpr_save_plate_crop=True,
        alpr_save_rejected_candidates=False,
        alpr_media_retention_days=30,
        alpr_review_media_retention_days=90,
        dataset_collection_enabled=True,
        dataset_collection_require_review=True,
    )


def test_rtsp_url_redaction() -> None:
    assert redact_url("rtsp://USERNAME:PASSWORD@192.0.2.10:8554/live?token=TOKEN") == "rtsp://***:***@192.0.2.10:8554/..."


def test_mocked_successful_frame_capture(tmp_path: Path) -> None:
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    service = CameraService(make_config(tmp_path), MockAdapter(frame=frame))

    result = service.test_connection()

    assert result["decoded_frame"] is True
    assert result["connected"] is True
    assert result["frame_width"] == 160
    assert result["frame_height"] == 120


def test_mocked_connection_failure(tmp_path: Path) -> None:
    service = CameraService(make_config(tmp_path), MockAdapter(fail=ConnectionError("Unable to open RTSP stream")))

    result = service.test_connection()

    assert result["decoded_frame"] is False
    assert result["connected"] is False
    assert result["failure_count"] == 1
    assert result["last_error"] == "stream unavailable"


def test_snapshot_file_creation(tmp_path: Path) -> None:
    frame = np.full((64, 96, 3), 255, dtype=np.uint8)
    service = CameraService(make_config(tmp_path), MockAdapter(frame=frame))

    metadata = service.capture_snapshot()

    assert Path(metadata.snapshot_path).exists()
    assert metadata.frame_width == 96
    assert metadata.frame_height == 64
    assert metadata.snapshot_url.startswith("/snapshots/")


def test_reconnect_state_handling(tmp_path: Path) -> None:
    frame = np.zeros((32, 48, 3), dtype=np.uint8)
    service = CameraService(make_config(tmp_path), MockAdapter(frame=frame))
    service.failure_count = 3
    service.last_error = "stream unavailable"

    result = service.reconnect()

    assert result["decoded_frame"] is True
    assert result["failure_count"] == 0
    assert result["last_error"] is None


def test_normalized_polygons_remain_valid_after_resolution_change(tmp_path: Path) -> None:
    repository = EdgeRepository(tmp_path / "edge.db")
    preset = repository.create_preset(PTZPresetCreate(name="Parking"))
    zone = repository.create_zone(
        PolygonZoneCreate(
            preset_id=preset["id"],
            code="P-ROW",
            name="Parking row",
            zone_type="paid_parking",
            polygon_points=[
                {"x": 0.1, "y": 0.1},
                {"x": 0.8, "y": 0.1},
                {"x": 0.8, "y": 0.6},
                {"x": 0.1, "y": 0.6},
            ],
        )
    )

    repository.update_preset(preset["id"], PTZPresetPatch(snapshot_width=3840, snapshot_height=2160))
    reloaded = repository.get_zone(zone["id"])

    assert reloaded is not None
    assert reloaded["polygon_points"][0] == {"x": 0.1, "y": 0.1}
