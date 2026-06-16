import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Topbar } from "@/components/Topbar";
import { Endpoints } from "@/lib/api";
import { Loader2 } from "lucide-react";

export const Route = createFileRoute("/map")({
  head: () => ({ meta: [{ title: "Map · City Parking Control Center" }, { name: "description", content: "Geographic distribution of stations across Tajikistan." }] }),
  component: MapPage,
});

const BBOX = { minLng: 67.3, maxLng: 75.2, minLat: 36.6, maxLat: 41.1 };
const REFETCH_MS = 30_000;

function project(lat: number, lng: number, w: number, h: number) {
  const x = ((lng - BBOX.minLng) / (BBOX.maxLng - BBOX.minLng)) * w;
  const y = h - ((lat - BBOX.minLat) / (BBOX.maxLat - BBOX.minLat)) * h;
  return { x, y };
}

function MapPage() {
  const q = useQuery({ queryKey: ["stations"], queryFn: Endpoints.stations, refetchInterval: REFETCH_MS });
  const stations = q.data ?? [];
  const w = 1000, h = 560;

  return (
    <>
      <Topbar title="Map" subtitle="Tajikistan · all stations" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="glass rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold">Station Distribution</h2>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-success" /> Online</span>
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-warning" /> Warning</span>
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-destructive" /> Offline</span>
            </div>
          </div>
          <div className="relative w-full aspect-[1000/560] rounded-lg overflow-hidden border border-border bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900">
            {q.isLoading && (
              <div className="absolute inset-0 grid place-items-center text-muted-foreground"><Loader2 className="size-6 animate-spin" /></div>
            )}
            <svg viewBox={`0 0 ${w} ${h}`} className="absolute inset-0 w-full h-full">
              <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
                </pattern>
              </defs>
              <rect width={w} height={h} fill="url(#grid)" />
              <path d="M120,360 C160,280 220,260 280,270 C340,210 420,180 480,200 C540,170 620,160 680,180 C740,160 820,170 880,210 C900,260 880,310 840,340 C800,380 760,360 700,380 C660,420 600,430 540,420 C480,440 420,430 360,410 C300,420 240,400 200,420 C160,420 130,400 120,360 Z"
                fill="rgba(80,140,220,0.08)" stroke="rgba(120,180,255,0.35)" strokeWidth="1.2" />
              {stations.map((s) => {
                const { x, y } = project(s.lat, s.lng, w, h);
                const color = s.status === "online" ? "rgb(74 222 128)" : s.status === "warning" ? "rgb(250 204 21)" : "rgb(248 113 113)";
                return (
                  <g key={s.id}>
                    {s.status !== "offline" && (
                      <circle cx={x} cy={y} r="10" fill={color} opacity="0.18">
                        <animate attributeName="r" values="6;14;6" dur="2.4s" repeatCount="indefinite" />
                        <animate attributeName="opacity" values="0.35;0;0.35" dur="2.4s" repeatCount="indefinite" />
                      </circle>
                    )}
                    <circle cx={x} cy={y} r="4" fill={color} stroke="rgba(0,0,0,0.6)" strokeWidth="1">
                      <title>{`${s.name} · ${s.region} · ${s.status} · ${s.vpn_ip}`}</title>
                    </circle>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      </div>
    </>
  );
}
