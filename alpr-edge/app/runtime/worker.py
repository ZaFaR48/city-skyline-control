from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone

from app.config import AppConfig, load_config
from app.alpr.pipeline import build_pipeline
from app.camera import RTSPCamera
from app.database.repositories import EdgeRepository
from app.database.connection import connect
from app.database.migrations import run_migrations
from app.logger import configure_logging
from app.parking.repositories import ParkingRepository
from app.parking.session_engine import ParkingSessionEngine
from app.runtime.lifecycle import RuntimeStateRepository
from app.runtime.scheduler import OperatingSchedule

logger = logging.getLogger(__name__)


class PatrolRuntime:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def can_move_real_camera(self, preset_mapping_validated: bool = False) -> tuple[bool, list[str]]:
        reasons = []
        if self.config.ptz_dry_run:
            reasons.append("PTZ_DRY_RUN is true")
        if not self.config.ptz_auto_patrol:
            reasons.append("PTZ_AUTO_PATROL is false")
        if not self.config.ptz_patrol_require_approval:
            reasons.append("PTZ_PATROL_REQUIRE_APPROVAL is false")
        if not self.config.ptz_patrol_approved:
            reasons.append("PTZ_PATROL_APPROVED is false")
        if not (self.config.onvif_host and self.config.onvif_username and self.config.onvif_password):
            reasons.append("ONVIF is not fully configured")
        if not preset_mapping_validated:
            reasons.append("preset mapping is not validated")
        return not reasons, reasons

    def run_once(self) -> dict:
        allowed, reasons = self.can_move_real_camera(preset_mapping_validated=False)
        if not allowed:
            logger.info("PTZ patrol safely refused: %s", "; ".join(reasons))
            return {"physical_camera_moved": False, "allowed": False, "reasons": reasons}
        return {"physical_camera_moved": False, "allowed": True, "reasons": []}


class EdgeWorker:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.running = False
        self.state = RuntimeStateRepository(config.edge_database_path)
        self.schedule = OperatingSchedule(config)
        self.repository = ParkingRepository(config.edge_database_path)
        self.engine = ParkingSessionEngine(config, self.repository)
        self.patrol = PatrolRuntime(config)
        self.alpr_pipeline = build_pipeline(config, EdgeRepository(config.edge_database_path), self.engine)
        self.camera: RTSPCamera | None = None

    def request_stop(self, signum: int | None = None, frame: object | None = None) -> None:
        del signum, frame
        self.running = False
        self.state.set("worker_status", "stopping")

    def run_forever(self, poll_seconds: float = 5.0) -> int:
        self.running = True
        self.state.set("worker_status", "running")
        logger.info("Starting edge worker")
        try:
            while self.running:
                self.tick()
                time.sleep(poll_seconds)
        finally:
            self.state.set("worker_status", "stopped")
            logger.info("Edge worker stopped")
        return 0

    def tick(self) -> None:
        now = datetime.now(timezone.utc)
        self.state.set("last_worker_heartbeat", now.isoformat())
        self.state.set("working_hours_active", str(self.schedule.is_working_time(now)).lower())
        self.engine.refresh_billing(now)
        self.patrol.run_once()
        if not self.schedule.is_working_time(now):
            return
        if not self.config.pilot_fixed_preset_id and not self.config.ptz_auto_patrol:
            self.state.set("alpr_warning", "PILOT_FIXED_PRESET_ID is not configured; ALPR slot sessions disabled")
            return
        if not self.config.rtsp_url:
            self.state.set("alpr_warning", "RTSP_URL is not configured")
            return
        try:
            if self.camera is None:
                self.camera = RTSPCamera(self.config.rtsp_url)
                self.camera.open()
            frame = self.camera.read_frame()
            if frame is None:
                self.camera.close()
                self.camera = None
                return
            self.alpr_pipeline.process_frame(frame, create_sessions=True)
        except Exception as exc:
            logger.warning("ALPR worker tick failed safely: %s", exc)
            self.state.set("alpr_warning", str(exc))
            if self.camera is not None:
                self.camera.close()
                self.camera = None


def main() -> int:
    config = load_config()
    configure_logging(config.log_level)
    config.edge_database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(config.edge_database_path) as connection:
        run_migrations(connection)
    worker = EdgeWorker(config)
    signal.signal(signal.SIGINT, worker.request_stop)
    signal.signal(signal.SIGTERM, worker.request_stop)
    return worker.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
