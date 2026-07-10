#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/common.sh"

require_root
ensure_private_umask

PYTHON_BIN="${PYTHON_BIN:-python3}"
SOURCE_DIR="${SOURCE_DIR:-${REPO_DIR}}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"

status_line "PASS" "Preparing City Skyline Edge installation at ${INSTALL_DIR}"

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --home-dir "${DATA_DIR}" --shell /usr/sbin/nologin "${SERVICE_USER}"
  status_line "PASS" "Created system user ${SERVICE_USER}"
else
  status_line "PASS" "System user ${SERVICE_USER} already exists"
fi

install -d -o root -g "${SERVICE_GROUP}" -m 0750 "${CONFIG_DIR}"
for dir in sqlite frames snapshots queue logs backups models; do
  install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0750 "${DATA_DIR}/${dir}"
done

copy_tree_to_install_dir "${SOURCE_DIR}"
chown -R root:root "${INSTALL_DIR}"
find "${INSTALL_DIR}/deployment/ubuntu" -type f -name '*.sh' -exec chmod 0755 {} \;
chmod 0755 "${INSTALL_DIR}/scripts/run_api.sh" "${INSTALL_DIR}/scripts/run_edge.sh" "${INSTALL_DIR}/scripts/run_worker.sh"

if [[ -f "${ENV_FILE}" ]]; then
  status_line "WARN" "Keeping existing environment file: ${ENV_FILE}"
else
  install -o root -g "${SERVICE_GROUP}" -m 0640 \
    "${INSTALL_DIR}/deployment/systemd/city-skyline-edge.env.example" "${ENV_FILE}"
  status_line "PASS" "Created environment file from example: ${ENV_FILE}"
fi
chmod 0640 "${ENV_FILE}"
chown root:"${SERVICE_GROUP}" "${ENV_FILE}"

if ! "${PYTHON_BIN}" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  status_line "FAIL" "Python 3.10 or newer is required."
  exit 1
fi
status_line "PASS" "Python version is compatible"

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

"${INSTALL_DIR}/.venv/bin/python" - <<'PY'
from app.config import load_config
from app.database.migrations import run_migrations
print("import smoke test ok")
PY
status_line "PASS" "Python import smoke test completed"

for unit in city-skyline-edge-api.service city-skyline-edge-worker.service city-skyline-edge.target; do
  install -o root -g root -m 0644 \
    "${INSTALL_DIR}/deployment/systemd/${unit}" \
    "${SYSTEMD_DIR}/${unit}"
done
status_line "PASS" "Installed systemd API, worker and target templates"

maybe_chown_runtime

cat <<'TEXT'

Installation files are prepared. The service has not been enabled or started.

Review and edit:
  sudo nano /etc/city-skyline-edge/edge.env

Then, when ready on the mini PC:
  sudo systemctl daemon-reload
  sudo systemctl enable --now city-skyline-edge.target
TEXT
