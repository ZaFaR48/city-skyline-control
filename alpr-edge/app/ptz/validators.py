from __future__ import annotations

from app.ptz.models import PatrolPlanWrite, PresetType, PTZPresetCreate, PTZPresetPatch


def home_priority_values() -> tuple[int, int]:
    return (0, 0)


def normalize_home_preset(payload: PTZPresetCreate | PTZPresetPatch) -> None:
    if getattr(payload, "preset_type", None) == PresetType.HOME:
        payload.priority, payload.sort_order = home_priority_values()


def validate_patrol_plan(plan: PatrolPlanWrite) -> None:
    orders = [step.order for step in plan.steps]
    if len(orders) != len(set(orders)):
        raise ValueError("patrol step order values must be unique")
