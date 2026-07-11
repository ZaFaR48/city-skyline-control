import { createFileRoute } from "@tanstack/react-router";
import { createClientOnlyFn } from "@tanstack/react-start";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Topbar } from "@/components/Topbar";
import { getStations } from "@/lib/api";
import type { Station } from "@/lib/types";

export const Route = createFileRoute("/map")({ component: MapPage });

const loadStationMap = createClientOnlyFn(() => import("@/components/StationMap.client"));
const StationMapClient = lazy(loadStationMap);

function MapPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
    getStations({ limit: 200 })
      .then((result) => setStations(result.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Map data unavailable"));
  }, []);
  const placed = useMemo(
    () =>
      stations.filter(
        (station) =>
          station.latitude !== null &&
          station.longitude !== null &&
          !(station.latitude === 0 && station.longitude === 0),
      ),
    [stations],
  );
  const unplaced = useMemo(
    () =>
      stations.filter(
        (station) =>
          station.latitude === null ||
          station.longitude === null ||
          (station.latitude === 0 && station.longitude === 0),
      ),
    [stations],
  );
  return (
    <>
      <Topbar title="Map" subtitle={`${placed.length} placed · ${unplaced.length} unplaced`} />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {error && <div className="glass p-4 text-destructive">{error}</div>}
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_280px] gap-4">
          <div className="glass rounded-xl overflow-hidden">
            {mounted ? (
              <Suspense fallback={<div className="h-[700px] animate-pulse bg-panel" />}>
                <StationMapClient stations={placed} />
              </Suspense>
            ) : (
              <div className="h-[700px] bg-panel" />
            )}
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
