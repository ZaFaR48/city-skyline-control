from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import cv2
from cv2.typing import MatLike

logger = logging.getLogger(__name__)


class RTSPCamera:
    def __init__(self, rtsp_url: str) -> None:
        self._rtsp_url = rtsp_url
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        if not self._rtsp_url:
            raise ValueError("RTSP_URL is required")

        self._capture = cv2.VideoCapture(self._rtsp_url)
        if not self._capture.isOpened():
            raise ConnectionError("Unable to open RTSP camera stream")
        logger.info("Connected to RTSP camera")

    def read_frame(self) -> MatLike | None:
        if self._capture is None:
            self.open()

        assert self._capture is not None
        ok, frame = self._capture.read()
        if not ok:
            logger.warning("Failed to read frame from RTSP stream")
            return None
        return frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            logger.info("RTSP camera connection closed")


def save_frame(frame: MatLike, output_dir: Path, station_code: str, camera_id: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    filename = f"{station_code}_{camera_id}_{timestamp}.jpg"
    path = output_dir / filename

    ok = cv2.imwrite(str(path), frame)
    if not ok:
        raise OSError(f"Failed to save frame to {path}")
    return path
