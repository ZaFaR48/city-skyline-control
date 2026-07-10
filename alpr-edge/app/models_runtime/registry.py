from __future__ import annotations

from pathlib import Path

from app.models_runtime.checksums import verify_sha256
from app.models_runtime.manifest import ModelManifestEntry, load_manifest


class ModelRegistry:
    def __init__(self, manifest_path: Path | None) -> None:
        self.manifest_path = manifest_path
        self.entries = load_manifest(manifest_path) if manifest_path else []

    def find(self, role: str) -> ModelManifestEntry | None:
        for entry in self.entries:
            if entry.role == role:
                return entry
        return None

    def validate(self, role: str, base_dir: Path) -> dict:
        entry = self.find(role)
        if entry is None:
            return {"role": role, "configured": False, "valid": False, "reason": "manifest entry missing"}
        model_path = (base_dir / entry.path).resolve()
        if not model_path.exists():
            return {"role": role, "configured": True, "valid": False, "reason": "model file missing", "name": entry.name}
        valid = verify_sha256(model_path, entry.sha256)
        return {
            "role": role,
            "configured": True,
            "valid": valid,
            "reason": "ok" if valid else "sha256 mismatch",
            "name": entry.name,
            "version": entry.version,
            "license": entry.license,
        }
