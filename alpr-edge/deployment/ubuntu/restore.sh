#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/common.sh"

require_root
ensure_private_umask

archive="${1:-}"
ASSUME_YES="${ASSUME_YES:-false}"
if [[ -z "${archive}" || ! -f "${archive}" ]]; then
  status_line "FAIL" "Usage: sudo $0 /path/to/backup.tar.gz"
  exit 1
fi

if ! tar -tzf "${archive}" >/dev/null; then
  status_line "FAIL" "Archive verification failed"
  exit 1
fi

if [[ "${ASSUME_YES}" != "true" ]]; then
  read -r -p "Restore ${archive} over current station config/data? [y/N] " answer
  if [[ "${answer}" != "y" && "${answer}" != "Y" ]]; then
    status_line "WARN" "Restore cancelled"
    exit 0
  fi
fi

if systemctl is-active --quiet "${SERVICE_NAME}.target"; then
  systemctl stop "${SERVICE_NAME}.target"
  status_line "PASS" "Stopped ${SERVICE_NAME}.target"
fi

"${SCRIPT_DIR}/backup.sh" || status_line "WARN" "Rollback backup could not be created"

stage="$(mktemp -d)"
trap 'rm -rf "${stage}"' EXIT
tar -C "${stage}" -xzf "${archive}"

if [[ -f "${stage}/config/edge.env" ]]; then
  install -d -o root -g "${SERVICE_GROUP}" -m 0750 "${CONFIG_DIR}"
  install -o root -g "${SERVICE_GROUP}" -m 0640 "${stage}/config/edge.env" "${ENV_FILE}"
fi

for dir_name in sqlite snapshots queue models; do
  if [[ -d "${stage}/data/${dir_name}" ]]; then
    rm -rf "${DATA_DIR:?}/${dir_name}"
    install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0750 "${DATA_DIR}/${dir_name}"
    tar -C "${stage}/data/${dir_name}" -cf - . | tar -C "${DATA_DIR}/${dir_name}" -xf -
  fi
done

maybe_chown_runtime
status_line "PASS" "Restore completed. Start the service manually after review."
