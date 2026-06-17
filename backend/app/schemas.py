from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from .models import AlertSeverity, AlertType, Role, StationStatus


# ---- Auth ----
class LoginIn(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: Role
    class Config: from_attributes = True


# ---- Stations ----
class StationBase(BaseModel):
    code: str
    name: str
    region: str
    address: str
    vpn_ip: str
    local_ip: str
    rustdesk_id: Optional[str] = None
    lat: float
    lng: float

class StationCreate(StationBase): pass
class StationUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    vpn_ip: Optional[str] = None
    local_ip: Optional[str] = None
    rustdesk_id: Optional[str] = None

class StationOut(StationBase):
    id: int
    status: StationStatus
    cpu: int
    ram: int
    disk: int
    last_ping_ms: int
    last_seen: Optional[datetime]
    class Config: from_attributes = True


class StationDetailOut(StationOut):
    headscale_node: Optional["HeadscaleNodeOut"] = None


# ---- Cameras ----
class CameraBase(BaseModel):
    station_id: int
    name: str
    ip: str
    rtsp_url: str
    ptz: bool = False
    resolution: str = "1920x1080"
    fps: int = 25

class CameraCreate(CameraBase): pass
class CameraOut(CameraBase):
    id: int
    status: StationStatus
    class Config: from_attributes = True


# ---- Alerts ----
class AlertOut(BaseModel):
    id: int
    station_id: Optional[int]
    type: AlertType
    severity: AlertSeverity
    message: str
    acknowledged: bool
    created_at: datetime
    class Config: from_attributes = True


# ---- Headscale ----
class HeadscaleNodeOut(BaseModel):
    id: int
    hostname: str
    vpn_ip: str
    online: bool
    last_seen: Optional[datetime]
    station_id: Optional[int]
    class Config: from_attributes = True


StationDetailOut.model_rebuild()


# ---- Ping ----
class PingPoint(BaseModel):
    latency_ms: float
    packet_loss: float
    success: bool
    created_at: datetime
    class Config: from_attributes = True


# ---- Analytics ----
class SummaryOut(BaseModel):
    stations_total: int
    stations_online: int
    stations_warning: int
    stations_offline: int
    cameras_total: int
    cameras_online: int
    alerts_active: int
    vpn_nodes: int
