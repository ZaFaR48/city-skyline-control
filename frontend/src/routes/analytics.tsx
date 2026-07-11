import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Topbar } from "@/components/Topbar";
import { getRegions, getUptimeReport } from "@/lib/api";
import type { Region, UptimeReportRow } from "@/lib/types";

export const Route = createFileRoute("/analytics")({ component: ReportsPage });
function isoInput(date: Date) {
  return date.toISOString().slice(0, 16);
}
function fmt(seconds: number | null) {
  if (seconds === null) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}
function ReportsPage() {
  const now = useMemo(() => new Date(), []);
  const startDefault = useMemo(() => new Date(now.getTime() - 7 * 86400_000), [now]);
  const [start, setStart] = useState(isoInput(startDefault));
  const [end, setEnd] = useState(isoInput(now));
  const [district, setDistrict] = useState("");
  const [regions, setRegions] = useState<Region[]>([]);
  const [rows, setRows] = useState<UptimeReportRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    getRegions(true)
      .then(setRegions)
      .catch(() => setRegions([]));
  }, []);
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(
        await getUptimeReport(
          new Date(start).toISOString(),
          new Date(end).toISOString(),
          district ? Number(district) : undefined,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [start, end, district]);
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
        </div>
        {error && <div className="glass p-4 text-destructive">{error}</div>}
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full min-w-[1200px] text-sm">
            <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Code / station</th>
                <th>District</th>
                <th>Availability</th>
                <th>Online</th>
                <th>Offline</th>
                <th>Degraded</th>
                <th>Unknown</th>
                <th>Outages</th>
                <th>Longest</th>
                <th>Average</th>
                <th>Current</th>
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
                  <td>{fmt(row.online_seconds)}</td>
                  <td>{fmt(row.offline_seconds)}</td>
                  <td>{fmt(row.degraded_seconds)}</td>
                  <td>{fmt(row.unknown_seconds)}</td>
                  <td>{row.outages}</td>
                  <td>{fmt(row.longest_outage_seconds)}</td>
                  <td>{fmt(row.average_outage_seconds)}</td>
                  <td>{fmt(row.current_outage_seconds)}</td>
                </tr>
              ))}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={11} className="py-14 text-center text-muted-foreground">
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
