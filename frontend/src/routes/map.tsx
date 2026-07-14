import { createFileRoute } from "@tanstack/react-router";
import { createClientOnlyFn } from "@tanstack/react-start";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { getStations } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Station } from "@/lib/types";

export const Route = createFileRoute("/map")({ component: MapPage });

const loadStationMap = createClientOnlyFn(() => import("@/components/StationMap.client"));
const StationMapClient = lazy(loadStationMap);

function MapPage() {
  const { t } = useI18n();
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const stationsQuery = useQuery({
    queryKey: ["stations", { limit: 200, approval: "approved", view: "map" }],
    queryFn: ({ signal }) => getStations({ limit: 200 }, signal),
    refetchInterval: 30_000,
  });
  const stations: Station[] = useMemo(
    () => stationsQuery.data?.items ?? [],
    [stationsQuery.data?.items],
  );
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
      <Topbar
        title="Map"
        subtitle={
          stationsQuery.data
            ? `${placed.length} placed · ${unplaced.length} unplaced`
            : t("loading.stations")
        }
      />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {stationsQuery.error && (
          <div className="glass p-4 text-destructive flex justify-between gap-3">
            <span>
              {stationsQuery.error instanceof Error
                ? stationsQuery.error.message
                : t("api.unavailable")}
            </span>
            <button
              onClick={() => void stationsQuery.refetch()}
              className="inline-flex items-center gap-2"
            >
              <RefreshCw className="size-4" /> {t("common.retry")}
            </button>
          </div>
        )}
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_280px] gap-4">
          <div className="glass rounded-xl overflow-hidden">
            {mounted && stationsQuery.data ? (
              <Suspense fallback={<div className="h-[700px] animate-pulse bg-panel" />}>
                <StationMapClient stations={placed} />
              </Suspense>
            ) : (
              <div className="h-[700px] bg-panel" />
            )}
          </div>
          <aside className="glass rounded-xl p-4 max-h-[700px] overflow-y-auto">
            <h2 className="text-sm font-semibold">
              {stationsQuery.data
                ? `Unplaced stations (${unplaced.length})`
                : t("loading.stations")}
            </h2>
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
            {stationsQuery.isSuccess && unplaced.length === 0 && (
              <p className="text-sm text-muted-foreground py-4">No unplaced stations.</p>
            )}
          </aside>
        </div>
      </div>
    </>
  );
}
