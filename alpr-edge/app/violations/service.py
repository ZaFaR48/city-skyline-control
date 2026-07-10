from __future__ import annotations

from app.parking.evidence import evidence_hash
from app.parking.repositories import ParkingRepository, ViolationRepository


class ViolationService:
    def __init__(self, parking_repository: ParkingRepository, violation_repository: ViolationRepository) -> None:
        self.parking_repository = parking_repository
        self.violation_repository = violation_repository

    def list_candidates(self) -> list[dict]:
        return self.violation_repository.list_candidates()

    def get_candidate(self, violation_id: str) -> dict | None:
        return self.violation_repository.get_candidate(violation_id)

    def create_candidate_for_unpaid_session(self, session_id: str, reason: str = "payment confirmed unpaid") -> dict:
        session = self.parking_repository.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        if session["payment_status"] != "unpaid":
            raise ValueError("Violation candidate requires explicit unpaid confirmation")
        paths = [path for path in [session["first_frame_path"], session["latest_frame_path"], session["plate_crop_path"]] if path]
        candidate = self.violation_repository.create_candidate(
            {
                "session_id": session["session_id"],
                "station_code": session["station_code"],
                "plate_text": session["plate_text"],
                "slot_code": session["slot_code"],
                "zone_type": session["zone_type"],
                "first_seen_at": session["first_seen_at"],
                "last_seen_at": session["last_seen_at"],
                "unpaid_amount_tjs": session["amount_tjs"],
                "evidence_frame_paths": paths,
                "evidence_hashes": [evidence_hash(path) for path in paths],
                "reason": reason,
            }
        )
        self.parking_repository.update_session(session_id, {"session_status": "violation_candidate"})
        return candidate

    def confirm(self, violation_id: str, moderator_id: str | None = None, note: str | None = None) -> dict | None:
        return self.violation_repository.moderate(violation_id, "confirmed_internal", moderator_id, note)

    def reject(self, violation_id: str, moderator_id: str | None = None, note: str | None = None) -> dict | None:
        return self.violation_repository.moderate(violation_id, "rejected", moderator_id, note)
