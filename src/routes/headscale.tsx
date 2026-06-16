import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Topbar } from "@/components/Topbar";
import { Endpoints } from "@/lib/api";
import { Network, RefreshCw, Loader2, AlertOctagon, ServerCog, ServerOff } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { StatCard } from "@/components/StatCard";
import { useMemo } from "react";

export const Route = createFileRoute("/headscale")({
  head: () => ({ meta: [{ title: "Headscale · City Parking Control Center" }, { name: "description", content: "Headscale VPN mesh: discovered nodes, hostnames and last-seen times." }] }),
  component: HeadscalePage,
});

const REFETCH_MS = 30_000;

function HeadscalePage() {
  const qc = useQueryClient();
  const nodesQ = useQuery({
    queryKey: ["headscale", "nodes"],
    queryFn: Endpoints.nodes,
    refetchInterval: REFETCH_MS,
  });
  const syncM = useMutation({
    mutationFn: Endpoints.syncNodes,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["headscale", "nodes"] }),
  });

  const nodes = nodesQ.data ?? [];
  const stats = useMemo(() => {
    const total = nodes.length;
    const online = nodes.filter((n) => n.online).length;
    return { total, online, offline: total - online };
  }, [nodes]);

  return (
    <>
      <Topbar title="Headscale" subtitle={`VPN mesh discovery · auto-refresh every ${REFETCH_MS / 1000}s`} />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatCard label="Total Nodes" value={stats.total} icon={Network} tone="info" />
          <StatCard label="Online Nodes" value={stats.online} icon={ServerCog} tone="success" />
          <StatCard label="Offline Nodes" value={stats.offline} icon={ServerOff} tone="danger" />
        </div>

        <div className="glass rounded-xl p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-lg grid place-items-center bg-success/20 border border-success/30 text-success"><Network className="size-5" /></div>
            <div>
              <div className="text-sm font-semibold">{stats.offline === 0 ? "Mesh healthy" : "Degraded mesh"}</div>
              <div className="text-xs text-muted-foreground">{stats.total} nodes registered · auto-discovery enabled</div>
            </div>
          </div>
          <button
            onClick={() => syncM.mutate()}
            disabled={syncM.isPending}
            className="inline-flex items-center gap-1.5 h-9 px-3 text-xs rounded-md border border-border bg-accent/40 hover:bg-accent disabled:opacity-50"
          >
            {syncM.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
            Sync now
          </button>
        </div>

        {nodesQ.error && (
          <div className="glass rounded-xl p-4 flex items-center gap-3 border border-destructive/40">
            <AlertOctagon className="size-5 text-destructive" />
            <div className="text-sm">{(nodesQ.error as Error).message}</div>
          </div>
        )}

        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-panel/60 text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="text-left font-medium px-4 py-3">Hostname</th>
                <th className="text-left font-medium px-4 py-3">VPN IP</th>
                <th className="text-left font-medium px-4 py-3">Status</th>
                <th className="text-left font-medium px-4 py-3">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {nodesQ.isLoading && (
                <tr><td colSpan={4} className="px-4 py-10 text-center text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin inline-block mr-2" /> Loading…</td></tr>
              )}
              {!nodesQ.isLoading && nodes.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-10 text-center text-sm text-muted-foreground">No nodes registered.</td></tr>
              )}
              {nodes.map((n) => (
                <tr key={n.id} className="border-t border-border">
                  <td className="px-4 py-3 font-medium">{n.hostname}</td>
                  <td className="px-4 py-3 font-mono">{n.vpn_ip}</td>
                  <td className="px-4 py-3"><StatusBadge status={n.online ? "online" : "offline"} /></td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {n.last_seen ? new Date(n.last_seen).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
