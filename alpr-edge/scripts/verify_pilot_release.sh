#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: $0 dist-pilot/city-skyline-edge-usb-<version>-<timestamp>.tar.gz" >&2
  exit 1
fi

ARCHIVE="$1"
if [[ ! -f "${ARCHIVE}" ]]; then
  echo "[FAIL] Archive not found: ${ARCHIVE}" >&2
  exit 1
fi

ARCHIVE_ABS="$(cd "$(dirname "${ARCHIVE}")" && pwd)/$(basename "${ARCHIVE}")"
BASE="${ARCHIVE_ABS%.tar.gz}"
SHA_FILE="${ARCHIVE_ABS}.sha256"
MANIFEST_FILE="${BASE}.manifest.json"
INVENTORY_FILE="${BASE}.inventory.txt"

for sidecar in "${SHA_FILE}" "${MANIFEST_FILE}" "${INVENTORY_FILE}"; do
  if [[ ! -f "${sidecar}" ]]; then
    echo "[FAIL] Missing sidecar: ${sidecar}" >&2
    exit 1
  fi
done

echo "[PASS] Verifying SHA256"
(cd "$(dirname "${ARCHIVE_ABS}")" && sha256sum -c "$(basename "${SHA_FILE}")")

PYTHON_BIN="python3"
if [[ -x "$(dirname "${BASH_SOURCE[0]}")/../.venv/bin/python" ]]; then
  PYTHON_BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.venv/bin/python"
fi

ARCHIVE="${ARCHIVE_ABS}" \
MANIFEST_FILE="${MANIFEST_FILE}" \
INVENTORY_FILE="${INVENTORY_FILE}" \
"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tarfile
from pathlib import PurePosixPath
from urllib.parse import urlsplit

archive = os.environ["ARCHIVE"]
manifest_file = os.environ["MANIFEST_FILE"]
inventory_file = os.environ["INVENTORY_FILE"]
required_suffixes = {
    "app/version.py",
    "app/api/main.py",
    "app/database/migrations.py",
    "deployment/ubuntu/install.sh",
    "deployment/ubuntu/doctor.sh",
    "deployment/systemd/city-skyline-edge-api.service",
    "deployment/systemd/city-skyline-edge-worker.service",
    "deployment/systemd/city-skyline-edge.target",
    "docs/PILOT_DEPLOYMENT_RUNBOOK.md",
    "docs/PARKING_SESSION_ENGINE.md",
    "docs/PILOT_ACCEPTANCE_CHECKLIST.md",
    "models-pilot/manifest.json",
    "models-pilot/SHA256SUMS",
    "models-pilot/licenses/RAPIDOCR.md",
    "models-pilot/licenses/SSD_MOBILENET_V1_12.md",
    "wheelhouse-py310-linux-x86_64",
    "scripts/build_pilot_release.sh",
    "scripts/verify_pilot_release.sh",
    "scripts/verify_offline_wheelhouse.sh",
    "scripts/verify_pilot_models.sh",
    "scripts/run_worker.sh",
    "requirements.txt",
    "requirements-dev.txt",
    "README.md",
    ".env.example",
    "VERSION",
}
forbidden_parts = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "dist-pilot"}
forbidden_names = {".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
forbidden_runtime_dirs = {"frames", "snapshots", "queue", "logs", "backups"}
forbidden_suffixes = {".db", ".sqlite", ".sqlite3", ".pt", ".pth", ".engine", ".tflite", ".tar.gz"}
secret_var = re.compile(r"^\s*([A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET|PRIVATE_KEY|API_KEY)[A-Z0-9_]*)\s*=\s*(.*)\s*$")
credential_url = re.compile(r"\b(?:rtsp|https?)://[^\s'\"<>]+", re.I)
private_key = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
placeholder_values = {"", "***", "placeholder", "change_me", "changeme", "replace_me", "username", "password", "user", "pass", "token", "example", "vendor_stream_path"}
failures: list[str] = []

def fail(message: str) -> None:
    failures.append(message)

def is_placeholder(value: str) -> bool:
    cleaned = value.strip().strip('"').strip("'").strip("<>").lower()
    return cleaned in placeholder_values or cleaned.startswith("your_")

def validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute():
        fail(f"{name}: absolute archive path")
    if any(part == ".." for part in path.parts):
        fail(f"{name}: path traversal entry")
    if any(part in forbidden_parts for part in path.parts):
        fail(f"{name}: forbidden cache/build metadata")
    if path.name in forbidden_names:
        fail(f"{name}: forbidden secret filename")
    if any(part in forbidden_runtime_dirs for part in path.parts):
        fail(f"{name}: forbidden runtime data directory")
    if any(name.endswith(suffix) for suffix in forbidden_suffixes):
        fail(f"{name}: forbidden binary/database/archive content")
    suffix = "/".join(path.parts[1:])
    if name.endswith(".onnx") and not suffix.startswith("models-pilot/"):
        fail(f"{name}: ONNX model outside model pack")
    if name.endswith(".whl") and not suffix.startswith("wheelhouse-py310-linux-x86_64/"):
        fail(f"{name}: wheel outside offline wheelhouse")

with tarfile.open(archive, "r:gz") as tar:
    members = tar.getmembers()
    names = [member.name for member in members]
    root_parts = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    if len(root_parts) != 1:
        fail("archive must contain exactly one top-level package directory")
    root = next(iter(root_parts), "")
    for member in members:
        validate_member_name(member.name)
        if member.issym() or member.islnk():
            target = PurePosixPath(member.linkname)
            if target.is_absolute() or any(part == ".." for part in target.parts):
                fail(f"{member.name}: symlink/link escapes package")
            else:
                joined = PurePosixPath(member.name).parent.joinpath(target)
                if root and (not joined.parts or joined.parts[0] != root):
                    fail(f"{member.name}: symlink/link escapes package root")
        if member.isfile():
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            data = extracted.read()
            suffix = "/".join(PurePosixPath(member.name).parts[1:])
            if suffix.startswith("models-pilot/") and suffix.endswith(".onnx"):
                continue
            if suffix.startswith("wheelhouse-py310-linux-x86_64/") and suffix.endswith(".whl"):
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                fail(f"{member.name}: unexpected binary file")
                continue
            if private_key.search(text):
                fail(f"{member.name}: private key material detected")
            for line in text.splitlines():
                match = secret_var.match(line)
                if match and not is_placeholder(match.group(2)):
                    fail(f"{member.name}: non-placeholder sensitive variable {match.group(1)}")
            for match in credential_url.finditer(text):
                if any(char in match.group(0) for char in "[]()\\"):
                    continue
                try:
                    parsed = urlsplit(match.group(0))
                except ValueError:
                    if "@" in match.group(0):
                        fail(f"{member.name}: unparsable credential-looking URL detected")
                    continue
                if parsed.username or parsed.password:
                    if not (is_placeholder(parsed.username or "") and is_placeholder(parsed.password or "")):
                        fail(f"{member.name}: credential-containing URL detected")
    suffixes = {"/".join(PurePosixPath(name).parts[1:]) for name in names if len(PurePosixPath(name).parts) > 1}
    missing = sorted(required_suffixes - suffixes)
    for suffix in missing:
        fail(f"required file missing: {suffix}")

with open(archive, "rb") as handle:
    digest = hashlib.sha256(handle.read()).hexdigest()
manifest = json.loads(open(manifest_file, encoding="utf-8").read())
required_manifest_keys = {
    "product_name",
    "release_version",
    "build_timestamp_utc",
    "python_minimum_version",
    "target_os",
    "target_architecture",
    "ptz_dry_run_default",
    "api_default_host",
    "api_default_port",
    "included_files_count",
    "archive_sha256",
    "git_commit",
    "build_host_identifier",
    "test_summary",
    "release_status",
}
for key in sorted(required_manifest_keys - set(manifest)):
    fail(f"manifest missing key: {key}")
if manifest.get("archive_sha256") != digest:
    fail("manifest archive_sha256 does not match archive")
if manifest.get("release_status") != "pilot":
    fail("manifest release_status is not pilot")
if manifest.get("api_default_host") != "127.0.0.1":
    fail("manifest API host is not localhost")
if manifest.get("api_default_port") != 18080:
    fail("manifest API port is not 18080")
if manifest.get("ptz_dry_run_default") is not True:
    fail("manifest PTZ dry-run default is not true")
if manifest.get("python_minimum_version") != "3.10":
    fail("manifest Python minimum is not 3.10")
if manifest.get("includes_offline_wheelhouse") is not True:
    fail("manifest does not record offline wheelhouse")
if manifest.get("includes_model_pack") is not True:
    fail("manifest does not record model pack")

inventory = [line.strip() for line in open(inventory_file, encoding="utf-8") if line.strip()]
if manifest.get("included_files_count") != len(inventory):
    fail("manifest included_files_count does not match inventory")
if any(line.endswith(".env") or "/.env" in line for line in inventory):
    fail("inventory contains real .env")

if failures:
    for message in failures:
        print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)

print("[PASS] Archive structure, required files, forbidden files, secret scan, and manifest validated")
PY

echo "[PASS] Safe archive contents:"
tar -tzf "${ARCHIVE_ABS}" | sed -n '1,120p'
echo "[PASS] Pilot release verification completed"
