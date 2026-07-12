import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Station, StationStatus } from "@/lib/types";

const COLORS: Record<StationStatus, string> = {
  online: "#22c55e",
  degraded: "#eab308",
  offline: "#ef4444",
  unknown: "#64748b",
};

function icon(status: StationStatus) {
  const color = COLORS[status];
  return L.divIcon({
    className: "",
    html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 0 8px ${color}"></div>`,
    iconSize: [14, 14],
  });
}

function elapsed(value: string | null) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function exact(value: string | null) {
  return value
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "medium",
        timeZone: "Asia/Dushanbe",
      }).format(new Date(value))
    : "—";
}

const REASONS: Record<string, string> = {
  HEALTHY: "Connectivity and configured components are healthy",
  HEADSCALE_OFFLINE: "Headscale is offline",
  HEADSCALE_LAST_SEEN_STALE: "Headscale last seen is stale",
  PING_TIMEOUT: "Station connectivity check failed",
  PING_HIGH_LATENCY: "Measured ping latency is high",
  AGENT_HEARTBEAT_STALE: "Monitoring-agent heartbeat is stale",
  CAMERA_OFFLINE: "Station online, camera offline",
  CAMERA_RTSP_FAILED: "Camera RTSP check failed",
  MONITORING_NOT_CONFIGURED: "Monitoring is not configured",
  INSUFFICIENT_FRESH_DATA: "Insufficient fresh measured data",
  CONFLICTING_TELEMETRY: "Exact cause is not determined",
};

export default function StationMapClient({ stations }: { stations: Station[] }) {
  return (
    <MapContainer center={[38.5598, 68.787]} zoom={12} style={{ height: "700px", width: "100%" }}>
      <TileLayer
        attribution="OpenStreetMap"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {stations.map((station) => (
        <Marker
          key={station.id}
          position={[station.latitude!, station.longitude!]}
          icon={icon(station.status)}
        >
          <Popup>
            <strong>
              {station.station_code} · {station.name}
            </strong>
            <br />
            District: {station.district ?? "—"}
            <br />
            Address: {station.address || "—"}
            <br />
            VPN: {station.vpn_ip ?? "—"}
            <br />
            Status: {station.status}
            <br />
            {station.status === "online" && (
              <>
                Online for: {elapsed(station.health.current_state_started_at)}
                <br />
                Last seen: {elapsed(station.health.last_seen_at)} ago ·{" "}
                {exact(station.health.last_seen_at)}
                <br />
                Camera: {station.health.camera_status.replaceAll("_", " ")}
                <br />
                Internet: {station.health.internet_status.replaceAll("_", " ")}
              </>
            )}
            {station.status === "degraded" && (
              <>
                Station connectivity: {station.health.connectivity_status}
                <br />
                Problem:{" "}
                {REASONS[station.health.overall_reason_code] ?? "Exact cause is not determined"}
                <br />
                Problem duration: {elapsed(station.health.current_state_started_at)}
                <br />
                Last seen: {exact(station.health.last_seen_at)}
              </>
            )}
            {station.status === "offline" && (
              <>
                Offline since: {exact(station.health.current_state_started_at)}
                <br />
                Offline for: {elapsed(station.health.current_state_started_at)}
                <br />
                Reason:{" "}
                {REASONS[station.health.overall_reason_code] ?? "Exact cause is not determined"}
              </>
            )}
            {station.status === "unknown" && (
              <>
                Reason:{" "}
                {REASONS[station.health.overall_reason_code] ?? "Exact cause is not determined"}
                <br />
                Last reliable observation: {exact(station.health.observed_at)}
              </>
            )}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
