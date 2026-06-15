import { createFileRoute } from "@tanstack/react-router";
import { Topbar } from "@/components/Topbar";
import { getDataset } from "@/lib/mock-data";

export const Route = createFileRoute("/analytics")({
  head: () => ({ meta: [{ title: "Analytics · City Parking Control Center" }, { name: "description", content: "Availability, growth and connectivity charts across the parking network." }] }),
  component: AnalyticsPage,
});

function AreaChart({ data, color }: { data: number[]; color: string }) {
  const w = 600, h = 160, p = 8;
  const max = Math.max(...data, 1);
  const step = (w - p * 2) / (data.length - 1);
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

function bars(n: number, seed: number) {
  return Array.from({ length: n }, (_, i) => 40 + Math.round(Math.abs(Math.sin(i * 0.7 + seed)) * 55));
}

function AnalyticsPage() {
  const { stations, cameras } = getDataset();
  const online = stations.filter((s) => s.status === "online").length;
  const total = stations.length;
  const avail = Math.round((online / total) * 100);

  return (
    <>
      <Topbar title="Analytics" subtitle="Network-wide performance · last 30 days" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ChartCard title="Daily Availability" subtitle={`Current: ${avail}%`} color="rgb(74 222 128)" data={bars(30, 1)} />
          <ChartCard title="Online vs Offline" subtitle={`${online}/${total} stations online`} color="rgb(96 165 250)" data={bars(30, 2)} />
          <ChartCard title="Camera Availability" subtitle={`${cameras.length} cameras tracked`} color="rgb(168 139 250)" data={bars(30, 3)} />
          <ChartCard title="VPN Connectivity" subtitle="Headscale mesh uptime" color="rgb(45 212 191)" data={bars(30, 4)} />
        </div>
        <div className="glass rounded-xl p-5">
          <h2 className="text-sm font-semibold mb-2">Station Growth</h2>
          <p className="text-xs text-muted-foreground mb-3">Cumulative deployments per month</p>
          <AreaChart data={[3,6,8,12,15,19,24,27,30,34,38,42]} color="rgb(34 211 238)" />
        </div>
      </div>
    </>
  );
}

function ChartCard({ title, subtitle, color, data }: { title: string; subtitle: string; color: string; data: number[] }) {
  return (
    <div className="glass rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      <AreaChart data={data} color={color} />
    </div>
  );
}
