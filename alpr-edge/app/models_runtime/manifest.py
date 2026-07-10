from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelManifestEntry:
    name: str
    role: str
    path: str
    sha256: str
    source_url: str
    license: str
    version: str


def load_manifest(path: Path) -> list[ModelManifestEntry]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("models", data if isinstance(data, list) else [])
    return [ModelManifestEntry(**entry) for entry in entries]
