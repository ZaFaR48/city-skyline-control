from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_camera import router as camera_router
from app.api.routes_alpr import router as alpr_router
from app.api.routes_health import router as health_router
from app.api.routes_patrol import router as patrol_router
from app.api.routes_parking import router as parking_router
from app.api.routes_ptz import router as ptz_router
from app.api.routes_runtime import router as runtime_router
from app.api.routes_tariff import router as tariff_router
from app.api.routes_violations import router as violations_router
from app.api.routes_zones import router as zones_router
from app.config import load_config
from app.camera_service import CameraService
from app.database.connection import connect
from app.database.migrations import run_migrations
from app.logger import configure_logging
from app.runtime.controller import RuntimeController
from app.version import __version__

VERSION = __version__


def create_app() -> FastAPI:
    config = load_config()
    configure_logging(config.log_level)
    config.edge_database_path.parent.mkdir(parents=True, exist_ok=True)
    config.snapshot_dir.mkdir(parents=True, exist_ok=True)
    with connect(config.edge_database_path) as connection:
        run_migrations(connection)

    app = FastAPI(
        title="City Skyline Edge - PTZ Zone Designer",
        version=VERSION,
        docs_url=None,
        redoc_url=None,
    )
    app.state.config = config
    app.state.camera_service = CameraService(config)
    app.state.runtime_controller = RuntimeController(config)

    web_dir = Path(__file__).resolve().parents[1] / "web"
    app.mount("/static", StaticFiles(directory=web_dir), name="static")
    app.mount("/snapshots", StaticFiles(directory=config.snapshot_dir), name="snapshots")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    @app.get("/docs", include_in_schema=False)
    def docs() -> FileResponse:
        return FileResponse(web_dir / "docs.html")

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(camera_router, prefix="/api/v1")
    app.include_router(alpr_router, prefix="/api/v1")
    app.include_router(ptz_router, prefix="/api/v1")
    app.include_router(zones_router, prefix="/api/v1")
    app.include_router(patrol_router, prefix="/api/v1")
    app.include_router(runtime_router, prefix="/api/v1")
    app.include_router(parking_router, prefix="/api/v1")
    app.include_router(violations_router, prefix="/api/v1")
    app.include_router(tariff_router, prefix="/api/v1")
    return app


app = create_app()
