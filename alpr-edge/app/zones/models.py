from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.zones.validators import validate_polygon_points


class ZoneType(str, Enum):
    PAID_PARKING = "paid_parking"
    NO_PARKING = "no_parking"
    DISABLED_ONLY = "disabled_only"
    SERVICE = "service"
    ENTRANCE = "entrance"
    EXIT = "exit"
    LANE = "lane"
    IGNORE = "ignore"


class SlotType(str, Enum):
    NORMAL = "normal"
    DISABLED = "disabled"
    SERVICE = "service"
    RESERVED = "reserved"


class OccupancyStatus(str, Enum):
    UNKNOWN = "unknown"
    FREE = "free"
    OCCUPIED = "occupied"
    NEEDS_REVIEW = "needs_review"


class PolygonPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: Annotated[float, Field(ge=0.0, le=1.0)]
    y: Annotated[float, Field(ge=0.0, le=1.0)]


class PolygonZoneBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    zone_type: ZoneType
    polygon_points: list[PolygonPoint]
    priority: int = Field(default=100, ge=0)
    enabled: bool = True
    capacity: int = Field(default=0, ge=0)
    notes: str = ""
    overlap_group: str | None = None
    deduplication_window_seconds: int = Field(default=60, ge=0)

    @field_validator("polygon_points")
    @classmethod
    def validate_points(cls, value: list[PolygonPoint]) -> list[PolygonPoint]:
        validate_polygon_points([point.model_dump() for point in value])
        return value


class PolygonZoneCreate(PolygonZoneBase):
    pass


class PolygonZonePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    zone_type: ZoneType | None = None
    polygon_points: list[PolygonPoint] | None = None
    priority: int | None = Field(default=None, ge=0)
    enabled: bool | None = None
    capacity: int | None = Field(default=None, ge=0)
    notes: str | None = None
    overlap_group: str | None = None
    deduplication_window_seconds: int | None = Field(default=None, ge=0)

    @field_validator("polygon_points")
    @classmethod
    def validate_points(cls, value: list[PolygonPoint] | None) -> list[PolygonPoint] | None:
        if value is not None:
            validate_polygon_points([point.model_dump() for point in value])
        return value


class PolygonZoneRead(PolygonZoneBase):
    id: str
    created_at: datetime
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class ParkingSlotBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: str
    preset_id: str
    slot_code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    polygon_points: list[PolygonPoint]
    slot_type: SlotType = SlotType.NORMAL
    enabled: bool = True
    occupancy_status: OccupancyStatus = OccupancyStatus.UNKNOWN
    overlap_group: str | None = None
    deduplication_window_seconds: int = Field(default=60, ge=0)

    @field_validator("polygon_points")
    @classmethod
    def validate_points(cls, value: list[PolygonPoint]) -> list[PolygonPoint]:
        validate_polygon_points([point.model_dump() for point in value])
        return value


class ParkingSlotCreate(ParkingSlotBase):
    pass


class ParkingSlotPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_code: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    polygon_points: list[PolygonPoint] | None = None
    slot_type: SlotType | None = None
    enabled: bool | None = None
    occupancy_status: OccupancyStatus | None = None
    overlap_group: str | None = None
    deduplication_window_seconds: int | None = Field(default=None, ge=0)

    @field_validator("polygon_points")
    @classmethod
    def validate_points(cls, value: list[PolygonPoint] | None) -> list[PolygonPoint] | None:
        if value is not None:
            validate_polygon_points([point.model_dump() for point in value])
        return value


class ParkingSlotRead(ParkingSlotBase):
    id: str
    last_changed_at: datetime
    created_at: datetime
    updated_at: datetime
