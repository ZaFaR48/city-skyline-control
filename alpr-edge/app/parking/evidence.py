from __future__ import annotations

import hashlib
from pathlib import Path


def evidence_hash(path: str) -> str:
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return hashlib.sha256(path.encode("utf-8")).hexdigest()
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
