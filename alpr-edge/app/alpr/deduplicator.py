from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.alpr.models import BoundingBox
from app.parking.validators import ensure_utc


@dataclass
class DedupEntry:
    canonical_plate: str
    slot_id: str
    preset_id: str
    frame_hash: str
    bbox: BoundingBox | None
    seen_at: datetime


class TemporalDeduplicator:
    def __init__(self, window_seconds: int, reprocess_interval_seconds: int) -> None:
        self.window = timedelta(seconds=window_seconds)
        self.reprocess_interval = timedelta(seconds=reprocess_interval_seconds)
        self.entries: list[DedupEntry] = []

    def should_skip(
        self,
        canonical_plate: str,
        slot_id: str,
        preset_id: str,
        frame_hash: str,
        bbox: BoundingBox | None,
        seen_at: datetime,
    ) -> bool:
        seen_at = ensure_utc(seen_at)
        self.entries = [entry for entry in self.entries if seen_at - entry.seen_at <= self.window]
        for entry in self.entries:
            if entry.canonical_plate != canonical_plate or entry.slot_id != slot_id or entry.preset_id != preset_id:
                continue
            if entry.frame_hash == frame_hash or seen_at - entry.seen_at < self.reprocess_interval:
                return True
        self.entries.append(DedupEntry(canonical_plate, slot_id, preset_id, frame_hash, bbox, seen_at))
        return False
