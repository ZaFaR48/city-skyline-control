from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.camera_service import CameraService
from app.version import __version__


def build_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("EDGE_DATABASE_PATH", str(tmp_path / "edge.db"))
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("RTSP_URL", "rtsp://USERNAME:PASSWORD@192.0.2.10/stream")
    monkeypatch.setenv("PTZ_DRY_RUN", "true")
    module = importlib.import_module("app.api.main")
    app = module.create_app()
    return TestClient(app)


def test_api_health_endpoint(monkeypatch, tmp_path) -> None:
    client = build_client(monkeypatch, tmp_path)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == __version__


def test_api_index_exposes_safe_version(monkeypatch, tmp_path) -> None:
    client = build_client(monkeypatch, tmp_path)

    response = client.get("/api/v1")

    assert response.status_code == 200
    assert response.json()["version"] == __version__
    assert "RTSP_URL" not in response.text
    assert "CENTRAL_API_TOKEN" not in response.text


def test_no_secret_exposure_in_api_responses(monkeypatch, tmp_path) -> None:
    client = build_client(monkeypatch, tmp_path)

    root = client.get("/api/v1")
    presets = client.get("/api/v1/ptz/presets")
    camera_status = client.get("/api/v1/camera/status")
    combined = root.text + presets.text + camera_status.text

    assert "USERNAME" not in combined
    assert "PASSWORD" not in combined
    assert "rtsp://USERNAME" not in combined


def test_camera_not_configured_response(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EDGE_DATABASE_PATH", str(tmp_path / "edge.db"))
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    monkeypatch.setenv("RTSP_URL", "")
    module = importlib.import_module("app.api.main")
    client = TestClient(module.create_app())

    response = client.get("/api/v1/camera/status")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["connected"] is False
    assert response.json()["ptz_dry_run"] is True


class FailingCameraService:
    def status(self) -> dict:
        return {
            "configured": True,
            "connected": False,
            "camera_name": "Test",
            "camera_vendor": "generic",
            "camera_local_ip": "192.0.2.10",
            "rtsp_url_redacted": "rtsp://***:***@192.0.2.10/stream",
            "frame_width": None,
            "frame_height": None,
            "measured_fps": None,
            "last_frame_at": None,
            "failure_count": 1,
            "last_error": "stream unavailable",
            "ptz_dry_run": True,
            "disk_free_bytes": 1,
        }

    def capture_snapshot(self):
        raise RuntimeError("stream unavailable")


def test_snapshot_endpoint_503_on_failure(monkeypatch, tmp_path) -> None:
    client = build_client(monkeypatch, tmp_path)
    client.app.state.camera_service = FailingCameraService()

    response = client.post("/api/v1/camera/snapshot")

    assert response.status_code == 503
    assert "PASSWORD" not in response.text


def test_ptz_dry_run_default(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("PTZ_DRY_RUN", raising=False)
    monkeypatch.setenv("EDGE_DATABASE_PATH", str(tmp_path / "edge.db"))
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    module = importlib.import_module("app.api.main")
    client = TestClient(module.create_app())

    assert client.get("/api/v1/camera/status").json()["ptz_dry_run"] is True
