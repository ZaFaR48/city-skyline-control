import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  Eye, Pencil, Video, Monitor, TerminalSquare, Search, ChevronLeft, ChevronRight, ArrowUpDown,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { StatusBadge, pingTone } from "@/components/StatusBadge";
import { Meter } from "@/components/Meter";
import { getStations, type StationApi } from "@/lib/api";
import type { StationStatus } from "@/lib/mock-data";

export const Route = createFileRoute("/stations")({
  head: () => ({
    meta: [
      { title: "Stations · City Parking Control Center" },
      { name: "description", content: "Browse and manage every parking station: VPN/local IPs, health metrics, ping and remote actions." },
    ],
  }),
  component: StationsPage,
});

type SortKey =
  | "id"
  | "name"
  | "region"
  | "status"
  | "cpu"
  | "ram"
  | "disk";

function StationsPage() {
  const [stations, setStations] = useState<StationApi[]>([]);

  useEffect(() => {
    const token = localStorage.getItem("cpcc.access_token");

    if (!token) {
      console.error("Token not found");
      return;
    }

    getStations(token)
      .then(setStations)
      .catch(console.error);
  }, []);

  const [q, setQ] = useState("");
  const [region, setRegion] = useState<string>("all");
  const [status, setStatus] = useState<"all" | StationStatus>("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "name",
    dir: "asc",
  });
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const regions = useMemo(() => Array.from(new Set(stations.map((s) => s.region))).sort(), [stations]);

  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return stations.filter((s) =>
      (status === "all" || s.status === status) &&
      (region === "all" || s.region === region) &&
      (ql === "" ||
        s.name.toLowerCase().includes(ql) ||
        String(s.id).includes(ql) ||
        s.vpn_ip.includes(ql) ||
        s.local_ip.includes(ql) ||
        s.address.toLowerCase().includes(ql))
    );
  }, [stations, q, region, status]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const av = a[sort.key]; const bv = b[sort.key];
      if (av < bv) return sort.dir === "asc" ? -1 : 1;
      if (av > bv) return sort.dir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sort]);

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const curPage = Math.min(page, pages);
  const slice = sorted.slice((curPage - 1) * pageSize, curPage * pageSize);

  function toggleSort(key: SortKey) {
    setSort((s) => s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" });
  }

  return (
    <>
      <Topbar title="Stations" subtitle={`${stations.length} parking stations registered · ${filtered.length} match filters`} />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="glass rounded-xl p-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="size-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }}
              placeholder="Search by name, ID, IP, address…"
              className="w-full h-9 pl-9 pr-3 rounded-md bg-input/60 border border-border text-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
            />
          </div>
          <Select value={region} onChange={(v) => { setRegion(v); setPage(1); }} options={[["all", "All regions"], ...regions.map((r) => [r, r] as [string, string])]} />
          <Select value={status} onChange={(v) => { setStatus(v as StationStatus | "all"); setPage(1); }} options={[["all", "All statuses"], ["online", "Online"], ["warning", "Warning"], ["offline", "Offline"]]} />
        </div>

        <div className="glass rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-panel/60 text-muted-foreground text-[11px] uppercase tracking-wider">
                <tr>
                  <Th onClick={() => toggleSort("id")}>ID</Th>
                  <Th onClick={() => toggleSort("name")}>Station</Th>
                  <Th onClick={() => toggleSort("region")}>Region</Th>
                  <th className="text-left font-medium px-4 py-3">Address</th>
                  <th className="text-left font-medium px-4 py-3">VPN IP</th>
                  <th className="text-left font-medium px-4 py-3">Local IP</th>
                  <Th onClick={() => toggleSort("status")}>Status</Th>
                  <th className="text-right font-medium px-4 py-3">Ping</th>
                  <Th onClick={() => toggleSort("cpu")}>CPU</Th>
                  <Th onClick={() => toggleSort("ram")}>RAM</Th>
                  <Th onClick={() => toggleSort("disk")}>Disk</Th>
                  <th className="text-left font-medium px-4 py-3">Last Seen</th>
                  <th className="text-right font-medium px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {slice.map((s) => (
                  <tr key={s.id} className="border-t border-border hover:bg-accent/30 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{s.id}</td>
                    <td className="px-4 py-3 font-medium">{s.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{s.region}</td>
                    <td className="px-4 py-3 text-muted-foreground max-w-[180px] truncate">{s.address}</td>
                    <td className="px-4 py-3 font-mono text-xs">{s.vpn_ip}</td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{s.local_ip}</td>
                    <td className="px-4 py-3"><StatusBadge status={s.status as StationStatus} /></td>
                    <td className={`px-4 py-3 text-right font-mono tabular-nums ${pingTone(s.last_ping_ms, s.status)}`}>{s.last_ping_ms || "—"}ms</td>
                    <td className="px-4 py-3 w-[110px]"><Meter value={s.cpu} /></td>
                    <td className="px-4 py-3 w-[110px]"><Meter value={s.ram} /></td>
                    <td className="px-4 py-3 w-[110px]"><Meter value={s.disk} /></td>
                    <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">{s.last_seen
  ? new Date(s.last_seen).toLocaleTimeString()
  : "-"}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <ActionBtn title="View"><Eye className="size-3.5" /></ActionBtn>
                        <ActionBtn title="Edit"><Pencil className="size-3.5" /></ActionBtn>
                        <ActionBtn title="Open camera"><Video className="size-3.5" /></ActionBtn>
                        <ActionBtn title="RustDesk"><Monitor className="size-3.5" /></ActionBtn>
                        <ActionBtn title="Terminal"><TerminalSquare className="size-3.5" /></ActionBtn>
                      </div>
                    </td>
                  </tr>
                ))}
                {slice.length === 0 && (
                  <tr><td colSpan={13} className="px-4 py-10 text-center text-sm text-muted-foreground">No stations match the current filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground">
            <span>
              Showing {(curPage - 1) * pageSize + 1}–{Math.min(curPage * pageSize, sorted.length)} of {sorted.length}
            </span>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={curPage === 1} className="h-7 px-2 rounded-md border border-border hover:bg-accent disabled:opacity-40 inline-flex items-center gap-1"><ChevronLeft className="size-3.5" /></button>
              <span className="px-2 tabular-nums">Page {curPage} / {pages}</span>
              <button onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={curPage === pages} className="h-7 px-2 rounded-md border border-border hover:bg-accent disabled:opacity-40 inline-flex items-center gap-1"><ChevronRight className="size-3.5" /></button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function Th({ children, onClick, className }: { children: React.ReactNode; onClick?: () => void; className?: string }) {
  return (
    <th className={`text-left font-medium px-4 py-3 ${className ?? ""}`}>
      <button onClick={onClick} className="inline-flex items-center gap-1 hover:text-foreground">
        {children} <ArrowUpDown className="size-3 opacity-60" />
      </button>
    </th>
  );
}

function ActionBtn({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <button title={title} className="size-7 grid place-items-center rounded-md border border-border bg-accent/40 hover:bg-accent text-muted-foreground hover:text-foreground transition-colors">
      {children}
    </button>
  );
}

function Select({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 px-3 rounded-md bg-input/60 border border-border text-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
    >
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}
