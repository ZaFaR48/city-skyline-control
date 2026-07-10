from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.database.connection import connect
from app.database.migrations import run_migrations


OPEN_SESSION_STATUSES = {
    "candidate",
    "active_free",
    "active_billable",
    "paid",
    "unpaid",
    "exit_pending",
    "violation_candidate",
    "needs_review",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class ParkingRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        with connect(self.database_path) as connection:
            run_migrations(connection)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.database_path)

    def find_open_session(self, slot_id: str, plate_text: str) -> dict[str, Any] | None:
        placeholders = ", ".join("?" for _ in OPEN_SESSION_STATUSES)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT * FROM parking_sessions
                WHERE slot_id = ? AND plate_text = ? AND session_status IN ({placeholders})
                ORDER BY last_seen_at DESC
                LIMIT 1
                """,
                (slot_id, plate_text, *sorted(OPEN_SESSION_STATUSES)),
            ).fetchone()
            return row_to_dict(row)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return row_to_dict(
                connection.execute("SELECT * FROM parking_sessions WHERE session_id = ?", (session_id,)).fetchone()
            )

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM parking_sessions ORDER BY last_seen_at DESC").fetchall()
            return [dict(row) for row in rows]

    def list_active_sessions(self) -> list[dict[str, Any]]:
        placeholders = ", ".join("?" for _ in OPEN_SESSION_STATUSES)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM parking_sessions WHERE session_status IN ({placeholders}) ORDER BY last_seen_at DESC",
                tuple(sorted(OPEN_SESSION_STATUSES)),
            ).fetchall()
            return [dict(row) for row in rows]

    def create_candidate(self, data: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        record = {
            "session_id": str(uuid4()),
            "created_at": now,
            "updated_at": now,
            "observation_count": 1,
            "exit_miss_count": 0,
            "payment_status": "unknown",
            "session_status": "candidate",
            "billable_seconds": 0,
            "amount_tjs": 0.0,
            **data,
        }
        columns = list(record)
        placeholders = ", ".join("?" for _ in columns)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO parking_sessions ({', '.join(columns)}) VALUES ({placeholders})",
                [record[column] for column in columns],
            )
            connection.commit()
        return record

    def update_session(self, session_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        updates = dict(updates)
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE parking_sessions SET {assignments} WHERE session_id = ?",
                [*updates.values(), session_id],
            )
            connection.commit()
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def add_observation(self, session_id: str, data: dict[str, Any]) -> None:
        record = {
            "observation_id": str(uuid4()),
            "session_id": session_id,
            "compatible": 1,
            "created_at": utc_now(),
            **data,
        }
        columns = list(record)
        placeholders = ", ".join("?" for _ in columns)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO parking_observations ({', '.join(columns)}) VALUES ({placeholders})",
                [record[column] for column in columns],
            )
            connection.commit()

    def count_observations_since(self, session_id: str, since: str) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM parking_observations WHERE session_id = ? AND observed_at >= ?",
                    (session_id, since),
                ).fetchone()[0]
            )

    def add_payment_check(self, session_id: str, provider_status: str, payment_status: str, raw_reference: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO payment_checks
                (payment_check_id, session_id, provider_status, payment_status, checked_at, raw_reference)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), session_id, provider_status, payment_status, utc_now(), raw_reference),
            )
            connection.commit()


class ViolationRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        with connect(self.database_path) as connection:
            run_migrations(connection)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.database_path)

    def list_candidates(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM violation_candidates ORDER BY created_at DESC").fetchall()
            return [self._decode(dict(row)) for row in rows]

    def get_candidate(self, violation_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM violation_candidates WHERE violation_id = ?", (violation_id,)
            ).fetchone()
            return self._decode(dict(row)) if row else None

    def create_candidate(self, data: dict[str, Any]) -> dict[str, Any]:
        record = {
            "violation_id": str(uuid4()),
            "status": "pending_review",
            "created_at": utc_now(),
            "reviewed_at": None,
            "moderator_id": None,
            "moderator_note": None,
            **data,
        }
        record["evidence_frame_paths"] = json.dumps(record["evidence_frame_paths"], sort_keys=True)
        record["evidence_hashes"] = json.dumps(record["evidence_hashes"], sort_keys=True)
        columns = list(record)
        placeholders = ", ".join("?" for _ in columns)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO violation_candidates ({', '.join(columns)}) VALUES ({placeholders})",
                [record[column] for column in columns],
            )
            connection.commit()
        return self.get_candidate(record["violation_id"]) or record

    def moderate(self, violation_id: str, status: str, moderator_id: str | None, note: str | None) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE violation_candidates
                SET status = ?, moderator_id = ?, moderator_note = ?, reviewed_at = ?
                WHERE violation_id = ?
                """,
                (status, moderator_id, note, utc_now(), violation_id),
            )
            connection.commit()
        return self.get_candidate(violation_id)

    def _decode(self, record: dict[str, Any]) -> dict[str, Any]:
        record["evidence_frame_paths"] = json.loads(record["evidence_frame_paths"])
        record["evidence_hashes"] = json.loads(record["evidence_hashes"])
        return record
