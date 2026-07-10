from __future__ import annotations

from app.ptz.models import PresetType, PTZPresetCreate, PTZPresetPatch


def enforce_home_defaults(payload: PTZPresetCreate | PTZPresetPatch) -> None:
    if getattr(payload, "preset_type", None) == PresetType.HOME:
        payload.priority = 0
        payload.sort_order = 0
