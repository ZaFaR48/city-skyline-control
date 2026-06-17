import { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import type { Station, StationStatus } from "@/lib/types";
import "leaflet/dist/leaflet.css";

const DUSHANBE: [number, number] = [38.5598, 68.787];

const COLORS: Record<StationStatus, string> = {
  online: "#22c55e",
  warning: "#eab308",
  offline: "#ef4444",
};

function FitBounds({ stations }: { stations: Station[] }) {
  const map = useMap();
  useEffect(() => {
    if (!stations.length) return;
    const pts = stations.map((s) => [s.lat, s.lng] as [number, number]);
    if (pts.length === 1) { map.setView(pts[0], 12); return; }
    map.fitBounds(pts, { padding: [40, 40] });
  }, [stations, map]);
  return null;
}

export default function LeafletStationMap({
  stations,
  onSelect,
}: {
  stations: Station[];
  onSelect: (id: number) => void;
}) {
  return (
    <MapContainer
      center={DUSHANBE}
      zoom={7}
      scrollWheelZoom
      className="absolute inset-0 h-full w-full"
      style={{ background: "#0b1220" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      <FitBounds stations={stations} />
      {stations.map((s) => (
        <CircleMarker
          key={s.id}
          center={[s.lat, s.lng]}
          radius={8}
          pathOptions={{
            color: COLORS[s.status],
            fillColor: COLORS[s.status],
            fillOpacity: 0.85,
            weight: 2,
          }}
          eventHandlers={{ click: () => onSelect(s.id) }}
        >
          <Popup>
            <div className="text-xs space-y-1 min-w-[200px]">
              <div className="font-semibold text-sm">{s.name}</div>
              <div><b>ID:</b> <span className="font-mono">{s.code}</span></div>
              <div><b>Address:</b> {s.address}</div>
              <div><b>VPN IP:</b> <span className="font-mono">{s.vpn_ip}</span></div>
              <div>
                <b>Status:</b>{" "}
                <span style={{ color: COLORS[s.status], fontWeight: 600 }}>
                  {s.status.toUpperCase()}
                </span>
              </div>
              <div><b>Ping:</b> {s.last_ping_ms || "—"} ms</div>
              <div><b>Last seen:</b> {s.last_seen ? new Date(s.last_seen).toLocaleString() : "—"}</div>
              <button
                onClick={() => onSelect(s.id)}
                className="mt-2 w-full h-7 rounded bg-primary text-primary-foreground text-xs font-medium"
              >
                Open station
              </button>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
