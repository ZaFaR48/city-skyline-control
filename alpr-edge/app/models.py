from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class EventStatus(str, Enum):
    DETECTED = "detected"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class PlateDetection:
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass(frozen=True)
class OCRResult:
    plate_text: str
    confidence: float


@dataclass(frozen=True)
class PlateEvent:
    station_code: str
    camera_id: str
    timestamp: datetime
    plate_text: str | None
    confidence: float | None
    image_path: Path
    direction: str
    zone_type: str
    status: EventStatus

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.astimezone(timezone.utc).isoformat()
        data["image_path"] = str(self.image_path)
        data["status"] = self.status.value
        return data
