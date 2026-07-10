from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np


class ALPRStatus(str, Enum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    def clipped(self, frame_width: int, frame_height: int) -> "BoundingBox":
        x1 = max(0, min(self.x, frame_width - 1))
        y1 = max(0, min(self.y, frame_height - 1))
        x2 = max(x1 + 1, min(self.x2, frame_width))
        y2 = max(y1 + 1, min(self.y2, frame_height))
        return BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1)

    def as_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class VehicleDetection:
    bbox: BoundingBox
    vehicle_class: str
    confidence: float
    source_frame_size: tuple[int, int]
    inference_time_ms: float


@dataclass(frozen=True)
class PlateCandidate:
    bbox: BoundingBox
    confidence: float
    angle: float
    crop: np.ndarray
    corrected_crop: np.ndarray
    source: str
    diagnostics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class OCRText:
    text: str
    confidence: float
    boxes: list[Any]
    inference_time_ms: float
    variant: str


@dataclass(frozen=True)
class NormalizedPlate:
    raw_text: str
    canonical_text: str
    display_text: str
    normalization_changes: list[str]
    normalization_score: float


@dataclass(frozen=True)
class PlateValidation:
    canonical_text: str
    plate_format: str
    status: str
    region_code: str | None
    warnings: list[str]


@dataclass(frozen=True)
class SlotContext:
    preset_id: str
    zone_id: str
    slot_id: str
    slot_code: str
    zone_type: str
    polygon_points: list[dict[str, float]]
    overlap_group: str | None = None


@dataclass(frozen=True)
class ALPRObservation:
    observation_id: str
    station_code: str
    camera_id: str
    preset_id: str
    zone_id: str
    slot_id: str
    slot_code: str
    observed_at: datetime
    plate_raw: str
    plate_canonical: str
    plate_display: str
    plate_format: str
    plate_confidence: float
    vehicle_class: str | None
    vehicle_confidence: float | None
    vehicle_bbox: dict[str, int] | None
    plate_bbox: dict[str, int] | None
    frame_path: str | None
    vehicle_crop_path: str | None
    plate_crop_path: str | None
    corrected_plate_path: str | None
    frame_hash: str
    model_versions: dict[str, str]
    processing_time_ms: float
    status: str
    review_reason: str | None = None
