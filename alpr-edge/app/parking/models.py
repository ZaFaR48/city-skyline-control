from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE_FREE = "active_free"
    ACTIVE_BILLABLE = "active_billable"
    PAID = "paid"
    UNPAID = "unpaid"
    EXIT_PENDING = "exit_pending"
    CLOSED = "closed"
    VIOLATION_CANDIDATE = "violation_candidate"
    NEEDS_REVIEW = "needs_review"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    UNKNOWN = "unknown"
    NOT_INTEGRATED = "not_integrated"
    PAID = "paid"
    UNPAID = "unpaid"


@dataclass(frozen=True)
class ParkingObservation:
    station_code: str
    camera_id: str
    preset_id: str
    zone_id: str
    slot_id: str
    slot_code: str
    plate_text: str
    plate_confidence: float
    observed_at: datetime
    frame_path: str | None = None
    plate_crop_path: str | None = None
    model_version: str | None = None
    zone_type: str = "paid_parking"


@dataclass(frozen=True)
class SessionUpdate:
    session: dict
    confirmed: bool
    created: bool
