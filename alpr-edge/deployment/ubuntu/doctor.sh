#!/usr/bin/env bash
set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/common.sh"

critical_failures=0
load_edge_env

pass() { status_line "PASS" "$1"; }
warn() { status_line "WARN" "$1"; }
fail() { status_line "FAIL" "$1"; critical_failures=$((critical_failures + 1)); }

check_os() {
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${VERSION_ID:-}" in
      22.04|24.04) pass "Operating system: ${PRETTY_NAME:-Ubuntu ${VERSION_ID}}" ;;
      *) warn "Operating system is not Ubuntu 22.04/24.04: ${PRETTY_NAME:-unknown}" ;;
    esac
  else
    warn "Cannot read /etc/os-release"
  fi
}

check_python() {
  if python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
  then
    pass "Python version: $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  else
    fail "Python 3.10 or newer is required"
  fi
}

check_host_resources() {
  local arch
  arch="$(uname -m)"
  if [[ "${arch}" == "x86_64" ]]; then
    pass "CPU architecture: ${arch}"
  else
    warn "CPU architecture is ${arch}; pilot wheelhouse targets x86_64"
  fi
  local mem_kb
  mem_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || printf '0')"
  if [[ "${mem_kb}" -ge 1900000 ]]; then
    pass "Available RAM: $((mem_kb / 1024)) MB"
  else
    warn "Available RAM appears low: $((mem_kb / 1024)) MB"
  fi
  local disk_kb
  disk_kb="$(df -Pk "${DATA_DIR%/*}" 2>/dev/null | awk 'NR==2 {print $4}' || printf '0')"
  if [[ "${disk_kb}" -ge 5242880 ]]; then
    pass "Available disk near runtime path: $((disk_kb / 1024)) MB"
  else
    warn "Available disk near runtime path appears low: $((disk_kb / 1024)) MB"
  fi
}

check_time() {
  pass "Local time: $(date)"
  local timezone
  timezone="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
  if [[ "${timezone}" == "Asia/Dushanbe" ]]; then
    pass "Timezone: Asia/Dushanbe"
  else
    warn "Timezone is ${timezone:-unknown}; expected Asia/Dushanbe"
  fi
  local ntp synchronized
  ntp="$(timedatectl show -p NTP --value 2>/dev/null || true)"
  synchronized="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || true)"
  if [[ "${ntp}" == "yes" && "${synchronized}" == "yes" ]]; then
    pass "NTP enabled and synchronized"
  else
    fail "NTP not synchronized"
  fi
}

camera_host() {
  if [[ -n "${CAMERA_LOCAL_IP:-}" ]]; then
    printf '%s\n' "${CAMERA_LOCAL_IP}"
    return 0
  fi
  python3 - <<'PY' 2>/dev/null
import os
from urllib.parse import urlsplit
print(urlsplit(os.getenv("RTSP_URL", "")).hostname or "")
PY
}

rtsp_port() {
  python3 - <<'PY' 2>/dev/null
import os
from urllib.parse import urlsplit
print(urlsplit(os.getenv("RTSP_URL", "")).port or 554)
PY
}

check_camera_network() {
  local host port
  host="$(camera_host)"
  port="$(rtsp_port)"
  if [[ -z "${host}" ]]; then
    warn "Camera IP/RTSP host not configured"
    return 0
  fi
  if ping -c 1 -W 2 "${host}" >/dev/null 2>&1; then
    pass "Camera host reachable"
  else
    warn "Camera host did not respond to ping: ${host}"
  fi
  if timeout 5 bash -c ":</dev/tcp/${host}/${port}" >/dev/null 2>&1; then
    pass "RTSP TCP port reachable"
  else
    warn "RTSP TCP port not reachable: ${host}:${port}"
  fi
}

check_video_frame() {
  if [[ -z "${RTSP_URL:-}" ]]; then
    warn "RTSP_URL not configured; video decode skipped"
    return 0
  fi
  local result
  if result="$(python3 - <<'PY' 2>/dev/null
import os
import sys
import cv2

url = os.environ["RTSP_URL"]
transport = os.getenv("RTSP_TRANSPORT", "tcp")
previous = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{transport}"
try:
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, float(os.getenv("RTSP_CONNECT_TIMEOUT_SECONDS", "10")) * 1000)
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, float(os.getenv("RTSP_READ_TIMEOUT_SECONDS", "10")) * 1000)
    ok, frame = cap.read()
    if not ok or frame is None or getattr(frame, "size", 0) == 0:
        raise RuntimeError("no decoded frame")
    height, width = frame.shape[:2]
    print(f"{width}x{height}")
finally:
    try:
        cap.release()
    except Exception:
        pass
    if previous is None:
        os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
    else:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = previous
PY
  )" && [[ -n "${result}" ]]; then
    pass "Video frame decoded: ${result}"
  else
    fail "Video frame could not be decoded"
  fi
}

check_writes() {
  local snapshot_dir="${SNAPSHOT_DIR:-${DATA_DIR}/snapshots}"
  if write_probe_file "${snapshot_dir}" 2>/dev/null; then
    pass "Snapshot directory writable"
  else
    fail "Snapshot directory is not writable"
  fi

  local db_path="${EDGE_DATABASE_PATH:-${DATA_DIR}/sqlite/edge_config.db}"
  if EDGE_DATABASE_PATH="${db_path}" python3 - <<'PY' >/dev/null 2>&1
import os
import sqlite3
from pathlib import Path
db = Path(os.environ["EDGE_DATABASE_PATH"])
db.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(db) as connection:
    connection.execute("CREATE TABLE IF NOT EXISTS doctor_probe (id INTEGER PRIMARY KEY, checked_at TEXT)")
    connection.execute("INSERT INTO doctor_probe (checked_at) VALUES (datetime('now'))")
    connection.execute("DELETE FROM doctor_probe")
PY
  then
    pass "SQLite write succeeded"
  else
    fail "SQLite write failed"
  fi
}

check_local_api() {
  local host="${EDGE_API_HOST:-127.0.0.1}"
  local port="${EDGE_API_PORT:-18080}"
  if [[ "${host}" != "127.0.0.1" && "${host}" != "localhost" ]]; then
    fail "EDGE_API_HOST is ${host}; expected 127.0.0.1"
  else
    pass "Local API bind host: ${host}"
  fi
  if command -v curl >/dev/null 2>&1 && curl -fsS "http://${host}:${port}/api/v1/health" >/dev/null 2>&1; then
    pass "Local API available on ${host}:${port}"
  else
    warn "Local API is not currently reachable on ${host}:${port}"
  fi
}

check_ptz() {
  if [[ "${PTZ_DRY_RUN:-true}" == "true" ]]; then
    pass "PTZ dry-run enabled"
  else
    fail "PTZ_DRY_RUN is not true"
  fi
  if [[ -n "${ONVIF_HOST:-}" ]]; then
    warn "ONVIF host configured; real PTZ movement still blocked while PTZ_DRY_RUN=true"
  else
    warn "ONVIF not configured"
  fi
}

check_tailnet() {
  if command -v headscale >/dev/null 2>&1; then
    headscale version >/dev/null 2>&1 && pass "Headscale command available" || warn "Headscale command exists but is not healthy"
  elif command -v tailscale >/dev/null 2>&1; then
    tailscale status >/dev/null 2>&1 && pass "Tailscale connectivity available" || warn "Tailscale command exists but is not connected"
  else
    warn "Headscale/Tailscale command not installed"
  fi
}

check_dns_internet() {
  if getent hosts example.com >/dev/null 2>&1; then
    pass "DNS resolution works"
  else
    warn "DNS resolution failed"
  fi
  if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 5 https://example.com >/dev/null 2>&1; then
    pass "Internet HTTPS connectivity works"
  else
    warn "Internet HTTPS connectivity failed"
  fi
}

check_queue_depth() {
  local queue_dir="${QUEUE_DIR:-${DATA_DIR}/queue}"
  local count=0
  if [[ -d "${queue_dir}" ]]; then
    count="$(find "${queue_dir}" -maxdepth 1 -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
  fi
  pass "Current queue depth: ${count}"
}

check_alpr_runtime() {
  if python3 - <<'PY' >/dev/null 2>&1
import onnxruntime
PY
  then
    pass "ONNX Runtime import works"
  else
    fail "ONNX Runtime import failed"
  fi
  if python3 - <<'PY' >/dev/null 2>&1
from rapidocr_onnxruntime import RapidOCR
RapidOCR()
PY
  then
    pass "RapidOCR engine loads"
  else
    fail "RapidOCR engine load failed"
  fi
}

check_redacted_config() {
  if [[ "${DOCTOR_SHOW_CONFIG:-false}" == "true" ]]; then
    redacted_env_summary
  else
    redacted_env_summary >/dev/null
  fi
  pass "Configuration summary redaction available"
}

if [[ "${DOCTOR_SKIP_HOST_CHECKS:-false}" != "true" ]]; then
  check_os
  check_python
  check_host_resources
  check_time
fi
check_camera_network
check_video_frame
check_writes
check_local_api
check_ptz
check_tailnet
check_dns_internet
check_queue_depth
check_alpr_runtime
check_redacted_config

if [[ "${critical_failures}" -gt 0 ]]; then
  status_line "FAIL" "Doctor completed with ${critical_failures} critical failure(s)"
  exit 1
fi
status_line "PASS" "Doctor completed without critical failures"
