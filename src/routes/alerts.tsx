import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { AlertTriangle, AlertOctagon, Info, Check, Search } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { getDataset, type AlertItem, type AlertSeverity, type AlertType } from "@/lib/mock-data";

export const Route = createFileRoute("/alerts")({
  head: () => ({
    meta: [
      { title: "Alerts · City Parking Control Center" },
      { name: "description", content: "Active and historical alerts: offline stations, camera failures, VPN loss, disk/CPU/RAM thresholds." },
    ],
  }),
  component: AlertsPage,
});

const TYPE_LABEL: Record<AlertType, string> = {
  offline_station: "Offline Station",
  camera_offline: "Camera Offline",
  vpn_lost: "VPN Lost",
  disk_full: "Disk Full",
  cpu_high: "CPU High",
  ram_high: "RAM High",
};

function sevIcon(s: AlertSeverity) {
  if (s === "critical") return <AlertOctagon className="size-4 text-destructive" />;
  if (s === "warning") return <AlertTriangle className="size-4 text-warning" />;
  return <Info className="size-4 text-info" />;
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

function AlertsPage() {
  const { alerts } = getDataset();
  const [sev, setSev] = useState<"all" | AlertSeverity>("all");
  const [type, setType] = useState<"all" | AlertType>("all");
  const [q, setQ] = useState("");
  const [acked, setAcked] = useState<Set<string>>(new Set());

  const list = useMemo(() => {
    const ql = q.toLowerCase();
    return alerts.filter((a) =>
      (sev === "all" || a.severity === sev) &&
      (type === "all" || a.type === type) &&
      (ql === "" || a.station.toLowerCase().includes(ql) || a.message.toLowerCase().includes(ql))
    );
  }, [alerts, sev, type, q]);

  const counts = useMemo(() => ({
    critical: alerts.filter((a) => a.severity === "critical").length,
    warning: alerts.filter((a) => a.severity === "warning").length,
    info: alerts.filter((a) => a.severity === "info").length,
  }), [alerts]);

  function ack(id: string) {
    setAcked((s) => new Set(s).add(id));
  }

  return (
    <>
      <Topbar title="Alerts" subtitle={`${alerts.length} total · ${alerts.length - acked.size} unacknowledged`} />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="grid grid-cols-3 gap-4">
          <SevCard label="Critical" value={counts.critical} tone="danger" icon={<AlertOctagon className="size-5" />} />
          <SevCard label="Warning" value={counts.warning} tone="warning" icon={<AlertTriangle className="size-5" />} />
          <SevCard label="Info" value={counts.info} tone="info" icon={<Info className="size-5" />} />
        </div>

        <div className="glass rounded-xl p-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="size-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search alerts…"
              className="w-full h-9 pl-9 pr-3 rounded-md bg-input/60 border border-border text-sm focus:outline-none focus:ring-2 focus:ring-ring/50" />
          </div>
          <select value={sev} onChange={(e) => setSev(e.target.value as AlertSeverity | "all")}
            className="h-9 px-3 rounded-md bg-input/60 border border-border text-sm">
            <option value="all">All severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
          <select value={type} onChange={(e) => setType(e.target.value as AlertType | "all")}
            className="h-9 px-3 rounded-md bg-input/60 border border-border text-sm">
            <option value="all">All types</option>
            {Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>

        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-panel/60 text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="text-left font-medium px-4 py-3 w-10"></th>
                <th className="text-left font-medium px-4 py-3">Type</th>
                <th className="text-left font-medium px-4 py-3">Station</th>
                <th className="text-left font-medium px-4 py-3">Message</th>
                <th className="text-left font-medium px-4 py-3">Time</th>
                <th className="text-right font-medium px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {list.map((a) => {
                const ok = acked.has(a.id);
                return (
                  <tr key={a.id} className={`border-t border-border ${ok ? "opacity-50" : ""}`}>
                    <td className="px-4 py-3">{sevIcon(a.severity)}</td>
                    <td className="px-4 py-3 text-xs uppercase tracking-wider text-muted-foreground">{TYPE_LABEL[a.type]}</td>
                    <td className="px-4 py-3 font-medium">{a.station}</td>
                    <td className="px-4 py-3 text-muted-foreground">{a.message}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">{fmt(a.createdAt)}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => ack(a.id)} disabled={ok}
                        className="inline-flex items-center gap-1 h-7 px-2 text-xs rounded-md border border-border bg-accent/40 hover:bg-accent text-muted-foreground hover:text-foreground disabled:opacity-50">
                        <Check className="size-3.5" /> {ok ? "Acked" : "Ack"}
                      </button>
                    </td>
                  </tr>
                );
              })}
              {list.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-muted-foreground">No alerts match.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function SevCard({ label, value, tone, icon }: { label: string; value: number; tone: "danger" | "warning" | "info"; icon: React.ReactNode }) {
  const cls = tone === "danger" ? "text-destructive" : tone === "warning" ? "text-warning" : "text-info";
  return (
    <div className="glass rounded-xl p-5 flex items-center gap-4">
      <div className={`size-12 rounded-lg grid place-items-center bg-accent/60 border border-border ${cls}`}>{icon}</div>
      <div>
        <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
        <div className="text-3xl font-semibold tabular-nums">{value}</div>
      </div>
    </div>
  );
}
