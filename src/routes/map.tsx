import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { Endpoints } from "@/lib/api";
import type { Station, StationStatus } from "@/lib/types";

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

const LeafletMap = lazy(() => import("@/components/LeafletStationMap"));

function MapPage() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ["stations"],
    queryFn: Endpoints.stations,
    refetchInterval: REFETCH_MS,
  });
  const stations = useMemo<Station[]>(
    () => (q.data ?? []).filter((s) => Number.isFinite(s.lat) && Number.isFinite(s.lng)),
    [q.data],
  );

  const counts = useMemo(() => {
    const c: Record<StationStatus, number> = { online: 0, warning: 0, offline: 0 };
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
          <div className="relative w-full aspect-[16/9] rounded-lg overflow-hidden border border-border bg-slate-950">
            {mounted ? (
              <Suspense fallback={<MapFallback />}>
                <LeafletMap
                  stations={stations}
                  onSelect={(id) => navigate({ to: "/stations", search: { focus: id } as never })}
                />
              </Suspense>
            ) : (
              <MapFallback />
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function MapFallback() {
  return (
    <div className="absolute inset-0 grid place-items-center text-muted-foreground">
      <Loader2 className="size-6 animate-spin" />
    </div>
  );
}
