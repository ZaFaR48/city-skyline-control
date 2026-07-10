#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEELHOUSE="${ROOT_DIR}/wheelhouse-py310-linux-x86_64"

rm -rf "${WHEELHOUSE}"
mkdir -p "${WHEELHOUSE}"

python3 -m pip download \
  --only-binary=:all: \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 310 \
  --abi cp310 \
  --dest "${WHEELHOUSE}" \
  -r "${ROOT_DIR}/requirements.txt"

"${ROOT_DIR}/scripts/verify_offline_wheelhouse.sh" "${WHEELHOUSE}"
