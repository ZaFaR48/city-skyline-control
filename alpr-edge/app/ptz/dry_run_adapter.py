from __future__ import annotations

import logging

from app.ptz.models import PTZActionResult, PTZPresetRead

logger = logging.getLogger(__name__)


class DryRunPTZAdapter:
    def list_presets(self) -> list[dict]:
        logger.info("Dry-run PTZ list_presets requested")
        return []

    def get_status(self) -> dict:
        logger.info("Dry-run PTZ status requested")
        return {
            "dry_run": True,
            "physical_camera_moved": False,
            "status": "not_connected",
        }

    def create_preset(self, preset: PTZPresetRead) -> PTZActionResult:
        logger.info("Dry-run PTZ create_preset requested for preset_id=%s", preset.id)
        return PTZActionResult(
            action="create_preset",
            preset_id=preset.id,
            dry_run=True,
            physical_camera_moved=False,
            message="Dry-run only; ONVIF preset was not created on the physical camera.",
        )

    def update_preset(self, preset: PTZPresetRead) -> PTZActionResult:
        logger.info("Dry-run PTZ update_preset requested for preset_id=%s", preset.id)
        return PTZActionResult(
            action="update_preset",
            preset_id=preset.id,
            dry_run=True,
            physical_camera_moved=False,
            message="Dry-run only; ONVIF preset was not updated on the physical camera.",
        )

    def goto_preset(self, preset: PTZPresetRead) -> PTZActionResult:
        logger.info("Dry-run PTZ goto_preset requested for preset_id=%s", preset.id)
        return PTZActionResult(
            action="goto_preset",
            preset_id=preset.id,
            dry_run=True,
            physical_camera_moved=False,
            message="Dry-run only; physical camera movement was not executed.",
        )

    def stop_movement(self) -> PTZActionResult:
        logger.info("Dry-run PTZ stop_movement requested")
        return PTZActionResult(
            action="stop_movement",
            dry_run=True,
            physical_camera_moved=False,
            message="Dry-run only; physical camera stop command was not executed.",
        )

    def get_capabilities(self) -> dict:
        return {
            "dry_run": True,
            "physical_camera_moved": False,
            "ptz": True,
            "presets": True,
            "patrol": False,
        }
