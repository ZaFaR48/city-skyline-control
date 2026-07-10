from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PresetType(str, Enum):
    HOME = "home"
    ENTRANCE = "entrance"
    EXIT = "exit"
    PARKING = "parking"
    NO_PARKING = "no_parking"
    DISABLED = "disabled"
    SERVICE = "service"


class PTZPresetBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera_id: str = Field(default="CAM-001", min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    onvif_preset_token: str | None = None
    preset_type: PresetType = PresetType.PARKING
    pan: float | None = None
    tilt: float | None = None
    zoom: float | None = None
    focus: float | None = None
    enabled: bool = True
    priority: int = Field(default=100, ge=0)
    sort_order: int = Field(default=0, ge=0)
    settle_time_ms: int = Field(default=1500, ge=0)
    dwell_time_ms: int = Field(default=5000, ge=0)
    revisit_interval_seconds: int = Field(default=60, ge=0)
    reference_snapshot_path: str | None = None
    snapshot_width: int | None = Field(default=None, ge=1)
    snapshot_height: int | None = Field(default=None, ge=1)
    calibration_version: int = Field(default=1, ge=1)
    overlap_group: str | None = None
    deduplication_window_seconds: int = Field(default=60, ge=0)


class PTZPresetCreate(PTZPresetBase):
    pass


class PTZPresetPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera_id: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    onvif_preset_token: str | None = None
    preset_type: PresetType | None = None
    pan: float | None = None
    tilt: float | None = None
    zoom: float | None = None
    focus: float | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)
    settle_time_ms: int | None = Field(default=None, ge=0)
    dwell_time_ms: int | None = Field(default=None, ge=0)
    revisit_interval_seconds: int | None = Field(default=None, ge=0)
    reference_snapshot_path: str | None = None
    snapshot_width: int | None = Field(default=None, ge=1)
    snapshot_height: int | None = Field(default=None, ge=1)
    calibration_version: int | None = Field(default=None, ge=1)
    overlap_group: str | None = None
    deduplication_window_seconds: int | None = Field(default=None, ge=0)


class PTZPresetRead(PTZPresetBase):
    id: str
    created_at: datetime
    updated_at: datetime


class PTZActionResult(BaseModel):
    action: str
    preset_id: str | None = None
    dry_run: bool
    physical_camera_moved: bool
    message: str


class PatrolStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    order: int = Field(ge=0)
    enabled: bool = True
    settle_time_ms: int = Field(default=1500, ge=0)
    dwell_time_ms: int = Field(default=5000, ge=0)
    capture_burst_count: int = Field(default=3, ge=1)
    revisit_interval_seconds: int = Field(default=60, ge=0)
    priority: int = Field(default=100, ge=0)


class PatrolPlanWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str = Field(default="Default Patrol", min_length=1, max_length=120)
    enabled: bool = True
    home_preset_id: str | None = None
    notes: str = ""
    steps: list[PatrolStep] = Field(default_factory=list)


class PatrolStepRead(PatrolStep):
    id: str
    patrol_plan_id: str
    created_at: datetime
    updated_at: datetime


class PatrolPlanRead(BaseModel):
    id: str
    name: str
    enabled: bool
    home_preset_id: str | None
    notes: str
    created_at: datetime
    updated_at: datetime
    steps: list[PatrolStepRead]


class PatrolSimulation(BaseModel):
    step_count: int
    estimated_complete_cycle_seconds: float
    estimated_maximum_detection_delay_seconds: float
    warnings: list[str]
    dry_run: bool = True
    physical_camera_moved: bool = False
