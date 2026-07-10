from __future__ import annotations

from app.ptz.models import PatrolPlanRead, PatrolSimulation


def simulate_patrol(plan: PatrolPlanRead) -> PatrolSimulation:
    enabled_steps = sorted(
        [step for step in plan.steps if step.enabled],
        key=lambda step: (step.order, step.priority),
    )
    total_ms = sum(step.settle_time_ms + step.dwell_time_ms for step in enabled_steps)
    cycle_seconds = total_ms / 1000.0
    warnings: list[str] = []

    if not enabled_steps:
        warnings.append("No enabled patrol steps configured.")
    if cycle_seconds > 60:
        warnings.append("Patrol cycle exceeds 60 seconds; detection and billing timestamps may be delayed.")
    if plan.home_preset_id is None:
        warnings.append("No Home preset is assigned to this patrol plan.")

    return PatrolSimulation(
        step_count=len(enabled_steps),
        estimated_complete_cycle_seconds=cycle_seconds,
        estimated_maximum_detection_delay_seconds=cycle_seconds,
        warnings=warnings,
    )
