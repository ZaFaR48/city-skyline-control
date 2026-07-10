from __future__ import annotations

import os
import tarfile
import textwrap
from pathlib import Path
from subprocess import run

from app.camera_service import redact_url
from app.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_configuration_path_separation() -> None:
    env_example = (ROOT / "deployment/systemd/city-skyline-edge.env.example").read_text()

    assert "EDGE_DATABASE_PATH=/var/lib/city-skyline-edge/sqlite/edge_config.db" in env_example
    assert "SNAPSHOT_DIR=/var/lib/city-skyline-edge/snapshots" in env_example
    assert "QUEUE_DIR=/var/lib/city-skyline-edge/queue" in env_example
    assert "WorkingDirectory=/opt/city-skyline-edge" in (
        ROOT / "deployment/systemd/city-skyline-edge.service"
    ).read_text()


def test_default_localhost_api_binding(monkeypatch) -> None:
    monkeypatch.delenv("EDGE_API_HOST", raising=False)
    monkeypatch.delenv("EDGE_API_PORT", raising=False)

    config = load_config()

    assert config.edge_api_host == "127.0.0.1"
    assert config.edge_api_port == 18080


def test_ptz_dry_run_default(monkeypatch) -> None:
    monkeypatch.delenv("PTZ_DRY_RUN", raising=False)

    assert load_config().ptz_dry_run is True


def test_credential_redaction() -> None:
    redacted = redact_url("rtsp://USERNAME:PASSWORD@192.0.2.10:554/live?token=TOKEN")

    assert redacted == "rtsp://***:***@192.0.2.10:554/..."
    assert "USERNAME" not in redacted
    assert "PASSWORD" not in redacted
    assert "token=TOKEN" not in redacted


def test_doctor_output_redaction(tmp_path: Path) -> None:
    env_file = tmp_path / "edge.env"
    data_dir = tmp_path / "data"
    env_file.write_text(
        textwrap.dedent(
            f"""
            RTSP_URL=
            CENTRAL_API_TOKEN=TOKEN
            ONVIF_PASSWORD=PASSWORD
            PTZ_DRY_RUN=true
            EDGE_API_HOST=127.0.0.1
            EDGE_API_PORT=18080
            EDGE_DATABASE_PATH={data_dir}/sqlite/edge.db
            SNAPSHOT_DIR={data_dir}/snapshots
            QUEUE_DIR={data_dir}/queue
            """
        ).strip()
        + "\n"
    )

    result = run(
        [str(ROOT / "deployment/ubuntu/doctor.sh")],
        cwd=ROOT,
        env={
            **os.environ,
            "ENV_FILE": str(env_file),
            "DATA_DIR": str(data_dir),
            "DOCTOR_SKIP_HOST_CHECKS": "true",
            "DOCTOR_SHOW_CONFIG": "true",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert "CENTRAL_API_TOKEN=TOKEN" not in output
    assert "ONVIF_PASSWORD=PASSWORD" not in output
    assert "CENTRAL_API_TOKEN=***" in output
    assert "ONVIF_PASSWORD=***" in output


def test_systemd_unit_does_not_run_as_root_and_uses_environment_file() -> None:
    unit = (ROOT / "deployment/systemd/city-skyline-edge-worker.service").read_text()

    assert "User=cityedge" in unit
    assert "Group=cityedge" in unit
    assert "User=root" not in unit
    assert "EnvironmentFile=/etc/city-skyline-edge/edge.env" in unit
    assert "python -m app.runtime.worker" in unit


def test_worker_auto_start_systemd_configuration() -> None:
    target = (ROOT / "deployment/systemd/city-skyline-edge.target").read_text()
    api = (ROOT / "deployment/systemd/city-skyline-edge-api.service").read_text()
    worker = (ROOT / "deployment/systemd/city-skyline-edge-worker.service").read_text()
    installer = (ROOT / "deployment/ubuntu/install.sh").read_text()

    assert "city-skyline-edge-api.service city-skyline-edge-worker.service" in target
    assert "WantedBy=multi-user.target" in target
    assert "WantedBy=city-skyline-edge.target" in api
    assert "WantedBy=city-skyline-edge.target" in worker
    assert "city-skyline-edge.target" in installer


def test_installer_does_not_overwrite_existing_environment_config() -> None:
    installer = (ROOT / "deployment/ubuntu/install.sh").read_text()

    assert 'if [[ -f "${ENV_FILE}" ]]; then' in installer
    assert "Keeping existing environment file" in installer
    assert "city-skyline-edge.env.example" in installer


def test_backup_archive_creation(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "etc"
    backup_dir = data_dir / "backups"
    db_dir = data_dir / "sqlite"
    frames_dir = data_dir / "frames"
    db_dir.mkdir(parents=True)
    frames_dir.mkdir(parents=True)
    (db_dir / "edge_config.db").write_text("sqlite placeholder")
    (frames_dir / "cached.jpg").write_text("discard")
    env_file = config_dir / "edge.env"
    config_dir.mkdir()
    env_file.write_text(f"EDGE_DATABASE_PATH={db_dir / 'edge_config.db'}\nCENTRAL_API_TOKEN=TOKEN\n")

    result = run(
        [str(ROOT / "deployment/ubuntu/backup.sh")],
        cwd=ROOT,
        env={
            **os.environ,
            "ENV_FILE": str(env_file),
            "DATA_DIR": str(data_dir),
            "BACKUP_DIR": str(backup_dir),
            "SERVICE_NAME": "city-skyline-edge-test",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archive = next(backup_dir.glob("*.tar.gz"))
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert "./config/edge.env" in names
    assert "./data/sqlite/edge_config.db" in names
    assert not any("frames/cached.jpg" in name for name in names)


def test_doctor_critical_failure_exit_code(tmp_path: Path) -> None:
    env_file = tmp_path / "edge.env"
    data_dir = tmp_path / "data"
    env_file.write_text(
        textwrap.dedent(
            f"""
            RTSP_URL=
            PTZ_DRY_RUN=false
            EDGE_API_HOST=127.0.0.1
            EDGE_API_PORT=18080
            EDGE_DATABASE_PATH={data_dir}/sqlite/edge.db
            SNAPSHOT_DIR={data_dir}/snapshots
            QUEUE_DIR={data_dir}/queue
            """
        ).strip()
        + "\n"
    )

    result = run(
        [str(ROOT / "deployment/ubuntu/doctor.sh")],
        cwd=ROOT,
        env={
            **os.environ,
            "ENV_FILE": str(env_file),
            "DATA_DIR": str(data_dir),
            "DOCTOR_SKIP_HOST_CHECKS": "true",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "[FAIL] PTZ_DRY_RUN is not true" in result.stdout


def test_log_package_excludes_secrets(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    log_dir = data_dir / "logs"
    config_dir = tmp_path / "etc"
    config_dir.mkdir()
    env_file = config_dir / "edge.env"
    env_file.write_text(
        textwrap.dedent(
            f"""
            RTSP_URL=rtsp://USERNAME:PASSWORD@192.0.2.10/live
            CENTRAL_API_TOKEN=TOKEN
            ONVIF_PASSWORD=PASSWORD
            PTZ_DRY_RUN=true
            EDGE_API_HOST=127.0.0.1
            EDGE_API_PORT=18080
            EDGE_DATABASE_PATH={data_dir}/sqlite/edge.db
            SNAPSHOT_DIR={data_dir}/snapshots
            QUEUE_DIR={data_dir}/queue
            """
        ).strip()
        + "\n"
    )

    result = run(
        [str(ROOT / "deployment/ubuntu/collect_logs.sh")],
        cwd=ROOT,
        env={
            **os.environ,
            "ENV_FILE": str(env_file),
            "DATA_DIR": str(data_dir),
            "LOG_DIR": str(log_dir),
            "INSTALL_DIR": str(tmp_path / "install"),
            "DOCTOR_SKIP_HOST_CHECKS": "true",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archive = next(log_dir.glob("*.tar.gz"))
    extracted = tmp_path / "support"
    extracted.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(extracted)
    combined = "\n".join(path.read_text(errors="ignore") for path in extracted.rglob("*") if path.is_file())
    assert "rtsp://USERNAME:PASSWORD" not in combined
    assert "CENTRAL_API_TOKEN=TOKEN" not in combined
    assert "ONVIF_PASSWORD=PASSWORD" not in combined
