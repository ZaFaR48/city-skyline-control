from __future__ import annotations

from fastapi import Request

from app.camera_service import CameraService
from app.database.repositories import EdgeRepository
from app.alpr.pipeline import build_pipeline
from app.parking.repositories import ParkingRepository, ViolationRepository
from app.runtime.lifecycle import RuntimeStatusService
from app.violations.service import ViolationService


def get_repository(request: Request) -> EdgeRepository:
    return EdgeRepository(request.app.state.config.edge_database_path)


def get_camera_service(request: Request) -> CameraService:
    return request.app.state.camera_service


def get_parking_repository(request: Request) -> ParkingRepository:
    return ParkingRepository(request.app.state.config.edge_database_path)


def get_violation_service(request: Request) -> ViolationService:
    parking = ParkingRepository(request.app.state.config.edge_database_path)
    violations = ViolationRepository(request.app.state.config.edge_database_path)
    return ViolationService(parking, violations)


def get_runtime_status_service(request: Request) -> RuntimeStatusService:
    return RuntimeStatusService(request.app.state.config)


def get_alpr_pipeline(request: Request):
    parking = ParkingRepository(request.app.state.config.edge_database_path)
    from app.parking.session_engine import ParkingSessionEngine

    engine = ParkingSessionEngine(request.app.state.config, parking)
    return build_pipeline(request.app.state.config, EdgeRepository(request.app.state.config.edge_database_path), engine)
