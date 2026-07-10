from __future__ import annotations

import logging
from pathlib import Path

from cv2.typing import MatLike

from app.models import PlateDetection

logger = logging.getLogger(__name__)


class PlateDetector:
    """Interface for a future real license plate detector."""

    def __init__(self, model_path: Path | None) -> None:
        self.model_path = model_path
        self.is_configured = model_path is not None
        if self.is_configured:
            logger.warning("Detector model path configured, but loader is not implemented yet")

    def detect(self, frame: MatLike) -> list[PlateDetection]:
        del frame
        if not self.is_configured:
            return []
        logger.warning("Detector adapter is not implemented; no plate candidates returned")
        return []
