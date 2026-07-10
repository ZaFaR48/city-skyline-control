#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/common.sh"

ensure_private_umask
load_edge_env

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="${BACKUP_DIR}/${SERVICE_NAME}-backup-${timestamp}.tar.gz"
stage="$(mktemp -d)"
trap 'rm -rf "${stage}"' EXIT

mkdir -p "${BACKUP_DIR}" "${stage}/config" "${stage}/data" "${stage}/metadata"

if [[ -f "${ENV_FILE}" ]]; then
  cp -p "${ENV_FILE}" "${stage}/config/edge.env"
  redacted_env_summary > "${stage}/metadata/edge.env.redacted.txt"
else
  status_line "WARN" "Environment file not found: ${ENV_FILE}"
fi

db_path="${EDGE_DATABASE_PATH:-${DATA_DIR}/sqlite/edge_config.db}"
if [[ -f "${db_path}" ]]; then
  mkdir -p "${stage}/data/sqlite"
  cp -p "${db_path}" "${stage}/data/sqlite/edge_config.db"
  for suffix in -wal -shm; do
    [[ -f "${db_path}${suffix}" ]] && cp -p "${db_path}${suffix}" "${stage}/data/sqlite/edge_config.db${suffix}"
  done
else
  status_line "WARN" "SQLite database not found: ${db_path}"
fi

for dir_name in snapshots queue models; do
  source_dir="${DATA_DIR}/${dir_name}"
  if [[ -d "${source_dir}" ]]; then
    mkdir -p "${stage}/data/${dir_name}"
    tar -C "${source_dir}" -cf - . | tar -C "${stage}/data/${dir_name}" -xf -
  fi
done

{
  printf 'created_at_utc=%s\n' "${timestamp}"
  printf 'service_name=%s\n' "${SERVICE_NAME}"
  printf 'install_dir=%s\n' "${INSTALL_DIR}"
  printf 'data_dir=%s\n' "${DATA_DIR}"
} > "${stage}/metadata/backup.txt"

tar -C "${stage}" -czf "${archive}" .
chmod 0640 "${archive}"
status_line "PASS" "Backup archive created: ${archive}"
