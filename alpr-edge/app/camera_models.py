from __future__ import annotations

from pydantic import BaseModel


class CameraStatusResponse(BaseModel):
    configured: bool
    connected: bool
    camera_name: str
    camera_vendor: str
    camera_local_ip: str | None
    rtsp_url_redacted: str
    frame_width: int | None
    frame_height: int | None
    measured_fps: float | None
    last_frame_at: str | None
    failure_count: int
    last_error: str | None
    ptz_dry_run: bool
    disk_free_bytes: int


class CameraTestResponse(CameraStatusResponse):
    decoded_frame: bool
    capture_latency_ms: float | None


class SnapshotResponse(BaseModel):
    snapshot_path: str
    snapshot_url: str
    frame_width: int
    frame_height: int
    captured_at: str
    capture_latency_ms: float
    file_size_bytes: int
    disk_free_bytes: int
