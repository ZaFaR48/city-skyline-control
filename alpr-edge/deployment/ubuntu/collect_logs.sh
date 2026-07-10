#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/common.sh"

ensure_private_umask
load_edge_env

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
support_dir="${LOG_DIR}/support-${timestamp}"
archive="${LOG_DIR}/${SERVICE_NAME}-support-${timestamp}.tar.gz"
mkdir -p "${support_dir}" "${LOG_DIR}"
trap 'rm -rf "${support_dir}"' EXIT

redacted_env_summary > "${support_dir}/config-redacted.txt" || true

if command -v systemctl >/dev/null 2>&1; then
  {
    systemctl status "${SERVICE_NAME}.target" --no-pager
    systemctl status "${SERVICE_NAME}-api.service" --no-pager
    systemctl status "${SERVICE_NAME}-worker.service" --no-pager
  } > "${support_dir}/systemd-status.txt" 2>&1 || true
fi

if command -v journalctl >/dev/null 2>&1; then
  journalctl \
    -u "${SERVICE_NAME}-api.service" \
    -u "${SERVICE_NAME}-worker.service" \
    --since "24 hours ago" --no-pager 2>&1 | redact_text > "${support_dir}/journal-24h-redacted.txt" || true
fi

"${SCRIPT_DIR}/doctor.sh" > "${support_dir}/doctor.txt" 2>&1 || true
df -h > "${support_dir}/disk-usage.txt" 2>&1 || true
du -sh "${DATA_DIR}"/* > "${support_dir}/runtime-dir-usage.txt" 2>&1 || true

if [[ -f "${INSTALL_DIR}/app/api/main.py" ]]; then
  grep -E '^VERSION = ' "${INSTALL_DIR}/app/api/main.py" > "${support_dir}/service-version.txt" || true
fi

if [[ -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
  "${INSTALL_DIR}/.venv/bin/python" --version > "${support_dir}/python-version.txt" 2>&1 || true
  "${INSTALL_DIR}/.venv/bin/python" -m pip freeze > "${support_dir}/python-packages.txt" 2>&1 || true
else
  python3 --version > "${support_dir}/python-version.txt" 2>&1 || true
fi

queue_dir="${QUEUE_DIR:-${DATA_DIR}/queue}"
{
  printf 'queue_dir=%s\n' "${queue_dir}"
  if [[ -d "${queue_dir}" ]]; then
    printf 'queue_depth=%s\n' "$(find "${queue_dir}" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' ')"
  else
    printf 'queue_depth=0\n'
  fi
} > "${support_dir}/queue-status.txt"

find "${support_dir}" -type f -exec sh -c 'for file do sed -E -i \
  -e "s#(rtsp://)([^/@:]+)(:([^/@]+))?@#\1***:***@#g" \
  -e "s#(https?://)([^/@:]+)(:([^/@]+))?@#\1***:***@#g" \
  -e "s#(token|password|secret)=([^&[:space:]]+)#\1=***#Ig" "$file"; done' sh {} +

tar -C "${support_dir}" -czf "${archive}" .
chmod 0640 "${archive}"
status_line "PASS" "Support archive created: ${archive}"
