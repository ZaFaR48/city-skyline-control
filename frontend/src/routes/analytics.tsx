import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Topbar } from "@/components/Topbar";
import { downloadUptimeExport, getRegions, getStations, getUptimeReport } from "@/lib/api";
import type { Region, Station, UptimeReportRow } from "@/lib/types";
import type { User } from "@/lib/types";
import { getStoredUser } from "@/lib/auth";

export const Route = createFileRoute("/analytics")({ component: ReportsPage });
function isoInput(date: Date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Dushanbe",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}T${value.hour}:${value.minute}`;
}
const utcFromDushanbeInput = (value: string) => new Date(`${value}:00+05:00`).toISOString();
function fmt(seconds: number | null) {
  if (seconds === null) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}
function ReportsPage() {
  const user = getStoredUser<User>();
  const now = useMemo(() => new Date(), []);
  const startDefault = useMemo(() => new Date(now.getTime() - 24 * 3600_000), [now]);
  const [start, setStart] = useState(isoInput(startDefault));
  const [end, setEnd] = useState(isoInput(now));
  const [district, setDistrict] = useState("");
  const [station, setStation] = useState("");
  const [status, setStatus] = useState("");
  const [regions, setRegions] = useState<Region[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [rows, setRows] = useState<UptimeReportRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState<"csv" | "xlsx" | null>(null);
  useEffect(() => {
    Promise.all([getRegions(true), getStations({ limit: 200 })])
      .then(([regionRows, stationRows]) => {
        setRegions(regionRows);
        setStations(stationRows.items);
      })
      .catch(() => {
        setRegions([]);
        setStations([]);
      });
  }, []);
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const from = utcFromDushanbeInput(start);
      const to = utcFromDushanbeInput(end);
      if (new Date(from) >= new Date(to) || new Date(to) > new Date()) {
        throw new Error("Select a valid past range where From is before To");
      }
      setRows(
        await getUptimeReport(
          from,
          to,
          district ? Number(district) : undefined,
          station ? Number(station) : undefined,
          status || undefined,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [start, end, district, station, status]);
  const download = useCallback(
    async (format: "csv" | "xlsx") => {
      if (exporting) return;
      setExporting(format);
      setError(null);
      try {
        await downloadUptimeExport(
          format,
          utcFromDushanbeInput(start),
          utcFromDushanbeInput(end),
          district ? Number(district) : undefined,
          station ? Number(station) : undefined,
          status || undefined,
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Report export failed");
      } finally {
        setExporting(null);
      }
    },
    [district, end, exporting, start, station, status],
  );
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <>
      <Topbar
        title="Uptime Reports"
        subtitle="Measured status history · unknown intervals remain unknown"
      />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="glass rounded-xl p-4 flex flex-wrap gap-3 items-end">
          <label className="text-xs">
            From
            <input
              type="datetime-local"
              value={start}
              onChange={(event) => setStart(event.target.value)}
              className="block mt-1 h-9 px-3 bg-input border border-border rounded"
            />
          </label>
          <label className="text-xs">
            Station
            <select
              value={station}
              onChange={(event) => setStation(event.target.value)}
              className="block mt-1 h-9 px-3 bg-input border border-border rounded"
            >
              <option value="">All stations</option>
              {stations.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.station_code} · {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs">
            Current status
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              className="block mt-1 h-9 px-3 bg-input border border-border rounded"
            >
              <option value="">All statuses</option>
              {(["online", "degraded", "offline", "unknown"] as const).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs">
            To
            <input
              type="datetime-local"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
              className="block mt-1 h-9 px-3 bg-input border border-border rounded"
            />
          </label>
          <label className="text-xs">
            District
            <select
              value={district}
              onChange={(event) => setDistrict(event.target.value)}
              className="block mt-1 h-9 px-3 bg-input border border-border rounded"
            >
              <option value="">All districts</option>
              {regions
                .filter((region) => region.region_type === "district")
                .map((region) => (
                  <option key={region.id} value={region.id}>
                    {region.name}
                  </option>
                ))}
            </select>
          </label>
          <button
            disabled={loading}
            onClick={load}
            className="h-9 px-4 bg-primary/20 text-primary border border-primary/40 rounded"
          >
            {loading ? "Loading…" : "Run report"}
          </button>
          {user && ["admin", "operator"].includes(user.role) && (
            <>
              <button
                disabled={loading || exporting !== null}
                onClick={() => void download("csv")}
                className="h-9 px-4 border border-border rounded disabled:opacity-50"
              >
                {exporting === "csv" ? "Preparing CSV…" : "Download CSV"}
              </button>
              <button
                disabled={loading || exporting !== null}
                onClick={() => void download("xlsx")}
                className="h-9 px-4 border border-border rounded disabled:opacity-50"
              >
                {exporting === "xlsx" ? "Preparing XLSX…" : "Download XLSX"}
              </button>
            </>
          )}
        </div>
        <div className="glass rounded-xl p-4 text-xs text-muted-foreground">
          Measured uptime = online ÷ (online + degraded + offline). Data coverage = measured time ÷
          selected range. Unknown means no measured data and is never counted as offline.
        </div>
        {error && <div className="glass p-4 text-destructive">{error}</div>}
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full min-w-[1500px] text-sm">
            <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Code / station</th>
                <th>District</th>
                <th>Measured uptime</th>
                <th>Data coverage</th>
                <th>Online</th>
                <th>Offline</th>
                <th>Degraded</th>
                <th>Unknown</th>
                <th>Outages</th>
                <th>Longest</th>
                <th>Average</th>
                <th>Current</th>
                <th>Last change</th>
                <th>Current status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.station_id} className="border-t border-border">
                  <td className="p-3">
                    <div className="font-mono">{row.station_code}</div>
                    <div>{row.station_name}</div>
                  </td>
                  <td>{row.district ?? "—"}</td>
                  <td>
                    {row.availability_percentage === null
                      ? "No data"
                      : `${row.availability_percentage}%`}
                  </td>
                  <td>{row.data_coverage_percentage}%</td>
                  <td>{fmt(row.online_seconds)}</td>
                  <td>{fmt(row.offline_seconds)}</td>
                  <td>{fmt(row.degraded_seconds)}</td>
                  <td>{fmt(row.unknown_seconds)}</td>
                  <td>{row.outages}</td>
                  <td>{fmt(row.longest_outage_seconds)}</td>
                  <td>{fmt(row.average_outage_seconds)}</td>
                  <td>{fmt(row.current_outage_seconds)}</td>
                  <td>
                    {row.last_status_change_at
                      ? new Intl.DateTimeFormat(undefined, {
                          dateStyle: "short",
                          timeStyle: "medium",
                          timeZone: "Asia/Dushanbe",
                        }).format(new Date(row.last_status_change_at))
                      : "—"}
                  </td>
                  <td>{row.current_status}</td>
                </tr>
              ))}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={14} className="py-14 text-center text-muted-foreground">
                    No monitored status history for this period.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
