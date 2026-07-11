from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field

from .models import (
    AlertSeverity,
    AlertType,
    ApprovalStatus,
    DeviceType,
    EventSource,
    RegistrationStatus,
    Role,
    StationStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: int
    username: str
    email: EmailStr
    role: Role


class RegionOut(ORMModel):
    id: int
    code: str
    name: str
    region_type: str
    parent_id: int | None
    is_active: bool
    sort_order: int


class RegionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=128)
    region_type: str
    parent_id: int | None = None
    is_active: bool = False
    sort_order: int = 0


class StationCreate(BaseModel):
    station_code: str = Field(
        min_length=1,
        max_length=32,
        validation_alias=AliasChoices("station_code", "code"),
    )
    name: str = Field(min_length=1, max_length=128)
    city_id: int
    district_id: int | None = None
    address: str = Field(default="", max_length=255)
    latitude: float | None = Field(default=None, validation_alias=AliasChoices("latitude", "lat"))
    longitude: float | None = Field(default=None, validation_alias=AliasChoices("longitude", "lng"))
    vpn_ip: str | None = None
    local_ip: str | None = None
    rustdesk_id: str | None = None


class StationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    city_id: int | None = None
    district_id: int | None = None
    address: str | None = Field(default=None, max_length=255)
    latitude: float | None = None
    longitude: float | None = None
    vpn_ip: str | None = None
    local_ip: str | None = None
    rustdesk_id: str | None = None
    is_active: bool | None = None
    is_archived: bool | None = None


class StationOut(BaseModel):
    id: int
    station_code: str
    name: str
    city_id: int
    city: str
    district_id: int | None
    district: str | None
    address: str
    latitude: float | None
    longitude: float | None
    vpn_ip: str | None
    local_ip: str | None
    rustdesk_id: str | None
    status: StationStatus
    status_reason: str | None
    last_seen_at: datetime | None
    last_ping_at: datetime | None
    last_ping_ms: int | None
    offline_since: datetime | None
    cpu: int | None
    ram: int | None
    disk: int | None
    telemetry_at: datetime | None
    is_active: bool
    is_archived: bool
    monitoring_configured: bool
    headscale_linked: bool
    headscale_hostname: str | None
    cameras_total: int
    cameras_online: int
    active_alerts: int


class StationListOut(BaseModel):
    items: list[StationOut]
    total: int
    limit: int
    offset: int


class StationDetailOut(StationOut):
    headscale_node: HeadscaleNodeOut | None = None
    cameras: list[CameraOut] = []
    ping_history: list[PingPoint] = []
    open_alerts: list[AlertOut] = []
    status_timeline: list[StatusEventOut] = []
    audit_history: list[AuditLogOut] = []


class CameraCreate(BaseModel):
    station_id: int
    name: str
    ip: str
    rtsp_url: str
    ptz: bool = False
    resolution: str = "1920x1080"
    fps: int = 25


class CameraOut(ORMModel):
    id: int
    station_id: int
    name: str
    ip: str
    rtsp_url: str
    ptz: bool
    resolution: str
    fps: int
    status: StationStatus
    last_seen_at: datetime | None


class AlertOut(ORMModel):
    id: int
    station_id: int | None
    type: AlertType
    severity: AlertSeverity
    message: str
    acknowledged: bool
    acknowledged_at: datetime | None
    created_at: datetime
    resolved_at: datetime | None


class HeadscaleNodeOut(ORMModel):
    id: int
    hostname: str
    given_name: str | None
    vpn_ip: str | None
    online: bool
    first_seen_at: datetime
    last_seen_at: datetime | None
    operating_system: str | None
    tags: list[str] | None
    device_type: DeviceType
    approval_status: ApprovalStatus
    station_id: int | None
    approved_at: datetime | None
    linked_station_code: str | None = None
    linked_station_name: str | None = None
    duplicate_vpn_ip: bool = False
    duplicate_vpn_node_ids: list[int] = Field(default_factory=list)


class HeadscaleApproveIn(BaseModel):
    device_type: DeviceType
    station_id: int | None = None
    display_name: str | None = Field(default=None, max_length=255)


class HeadscaleApproveConfirmIn(HeadscaleApproveIn):
    preview_token: str
    confirmation: Literal["APPROVE AND LINK"]


class HeadscaleApprovalPreviewOut(BaseModel):
    node_id: int
    node_hostname: str
    node_given_name: str | None
    vpn_ip: str | None
    device_type: DeviceType
    station_id: int | None
    station_code: str | None
    station_name: str | None
    district: str | None
    node_existing_station_id: int | None
    station_existing_node_id: int | None
    valid: bool
    errors: list[str]
    preview_token: str | None


class HeadscaleLinkIn(BaseModel):
    station_id: int
    preview_token: str
    confirmation: Literal["LINK STATION"]


class PingPoint(ORMModel):
    latency_ms: float | None
    packet_loss: float | None
    success: bool
    checked_at: datetime
    error_type: str | None


class StatusEventOut(ORMModel):
    id: int
    station_id: int
    previous_status: StationStatus
    new_status: StationStatus
    source: EventSource
    reason: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None


class DistrictHealth(BaseModel):
    id: int
    code: str
    name: str
    total_stations: int
    online: int
    offline: int
    degraded: int
    unknown: int
    availability_percentage: float | None


class AttentionStation(BaseModel):
    station_id: int
    station_code: str
    name: str
    district: str | None
    status: StationStatus
    vpn_ip: str | None
    last_ping_ms: int | None
    last_seen_at: datetime | None
    offline_since: datetime | None
    active_alerts: int


class DashboardSummaryOut(BaseModel):
    total_stations: int
    online_stations: int
    offline_stations: int
    degraded_stations: int
    unknown_stations: int
    online_percentage: float | None
    total_cameras: int | None
    online_cameras: int | None
    offline_cameras: int | None
    camera_monitoring_configured: bool
    active_alerts: int
    approved_station_vpn_nodes: int
    pending_headscale_nodes: int
    district_health: list[DistrictHealth]
    recent_alerts: list[AlertOut]
    top_problem_stations: list[AttentionStation]


class ReportStationRow(BaseModel):
    station_id: int
    station_code: str
    station_name: str
    district: str | None
    total_monitored_seconds: int
    online_seconds: int
    offline_seconds: int
    degraded_seconds: int
    unknown_seconds: int
    availability_percentage: float | None
    outages: int
    longest_outage_seconds: int
    average_outage_seconds: float | None
    current_outage_seconds: int | None


class RegistrationUpsertIn(BaseModel):
    telegram_user_id: int
    telegram_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class RegistrationPreApproveIn(BaseModel):
    telegram_user_id: int
    role: Role
    display_name: str
    telegram_username: str | None = None


class RegistrationReviewIn(BaseModel):
    action: str = Field(pattern=r"^(approve|reject|clarification)$")
    role: Role | None = None
    clarification: str | None = None


class RegistrationOut(ORMModel):
    id: int
    telegram_user_id: int
    telegram_username: str | None
    first_name: str | None
    last_name: str | None
    display_name: str | None
    status: RegistrationStatus
    assigned_role: Role | None
    requested_at: datetime
    reviewed_at: datetime | None


class RegistrationStatusOut(BaseModel):
    status: RegistrationStatus
    username: str | None = None
    role: Role | None = None
    activation_code: str | None = None
    expires_at: datetime | None = None


class ActivationIn(BaseModel):
    code: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=12, max_length=256)


class AuditLogOut(ORMModel):
    id: int
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    timestamp: datetime
    source: str
    ip_address: str | None


class DistrictAssignmentIn(BaseModel):
    station_code: str = Field(min_length=1, max_length=32)
    district: str = Field(min_length=1, max_length=128)


class DistrictPreviewIn(BaseModel):
    assignments: list[DistrictAssignmentIn] = Field(min_length=1, max_length=1000)


class DistrictApplyIn(DistrictPreviewIn):
    preview_token: str
    confirmation: Literal["ASSIGN DISTRICTS"]


class DistrictAssignmentRow(BaseModel):
    station_id: int
    station_code: str
    station_name: str
    address: str
    vpn_ip: str | None
    headscale_hostname: str | None
    current_district: str | None
    proposed_district: str
    proposed_district_id: int
    changed: bool


class OnboardingValidationError(BaseModel):
    row: int
    station_code: str | None
    message: str


class DistrictPreviewOut(BaseModel):
    valid: bool
    rows: list[DistrictAssignmentRow]
    errors: list[OnboardingValidationError]
    preview_token: str | None


class DuplicateVpnStation(BaseModel):
    station_id: int
    station_code: str
    station_name: str
    status: StationStatus
    last_seen_at: datetime | None
    linked_node_id: int | None
    linked_node_hostname: str | None
    linked_node_approval_status: ApprovalStatus | None


class DuplicateVpnGroup(BaseModel):
    vpn_ip: str
    stations: list[DuplicateVpnStation]
    recommended_remediation: str


class DuplicateVpnActionPreviewIn(BaseModel):
    action: Literal["unlink_node", "clear_station_vpn", "select_canonical_node", "cancel"]
    vpn_ip: str
    station_id: int | None = None
    node_id: int | None = None


class DuplicateVpnActionApplyIn(DuplicateVpnActionPreviewIn):
    preview_token: str
    confirmation: Literal["APPLY VPN ACTION"]


class ActionPreviewOut(BaseModel):
    valid: bool
    description: str
    errors: list[str]
    preview_token: str | None


class DuplicateAlertGroup(BaseModel):
    station_id: int
    station_code: str
    station_name: str
    alert_type: AlertType
    open_alert_count: int
    oldest_alert_at: datetime
    newest_alert_at: datetime
    canonical_alert_id: int
    proposed_resolve_alert_ids: list[int]
    preview_token: str


class DuplicateAlertApplyIn(BaseModel):
    station_id: int
    alert_type: AlertType
    preview_token: str
    confirmation: Literal["RESOLVE DUPLICATES"]


StationDetailOut.model_rebuild()
