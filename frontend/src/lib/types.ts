export type StationStatus = "online" | "degraded" | "offline" | "unknown";
export type Role = "admin" | "operator" | "viewer";
export type DeviceType = "station" | "operator_pc" | "admin_pc" | "phone" | "server" | "unknown";
export type ApprovalStatus = "pending" | "approved" | "rejected";
export type AlertSeverity = "critical" | "warning" | "info";
export type AlertType =
  | "offline_station"
  | "camera_offline"
  | "vpn_lost"
  | "disk_full"
  | "cpu_high"
  | "ram_high";

export interface User {
  id: number;
  username: string;
  email: string;
  role: Role;
  is_active: boolean;
}

export interface Region {
  id: number;
  code: string;
  name: string;
  region_type: "city" | "district" | "operational_zone";
  parent_id: number | null;
  is_active: boolean;
  sort_order: number;
}

export interface Station {
  id: number;
  station_code: string;
  name: string;
  city_id: number;
  city: string;
  district_id: number | null;
  district: string | null;
  address: string;
  operational_area: string | null;
  latitude: number | null;
  longitude: number | null;
  vpn_ip: string | null;
  local_ip: string | null;
  rustdesk_id: string | null;
  status: StationStatus;
  status_reason: string | null;
  last_seen_at: string | null;
  last_ping_at: string | null;
  last_ping_ms: number | null;
  offline_since: string | null;
  cpu: number | null;
  ram: number | null;
  disk: number | null;
  telemetry_at: string | null;
  is_active: boolean;
  is_archived: boolean;
  approved_at: string | null;
  approved_by: number | null;
  monitoring_configured: boolean;
  headscale_linked: boolean;
  headscale_hostname: string | null;
  headscale_approval_status: ApprovalStatus | null;
  cameras_total: number;
  cameras_online: number;
  active_alerts: number;
  data_quality_warnings: string[];
}

export interface StationList {
  items: Station[];
  total: number;
  limit: number;
  offset: number;
}

export interface PingPoint {
  latency_ms: number | null;
  packet_loss: number | null;
  success: boolean;
  checked_at: string;
  error_type: string | null;
}
export interface StatusEvent {
  id: number;
  previous_status: StationStatus;
  new_status: StationStatus;
  source: string;
  reason: string | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
}
export interface AuditEntry {
  id: number;
  action: string;
  timestamp: string;
  source: string;
}
export interface StationDetail extends Station {
  headscale_node: HeadscaleNode | null;
  cameras: Camera[];
  ping_history: PingPoint[];
  open_alerts: AlertItem[];
  status_timeline: StatusEvent[];
  audit_history: AuditEntry[];
}

export interface Camera {
  id: number;
  station_id: number;
  name: string;
  ip: string;
  rtsp_url: string;
  ptz: boolean;
  resolution: string;
  fps: number;
  status: StationStatus;
  last_seen_at: string | null;
}

export interface AlertItem {
  id: number;
  station_id: number | null;
  type: AlertType;
  severity: AlertSeverity;
  message: string;
  acknowledged: boolean;
  acknowledged_at: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface HeadscaleNode {
  id: number;
  hostname: string;
  given_name: string | null;
  vpn_ip: string | null;
  online: boolean;
  first_seen_at: string;
  last_seen_at: string | null;
  operating_system: string | null;
  tags: string[] | null;
  device_type: DeviceType;
  approval_status: ApprovalStatus;
  station_id: number | null;
  approved_at: string | null;
  linked_station_code: string | null;
  linked_station_name: string | null;
  duplicate_vpn_ip: boolean;
  duplicate_vpn_node_ids: number[];
}

export interface HeadscaleApprovalPreview {
  node_id: number;
  node_hostname: string;
  node_given_name: string | null;
  vpn_ip: string | null;
  station_vpn_ip: string | null;
  device_type: DeviceType;
  station_id: number | null;
  station_code: string | null;
  station_name: string | null;
  district: string | null;
  node_existing_station_id: number | null;
  station_existing_node_id: number | null;
  valid: boolean;
  errors: string[];
  preview_token: string | null;
  vpn_replacement_warning: string | null;
}

export interface HeadscaleClassificationPreview {
  node_id: number;
  hostname: string;
  vpn_ip: string | null;
  online: boolean;
  approval_status: ApprovalStatus;
  current_device_type: DeviceType;
  current_station_id: number | null;
  current_station_code: string | null;
  proposed_device_type: DeviceType;
  proposed_station_id: number | null;
  proposed_station_code: string | null;
  station_vpn_ip: string | null;
  proposed_station_vpn_ip: string | null;
  vpn_replacement_warning: string | null;
  confirmation_phrase: string;
  valid: boolean;
  errors: string[];
  preview_token: string | null;
}

export interface DistrictHealth {
  id: number;
  code: string;
  name: string;
  total_stations: number;
  online: number;
  offline: number;
  degraded: number;
  unknown: number;
  availability_percentage: number | null;
}

export interface AttentionStation {
  station_id: number;
  station_code: string;
  name: string;
  district: string | null;
  status: StationStatus;
  vpn_ip: string | null;
  last_ping_ms: number | null;
  last_seen_at: string | null;
  offline_since: string | null;
  active_alerts: number;
}

export interface DashboardSummary {
  total_stations: number;
  online_stations: number;
  offline_stations: number;
  degraded_stations: number;
  unknown_stations: number;
  online_percentage: number | null;
  total_cameras: number | null;
  online_cameras: number | null;
  offline_cameras: number | null;
  camera_monitoring_configured: boolean;
  active_alerts: number;
  approved_station_vpn_nodes: number;
  pending_headscale_nodes: number;
  district_health: DistrictHealth[];
  recent_alerts: AlertItem[];
  top_problem_stations: AttentionStation[];
}

export interface UptimeReportRow {
  station_id: number;
  station_code: string;
  station_name: string;
  district: string | null;
  total_monitored_seconds: number;
  online_seconds: number;
  offline_seconds: number;
  degraded_seconds: number;
  unknown_seconds: number;
  availability_percentage: number | null;
  outages: number;
  longest_outage_seconds: number;
  average_outage_seconds: number | null;
  current_outage_seconds: number | null;
}

export interface RegistrationRequest {
  id: number;
  telegram_user_id: number;
  telegram_username: string | null;
  first_name: string | null;
  last_name: string | null;
  display_name: string | null;
  status: string;
  assigned_role: Role | null;
  requested_at: string;
  reviewed_at: string | null;
}

export interface StationApprovalPreview {
  station_id: number;
  station_code: string;
  station_name: string;
  district: string | null;
  address: string;
  vpn_ip: string | null;
  local_ip: string | null;
  headscale_hostname: string | null;
  headscale_approval_status: ApprovalStatus | null;
  monitoring_status: StationStatus;
  monitoring_ready: boolean;
  warning: string | null;
  production_approved: boolean;
  action: "approve" | "revoke";
  confirmation_phrase: string;
  valid: boolean;
  errors: string[];
  preview_token: string | null;
  checklist: Array<{ key: string; label: string; ready: boolean }>;
}

export interface StationRepairPreview {
  station_id: number;
  station_code: string;
  changes: Array<{ field: string; current: unknown; proposed: unknown }>;
  warnings: string[];
  errors: string[];
  confirmation_phrase: string;
  valid: boolean;
  preview_token: string | null;
}

export interface StationLifecyclePreview {
  station_id: number;
  station_code: string;
  action: "archive" | "restore";
  warnings: string[];
  linked_node_id: number | null;
  active_alerts: number;
  cameras: number;
  history_records: number;
  confirmation_phrase: string;
  valid: boolean;
  errors: string[];
  preview_token: string | null;
}

export interface SuspectedDuplicateStation {
  station_id: number;
  station_code: string;
  name: string;
  approval_status: string;
  is_active: boolean;
  is_archived: boolean;
  linked_node_id: number | null;
  active_alerts: number;
  cameras: number;
  history_records: number;
}

export interface SuspectedDuplicatePair {
  left: SuspectedDuplicateStation;
  right: SuspectedDuplicateStation;
  reasons: string[];
  recommendation: string;
}

export interface TelegramLinkPreview {
  registration_id: number;
  telegram_user_id: number;
  telegram_username: string | null;
  user_id: number;
  username: string;
  role: Role;
  is_active: boolean;
  warning: string | null;
  confirmation_phrase: string;
  valid: boolean;
  errors: string[];
  preview_token: string | null;
}

export interface PasswordResetPreview {
  registration_id: number;
  telegram_user_id: number;
  username: string;
  role: Role;
  is_active: boolean;
  confirmation_phrase: string;
  valid: boolean;
  errors: string[];
  preview_token: string | null;
}

export interface DistrictAssignment {
  station_code: string;
  district: string;
}

export interface DistrictAssignmentRow {
  station_id: number;
  station_code: string;
  station_name: string;
  address: string;
  vpn_ip: string | null;
  headscale_hostname: string | null;
  current_district: string | null;
  proposed_district: string;
  proposed_district_id: number;
  changed: boolean;
}

export interface DistrictPreview {
  valid: boolean;
  rows: DistrictAssignmentRow[];
  errors: Array<{ row: number; station_code: string | null; message: string }>;
  preview_token: string | null;
}

export interface DuplicateVpnGroup {
  vpn_ip: string;
  stations: Array<{
    station_id: number;
    station_code: string;
    station_name: string;
    status: StationStatus;
    last_seen_at: string | null;
    linked_node_id: number | null;
    linked_node_hostname: string | null;
    linked_node_approval_status: ApprovalStatus | null;
  }>;
  recommended_remediation: string;
}

export interface DuplicateAlertGroup {
  station_id: number;
  station_code: string;
  station_name: string;
  alert_type: AlertType;
  open_alert_count: number;
  oldest_alert_at: string;
  newest_alert_at: string;
  canonical_alert_id: number;
  proposed_resolve_alert_ids: number[];
  preview_token: string;
}

export interface ActionPreview {
  valid: boolean;
  description: string;
  errors: string[];
  preview_token: string | null;
}
