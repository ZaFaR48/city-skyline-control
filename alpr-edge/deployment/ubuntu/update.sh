#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/common.sh"

require_root
ensure_private_umask
load_edge_env

PYTHON_BIN="${PYTHON_BIN:-python3}"
SOURCE_DIR="${SOURCE_DIR:-${REPO_DIR}}"
was_running=false
rollback_archive="${BACKUP_DIR}/${SERVICE_NAME}-preupdate-files-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"

if systemctl is-active --quiet "${SERVICE_NAME}.target"; then
  was_running=true
fi

"${SCRIPT_DIR}/backup.sh"
tar -C "${INSTALL_DIR}" -czf "${rollback_archive}" .
chmod 0640 "${rollback_archive}"

rollback() {
  status_line "FAIL" "Update failed; attempting file rollback"
  rm -rf "${INSTALL_DIR:?}/"*
  tar -C "${INSTALL_DIR}" -xzf "${rollback_archive}"
  if [[ "${was_running}" == "true" ]]; then
    systemctl start "${SERVICE_NAME}" || true
  fi
}
trap rollback ERR

if [[ "${was_running}" == "true" ]]; then
  systemctl stop "${SERVICE_NAME}.target"
fi

copy_tree_to_install_dir "${SOURCE_DIR}"
chown -R root:root "${INSTALL_DIR}"
find "${INSTALL_DIR}/deployment/ubuntu" -type f -name '*.sh' -exec chmod 0755 {} \;
chmod 0755 "${INSTALL_DIR}/scripts/run_api.sh" "${INSTALL_DIR}/scripts/run_edge.sh" "${INSTALL_DIR}/scripts/run_worker.sh"

"${PYTHON_BIN}" -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip
if [[ -d "${INSTALL_DIR}/wheelhouse-py310-linux-x86_64" ]]; then
  "${INSTALL_DIR}/.venv/bin/python" -m pip install \
    --no-index \
    --find-links "${INSTALL_DIR}/wheelhouse-py310-linux-x86_64" \
    -r "${INSTALL_DIR}/requirements.txt"
else
  "${INSTALL_DIR}/.venv/bin/python" -m pip install -r "${INSTALL_DIR}/requirements.txt"
fi

ENV_FILE="${ENV_FILE}" "${INSTALL_DIR}/.venv/bin/python" - <<'PY'
from app.config import load_config
from app.database.connection import connect
from app.database.migrations import run_migrations
config = load_config()
with connect(config.edge_database_path) as connection:
    run_migrations(connection)
PY

"${INSTALL_DIR}/.venv/bin/python" -m compileall -q "${INSTALL_DIR}/app"
if [[ -d "${INSTALL_DIR}/tests" ]] && "${INSTALL_DIR}/.venv/bin/python" -m pytest --version >/dev/null 2>&1; then
  "${INSTALL_DIR}/.venv/bin/python" -m pytest -q "${INSTALL_DIR}/tests"
else
  "${INSTALL_DIR}/.venv/bin/python" - <<'PY'
from app.config import load_config
from app.api.main import create_app
load_config()
create_app()
PY
fi

trap - ERR
if [[ "${was_running}" == "true" ]]; then
  systemctl start "${SERVICE_NAME}.target"
fi
status_line "PASS" "Update completed"
