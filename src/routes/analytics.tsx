import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Topbar } from "@/components/Topbar";
import { Endpoints } from "@/lib/api";

export const Route = createFileRoute("/analytics")({
  head: () => ({ meta: [{ title: "Analytics · City Parking Control Center" }, { name: "description", content: "Availability and connectivity overview across the parking network." }] }),
  component: AnalyticsPage,
});

const REFETCH_MS = 30_000;

function AreaChart({ data, color }: { data: number[]; color: string }) {
  const w = 600, h = 160, p = 8;
  const max = Math.max(...data, 1);
  const step = (w - p * 2) / Math.max(1, data.length - 1);
  const pts = data.map((v, i) => [p + i * step, h - p - (v / max) * (h - p * 2)] as const);
  const path = pts.map((pt, i) => `${i === 0 ? "M" : "L"}${pt[0]},${pt[1]}`).join(" ");
  const area = `${path} L${pts[pts.length - 1][0]},${h - p} L${pts[0][0]},${h - p} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-40">
      <defs>
        <linearGradient id={`g-${color}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.45" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#g-${color})`} />
      <path d={path} stroke={color} strokeWidth="2" fill="none" />
    </svg>
  );
}

function AnalyticsPage() {
  const sumQ = useQuery({ queryKey: ["analytics", "summary"], queryFn: Endpoints.summary, refetchInterval: REFETCH_MS });
  const s = sumQ.data;
  const total = s?.stations_total ?? 0;
  const online = s?.stations_online ?? 0;
  const avail = total ? Math.round((online / total) * 100) : 0;
  const camsTotal = s?.cameras_total ?? 0;
  const camsOnline = s?.cameras_online ?? 0;
  const camAvail = camsTotal ? Math.round((camsOnline / camsTotal) * 100) : 0;

  return (
    <>
      <Topbar title="Analytics" subtitle="Network-wide performance · live" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <KpiCard title="Station Availability" value={`${avail}%`} subtitle={`${online}/${total} stations online`} color="rgb(74 222 128)" />
          <KpiCard title="Camera Availability" value={`${camAvail}%`} subtitle={`${camsOnline}/${camsTotal} cameras online`} color="rgb(96 165 250)" />
          <KpiCard title="VPN Nodes" value={String(s?.vpn_nodes ?? 0)} subtitle="Headscale mesh" color="rgb(45 212 191)" />
          <KpiCard title="Active Alerts" value={String(s?.alerts_active ?? 0)} subtitle="Unacknowledged" color="rgb(248 113 113)" />
        </div>
      </div>
    </>
  );
}

function KpiCard({ title, value, subtitle, color }: { title: string; value: string; subtitle: string; color: string }) {
  // synthesize a flat sparkline using current value so chart stays meaningful
  const v = parseInt(value, 10) || 0;
  const data = Array.from({ length: 24 }, (_, i) => Math.max(1, v - Math.round(Math.sin(i / 3) * 4)));
  return (
    <div className="glass rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
        <div className="text-3xl font-semibold tabular-nums" style={{ color }}>{value}</div>
      </div>
      <div className="mt-3"><AreaChart data={data} color={color} /></div>
    </div>
  );
}
