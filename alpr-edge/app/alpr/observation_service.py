from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.alpr.models import ALPRObservation
from app.database.connection import connect
from app.database.migrations import run_migrations
from app.parking.models import ParkingObservation
from app.parking.repositories import ParkingRepository
from app.parking.session_engine import ParkingSessionEngine


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ALPRObservationRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        with connect(self.database_path) as connection:
            run_migrations(connection)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.database_path)

    def save_observation(self, observation: ALPRObservation) -> dict:
        record = {
            "created_at": utc_now(),
            "reviewed_at": None,
            "corrected_plate": None,
            **observation.__dict__,
            "observed_at": observation.observed_at.isoformat(),
            "vehicle_bbox": json.dumps(observation.vehicle_bbox, sort_keys=True),
            "plate_bbox": json.dumps(observation.plate_bbox, sort_keys=True),
            "model_versions": json.dumps(observation.model_versions, sort_keys=True),
        }
        columns = list(record)
        placeholders = ", ".join("?" for _ in columns)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO alpr_observations ({', '.join(columns)}) VALUES ({placeholders})",
                [record[column] for column in columns],
            )
            connection.commit()
        return self.get_observation(observation.observation_id) or record

    def list_observations(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM alpr_observations ORDER BY observed_at DESC").fetchall()
            return [self._decode(dict(row)) for row in rows]

    def list_review(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM alpr_observations WHERE status = 'needs_review' ORDER BY observed_at DESC"
            ).fetchall()
            return [self._decode(dict(row)) for row in rows]

    def get_observation(self, observation_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM alpr_observations WHERE observation_id = ?", (observation_id,)
            ).fetchone()
            return self._decode(dict(row)) if row else None

    def update_review(self, observation_id: str, status: str, corrected_plate: str | None = None) -> dict | None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE alpr_observations
                SET status = ?, corrected_plate = ?, reviewed_at = ?
                WHERE observation_id = ?
                """,
                (status, corrected_plate, utc_now(), observation_id),
            )
            connection.commit()
        return self.get_observation(observation_id)

    def save_metrics(self, metrics: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO alpr_metrics
                (metric_id, measured_at, processed_frames, accepted_observations, needs_review_observations,
                 rejected_candidates, processing_time_ms, warnings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    utc_now(),
                    metrics.get("processed_frames", 0),
                    metrics.get("accepted_observations", 0),
                    metrics.get("needs_review_observations", 0),
                    metrics.get("rejected_candidates", 0),
                    metrics.get("last_processing_time_ms"),
                    json.dumps(metrics.get("warnings", [])),
                ),
            )
            connection.commit()

    def latest_metrics(self) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM alpr_metrics ORDER BY measured_at DESC LIMIT 1").fetchone()
            return dict(row) if row else {}

    def _decode(self, record: dict) -> dict:
        for key in ["vehicle_bbox", "plate_bbox", "model_versions"]:
            if record.get(key):
                record[key] = json.loads(record[key])
        return record


class ALPRObservationService:
    def __init__(self, database_path: Path, session_engine: ParkingSessionEngine) -> None:
        self.repository = ALPRObservationRepository(database_path)
        self.session_engine = session_engine

    def save_and_maybe_feed_session(self, observation: ALPRObservation, create_session: bool = True) -> dict:
        saved = self.repository.save_observation(observation)
        if create_session and observation.status == "accepted":
            parking_observation = ParkingObservation(
                station_code=observation.station_code,
                camera_id=observation.camera_id,
                preset_id=observation.preset_id,
                zone_id=observation.zone_id,
                slot_id=observation.slot_id,
                slot_code=observation.slot_code,
                plate_text=observation.plate_canonical,
                plate_confidence=observation.plate_confidence,
                observed_at=observation.observed_at,
                frame_path=observation.frame_path,
                plate_crop_path=observation.corrected_plate_path or observation.plate_crop_path,
                model_version=json.dumps(observation.model_versions, sort_keys=True),
            )
            self.session_engine.process_observation(parking_observation)
        return saved
