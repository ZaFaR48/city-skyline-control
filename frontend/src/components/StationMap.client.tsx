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
            Last seen: {station.last_seen_at ? `${elapsed(station.last_seen_at)} ago` : "—"}
            <br />
            Offline: {station.status === "offline" ? elapsed(station.offline_since) : "—"}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
