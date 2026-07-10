#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
uvicorn app.api.main:app --host "${EDGE_API_HOST:-127.0.0.1}" --port "${EDGE_API_PORT:-18080}"
