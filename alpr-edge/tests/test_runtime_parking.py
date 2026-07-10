from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import load_config
from app.parking.models import ParkingObservation
from app.parking.repositories import ParkingRepository, ViolationRepository
from app.parking.session_engine import ParkingSessionEngine
from app.parking.tariff import TariffConfig, TariffEngine
from app.runtime.scheduler import OperatingSchedule
from app.runtime.worker import PatrolRuntime
from app.violations.service import ViolationService


def make_config(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EDGE_DATABASE_PATH", str(tmp_path / "edge.db"))
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("FRAME_OUTPUT_DIR", str(tmp_path / "frames"))
    monkeypatch.setenv("QUEUE_DIR", str(tmp_path / "queue"))
    monkeypatch.setenv("RTSP_URL", "")
    monkeypatch.setenv("PTZ_DRY_RUN", "true")
    monkeypatch.setenv("PARKING_TIMEZONE", "Asia/Dushanbe")
    monkeypatch.setenv("PARKING_START_TIME", "07:00")
    monkeypatch.setenv("PARKING_END_TIME", "22:00")
    monkeypatch.setenv("PARKING_FREE_MINUTES", "10")
    monkeypatch.setenv("PARKING_RATE_TJS_PER_HOUR", "3.00")
    monkeypatch.setenv("PARKING_ROUNDING_MODE", "exact_minute")
    return load_config()


def observation(at: datetime, plate: str = "AA1234") -> ParkingObservation:
    return ParkingObservation(
        station_code="10001",
        camera_id="CAM-001",
        preset_id="preset-1",
        zone_id="zone-1",
        slot_id="slot-1",
        slot_code="A-01",
        plate_text=plate,
        plate_confidence=0.92,
        observed_at=at,
        frame_path=f"frames/{at.timestamp()}.jpg",
        plate_crop_path=f"frames/{at.timestamp()}-plate.jpg",
        model_version="test",
        zone_type="paid_parking",
    )


def test_runtime_schedule_uses_asia_dushanbe(monkeypatch, tmp_path: Path) -> None:
    config = make_config(monkeypatch, tmp_path)
    schedule = OperatingSchedule(config)

    assert schedule.timezone_name == "Asia/Dushanbe"
    assert schedule.is_working_time(datetime(2026, 7, 4, 2, 0, tzinfo=timezone.utc)) is True
    assert schedule.is_working_time(datetime(2026, 7, 4, 17, 0, tzinfo=timezone.utc)) is False


def test_free_first_10_minutes_and_amount_calculation() -> None:
    tariff = TariffEngine(TariffConfig())
    first_seen = datetime(2026, 7, 4, 2, 0, tzinfo=timezone.utc)

    assert tariff.amount_tjs(first_seen, first_seen + timedelta(minutes=9, seconds=59)) == 0
    assert tariff.billable_seconds(first_seen, first_seen + timedelta(minutes=11)) == 60
    assert tariff.amount_tjs(first_seen, first_seen + timedelta(minutes=11)) == 0.05


def test_configurable_rounding_modes() -> None:
    first_seen = datetime(2026, 7, 4, 2, 0, tzinfo=timezone.utc)
    one_billable_minute = first_seen + timedelta(minutes=11)

    assert TariffEngine(TariffConfig(rounding_mode="exact_minute")).amount_tjs(first_seen, one_billable_minute) == 0.05
    assert TariffEngine(TariffConfig(rounding_mode="started_hour")).amount_tjs(first_seen, one_billable_minute) == 3.0
    assert TariffEngine(TariffConfig(rounding_mode="completed_hour")).amount_tjs(first_seen, one_billable_minute) == 0.0


def test_one_observation_does_not_confirm_session(monkeypatch, tmp_path: Path) -> None:
    config = make_config(monkeypatch, tmp_path)
    engine = ParkingSessionEngine(config, ParkingRepository(config.edge_database_path))
    now = datetime(2026, 7, 4, 2, 0, tzinfo=timezone.utc)

    result = engine.process_observation(observation(now))

    assert result.session["session_status"] == "candidate"
    assert result.session["confirmed_at"] is None


def test_repeated_observations_confirm_session(monkeypatch, tmp_path: Path) -> None:
    config = make_config(monkeypatch, tmp_path)
    engine = ParkingSessionEngine(config, ParkingRepository(config.edge_database_path))
    now = datetime(2026, 7, 4, 2, 0, tzinfo=timezone.utc)

    engine.process_observation(observation(now))
    result = engine.process_observation(observation(now + timedelta(seconds=30)))

    assert result.confirmed is True
    assert result.session["confirmed_at"] is not None
    assert result.session["session_status"] == "active_free"


def test_exit_miss_protection(monkeypatch, tmp_path: Path) -> None:
    config = make_config(monkeypatch, tmp_path)
    engine = ParkingSessionEngine(config, ParkingRepository(config.edge_database_path))
    now = datetime(2026, 7, 4, 2, 0, tzinfo=timezone.utc)
    engine.process_observation(observation(now))
    result = engine.process_observation(observation(now + timedelta(seconds=30)))

    first_miss = engine.process_slot_missing("slot-1", now + timedelta(seconds=60))[0]
    second_miss = engine.process_slot_missing("slot-1", now + timedelta(minutes=4))[0]

    assert first_miss["session_status"] == "exit_pending"
    assert second_miss["session_status"] == "closed"
    assert second_miss["session_id"] == result.session["session_id"]


def test_restart_persistence(monkeypatch, tmp_path: Path) -> None:
    config = make_config(monkeypatch, tmp_path)
    now = datetime(2026, 7, 4, 2, 0, tzinfo=timezone.utc)
    engine = ParkingSessionEngine(config, ParkingRepository(config.edge_database_path))
    engine.process_observation(observation(now))
    confirmed = engine.process_observation(observation(now + timedelta(seconds=30))).session

    reloaded_repository = ParkingRepository(config.edge_database_path)
    persisted = reloaded_repository.get_session(confirmed["session_id"])

    assert persisted is not None
    assert persisted["session_status"] == "active_free"


def test_payment_unavailable_means_needs_review_and_no_unpaid_claim(monkeypatch, tmp_path: Path) -> None:
    config = make_config(monkeypatch, tmp_path)
    engine = ParkingSessionEngine(config, ParkingRepository(config.edge_database_path))
    now = datetime(2026, 7, 4, 2, 0, tzinfo=timezone.utc)
    engine.process_observation(observation(now))
    engine.process_observation(observation(now + timedelta(seconds=30)))
    result = engine.process_observation(observation(now + timedelta(minutes=11)))

    assert result.session["payment_status"] == "not_integrated"
    assert result.session["session_status"] == "needs_review"
    assert result.session["payment_status"] != "unpaid"


def test_violation_candidate_requires_unpaid_and_moderation(monkeypatch, tmp_path: Path) -> None:
    config = make_config(monkeypatch, tmp_path)
    parking_repository = ParkingRepository(config.edge_database_path)
    engine = ParkingSessionEngine(config, parking_repository)
    now = datetime(2026, 7, 4, 2, 0, tzinfo=timezone.utc)
    engine.process_observation(observation(now))
    engine.process_observation(observation(now + timedelta(seconds=30)))
    session = engine.process_observation(observation(now + timedelta(minutes=11))).session
    service = ViolationService(parking_repository, ViolationRepository(config.edge_database_path))

    with pytest.raises(ValueError):
        service.create_candidate_for_unpaid_session(session["session_id"])

    parking_repository.update_session(session["session_id"], {"payment_status": "unpaid", "session_status": "unpaid"})
    candidate = service.create_candidate_for_unpaid_session(session["session_id"], reason="operator marked unpaid")
    confirmed = service.confirm(candidate["violation_id"], moderator_id="operator-1", note="internal review")

    assert candidate["status"] == "pending_review"
    assert confirmed is not None
    assert confirmed["status"] == "confirmed_internal"


def test_ptz_movement_safety_gates(monkeypatch, tmp_path: Path) -> None:
    config = make_config(monkeypatch, tmp_path)
    allowed, reasons = PatrolRuntime(config).can_move_real_camera(preset_mapping_validated=True)

    assert allowed is False
    assert "PTZ_DRY_RUN is true" in reasons

    approved = replace(
        config,
        ptz_dry_run=False,
        ptz_auto_patrol=True,
        ptz_patrol_require_approval=True,
        ptz_patrol_approved=True,
        onvif_host="192.0.2.10",
        onvif_username="USERNAME",
        onvif_password="PASSWORD",
    )

    assert PatrolRuntime(approved).can_move_real_camera(preset_mapping_validated=True) == (True, [])
