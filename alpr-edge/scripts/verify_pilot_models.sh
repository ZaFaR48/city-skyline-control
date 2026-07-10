#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${1:-${ROOT_DIR}/models-pilot}"

if [[ ! -f "${MODEL_DIR}/manifest.json" || ! -f "${MODEL_DIR}/SHA256SUMS" ]]; then
  echo "[FAIL] Model manifest or SHA256SUMS missing in ${MODEL_DIR}" >&2
  exit 1
fi

(
  cd "${MODEL_DIR}"
  sha256sum -c SHA256SUMS
)

python3 - <<PY
import json
from pathlib import Path
data = json.loads(Path("${MODEL_DIR}/manifest.json").read_text())
models = data.get("models", [])
if not models:
    raise SystemExit("[FAIL] manifest contains no models")
for model in models:
    for key in ["name", "role", "path", "sha256", "source_url", "license", "version"]:
        if not model.get(key):
            raise SystemExit(f"[FAIL] model manifest missing {key}")
print("[PASS] Model manifest and checksums verified")
PY
