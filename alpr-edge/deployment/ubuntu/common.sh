#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-city-skyline-edge}"
SERVICE_USER="${SERVICE_USER:-cityedge}"
SERVICE_GROUP="${SERVICE_GROUP:-cityedge}"
INSTALL_DIR="${INSTALL_DIR:-/opt/city-skyline-edge}"
DATA_DIR="${DATA_DIR:-/var/lib/city-skyline-edge}"
CONFIG_DIR="${CONFIG_DIR:-/etc/city-skyline-edge}"
ENV_FILE="${ENV_FILE:-${CONFIG_DIR}/edge.env}"
BACKUP_DIR="${BACKUP_DIR:-${DATA_DIR}/backups}"
LOG_DIR="${LOG_DIR:-${DATA_DIR}/logs}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

status_line() {
  local level="$1"
  local message="$2"
  printf '[%s] %s\n' "$level" "$message"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    status_line "FAIL" "This command must be run with sudo/root."
    exit 1
  fi
}

load_edge_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "${ENV_FILE}"
    set +a
  fi
}

ensure_private_umask() {
  umask 027
}

redact_text() {
  sed -E \
    -e 's#(rtsp://)([^/@:]+)(:([^/@]+))?@#\1***:***@#g' \
    -e 's#(https?://)([^/@:]+)(:([^/@]+))?@#\1***:***@#g' \
    -e 's#^([[:space:]]*(RTSP_URL|ONVIF_PASSWORD|ONVIF_USERNAME|CENTRAL_API_TOKEN|API_TOKEN|TOKEN|PASSWORD|SECRET)[[:space:]]*=[[:space:]]*).*$#\1***#Ig' \
    -e 's#(token|password|secret)=([^&[:space:]]+)#\1=***#Ig'
}

redacted_env_summary() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    status_line "WARN" "Environment file not found: ${ENV_FILE}"
    return 0
  fi
  grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}" 2>/dev/null | redact_text || true
}

copy_tree_to_install_dir() {
  local source_dir="${1:-${REPO_DIR}}"
  mkdir -p "${INSTALL_DIR}"
  tar \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    -C "${source_dir}" -cf - . | tar -C "${INSTALL_DIR}" -xf -
}

maybe_chown_runtime() {
  if id "${SERVICE_USER}" >/dev/null 2>&1; then
    chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${DATA_DIR}"
  fi
}

write_probe_file() {
  local dir="$1"
  mkdir -p "${dir}"
  local probe="${dir}/.write-test.$$"
  printf 'ok\n' > "${probe}"
  rm -f "${probe}"
}
