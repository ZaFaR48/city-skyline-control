from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import cv2
from cv2.typing import MatLike

from app.config import AppConfig

logger = logging.getLogger(__name__)


def redact_url(value: str) -> str:
    if not value:
        return ""
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        if parts.username or parts.password:
            netloc = f"***:***@{host}"
        else:
            netloc = host
        return urlunsplit((parts.scheme, netloc, "/...", "", ""))
    except Exception:
        return "rtsp://***"


def safe_camera_error(exc: Exception | str) -> str:
    message = str(exc).lower()
    if "auth" in message or "401" in message or "unauthorized" in message:
        return "authentication failure"
    if "timed out" in message or "timeout" in message:
        return "timeout while reading camera stream"
    if "unreachable" in message or "network" in message or "resolve" in message:
        return "camera host unreachable"
    if "frame" in message:
        return "invalid frame"
    if "write" in message or "disk" in message:
        return "snapshot disk write failure"
    if "open" in message or "stream" in message:
        return "stream unavailable"
    return "camera connection failed"


@dataclass(frozen=True)
class SnapshotMetadata:
    snapshot_path: str
    snapshot_url: str
    frame_width: int
    frame_height: int
    captured_at: str
    capture_latency_ms: float
    file_size_bytes: int
    disk_free_bytes: int


class CameraAdapter(Protocol):
    def open(self) -> None:
        ...

    def read(self) -> MatLike:
        ...

    def close(self) -> None:
        ...

    def is_open(self) -> bool:
        ...


class OpenCVRTSPAdapter:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        if not self.config.rtsp_url:
            raise ValueError("RTSP_URL is required")

        previous_options = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
        options = [f"rtsp_transport;{self.config.rtsp_transport or 'tcp'}"]
        if self.config.rtsp_low_latency:
            options.extend(["fflags;nobuffer", "flags;low_delay"])
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "|".join(options)
        try:
            self.capture = cv2.VideoCapture(self.config.rtsp_url, cv2.CAP_FFMPEG)
        finally:
            if previous_options is None:
                os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
            else:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = previous_options

        if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
            self.capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.config.rtsp_connect_timeout_seconds * 1000)
        if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
            self.capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.config.rtsp_read_timeout_seconds * 1000)
        if not self.capture.isOpened():
            raise ConnectionError("Unable to open RTSP stream")

    def read(self) -> MatLike:
        if self.capture is None or not self.capture.isOpened():
            self.open()
        assert self.capture is not None
        started = time.monotonic()
        ok, frame = self.capture.read()
        elapsed = time.monotonic() - started
        if elapsed > self.config.rtsp_read_timeout_seconds:
            raise TimeoutError("RTSP read timeout")
        if not ok or frame is None or getattr(frame, "size", 0) == 0:
            raise ValueError("Invalid frame decoded from RTSP stream")
        return frame

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def is_open(self) -> bool:
        return self.capture is not None and self.capture.isOpened()


class CameraService:
    def __init__(self, config: AppConfig, adapter: CameraAdapter | None = None) -> None:
        self.config = config
        self.adapter = adapter or OpenCVRTSPAdapter(config)
        self.connected = False
        self.last_frame_at: str | None = None
        self.frame_width: int | None = None
        self.frame_height: int | None = None
        self.measured_fps: float | None = None
        self.failure_count = 0
        self.last_error: str | None = None
        self._last_frame_monotonic: float | None = None
        self._next_reconnect_delay = config.rtsp_reconnect_delay_seconds

    @property
    def configured(self) -> bool:
        return bool(self.config.rtsp_url)

    def status(self) -> dict:
        self.config.snapshot_dir.mkdir(parents=True, exist_ok=True)
        disk = shutil.disk_usage(self.config.snapshot_dir.parent if self.config.snapshot_dir.parent else Path("."))
        return {
            "configured": self.configured,
            "connected": self.connected,
            "camera_name": self.config.camera_name,
            "camera_vendor": self.config.camera_vendor or "generic",
            "camera_local_ip": self.config.camera_local_ip,
            "rtsp_url_redacted": redact_url(self.config.rtsp_url),
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "measured_fps": self.measured_fps,
            "last_frame_at": self.last_frame_at,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "ptz_dry_run": self.config.ptz_dry_run,
            "disk_free_bytes": disk.free,
        }

    def test_connection(self) -> dict:
        started = time.monotonic()
        try:
            frame = self._read_frame_with_reconnect()
            latency_ms = (time.monotonic() - started) * 1000
            return self.status() | {
                "decoded_frame": True,
                "capture_latency_ms": round(latency_ms, 2),
            }
        except Exception as exc:
            self._mark_failure(exc)
            return self.status() | {
                "decoded_frame": False,
                "capture_latency_ms": None,
            }
        finally:
            self.close()

    def reconnect(self) -> dict:
        self.close()
        self.connected = False
        self.last_error = None
        self._next_reconnect_delay = self.config.rtsp_reconnect_delay_seconds
        return self.test_connection()

    def capture_snapshot(self, snapshot_dir: Path | None = None) -> SnapshotMetadata:
        started = time.monotonic()
        try:
            frame = self._read_frame_with_reconnect()
            output_dir = snapshot_dir or self.config.snapshot_dir
            metadata = self.save_snapshot_frame(frame, output_dir, started)
            self.last_error = None
            return metadata
        except Exception as exc:
            self._mark_failure(exc)
            raise RuntimeError(self.last_error or "camera snapshot failed") from exc
        finally:
            self.close()

    def save_snapshot_frame(self, frame: MatLike, output_dir: Path, started: float | None = None) -> SnapshotMetadata:
        output_dir.mkdir(parents=True, exist_ok=True)
        captured_at = datetime.now(timezone.utc).isoformat()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = output_dir / f"{self.config.camera_id}_{timestamp}_{uuid4().hex[:8]}.jpg"
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(self.config.snapshot_jpeg_quality)]
        ok = cv2.imwrite(str(path), frame, params)
        if not ok:
            raise OSError("Snapshot disk write failure")
        height, width = frame.shape[:2]
        disk = shutil.disk_usage(output_dir)
        latency_ms = ((time.monotonic() - started) * 1000) if started is not None else 0.0
        return SnapshotMetadata(
            snapshot_path=str(path),
            snapshot_url=f"/snapshots/{path.name}",
            frame_width=int(width),
            frame_height=int(height),
            captured_at=captured_at,
            capture_latency_ms=round(latency_ms, 2),
            file_size_bytes=path.stat().st_size,
            disk_free_bytes=disk.free,
        )

    def _read_frame_with_reconnect(self) -> MatLike:
        if not self.configured:
            raise ValueError("RTSP_URL is required")
        try:
            frame = self.adapter.read()
            self._mark_success(frame)
            return frame
        except Exception:
            self.close()
            delay = min(self._next_reconnect_delay, self.config.rtsp_max_reconnect_delay_seconds)
            self._next_reconnect_delay = min(delay * 2, self.config.rtsp_max_reconnect_delay_seconds)
            if delay > 0:
                time.sleep(min(delay, 1.0))
            frame = self.adapter.read()
            self._mark_success(frame)
            return frame

    def _mark_success(self, frame: MatLike) -> None:
        now = time.monotonic()
        if self._last_frame_monotonic is not None:
            delta = now - self._last_frame_monotonic
            if delta > 0:
                self.measured_fps = round(1.0 / delta, 2)
        self._last_frame_monotonic = now
        height, width = frame.shape[:2]
        self.frame_width = int(width)
        self.frame_height = int(height)
        self.last_frame_at = datetime.now(timezone.utc).isoformat()
        self.failure_count = 0
        self.last_error = None
        self.connected = True
        self._next_reconnect_delay = self.config.rtsp_reconnect_delay_seconds

    def _mark_failure(self, exc: Exception | str) -> None:
        self.failure_count += 1
        self.connected = False
        self.last_error = safe_camera_error(exc)
        logger.warning("Camera operation failed: %s", self.last_error)

    def close(self) -> None:
        self.adapter.close()
