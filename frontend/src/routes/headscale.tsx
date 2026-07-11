import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import {
  approveHeadscaleNode,
  getHeadscaleNodes,
  getStations,
  rejectHeadscaleNode,
  syncHeadscale,
} from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import type { DeviceType, HeadscaleNode, Station, User } from "@/lib/types";

export const Route = createFileRoute("/headscale")({ component: HeadscalePage });
const DEVICE_TYPES: DeviceType[] = [
  "station",
  "operator_pc",
  "admin_pc",
  "phone",
  "server",
  "unknown",
];

function HeadscalePage() {
  const user = getStoredUser<User>();
  const isAdmin = user?.role === "admin";
  const [nodes, setNodes] = useState<HeadscaleNode[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selections, setSelections] = useState<
    Record<number, { type: DeviceType; stationId: string }>
  >({});
  const load = useCallback(async () => {
    setError(null);
    try {
      const [nodeRows, stationRows] = await Promise.all([
        getHeadscaleNodes(),
        getStations({ limit: 200 }),
      ]);
      setNodes(nodeRows);
      setStations(stationRows.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Headscale inventory unavailable");
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  async function sync() {
    setBusy(true);
    try {
      await syncHeadscale();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Synchronization failed");
    } finally {
      setBusy(false);
    }
  }
  async function approve(node: HeadscaleNode) {
    const selection = selections[node.id] ?? { type: "unknown" as DeviceType, stationId: "" };
    try {
      await approveHeadscaleNode(
        node.id,
        selection.type,
        selection.type === "station" && selection.stationId
          ? Number(selection.stationId)
          : undefined,
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed");
    }
  }
  async function reject(id: number) {
    try {
      await rejectHeadscaleNode(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rejection failed");
    }
  }
  const approvedStations = nodes.filter(
    (node) =>
      node.approval_status === "approved" &&
      node.device_type === "station" &&
      node.station_id !== null,
  ).length;
  return (
    <>
      <Topbar
        title="Headscale Inventory"
        subtitle={`${approvedStations} approved station nodes · ${nodes.filter((node) => node.approval_status === "pending").length} pending`}
      />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {error && <div className="glass p-4 text-destructive">{error}</div>}
        <div className="glass rounded-xl p-4 flex justify-between">
          <div>
            <div className="font-medium">Device inventory</div>
            <div className="text-xs text-muted-foreground">
              Devices do not count as stations until explicitly approved and linked.
            </div>
          </div>
          {isAdmin && (
            <button
              disabled={busy}
              onClick={sync}
              className="inline-flex gap-2 items-center border border-border rounded px-3 text-xs"
            >
              <RefreshCw className={`size-4 ${busy ? "animate-spin" : ""}`} /> Sync now
            </button>
          )}
        </div>
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full min-w-[1150px] text-sm">
            <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Hostname</th>
                <th>VPN IP</th>
                <th>OS</th>
                <th>Online</th>
                <th>Device type</th>
                <th>Approval</th>
                <th>Station</th>
                <th>Last seen</th>
                {isAdmin && <th className="text-right p-3">Review</th>}
              </tr>
            </thead>
            <tbody>
              {nodes.map((node) => {
                const selection = selections[node.id] ?? {
                  type: node.device_type,
                  stationId: node.station_id ? String(node.station_id) : "",
                };
                return (
                  <tr key={node.id} className="border-t border-border">
                    <td className="p-3">
                      <div className="font-medium">{node.hostname}</div>
                      <div className="text-xs text-muted-foreground">{node.given_name ?? "—"}</div>
                    </td>
                    <td className="font-mono text-xs">{node.vpn_ip ?? "—"}</td>
                    <td>{node.operating_system ?? "—"}</td>
                    <td>{node.online ? "Online" : "Offline"}</td>
                    <td className="capitalize">{node.device_type.replaceAll("_", " ")}</td>
                    <td className="capitalize">{node.approval_status}</td>
                    <td>
                      {node.station_id
                        ? (stations.find((station) => station.id === node.station_id)
                            ?.station_code ?? `#${node.station_id}`)
                        : "—"}
                    </td>
                    <td className="text-xs">
                      {node.last_seen_at ? new Date(node.last_seen_at).toLocaleString() : "—"}
                    </td>
                    {isAdmin && (
                      <td className="p-3">
                        <div className="flex justify-end gap-2">
                          {node.approval_status === "pending" ? (
                            <>
                              <select
                                value={selection.type}
                                onChange={(event) =>
                                  setSelections((current) => ({
                                    ...current,
                                    [node.id]: {
                                      ...selection,
                                      type: event.target.value as DeviceType,
                                    },
                                  }))
                                }
                                className="h-8 bg-input border border-border rounded text-xs"
                              >
                                {DEVICE_TYPES.map((type) => (
                                  <option key={type} value={type}>
                                    {type.replaceAll("_", " ")}
                                  </option>
                                ))}
                              </select>
                              {selection.type === "station" && (
                                <select
                                  value={selection.stationId}
                                  onChange={(event) =>
                                    setSelections((current) => ({
                                      ...current,
                                      [node.id]: { ...selection, stationId: event.target.value },
                                    }))
                                  }
                                  className="h-8 bg-input border border-border rounded text-xs"
                                >
                                  <option value="">Select station</option>
                                  {stations
                                    .filter(
                                      (station) =>
                                        !station.headscale_linked || station.id === node.station_id,
                                    )
                                    .map((station) => (
                                      <option key={station.id} value={station.id}>
                                        {station.station_code} · {station.name}
                                      </option>
                                    ))}
                                </select>
                              )}
                              <button
                                onClick={() => approve(node)}
                                className="size-8 grid place-items-center border border-success/40 text-success rounded"
                                title="Approve"
                              >
                                <ShieldCheck className="size-4" />
                              </button>
                              <button
                                onClick={() => reject(node.id)}
                                className="size-8 grid place-items-center border border-destructive/40 text-destructive rounded"
                                title="Reject"
                              >
                                <XCircle className="size-4" />
                              </button>
                            </>
                          ) : (
                            <span className="text-xs text-muted-foreground">Reviewed</span>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
              {nodes.length === 0 && (
                <tr>
                  <td colSpan={isAdmin ? 9 : 8} className="py-14 text-center text-muted-foreground">
                    No Headscale inventory data.
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
