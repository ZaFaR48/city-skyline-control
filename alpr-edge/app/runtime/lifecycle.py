from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app.config import AppConfig
from app.database.connection import connect
from app.database.migrations import run_migrations
from app.parking.repositories import ParkingRepository, ViolationRepository
from app.runtime.scheduler import OperatingSchedule
from app.violations.service import ViolationService

logger = logging.getLogger(__name__)


class RuntimeStateRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        with connect(self.database_path) as connection:
            run_migrations(connection)

    def set(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO runtime_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
            connection.commit()

    def get_all(self) -> dict[str, str]:
        with connect(self.database_path) as connection:
            rows = connection.execute("SELECT key, value FROM runtime_state").fetchall()
            return {row["key"]: row["value"] for row in rows}


class RuntimeStatusService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state = RuntimeStateRepository(config.edge_database_path)
        self.schedule = OperatingSchedule(config)
        self.parking = ParkingRepository(config.edge_database_path)
        self.violations = ViolationService(self.parking, ViolationRepository(config.edge_database_path))

    def status(self, embedded_worker_running: bool = False) -> dict:
        now = datetime.now(timezone.utc)
        schedule = self.schedule.status(now)
        active = self.parking.list_active_sessions()
        violations = [item for item in self.violations.list_candidates() if item["status"] == "pending_review"]
        runtime_state = self.state.get_all()
        return {
            "worker_process": runtime_state.get("worker_status", "unknown"),
            "api_embedded_worker_running": embedded_worker_running,
            "working_hours": asdict(schedule),
            "active_sessions_count": len(active),
            "active_free_sessions": sum(1 for session in active if session["session_status"] == "active_free"),
            "active_billable_sessions": sum(
                1 for session in active if session["session_status"] in {"active_billable", "needs_review"}
            ),
            "payment_integration_status": "not_integrated",
            "pending_violation_candidates": len(violations),
            "ptz_auto_patrol": self.config.ptz_auto_patrol,
            "ptz_dry_run": self.config.ptz_dry_run,
            "last_worker_heartbeat": runtime_state.get("last_worker_heartbeat"),
        }
