import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { BellRing, Network, RefreshCw, Server, ServerCog, ServerOff, Video } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { getDashboardSummary } from "@/lib/api";
import type { DashboardSummary } from "@/lib/types";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [{ title: "Dashboard · City Parking Control Center" }] }),
  component: Dashboard,
});

function ago(value: string | null) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds} seconds ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m ago`;
}

function duration(value: string | null) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function Dashboard() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getDashboardSummary());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dashboard data could not be loaded");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
    const timer = window.setInterval(load, 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  return (
    <>
      <Topbar title="Operations Overview" subtitle="Dushanbe pilot · verified monitoring data" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {loading && !data && <LoadingCards />}
        {error && <ErrorState message={error} retry={load} />}
        {data && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
              <StatCard
                label="Total Stations"
                value={data.total_stations}
                icon={Server}
                tone="info"
                hint="Active Dushanbe stations"
              />
              <StatCard
                label="Online"
                value={data.online_stations}
                icon={ServerCog}
                tone="success"
                delta={
                  data.online_percentage === null ? "No data" : `${data.online_percentage}% online`
                }
              />
              <StatCard
                label="Offline"
                value={data.offline_stations}
                icon={ServerOff}
                tone="danger"
                delta={`${data.degraded_stations} degraded · ${data.unknown_stations} unknown`}
              />
              <StatCard
                label="Cameras"
                value={
                  data.camera_monitoring_configured
                    ? `${data.online_cameras}/${data.total_cameras}`
                    : "Not configured"
                }
                icon={Video}
                tone="info"
                hint={data.camera_monitoring_configured ? "Online / total" : "No monitored cameras"}
              />
              <StatCard
                label="Active Alerts"
                value={data.active_alerts}
                icon={BellRing}
                tone={data.active_alerts ? "warning" : "success"}
              />
              <StatCard
                label="VPN Station Nodes"
                value={data.approved_station_vpn_nodes}
                icon={Network}
                tone="info"
                hint={`${data.pending_headscale_nodes} pending approval`}
              />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <section className="glass rounded-xl p-5 xl:col-span-2">
                <h2 className="text-sm font-semibold">Stations Requiring Attention</h2>
                <p className="text-xs text-muted-foreground mb-4">
                  Prioritized from outages, alerts, degraded state, ping, and camera failures
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] text-sm">
                    <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      <tr>
                        <th className="text-left py-2">Status</th>
                        <th className="text-left">Code / station</th>
                        <th className="text-left">District</th>
                        <th className="text-left">VPN IP</th>
                        <th className="text-right">Ping</th>
                        <th className="text-right">Offline</th>
                        <th className="text-right">Alerts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.top_problem_stations.map((station) => (
                        <tr key={station.station_id} className="border-t border-border">
                          <td className="py-3">
                            <StatusBadge status={station.status} />
                          </td>
                          <td>
                            <div className="font-mono text-xs">{station.station_code}</div>
                            <div className="max-w-[220px] truncate" title={station.name}>
                              {station.name}
                            </div>
                          </td>
                          <td className="text-muted-foreground">{station.district ?? "—"}</td>
                          <td className="font-mono text-xs">{station.vpn_ip ?? "—"}</td>
                          <td className="text-right font-mono">
                            {station.last_ping_ms === null ? "—" : `${station.last_ping_ms} ms`}
                          </td>
                          <td className="text-right">
                            {station.status === "offline" ? duration(station.offline_since) : "—"}
                          </td>
                          <td className="text-right tabular-nums">{station.active_alerts}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {data.top_problem_stations.length === 0 && (
                    <Empty text="No stations currently require attention." />
                  )}
                </div>
              </section>

              <section className="glass rounded-xl p-5">
                <h2 className="text-sm font-semibold">Recent Active Alerts</h2>
                <p className="text-xs text-muted-foreground mb-4">Unresolved monitoring events</p>
                <ul className="space-y-3">
                  {data.recent_alerts.map((alert) => (
                    <li key={alert.id} className="border-b border-border pb-3 last:border-0">
                      <div className="flex justify-between gap-2">
                        <span className="text-sm font-medium">
                          {alert.type.replaceAll("_", " ")}
                        </span>
                        <span className="text-[11px] text-muted-foreground">
                          {ago(alert.created_at)}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">{alert.message}</p>
                    </li>
                  ))}
                </ul>
                {data.recent_alerts.length === 0 && <Empty text="No active alerts." />}
              </section>
            </div>

            <section className="glass rounded-xl p-5">
              <h2 className="text-sm font-semibold mb-4">District Health</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
                {data.district_health.map((district) => (
                  <div key={district.id} className="panel p-4">
                    <div className="flex justify-between">
                      <span className="font-medium">{district.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {district.total_stations} stations
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-4 text-center text-xs gap-1">
                      <Health value={district.online} label="Online" tone="text-success" />
                      <Health value={district.degraded} label="Degraded" tone="text-warning" />
                      <Health value={district.offline} label="Offline" tone="text-destructive" />
                      <Health
                        value={district.unknown}
                        label="Unknown"
                        tone="text-muted-foreground"
                      />
                    </div>
                    <div className="mt-3 text-xs text-muted-foreground">
                      Availability:{" "}
                      {district.availability_percentage === null
                        ? "No data"
                        : `${district.availability_percentage}%`}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </>
  );
}

function Health({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <div>
      <div className={`text-lg font-semibold ${tone}`}>{value}</div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
    </div>
  );
}
function Empty({ text }: { text: string }) {
  return <div className="py-8 text-center text-sm text-muted-foreground">{text}</div>;
}
function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return (
    <div className="glass rounded-xl border-destructive/40 p-5 flex items-center justify-between gap-3">
      <span className="text-sm text-destructive">{message}</span>
      <button
        onClick={retry}
        className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs"
      >
        <RefreshCw className="size-3.5" /> Retry
      </button>
    </div>
  );
}
function LoadingCards() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="glass h-28 rounded-xl animate-pulse" />
      ))}
    </div>
  );
}
