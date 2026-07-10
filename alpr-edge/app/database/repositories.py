from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.database.connection import connect
from app.database.migrations import run_migrations
from app.ptz.models import PTZPresetCreate, PTZPresetPatch
from app.zones.models import ParkingSlotCreate, ParkingSlotPatch, PolygonZoneCreate, PolygonZonePatch


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _model_dump(model: Any, exclude_unset: bool = False) -> dict[str, Any]:
    data = model.model_dump(mode="json", exclude_unset=exclude_unset)
    return {key: value for key, value in data.items() if value is not None}


class EdgeRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        with connect(self.database_path) as connection:
            run_migrations(connection)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.database_path)

    def _audit(
        self,
        connection: sqlite3.Connection,
        action: str,
        entity_type: str,
        entity_id: str,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
        actor: str = "local-operator",
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_log
            (id, timestamp, actor, action, entity_type, entity_id, old_value, new_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                utc_now(),
                actor,
                action,
                entity_type,
                entity_id,
                _json_dump(old_value) if old_value is not None else None,
                _json_dump(new_value) if new_value is not None else None,
            ),
        )

    def _create_configuration_version(
        self,
        connection: sqlite3.Connection,
        actor: str = "local-operator",
        notes: str = "",
    ) -> None:
        current = connection.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM configuration_versions").fetchone()[0]
        snapshot = {
            "ptz_presets": self._fetch_table(connection, "ptz_presets"),
            "polygon_zones": self._fetch_table(connection, "polygon_zones"),
            "parking_slots": self._fetch_table(connection, "parking_slots"),
            "patrol_plans": self._fetch_table(connection, "patrol_plans"),
            "patrol_steps": self._fetch_table(connection, "patrol_steps"),
        }
        connection.execute(
            """
            INSERT INTO configuration_versions
            (id, version, snapshot_json, created_at, actor, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid4()), current, _json_dump(snapshot), utc_now(), actor, notes),
        )

    def _fetch_table(self, connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
        rows = connection.execute(f"SELECT * FROM {table_name}").fetchall()
        return [dict(row) for row in rows]

    def _commit_change(
        self,
        connection: sqlite3.Connection,
        action: str,
        entity_type: str,
        entity_id: str,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
    ) -> None:
        self._audit(connection, action, entity_type, entity_id, old_value, new_value)
        self._create_configuration_version(connection, notes=f"{action} {entity_type}")
        connection.commit()

    def list_presets(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ptz_presets ORDER BY priority ASC, sort_order ASC, name ASC"
            ).fetchall()
            return [self._decode_preset(row) for row in rows]

    def get_preset(self, preset_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM ptz_presets WHERE id = ?", (preset_id,)).fetchone()
            return self._decode_preset(row) if row else None

    def create_preset(self, payload: PTZPresetCreate) -> dict[str, Any]:
        data = _model_dump(payload)
        preset_id = str(uuid4())
        now = utc_now()
        data.update({"id": preset_id, "created_at": now, "updated_at": now})
        columns = list(data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO ptz_presets ({', '.join(columns)}) VALUES ({placeholders})",
                [self._encode_value(data[column]) for column in columns],
            )
            new_value = self.get_preset_with_connection(connection, preset_id)
            self._commit_change(connection, "create", "ptz_preset", preset_id, None, new_value)
            assert new_value is not None
            return new_value

    def update_preset(self, preset_id: str, payload: PTZPresetPatch) -> dict[str, Any] | None:
        updates = _model_dump(payload, exclude_unset=True)
        if not updates:
            return self.get_preset(preset_id)
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = [self._encode_value(value) for value in updates.values()]
        values.append(preset_id)
        with self._connect() as connection:
            old_value = self.get_preset_with_connection(connection, preset_id)
            if old_value is None:
                return None
            connection.execute(f"UPDATE ptz_presets SET {assignments} WHERE id = ?", values)
            new_value = self.get_preset_with_connection(connection, preset_id)
            self._commit_change(connection, "update", "ptz_preset", preset_id, old_value, new_value)
            return new_value

    def delete_preset(self, preset_id: str) -> bool:
        with self._connect() as connection:
            old_value = self.get_preset_with_connection(connection, preset_id)
            if old_value is None:
                return False
            connection.execute("DELETE FROM ptz_presets WHERE id = ?", (preset_id,))
            self._commit_change(connection, "delete", "ptz_preset", preset_id, old_value, None)
            return True

    def set_home_preset(self, preset_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            preset = self.get_preset_with_connection(connection, preset_id)
            if preset is None:
                return None
            old_values = self._fetch_table(connection, "ptz_presets")
            connection.execute(
                "UPDATE ptz_presets SET preset_type = 'entrance', updated_at = ? WHERE camera_id = ? AND preset_type = 'home'",
                (utc_now(), preset["camera_id"]),
            )
            connection.execute(
                """
                UPDATE ptz_presets
                SET preset_type = 'home', priority = 0, sort_order = 0, updated_at = ?
                WHERE id = ?
                """,
                (utc_now(), preset_id),
            )
            new_value = self.get_preset_with_connection(connection, preset_id)
            self._commit_change(connection, "set_home", "ptz_preset", preset_id, {"presets": old_values}, new_value)
            return new_value

    def get_preset_with_connection(self, connection: sqlite3.Connection, preset_id: str) -> dict[str, Any] | None:
        row = connection.execute("SELECT * FROM ptz_presets WHERE id = ?", (preset_id,)).fetchone()
        return self._decode_preset(row) if row else None

    def list_zones(self, preset_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM polygon_zones"
        params: tuple[Any, ...] = ()
        if preset_id:
            query += " WHERE preset_id = ?"
            params = (preset_id,)
        query += " ORDER BY priority ASC, code ASC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
            return [self._decode_zone(row) for row in rows]

    def get_zone(self, zone_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM polygon_zones WHERE id = ?", (zone_id,)).fetchone()
            return self._decode_zone(row) if row else None

    def create_zone(self, payload: PolygonZoneCreate) -> dict[str, Any]:
        return self._create_json_record("polygon_zones", "polygon_zone", payload, self._decode_zone)

    def update_zone(self, zone_id: str, payload: PolygonZonePatch) -> dict[str, Any] | None:
        return self._update_json_record("polygon_zones", "polygon_zone", zone_id, payload, self._decode_zone)

    def delete_zone(self, zone_id: str) -> bool:
        return self._delete_record("polygon_zones", "polygon_zone", zone_id, self._decode_zone)

    def list_slots(self, preset_id: str | None = None, zone_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM parking_slots"
        filters = []
        params: list[Any] = []
        if preset_id:
            filters.append("preset_id = ?")
            params.append(preset_id)
        if zone_id:
            filters.append("zone_id = ?")
            params.append(zone_id)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY slot_code ASC"
        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
            return [self._decode_slot(row) for row in rows]

    def create_slot(self, payload: ParkingSlotCreate) -> dict[str, Any]:
        data = _model_dump(payload)
        now = utc_now()
        data["last_changed_at"] = now
        return self._create_json_record("parking_slots", "parking_slot", data, self._decode_slot)

    def update_slot(self, slot_id: str, payload: ParkingSlotPatch) -> dict[str, Any] | None:
        updates = _model_dump(payload, exclude_unset=True)
        if updates:
            updates["last_changed_at"] = utc_now()
        return self._update_json_record("parking_slots", "parking_slot", slot_id, updates, self._decode_slot)

    def delete_slot(self, slot_id: str) -> bool:
        return self._delete_record("parking_slots", "parking_slot", slot_id, self._decode_slot)

    def get_patrol_plan(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            plan = connection.execute("SELECT * FROM patrol_plans ORDER BY created_at LIMIT 1").fetchone()
            if plan is None:
                return None
            return self._decode_patrol_plan(connection, plan)

    def put_patrol_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_id = payload.get("id") or str(uuid4())
        now = utc_now()
        with self._connect() as connection:
            old_value = self.get_patrol_plan_with_connection(connection)
            connection.execute("DELETE FROM patrol_plans")
            connection.execute(
                """
                INSERT INTO patrol_plans (id, name, enabled, home_preset_id, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    payload["name"],
                    int(payload["enabled"]),
                    payload.get("home_preset_id"),
                    payload.get("notes", ""),
                    now,
                    now,
                ),
            )
            for step in payload.get("steps", []):
                connection.execute(
                    """
                    INSERT INTO patrol_steps
                    (id, patrol_plan_id, preset_id, step_order, enabled, settle_time_ms, dwell_time_ms,
                     capture_burst_count, revisit_interval_seconds, priority, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        plan_id,
                        step["preset_id"],
                        step["order"],
                        int(step["enabled"]),
                        step["settle_time_ms"],
                        step["dwell_time_ms"],
                        step["capture_burst_count"],
                        step["revisit_interval_seconds"],
                        step["priority"],
                        now,
                        now,
                    ),
                )
            new_value = self.get_patrol_plan_with_connection(connection)
            self._commit_change(connection, "replace", "patrol_plan", plan_id, old_value, new_value)
            assert new_value is not None
            return new_value

    def get_patrol_plan_with_connection(self, connection: sqlite3.Connection) -> dict[str, Any] | None:
        plan = connection.execute("SELECT * FROM patrol_plans ORDER BY created_at LIMIT 1").fetchone()
        if plan is None:
            return None
        return self._decode_patrol_plan(connection, plan)

    def list_audit_log(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM audit_log ORDER BY timestamp DESC").fetchall()
            return [dict(row) for row in rows]

    def _create_json_record(self, table: str, entity_type: str, payload: Any, decoder: Any) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else _model_dump(payload)
        record_id = str(uuid4())
        now = utc_now()
        data.update({"id": record_id, "created_at": now, "updated_at": now})
        columns = list(data.keys())
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['?'] * len(columns))})",
                [self._encode_value(data[column]) for column in columns],
            )
            row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
            new_value = decoder(row)
            self._commit_change(connection, "create", entity_type, record_id, None, new_value)
            return new_value

    def _update_json_record(self, table: str, entity_type: str, record_id: str, payload: Any, decoder: Any) -> dict[str, Any] | None:
        updates = payload if isinstance(payload, dict) else _model_dump(payload, exclude_unset=True)
        if not updates:
            with self._connect() as connection:
                row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
                return decoder(row) if row else None
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = [self._encode_value(value) for value in updates.values()]
        values.append(record_id)
        with self._connect() as connection:
            old_row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
            if old_row is None:
                return None
            old_value = decoder(old_row)
            connection.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", values)
            new_row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
            new_value = decoder(new_row)
            self._commit_change(connection, "update", entity_type, record_id, old_value, new_value)
            return new_value

    def _delete_record(self, table: str, entity_type: str, record_id: str, decoder: Any) -> bool:
        with self._connect() as connection:
            row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
            if row is None:
                return False
            old_value = decoder(row)
            connection.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
            self._commit_change(connection, "delete", entity_type, record_id, old_value, None)
            return True

    def _decode_preset(self, row: sqlite3.Row | None) -> dict[str, Any]:
        data = _row_to_dict(row)
        if data is None:
            return {}
        return self._decode_common(data)

    def _decode_zone(self, row: sqlite3.Row | None) -> dict[str, Any]:
        data = _row_to_dict(row)
        if data is None:
            return {}
        data = self._decode_common(data)
        data["polygon_points"] = json.loads(data["polygon_points"])
        return data

    def _decode_slot(self, row: sqlite3.Row | None) -> dict[str, Any]:
        data = _row_to_dict(row)
        if data is None:
            return {}
        data = self._decode_common(data)
        data["polygon_points"] = json.loads(data["polygon_points"])
        return data

    def _decode_patrol_plan(self, connection: sqlite3.Connection, plan: sqlite3.Row) -> dict[str, Any]:
        data = self._decode_common(dict(plan))
        rows = connection.execute(
            "SELECT * FROM patrol_steps WHERE patrol_plan_id = ? ORDER BY step_order ASC",
            (data["id"],),
        ).fetchall()
        data["steps"] = [self._decode_common(dict(row), rename_order=True) for row in rows]
        return data

    def _decode_common(self, data: dict[str, Any], rename_order: bool = False) -> dict[str, Any]:
        for key, value in list(data.items()):
            if key in {"enabled"} and value is not None:
                data[key] = bool(value)
        if rename_order and "step_order" in data:
            data["order"] = data.pop("step_order")
        return data

    def _encode_value(self, value: Any) -> Any:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, list) or isinstance(value, dict):
            return _json_dump(value)
        return value
