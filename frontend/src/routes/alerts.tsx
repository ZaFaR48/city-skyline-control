import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Search } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { acknowledgeAlert, getAlerts } from "@/lib/api";
import type { AlertItem, AlertSeverity } from "@/lib/types";

export const Route = createFileRoute("/alerts")({ component: AlertsPage });
function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [severity, setSeverity] = useState<AlertSeverity | "">("");
  const load = useCallback(
    () =>
      getAlerts({ active: true, limit: 500 })
        .then(setAlerts)
        .catch((err) =>
          setError(err instanceof Error ? err.message : "Alerts could not be loaded"),
        ),
    [],
  );
  useEffect(() => {
    void load();
  }, [load]);
  const filtered = useMemo(
    () =>
      alerts.filter(
        (alert) =>
          (!severity || alert.severity === severity) &&
          (!q ||
            alert.message.toLowerCase().includes(q.toLowerCase()) ||
            alert.type.includes(q.toLowerCase())),
      ),
    [alerts, q, severity],
  );
  async function ack(id: number) {
    try {
      await acknowledgeAlert(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Alert could not be acknowledged");
    }
  }
  return (
    <>
      <Topbar title="Alerts" subtitle={`${alerts.length} active alerts`} />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {error && <div className="glass p-4 text-destructive">{error}</div>}
        <div className="glass rounded-xl p-4 flex gap-3">
          <div className="relative flex-1">
            <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Search active alerts…"
              className="w-full h-9 pl-9 rounded-md bg-input border border-border"
            />
          </div>
          <select
            value={severity}
            onChange={(event) => setSeverity(event.target.value as AlertSeverity | "")}
            className="h-9 px-3 rounded-md bg-input border border-border"
          >
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
        </div>
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full min-w-[800px] text-sm">
            <thead className="text-left text-xs uppercase text-muted-foreground bg-panel">
              <tr>
                <th className="p-3">Severity</th>
                <th>Type</th>
                <th>Message</th>
                <th>Created</th>
                <th>Acknowledged</th>
                <th className="text-right p-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((alert) => (
                <tr key={alert.id} className="border-t border-border">
                  <td className="p-3 capitalize">{alert.severity}</td>
                  <td className="capitalize">{alert.type.replaceAll("_", " ")}</td>
                  <td className="max-w-[420px] truncate" title={alert.message}>
                    {alert.message}
                  </td>
                  <td className="text-xs">{new Date(alert.created_at).toLocaleString()}</td>
                  <td>{alert.acknowledged ? "Yes" : "No"}</td>
                  <td className="p-3 text-right">
                    <button
                      disabled={alert.acknowledged}
                      onClick={() => ack(alert.id)}
                      className="inline-flex gap-1 items-center border border-border rounded px-2 py-1 disabled:opacity-40"
                    >
                      <Check className="size-3.5" /> Ack
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-14 text-center text-muted-foreground">
                    No active alerts match.
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
