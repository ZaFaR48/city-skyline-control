#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEELHOUSE="${1:-${ROOT_DIR}/wheelhouse-py310-linux-x86_64}"

if [[ ! -d "${WHEELHOUSE}" ]]; then
  echo "[FAIL] Wheelhouse not found: ${WHEELHOUSE}" >&2
  exit 1
fi

required=(
  "opencv_python"
  "onnxruntime"
  "rapidocr_onnxruntime"
  "fastapi"
  "uvicorn"
  "pydantic"
  "requests"
  "python_dotenv"
  "python_multipart"
)

for package in "${required[@]}"; do
  if ! find "${WHEELHOUSE}" -maxdepth 1 -type f -iname "${package}-*.whl" | grep -q .; then
    echo "[FAIL] Missing wheel for ${package}" >&2
    exit 1
  fi
done

if find "${WHEELHOUSE}" -maxdepth 1 -type f | grep -Ei 'cuda|gpu|tensorrt' >/dev/null; then
  echo "[FAIL] GPU/CUDA package found in CPU-only wheelhouse" >&2
  exit 1
fi

echo "[PASS] Offline wheelhouse has required CPU packages: ${WHEELHOUSE}"
