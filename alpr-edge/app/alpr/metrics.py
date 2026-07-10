from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ALPRMetrics:
    processed_frames: int = 0
    accepted_observations: int = 0
    needs_review_observations: int = 0
    rejected_candidates: int = 0
    last_processing_time_ms: float | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "processed_frames": self.processed_frames,
            "accepted_observations": self.accepted_observations,
            "needs_review_observations": self.needs_review_observations,
            "rejected_candidates": self.rejected_candidates,
            "last_processing_time_ms": self.last_processing_time_ms,
            "warnings": self.warnings[-20:],
        }
