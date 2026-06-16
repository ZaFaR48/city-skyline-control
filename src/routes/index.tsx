import { createFileRoute } from "@tanstack/react-router";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity, Server, ServerCog, ServerOff, Video, BellRing, Network, Cpu, HardDrive, Loader2, AlertOctagon,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { StatCard } from "@/components/StatCard";
import { StatusBadge, pingTone } from "@/components/StatusBadge";
import { Endpoints } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard · City Parking Control Center" },
      { name: "description", content: "Live operational overview of every parking station, camera and VPN node across Tajikistan." },
    ],
  }),
  component: Dashboard,
});

const REFETCH_MS = 30_000;

function Dashboard() {
  const summaryQ = useQuery({
    queryKey: ["analytics", "summary"],
    queryFn: Endpoints.summary,
    refetchInterval: REFETCH_MS,
  });
  const nodesQ = useQuery({
    queryKey: ["headscale", "nodes"],
    queryFn: Endpoints.nodes,
    refetchInterval: REFETCH_MS,
  });

  const summary = summaryQ.data;
  const nodes = nodesQ.data ?? [];

  const nodeStats = useMemo(() => {
    const total = nodes.length;
    const online = nodes.filter((n) => n.online).length;
    return { total, online, offline: total - online };
  }, [nodes]);

  const isLoading = summaryQ.isLoading || nodesQ.isLoading;
  const error = (summaryQ.error || nodesQ.error) as Error | null;

  return (
    <>
      <Topbar
        title="Operations Overview"
        subtitle={`Live status across all stations · auto-refresh every ${REFETCH_MS / 1000}s`}
      />
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          {error && (
            <div className="glass rounded-xl p-4 flex items-center gap-3 border border-destructive/40">
              <AlertOctagon className="size-5 text-destructive" />
              <div>
                <div className="text-sm font-semibold">Failed to load live data</div>
                <div className="text-xs text-muted-foreground">{error.message}</div>
              </div>
            </div>
          )}

          {isLoading && !summary ? (
            <div className="glass rounded-xl p-10 grid place-items-center text-muted-foreground">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
                <StatCard label="Total Stations" value={summary?.stations_total ?? 0} icon={Server} tone="info" />
                <StatCard
                  label="Online"
                  value={summary?.stations_online ?? 0}
                  icon={ServerCog}
                  tone="success"
                  delta={summary && summary.stations_total
                    ? `${Math.round((summary.stations_online / summary.stations_total) * 100)}% availability`
                    : undefined}
                />
                <StatCard
                  label="Offline"
                  value={summary?.stations_offline ?? 0}
                  icon={ServerOff}
                  tone="danger"
                  delta={summary ? `${summary.stations_warning} degraded` : undefined}
                />
                <StatCard
                  label="Cameras"
                  value={`${summary?.cameras_online ?? 0}/${summary?.cameras_total ?? 0}`}
                  icon={Video}
                  tone="info"
                  hint="Online / total"
                />
                <StatCard
                  label="Active Alerts"
                  value={summary?.alerts_active ?? 0}
                  icon={BellRing}
                  tone={(summary?.alerts_active ?? 0) > 5 ? "danger" : "warning"}
                />
                <StatCard
                  label="VPN Nodes"
                  value={summary?.vpn_nodes ?? nodeStats.total}
                  icon={Network}
                  tone="success"
                  hint="Headscale mesh"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <StatCard label="Total Nodes" value={nodeStats.total} icon={Network} tone="info" />
                <StatCard label="Online Nodes" value={nodeStats.online} icon={ServerCog} tone="success" />
                <StatCard label="Offline Nodes" value={nodeStats.offline} icon={ServerOff} tone="danger" />
              </div>

              <div className="glass rounded-xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-sm font-semibold">Headscale Mesh</h2>
                    <p className="text-xs text-muted-foreground">{nodeStats.total} registered nodes</p>
                  </div>
                  <Activity className="size-4 text-muted-foreground" />
                </div>
                {nodes.length === 0 ? (
                  <div className="text-sm text-muted-foreground py-6 text-center">No VPN nodes registered yet.</div>
                ) : (
                  <ul className="divide-y divide-border">
                    {nodes.slice(0, 8).map((n) => (
                      <li key={n.id} className="flex items-center justify-between py-2.5 text-sm">
                        <div className="flex items-center gap-3 min-w-0">
                          <StatusBadge status={n.online ? "online" : "offline"} />
                          <span className="font-medium truncate">{n.hostname}</span>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <span className="font-mono">{n.vpn_ip}</span>
                          <span className={pingTone(0, n.online ? "online" : "offline")}>
                            {n.last_seen ? new Date(n.last_seen).toLocaleString() : "—"}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

// silence unused-import lints for icons retained for future widgets
void Cpu; void HardDrive;
