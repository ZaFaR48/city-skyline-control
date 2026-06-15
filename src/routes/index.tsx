import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  Activity, Server, ServerCog, ServerOff, Video, BellRing, Network, Cpu, HardDrive,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { StatCard } from "@/components/StatCard";
import { StatusBadge, pingTone } from "@/components/StatusBadge";
import { getDataset, liveTick } from "@/lib/mock-data";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard · City Parking Control Center" },
      { name: "description", content: "Live operational overview of every parking station, camera and VPN node across Tajikistan." },
    ],
  }),
  component: Dashboard,
});

function fmtAgo(iso: string) {
  const s = Math.max(0, Math.floor((Date.now() - +new Date(iso)) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function Dashboard() {
  const [, force] = useState(0);
  useEffect(() => {
    const t = setInterval(() => { liveTick(); force((n) => n + 1); }, 10_000);
    return () => clearInterval(t);
  }, []);

  const { stations, cameras, alerts } = getDataset();

  const stats = useMemo(() => {
    const online = stations.filter((s) => s.status === "online").length;
    const warn = stations.filter((s) => s.status === "warning").length;
    const offline = stations.filter((s) => s.status === "offline").length;
    const camsOnline = cameras.filter((c) => c.status === "online").length;
    const active = alerts.filter((a) => !a.acknowledged).length;
    const avgCpu = Math.round(stations.reduce((a, s) => a + s.cpu, 0) / stations.length);
    const avgRam = Math.round(stations.reduce((a, s) => a + s.ram, 0) / stations.length);
    return { online, warn, offline, camsOnline, active, avgCpu, avgRam };
  }, [stations, cameras, alerts]);

  const recentAlerts = alerts.slice(0, 6);
  const topStations = [...stations].sort((a, b) => b.cpu - a.cpu).slice(0, 6);

  const regions = useMemo(() => {
    const map = new Map<string, { online: number; warning: number; offline: number; total: number }>();
    stations.forEach((s) => {
      const r = map.get(s.region) ?? { online: 0, warning: 0, offline: 0, total: 0 };
      r[s.status]++; r.total++;
      map.set(s.region, r);
    });
    return [...map.entries()].sort((a, b) => b[1].total - a[1].total);
  }, [stations]);

  return (
    <>
      <Topbar title="Operations Overview" subtitle="Live status across all stations · refresh every 10s" />
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
            <StatCard label="Total Stations" value={stations.length} icon={Server} tone="info" hint="Across 10 regions" />
            <StatCard label="Online" value={stats.online} icon={ServerCog} tone="success" delta={`${Math.round((stats.online/stations.length)*100)}% availability`} />
            <StatCard label="Offline" value={stats.offline} icon={ServerOff} tone="danger" delta={`${stats.warn} degraded`} />
            <StatCard label="Cameras" value={`${stats.camsOnline}/${cameras.length}`} icon={Video} tone="info" hint="Online / total" />
            <StatCard label="Active Alerts" value={stats.active} icon={BellRing} tone={stats.active > 5 ? "danger" : "warning"} />
            <StatCard label="VPN Nodes" value={stations.length} icon={Network} tone="success" hint="Headscale mesh" />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="glass rounded-xl p-5 xl:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-sm font-semibold">Top Stations by Load</h2>
                  <p className="text-xs text-muted-foreground">Sorted by CPU pressure</p>
                </div>
                <Activity className="size-4 text-muted-foreground" />
              </div>
              <div className="space-y-3">
                {topStations.map((s) => (
                  <div key={s.id} className="grid grid-cols-12 items-center gap-3 text-sm">
                    <div className="col-span-3 flex items-center gap-2 min-w-0">
                      <StatusBadge status={s.status} />
                      <span className="font-medium truncate">{s.name}</span>
                    </div>
                    <div className="col-span-2 font-mono text-xs text-muted-foreground truncate">{s.vpnIp}</div>
                    <MiniBar icon={Cpu} label="CPU" value={s.cpu} />
                    <MiniBar icon={Server} label="RAM" value={s.ram} />
                    <MiniBar icon={HardDrive} label="DSK" value={s.disk} />
                    <div className={`col-span-1 text-right font-mono text-xs ${pingTone(s.ping, s.status)}`}>{s.ping || "—"}ms</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-sm font-semibold">Recent Alerts</h2>
                  <p className="text-xs text-muted-foreground">Live feed</p>
                </div>
                <BellRing className="size-4 text-muted-foreground" />
              </div>
              <ul className="space-y-3">
                {recentAlerts.map((a) => (
                  <li key={a.id} className="flex items-start gap-3 text-sm">
                    <span className={`mt-1.5 size-2 rounded-full shrink-0 ${
                      a.severity === "critical" ? "bg-destructive" : a.severity === "warning" ? "bg-warning" : "bg-info"
                    }`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium truncate">{a.station}</span>
                        <span className="text-[11px] text-muted-foreground shrink-0">{fmtAgo(a.createdAt)}</span>
                      </div>
                      <p className="text-xs text-muted-foreground truncate">{a.message}</p>
                    </div>
                  </li>
                ))}
                {recentAlerts.length === 0 && <li className="text-sm text-muted-foreground">No active alerts.</li>}
              </ul>
            </div>
          </div>

          <div className="glass rounded-xl p-5">
            <h2 className="text-sm font-semibold mb-4">Regional Health</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              {regions.map(([name, r]) => {
                const pct = Math.round((r.online / r.total) * 100);
                return (
                  <div key={name} className="panel p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{name}</span>
                      <span className="text-xs text-muted-foreground tabular-nums">{r.total}</span>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-accent overflow-hidden flex">
                      <span className="bg-success" style={{ width: `${(r.online/r.total)*100}%` }} />
                      <span className="bg-warning" style={{ width: `${(r.warning/r.total)*100}%` }} />
                      <span className="bg-destructive" style={{ width: `${(r.offline/r.total)*100}%` }} />
                    </div>
                    <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground tabular-nums">
                      <span>{pct}% up</span>
                      <span>{r.offline} down</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function MiniBar({ icon: Icon, label, value }: { icon: typeof Cpu; label: string; value: number }) {
  const color = value >= 85 ? "bg-destructive" : value >= 70 ? "bg-warning" : "bg-success";
  return (
    <div className="col-span-2">
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1"><Icon className="size-3" />{label}</span>
        <span className="tabular-nums text-foreground">{value}%</span>
      </div>
      <div className="mt-1 h-1 rounded-full bg-accent overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}
