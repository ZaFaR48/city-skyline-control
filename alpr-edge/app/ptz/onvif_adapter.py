from __future__ import annotations

from app.ptz.models import PTZActionResult, PTZPresetRead


class ONVIFPTZAdapter:
    """Skeleton for future real ONVIF PTZ support.

    Real movement is intentionally disabled in this MVP. Production enablement
    must require explicit configuration, credentials, operator approval, and
    secret-safe logging.
    """

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def _disabled(self, action: str, preset_id: str | None = None) -> PTZActionResult:
        return PTZActionResult(
            action=action,
            preset_id=preset_id,
            dry_run=False,
            physical_camera_moved=False,
            message="Real ONVIF PTZ movement is disabled in this MVP.",
        )

    def list_presets(self) -> list[dict]:
        return []

    def get_status(self) -> dict:
        return {"enabled": self.enabled, "physical_camera_moved": False}

    def create_preset(self, preset: PTZPresetRead) -> PTZActionResult:
        return self._disabled("create_preset", preset.id)

    def update_preset(self, preset: PTZPresetRead) -> PTZActionResult:
        return self._disabled("update_preset", preset.id)

    def goto_preset(self, preset: PTZPresetRead) -> PTZActionResult:
        return self._disabled("goto_preset", preset.id)

    def stop_movement(self) -> PTZActionResult:
        return self._disabled("stop_movement")

    def get_capabilities(self) -> dict:
        return {"enabled": self.enabled, "physical_camera_moved": False}
