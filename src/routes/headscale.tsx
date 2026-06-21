import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Topbar } from "@/components/Topbar";
import { getDataset } from "@/lib/mock-data";
import { Network, RefreshCw } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";

export const Route = createFileRoute("/headscale")({
  head: () => ({ meta: [{ title: "Headscale · City Parking Control Center" }, { name: "description", content: "Headscale VPN mesh: discovered nodes, hostnames and last-seen times." }] }),
  component: HeadscalePage,
});

function HeadscalePage() {
  const { stations } = getDataset();
  return (
    <>
      <Topbar title="Headscale" subtitle="VPN mesh discovery · auto-sync every 30s" />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="glass rounded-xl p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-lg grid place-items-center bg-success/20 border border-success/30 text-success"><Network className="size-5" /></div>
            <div>
              <div className="text-sm font-semibold">Mesh healthy</div>
              <div className="text-xs text-muted-foreground">{stations.length} nodes registered · auto-discovery enabled</div>
            </div>
          </div>
          <button className="inline-flex items-center gap-1.5 h-9 px-3 text-xs rounded-md border border-border bg-accent/40 hover:bg-accent">
            <RefreshCw className="size-3.5" /> Sync now
          </button>
        </div>
        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-panel/60 text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="text-left font-medium px-4 py-3">Node</th>
                <th className="text-left font-medium px-4 py-3">Hostname</th>
                <th className="text-left font-medium px-4 py-3">VPN IP</th>
                <th className="text-left font-medium px-4 py-3">Status</th>
                <th className="text-left font-medium px-4 py-3">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {stations.map((s) => (
                <tr key={s.id} className="border-t border-border">
                  <td className="px-4 py-3 font-medium">{s.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{s.name.toLowerCase()}.tj.tail</td>
                  <td className="px-4 py-3 font-mono">{s.vpnIp}</td>
                  <td className="px-4 py-3"><StatusBadge status={s.status} /></td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{new Date(s.lastSeen).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
