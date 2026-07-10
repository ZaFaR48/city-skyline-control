#!/usr/bin/env bash
set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/common.sh"

critical_failures=0
pass() { status_line "PASS" "$1"; }
warn() { status_line "WARN" "$1"; }
fail() { status_line "FAIL" "$1"; critical_failures=$((critical_failures + 1)); }

[[ -d "${INSTALL_DIR}" ]] && pass "Install directory exists" || fail "Install directory missing: ${INSTALL_DIR}"
[[ -x "${INSTALL_DIR}/.venv/bin/python" ]] && pass "Virtual environment exists" || fail "Virtual environment missing"
[[ -f "${ENV_FILE}" ]] && pass "Environment file exists" || fail "Environment file missing: ${ENV_FILE}"

if [[ -f "${ENV_FILE}" ]]; then
  perms="$(stat -c '%a %U %G' "${ENV_FILE}" 2>/dev/null || true)"
  [[ "${perms}" == "640 root ${SERVICE_GROUP}" ]] && pass "Environment file permissions: ${perms}" || warn "Environment file permissions are ${perms}; expected 640 root ${SERVICE_GROUP}"
fi

for unit in "${SERVICE_NAME}.target" "${SERVICE_NAME}-api.service" "${SERVICE_NAME}-worker.service"; do
  path="/etc/systemd/system/${unit}"
  [[ -f "${path}" ]] && pass "Systemd unit installed: ${unit}" || warn "Systemd unit not installed at ${path}"
done

if [[ -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
  if "${INSTALL_DIR}/.venv/bin/python" - <<'PY' >/dev/null 2>&1
from app.config import load_config
from app.api.main import create_app
load_config()
create_app()
PY
  then
    pass "Python import/API smoke test passed"
  else
    fail "Python import/API smoke test failed"
  fi
fi

if [[ -f "${ENV_FILE}" ]] && grep -q '^EDGE_API_HOST=127\.0\.0\.1$' "${ENV_FILE}"; then
  pass "Local API configured for localhost"
else
  warn "EDGE_API_HOST is not explicitly 127.0.0.1"
fi

if [[ -f "${ENV_FILE}" ]] && grep -q '^PTZ_DRY_RUN=true$' "${ENV_FILE}"; then
  pass "PTZ dry-run configured"
else
  fail "PTZ_DRY_RUN is not true"
fi

if [[ "${critical_failures}" -gt 0 ]]; then
  status_line "FAIL" "Installation verification failed"
  exit 1
fi
status_line "PASS" "Installation verification completed"
