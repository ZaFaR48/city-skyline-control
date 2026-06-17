import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import { Topbar } from "@/components/Topbar";
import { Endpoints } from "@/lib/api";
import type { Station, StationStatus } from "@/lib/types";
import "leaflet/dist/leaflet.css";

export const Route = createFileRoute("/map")({
  head: () => ({
    meta: [
      { title: "Map · City Parking Control Center" },
      { name: "description", content: "Live geographic distribution of parking stations across Tajikistan." },
    ],
  }),
  component: MapPage,
});

const REFETCH_MS = 30_000;
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
    const pts = stations
      .filter((s) => Number.isFinite(s.lat) && Number.isFinite(s.lng))
      .map((s) => [s.lat, s.lng] as [number, number]);
    if (pts.length === 0) return;
    if (pts.length === 1) {
      map.setView(pts[0], 12);
      return;
    }
    map.fitBounds(pts, { padding: [40, 40] });
  }, [stations, map]);
  return null;
}

function MapPage() {
  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ["stations"],
    queryFn: Endpoints.stations,
    refetchInterval: REFETCH_MS,
  });
  const stations = useMemo(
    () => (q.data ?? []).filter((s) => Number.isFinite(s.lat) && Number.isFinite(s.lng)),
    [q.data],
  );

  const counts = useMemo(() => {
    const c = { online: 0, warning: 0, offline: 0 };
    stations.forEach((s) => { c[s.status] += 1; });
    return c;
  }, [stations]);

  return (
    <>
      <Topbar
        title="Map"
        subtitle={`Live · ${stations.length} stations · auto-refresh ${REFETCH_MS / 1000}s`}
      />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="glass rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold">Station Distribution · Tajikistan</h2>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-success" /> Online {counts.online}</span>
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-warning" /> Warning {counts.warning}</span>
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-destructive" /> Offline {counts.offline}</span>
            </div>
          </div>
          <div className="relative w-full aspect-[16/9] rounded-lg overflow-hidden border border-border">
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
                  eventHandlers={{
                    click: () => navigate({ to: "/stations", search: { focus: s.id } as never }),
                  }}
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
                        onClick={() => navigate({ to: "/stations", search: { focus: s.id } as never })}
                        className="mt-2 w-full h-7 rounded bg-primary text-primary-foreground text-xs font-medium"
                      >
                        Open station
                      </button>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>
        </div>
      </div>
    </>
  );
}
