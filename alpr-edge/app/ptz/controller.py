from __future__ import annotations

from app.ptz.dry_run_adapter import DryRunPTZAdapter
from app.ptz.models import PTZActionResult, PTZPresetRead
from app.ptz.onvif_adapter import ONVIFPTZAdapter


class PTZController:
    def __init__(self, dry_run: bool = True) -> None:
        self.adapter = DryRunPTZAdapter() if dry_run else ONVIFPTZAdapter(enabled=False)

    def goto_preset(self, preset: PTZPresetRead) -> PTZActionResult:
        return self.adapter.goto_preset(preset)

    def stop_movement(self) -> PTZActionResult:
        return self.adapter.stop_movement()

    def get_status(self) -> dict:
        return self.adapter.get_status()

    def get_capabilities(self) -> dict:
        return self.adapter.get_capabilities()
