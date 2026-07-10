#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/common.sh"

require_root

ASSUME_YES="${ASSUME_YES:-false}"
REMOVE_DATA="${REMOVE_DATA:-false}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"

confirm() {
  local prompt="$1"
  if [[ "${ASSUME_YES}" == "true" ]]; then
    return 0
  fi
  read -r -p "${prompt} [y/N] " answer
  [[ "${answer}" == "y" || "${answer}" == "Y" ]]
}

systemctl stop "${SERVICE_NAME}.target" "${SERVICE_NAME}-api.service" "${SERVICE_NAME}-worker.service" || true
systemctl disable "${SERVICE_NAME}.target" "${SERVICE_NAME}-api.service" "${SERVICE_NAME}-worker.service" || true

rm -f \
  "${SYSTEMD_DIR}/${SERVICE_NAME}.target" \
  "${SYSTEMD_DIR}/${SERVICE_NAME}-api.service" \
  "${SYSTEMD_DIR}/${SERVICE_NAME}-worker.service" \
  "${SYSTEMD_DIR}/${SERVICE_NAME}.service"
systemctl daemon-reload || true

if confirm "Remove application files from ${INSTALL_DIR}?"; then
  rm -rf "${INSTALL_DIR}"
  status_line "PASS" "Removed application files"
fi

if [[ "${REMOVE_DATA}" == "true" ]] && confirm "Remove runtime data from ${DATA_DIR}?"; then
  rm -rf "${DATA_DIR}"
  status_line "PASS" "Removed runtime data"
else
  status_line "WARN" "Runtime data preserved at ${DATA_DIR}"
fi

if confirm "Remove configuration from ${CONFIG_DIR}?"; then
  rm -rf "${CONFIG_DIR}"
  status_line "PASS" "Removed configuration"
else
  status_line "WARN" "Configuration preserved at ${CONFIG_DIR}"
fi

status_line "PASS" "Uninstall routine completed"
