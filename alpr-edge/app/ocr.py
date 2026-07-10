from __future__ import annotations

import logging
from pathlib import Path

from cv2.typing import MatLike

from app.models import OCRResult

logger = logging.getLogger(__name__)


class PlateOCR:
    """Interface for a future Tajikistan license plate OCR adapter."""

    def __init__(self, model_path: Path | None) -> None:
        self.model_path = model_path
        self.is_configured = model_path is not None
        if self.is_configured:
            logger.warning("OCR model path configured, but loader is not implemented yet")

    def recognize(self, plate_image: MatLike) -> OCRResult | None:
        del plate_image
        if not self.is_configured:
            return None
        logger.warning("OCR adapter is not implemented; no plate text returned")
        return None
