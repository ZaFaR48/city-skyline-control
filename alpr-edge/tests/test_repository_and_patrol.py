from __future__ import annotations

from pathlib import Path

from app.database.repositories import EdgeRepository
from app.ptz.dry_run_adapter import DryRunPTZAdapter
from app.ptz.models import PatrolPlanRead, PresetType, PTZPresetCreate, PTZPresetRead
from app.ptz.patrol_service import simulate_patrol


def repo(tmp_path: Path) -> EdgeRepository:
    return EdgeRepository(tmp_path / "edge.db")


def test_preset_creation_and_sqlite_persistence(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    created = repository.create_preset(PTZPresetCreate(name="Entrance", preset_type=PresetType.ENTRANCE))

    reloaded = repo(tmp_path).get_preset(created["id"])

    assert reloaded is not None
    assert reloaded["name"] == "Entrance"


def test_only_one_active_home_preset(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    first = repository.create_preset(PTZPresetCreate(name="Home A", preset_type=PresetType.HOME, priority=0))
    second = repository.create_preset(PTZPresetCreate(name="Parking B", preset_type=PresetType.PARKING))

    repository.set_home_preset(second["id"])
    presets = repository.list_presets()

    homes = [preset for preset in presets if preset["preset_type"] == "home" and preset["enabled"]]
    assert len(homes) == 1
    assert homes[0]["id"] == second["id"]
    assert first["id"] != second["id"]


def test_patrol_order_and_estimated_duration(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    first = repository.create_preset(PTZPresetCreate(name="Home", preset_type=PresetType.HOME))
    second = repository.create_preset(PTZPresetCreate(name="Parking", preset_type=PresetType.PARKING))
    plan = repository.put_patrol_plan(
        {
            "name": "Default",
            "enabled": True,
            "home_preset_id": first["id"],
            "notes": "",
            "steps": [
                {
                    "preset_id": first["id"],
                    "order": 0,
                    "enabled": True,
                    "settle_time_ms": 1000,
                    "dwell_time_ms": 2000,
                    "capture_burst_count": 2,
                    "revisit_interval_seconds": 30,
                    "priority": 0,
                },
                {
                    "preset_id": second["id"],
                    "order": 1,
                    "enabled": True,
                    "settle_time_ms": 1000,
                    "dwell_time_ms": 3000,
                    "capture_burst_count": 2,
                    "revisit_interval_seconds": 30,
                    "priority": 100,
                },
            ],
        }
    )

    read = PatrolPlanRead.model_validate(plan)
    simulation = simulate_patrol(read)

    assert [step.order for step in read.steps] == [0, 1]
    assert simulation.estimated_complete_cycle_seconds == 7.0
    assert simulation.estimated_maximum_detection_delay_seconds == 7.0


def test_dry_run_goto_preset() -> None:
    preset = PTZPresetRead.model_validate(
        {
            "id": "preset-1",
            "camera_id": "CAM-001",
            "name": "Home",
            "description": "",
            "onvif_preset_token": None,
            "preset_type": "home",
            "pan": None,
            "tilt": None,
            "zoom": None,
            "focus": None,
            "enabled": True,
            "priority": 0,
            "sort_order": 0,
            "settle_time_ms": 1000,
            "dwell_time_ms": 2000,
            "revisit_interval_seconds": 30,
            "reference_snapshot_path": None,
            "snapshot_width": None,
            "snapshot_height": None,
            "calibration_version": 1,
            "overlap_group": None,
            "deduplication_window_seconds": 60,
            "created_at": "2026-07-03T00:00:00+00:00",
            "updated_at": "2026-07-03T00:00:00+00:00",
        }
    )

    result = DryRunPTZAdapter().goto_preset(preset)

    assert result.dry_run is True
    assert result.physical_camera_moved is False
