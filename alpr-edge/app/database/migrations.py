from __future__ import annotations

import sqlite3


def run_migrations(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS ptz_presets (
          id TEXT PRIMARY KEY,
          camera_id TEXT NOT NULL,
          name TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          onvif_preset_token TEXT,
          preset_type TEXT NOT NULL,
          pan REAL,
          tilt REAL,
          zoom REAL,
          focus REAL,
          enabled INTEGER NOT NULL DEFAULT 1,
          priority INTEGER NOT NULL DEFAULT 100,
          sort_order INTEGER NOT NULL DEFAULT 0,
          settle_time_ms INTEGER NOT NULL DEFAULT 1500,
          dwell_time_ms INTEGER NOT NULL DEFAULT 5000,
          revisit_interval_seconds INTEGER NOT NULL DEFAULT 60,
          reference_snapshot_path TEXT,
          snapshot_width INTEGER,
          snapshot_height INTEGER,
          calibration_version INTEGER NOT NULL DEFAULT 1,
          overlap_group TEXT,
          deduplication_window_seconds INTEGER NOT NULL DEFAULT 60,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_ptz_home_one
        ON ptz_presets(camera_id)
        WHERE preset_type = 'home' AND enabled = 1;

        CREATE TABLE IF NOT EXISTS polygon_zones (
          id TEXT PRIMARY KEY,
          preset_id TEXT NOT NULL REFERENCES ptz_presets(id) ON DELETE CASCADE,
          code TEXT NOT NULL,
          name TEXT NOT NULL,
          zone_type TEXT NOT NULL,
          polygon_points TEXT NOT NULL,
          priority INTEGER NOT NULL DEFAULT 100,
          enabled INTEGER NOT NULL DEFAULT 1,
          capacity INTEGER NOT NULL DEFAULT 0,
          notes TEXT NOT NULL DEFAULT '',
          overlap_group TEXT,
          deduplication_window_seconds INTEGER NOT NULL DEFAULT 60,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS parking_slots (
          id TEXT PRIMARY KEY,
          zone_id TEXT NOT NULL REFERENCES polygon_zones(id) ON DELETE CASCADE,
          preset_id TEXT NOT NULL REFERENCES ptz_presets(id) ON DELETE CASCADE,
          slot_code TEXT NOT NULL,
          display_name TEXT NOT NULL,
          polygon_points TEXT NOT NULL,
          slot_type TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          occupancy_status TEXT NOT NULL DEFAULT 'unknown',
          overlap_group TEXT,
          deduplication_window_seconds INTEGER NOT NULL DEFAULT 60,
          last_changed_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS patrol_plans (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          home_preset_id TEXT REFERENCES ptz_presets(id) ON DELETE SET NULL,
          notes TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS patrol_steps (
          id TEXT PRIMARY KEY,
          patrol_plan_id TEXT NOT NULL REFERENCES patrol_plans(id) ON DELETE CASCADE,
          preset_id TEXT NOT NULL REFERENCES ptz_presets(id) ON DELETE CASCADE,
          step_order INTEGER NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          settle_time_ms INTEGER NOT NULL DEFAULT 1500,
          dwell_time_ms INTEGER NOT NULL DEFAULT 5000,
          capture_burst_count INTEGER NOT NULL DEFAULT 3,
          revisit_interval_seconds INTEGER NOT NULL DEFAULT 60,
          priority INTEGER NOT NULL DEFAULT 100,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS configuration_versions (
          id TEXT PRIMARY KEY,
          version INTEGER NOT NULL,
          snapshot_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          actor TEXT NOT NULL,
          notes TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS audit_log (
          id TEXT PRIMARY KEY,
          timestamp TEXT NOT NULL,
          actor TEXT NOT NULL,
          action TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          old_value TEXT,
          new_value TEXT
        );

        CREATE TABLE IF NOT EXISTS parking_sessions (
          session_id TEXT PRIMARY KEY,
          station_code TEXT NOT NULL,
          camera_id TEXT NOT NULL,
          preset_id TEXT NOT NULL,
          zone_id TEXT NOT NULL,
          slot_id TEXT NOT NULL,
          slot_code TEXT NOT NULL,
          zone_type TEXT NOT NULL DEFAULT 'paid_parking',
          plate_text TEXT NOT NULL,
          plate_confidence REAL NOT NULL DEFAULT 0,
          first_seen_at TEXT NOT NULL,
          confirmed_at TEXT,
          last_seen_at TEXT NOT NULL,
          exited_at TEXT,
          free_until TEXT NOT NULL,
          billable_seconds INTEGER NOT NULL DEFAULT 0,
          amount_tjs REAL NOT NULL DEFAULT 0,
          payment_status TEXT NOT NULL DEFAULT 'unknown',
          session_status TEXT NOT NULL,
          first_frame_path TEXT,
          latest_frame_path TEXT,
          plate_crop_path TEXT,
          model_version TEXT,
          observation_count INTEGER NOT NULL DEFAULT 1,
          exit_miss_count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_parking_sessions_active
        ON parking_sessions(session_status, slot_id, plate_text);

        CREATE TABLE IF NOT EXISTS parking_observations (
          observation_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES parking_sessions(session_id) ON DELETE CASCADE,
          station_code TEXT NOT NULL,
          camera_id TEXT NOT NULL,
          preset_id TEXT NOT NULL,
          zone_id TEXT NOT NULL,
          slot_id TEXT NOT NULL,
          slot_code TEXT NOT NULL,
          plate_text TEXT NOT NULL,
          plate_confidence REAL NOT NULL DEFAULT 0,
          observed_at TEXT NOT NULL,
          frame_path TEXT,
          plate_crop_path TEXT,
          model_version TEXT,
          compatible INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_parking_observations_session
        ON parking_observations(session_id, observed_at);

        CREATE TABLE IF NOT EXISTS payment_checks (
          payment_check_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES parking_sessions(session_id) ON DELETE CASCADE,
          provider_status TEXT NOT NULL,
          payment_status TEXT NOT NULL,
          checked_at TEXT NOT NULL,
          raw_reference TEXT
        );

        CREATE TABLE IF NOT EXISTS violation_candidates (
          violation_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES parking_sessions(session_id) ON DELETE CASCADE,
          station_code TEXT NOT NULL,
          plate_text TEXT NOT NULL,
          slot_code TEXT NOT NULL,
          zone_type TEXT NOT NULL,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          unpaid_amount_tjs REAL NOT NULL DEFAULT 0,
          evidence_frame_paths TEXT NOT NULL,
          evidence_hashes TEXT NOT NULL,
          reason TEXT NOT NULL,
          status TEXT NOT NULL,
          moderator_id TEXT,
          moderator_note TEXT,
          created_at TEXT NOT NULL,
          reviewed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_violation_candidates_status
        ON violation_candidates(status, created_at);

        CREATE TABLE IF NOT EXISTS runtime_state (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alpr_observations (
          observation_id TEXT PRIMARY KEY,
          station_code TEXT NOT NULL,
          camera_id TEXT NOT NULL,
          preset_id TEXT NOT NULL,
          zone_id TEXT NOT NULL,
          slot_id TEXT NOT NULL,
          slot_code TEXT NOT NULL,
          observed_at TEXT NOT NULL,
          plate_raw TEXT NOT NULL,
          plate_canonical TEXT NOT NULL,
          plate_display TEXT NOT NULL,
          plate_format TEXT NOT NULL,
          plate_confidence REAL NOT NULL,
          vehicle_class TEXT,
          vehicle_confidence REAL,
          vehicle_bbox TEXT,
          plate_bbox TEXT,
          frame_path TEXT,
          vehicle_crop_path TEXT,
          plate_crop_path TEXT,
          corrected_plate_path TEXT,
          frame_hash TEXT NOT NULL,
          model_versions TEXT NOT NULL,
          processing_time_ms REAL NOT NULL,
          status TEXT NOT NULL,
          review_reason TEXT,
          created_at TEXT NOT NULL,
          reviewed_at TEXT,
          corrected_plate TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_alpr_observations_status
        ON alpr_observations(status, observed_at);

        CREATE TABLE IF NOT EXISTS alpr_candidates (
          candidate_id TEXT PRIMARY KEY,
          observation_id TEXT REFERENCES alpr_observations(observation_id) ON DELETE CASCADE,
          candidate_type TEXT NOT NULL,
          bbox TEXT,
          confidence REAL NOT NULL,
          diagnostics TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alpr_metrics (
          metric_id TEXT PRIMARY KEY,
          measured_at TEXT NOT NULL,
          processed_frames INTEGER NOT NULL,
          accepted_observations INTEGER NOT NULL,
          needs_review_observations INTEGER NOT NULL,
          rejected_candidates INTEGER NOT NULL,
          processing_time_ms REAL,
          warnings TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS model_registry (
          model_id TEXT PRIMARY KEY,
          role TEXT NOT NULL,
          name TEXT NOT NULL,
          version TEXT NOT NULL,
          source_url TEXT NOT NULL,
          license TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          local_path TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS model_validation_results (
          validation_id TEXT PRIMARY KEY,
          role TEXT NOT NULL,
          model_name TEXT NOT NULL,
          valid INTEGER NOT NULL,
          sha256 TEXT,
          message TEXT NOT NULL,
          checked_at TEXT NOT NULL
        );
        """
    )
    connection.commit()
