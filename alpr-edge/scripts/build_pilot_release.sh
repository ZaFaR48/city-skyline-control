#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "${EUID}" -eq 0 ]]; then
  echo "[WARN] Running as root in the current shell; this script will not use sudo or install anything."
fi

if [[ "${ROOT_DIR}" == "/opt/city-skyline-edge" ]]; then
  echo "[FAIL] Refusing to build from the station installation directory." >&2
  exit 1
fi

if find data -type f 2>/dev/null | grep -q .; then
  echo "[FAIL] Refusing to build while local runtime data files exist under ./data." >&2
  exit 1
fi

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

VERSION="$("${PYTHON_BIN}" - <<'PY'
from app.version import __version__
print(__version__)
PY
)"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PACKAGE_NAME="city-skyline-edge-usb-${VERSION}-${TIMESTAMP}"
DIST_DIR="${ROOT_DIR}/dist-pilot"
STAGE_PARENT="${DIST_DIR}/.stage-${PACKAGE_NAME}"
STAGE_ROOT="${STAGE_PARENT}/${PACKAGE_NAME}"
ARCHIVE="${DIST_DIR}/${PACKAGE_NAME}.tar.gz"
SHA_FILE="${ARCHIVE}.sha256"
MANIFEST_FILE="${DIST_DIR}/${PACKAGE_NAME}.manifest.json"
INVENTORY_FILE="${DIST_DIR}/${PACKAGE_NAME}.inventory.txt"

mkdir -p "${STAGE_ROOT}" "${DIST_DIR}"
rm -rf "${DIST_DIR}"/.stage-*
mkdir -p "${STAGE_ROOT}"

echo "[PASS] Running Python compile checks"
"${PYTHON_BIN}" -m compileall -q app tests

echo "[PASS] Running shell syntax checks"
while IFS= read -r script; do
  bash -n "${script}"
done < <(find scripts deployment -type f -name '*.sh' | sort)

echo "[PASS] Verifying model pack"
"${ROOT_DIR}/scripts/verify_pilot_models.sh" "${ROOT_DIR}/models-pilot"

echo "[PASS] Verifying offline wheelhouse"
"${ROOT_DIR}/scripts/verify_offline_wheelhouse.sh" "${ROOT_DIR}/wheelhouse-py310-linux-x86_64"

echo "[PASS] Running pytest"
if ! "${PYTHON_BIN}" -m pytest -q; then
  echo "[FAIL] Pytest failed. Release archive was not created." >&2
  exit 1
fi

copy_path() {
  local source="$1"
  if [[ -d "${source}" ]]; then
    mkdir -p "${STAGE_ROOT}/${source}"
    tar \
      --exclude='__pycache__' \
      --exclude='.pytest_cache' \
      --exclude='.venv' \
      --exclude='venv' \
      --exclude='node_modules' \
      --exclude='dist-pilot' \
      -C "${ROOT_DIR}/${source}" -cf - . | tar -C "${STAGE_ROOT}/${source}" -xf -
  else
    install -m 0644 "${ROOT_DIR}/${source}" "${STAGE_ROOT}/${source}"
  fi
}

for path in app deployment docs scripts tests models-pilot wheelhouse-py310-linux-x86_64 requirements.txt requirements-dev.txt README.md .env.example; do
  copy_path "${path}"
done

printf '%s\n' "${VERSION}" > "${STAGE_ROOT}/VERSION"

find "${STAGE_ROOT}" \( \
  -name '__pycache__' -o \
  -name '.pytest_cache' -o \
  -name '.venv' -o \
  -name 'venv' -o \
  -name 'node_modules' -o \
  -name '.git' -o \
  -name '*.tar.gz' \
\) -prune -exec rm -rf {} +

echo "[PASS] Scanning staged files for forbidden content"
STAGE_ROOT="${STAGE_ROOT}" "${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit

root = Path(os.environ["STAGE_ROOT"])
placeholder_values = {
    "",
    "***",
    "placeholder",
    "change_me",
    "changeme",
    "replace_me",
    "username",
    "password",
    "user",
    "pass",
    "token",
    "example",
    "vendor_stream_path",
}
secret_var = re.compile(r"^\s*([A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET|PRIVATE_KEY|API_KEY)[A-Z0-9_]*)\s*=\s*(.*)\s*$")
credential_url = re.compile(r"\b(?:rtsp|https?)://[^\s'\"<>]+", re.I)
private_key = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
forbidden_names = {".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
forbidden_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "frames", "snapshots", "queue", "logs", "backups"}
forbidden_suffixes = {".db", ".sqlite", ".sqlite3", ".pt", ".pth", ".engine", ".tflite", ".tar.gz"}
failures: list[str] = []

def is_placeholder(value: str) -> bool:
    cleaned = value.strip().strip('"').strip("'").strip("<>").lower()
    return cleaned in placeholder_values or cleaned.startswith("your_")

for path in root.rglob("*"):
    rel = path.relative_to(root).as_posix()
    parts = set(path.relative_to(root).parts)
    if path.is_dir():
        continue
    if path.name in forbidden_names:
        failures.append(f"{rel}: forbidden secret filename")
    if parts & forbidden_dirs:
        failures.append(f"{rel}: forbidden runtime/cache directory")
    if any(rel.endswith(suffix) for suffix in forbidden_suffixes):
        failures.append(f"{rel}: forbidden database/model/archive file")
    if rel.endswith(".onnx") and not rel.startswith("models-pilot/"):
        failures.append(f"{rel}: ONNX model outside model pack")
    if rel.endswith(".whl") and not rel.startswith("wheelhouse-py310-linux-x86_64/"):
        failures.append(f"{rel}: wheel outside offline wheelhouse")
    if path.is_symlink():
        failures.append(f"{rel}: symlinks are not allowed in release archives")
        continue
    try:
        mode = path.stat().st_mode
    except OSError:
        continue
    if rel.startswith("deployment/ubuntu/") or rel.startswith("scripts/"):
        pass
    elif mode & (stat.S_IWGRP | stat.S_IWOTH):
        failures.append(f"{rel}: group/world writable file")
    if rel.startswith("models-pilot/") and path.suffix.lower() in {".onnx"}:
        continue
    if rel.startswith("wheelhouse-py310-linux-x86_64/") and path.suffix.lower() == ".whl":
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        failures.append(f"{rel}: unexpected binary file")
        continue
    if private_key.search(text):
        failures.append(f"{rel}: private key material detected")
    for line in text.splitlines():
        match = secret_var.match(line)
        if match and not is_placeholder(match.group(2)):
            failures.append(f"{rel}: non-placeholder sensitive variable {match.group(1)}")
    for match in credential_url.finditer(text):
        if any(char in match.group(0) for char in "[]()\\"):
            continue
        try:
            parsed = urlsplit(match.group(0))
        except ValueError:
            if "@" in match.group(0):
                failures.append(f"{rel}: unparsable credential-looking URL detected")
            continue
        if parsed.username or parsed.password:
            if not (is_placeholder(parsed.username or "") and is_placeholder(parsed.password or "")):
                failures.append(f"{rel}: credential-containing URL detected")

if failures:
    for failure in failures:
        print(f"[FAIL] {failure}", file=sys.stderr)
    raise SystemExit(1)
PY

find "${STAGE_ROOT}" -type f -printf '%P\n' | LC_ALL=C sort > "${INVENTORY_FILE}"
included_count="$(wc -l < "${INVENTORY_FILE}" | tr -d ' ')"

tar -C "${STAGE_PARENT}" -czf "${ARCHIVE}" "${PACKAGE_NAME}"
(
  cd "${DIST_DIR}"
  sha256sum "$(basename "${ARCHIVE}")" > "$(basename "${SHA_FILE}")"
)
archive_sha="$(cut -d ' ' -f1 "${SHA_FILE}")"

git_commit=""
if git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git_commit="$(git -C "${ROOT_DIR}" rev-parse HEAD 2>/dev/null || true)"
fi

test_summary="compileall passed; bash -n passed; model checksums passed; wheelhouse verification passed; pytest passed"
RELEASE_VERSION="${VERSION}" \
BUILD_TIMESTAMP_UTC="${TIMESTAMP}" \
INCLUDED_FILES_COUNT="${included_count}" \
ARCHIVE_SHA256="${archive_sha}" \
GIT_COMMIT="${git_commit}" \
TEST_SUMMARY="${test_summary}" \
MANIFEST_FILE="${MANIFEST_FILE}" \
"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import json
import os
import platform
import socket
from pathlib import Path

host_id = socket.gethostname().split(".")[0]
manifest = {
    "product_name": "City Skyline Edge",
    "release_version": os.environ["RELEASE_VERSION"],
    "build_timestamp_utc": os.environ["BUILD_TIMESTAMP_UTC"],
    "python_minimum_version": "3.10",
    "target_os": "Ubuntu 22.04",
    "target_architecture": "x86_64",
    "ptz_dry_run_default": True,
    "api_default_host": "127.0.0.1",
    "api_default_port": 18080,
    "included_files_count": int(os.environ["INCLUDED_FILES_COUNT"]),
    "archive_sha256": os.environ["ARCHIVE_SHA256"],
    "git_commit": os.environ["GIT_COMMIT"] or None,
    "build_host_identifier": host_id,
    "build_machine_architecture": platform.machine(),
    "test_summary": os.environ["TEST_SUMMARY"],
    "release_status": "pilot",
    "includes_offline_wheelhouse": True,
    "includes_model_pack": True,
}
Path(os.environ["MANIFEST_FILE"]).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

tar -tzf "${ARCHIVE}" >/dev/null

rm -rf "${STAGE_PARENT}"

echo "[PASS] USB pilot release archive created:"
echo "${ARCHIVE}"
echo "[PASS] SHA256: ${archive_sha}"
echo "[PASS] Manifest: ${MANIFEST_FILE}"
echo "[PASS] Inventory: ${INVENTORY_FILE}"
