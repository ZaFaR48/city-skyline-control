export type StationStatus = "online" | "warning" | "offline";

export type AlertSeverity = "critical" | "warning" | "info";
export type AlertType =
  | "offline_station"
  | "camera_offline"
  | "vpn_lost"
  | "disk_full"
  | "cpu_high"
  | "ram_high";

export interface Station {
  id: number;
  code: string;
  name: string;
  region: string;
  address: string;
  vpn_ip: string;
  local_ip: string;
  rustdesk_id: string | null;
  lat: number;
  lng: number;
  status: StationStatus;
  cpu: number;
  ram: number;
  disk: number;
  last_ping_ms: number;
  last_seen: string | null;
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
}

export interface AlertItem {
  id: number;
  station_id: number | null;
  type: AlertType;
  severity: AlertSeverity;
  message: string;
  acknowledged: boolean;
  created_at: string;
}

export interface HeadscaleNode {
  id: number;
  hostname: string;
  vpn_ip: string;
  online: boolean;
  last_seen: string | null;
  station_id: number | null;
}

export interface StationDetail extends Station {
  headscale_node: HeadscaleNode | null;
}

  id: number;
  hostname: string;
  vpn_ip: string;
  online: boolean;
  last_seen: string | null;
  station_id: number | null;
}

export interface SummaryOut {
  stations_total: number;
  stations_online: number;
  stations_warning: number;
  stations_offline: number;
  cameras_total: number;
  cameras_online: number;
  alerts_active: number;
  vpn_nodes: number;
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: "admin" | "operator" | "viewer";
}
