from __future__ import annotations

from enum import Enum


class ViolationStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    CONFIRMED_INTERNAL = "confirmed_internal"
    REJECTED = "rejected"
