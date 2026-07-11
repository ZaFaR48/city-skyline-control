import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Topbar } from "@/components/Topbar";
import { getStations } from "@/lib/api";
import type { Station, StationStatus } from "@/lib/types";

export const Route = createFileRoute("/map")({ component: MapPage });

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

function MapPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getStations({ limit: 200 })
      .then((result) => setStations(result.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Map data unavailable"));
  }, []);
  const placed = useMemo(
    () => stations.filter((station) => station.latitude !== null && station.longitude !== null),
    [stations],
  );
  const unplaced = useMemo(
    () => stations.filter((station) => station.latitude === null || station.longitude === null),
    [stations],
  );
  return (
    <>
      <Topbar title="Map" subtitle={`${placed.length} placed · ${unplaced.length} unplaced`} />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {error && <div className="glass p-4 text-destructive">{error}</div>}
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_280px] gap-4">
          <div className="glass rounded-xl overflow-hidden">
            <MapContainer
              center={[38.5598, 68.787]}
              zoom={12}
              style={{ height: "700px", width: "100%" }}
            >
              <TileLayer
                attribution="OpenStreetMap"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {placed.map((station) => (
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
          </div>
          <aside className="glass rounded-xl p-4 max-h-[700px] overflow-y-auto">
            <h2 className="text-sm font-semibold">Unplaced stations ({unplaced.length})</h2>
            <p className="text-xs text-muted-foreground mb-3">
              Add verified coordinates to place these stations.
            </p>
            {unplaced.map((station) => (
              <div key={station.id} className="py-2 border-b border-border text-sm">
                <div className="font-mono text-xs">{station.station_code}</div>
                <div className="truncate" title={station.name}>
                  {station.name}
                </div>
              </div>
            ))}
            {unplaced.length === 0 && (
              <p className="text-sm text-muted-foreground py-4">No unplaced stations.</p>
            )}
          </aside>
        </div>
      </div>
    </>
  );
}
