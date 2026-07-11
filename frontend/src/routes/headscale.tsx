import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, ShieldCheck, X, XCircle } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import {
  approveHeadscaleNode,
  getHeadscaleNodes,
  getStations,
  previewHeadscaleApproval,
  rejectHeadscaleNode,
  syncHeadscale,
} from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import type {
  ApprovalStatus,
  DeviceType,
  HeadscaleApprovalPreview,
  HeadscaleNode,
  Station,
  User,
} from "@/lib/types";

export const Route = createFileRoute("/headscale")({ component: HeadscalePage });

const DEVICE_TYPES: DeviceType[] = [
  "station",
  "operator_pc",
  "admin_pc",
  "phone",
  "server",
  "unknown",
];

type Selection = { type: DeviceType; stationId: string };
type Filters = {
  approval: ApprovalStatus | "";
  deviceType: DeviceType | "";
  online: "" | "true" | "false";
  linked: "" | "true" | "false";
};

const INITIAL_FILTERS: Filters = { approval: "", deviceType: "", online: "", linked: "" };

function HeadscalePage() {
  const user = getStoredUser<User>();
  const isAdmin = user?.role === "admin";
  const [nodes, setNodes] = useState<HeadscaleNode[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [filters, setFilters] = useState<Filters>(INITIAL_FILTERS);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selections, setSelections] = useState<Record<number, Selection>>({});
  const [preview, setPreview] = useState<HeadscaleApprovalPreview | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [nodeRows, stationRows] = await Promise.all([
        getHeadscaleNodes({
          approval_status: filters.approval || undefined,
          device_type: filters.deviceType || undefined,
          online: filters.online || undefined,
          linked: filters.linked || undefined,
        }),
        getStations({ limit: 200 }),
      ]);
      setNodes(nodeRows);
      setStations(stationRows.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Headscale inventory unavailable");
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

  const pendingCount = useMemo(
    () => nodes.filter((node) => node.approval_status === "pending").length,
    [nodes],
  );
  const linkedCount = useMemo(
    () => nodes.filter((node) => node.station_id !== null).length,
    [nodes],
  );

  async function sync() {
    setBusy(true);
    setError(null);
    try {
      await syncHeadscale();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Synchronization failed");
    } finally {
      setBusy(false);
    }
  }

  async function openApprovalPreview(node: HeadscaleNode) {
    const selection = selections[node.id] ?? { type: node.device_type, stationId: "" };
    setBusy(true);
    setError(null);
    try {
      const result = await previewHeadscaleApproval(
        node.id,
        selection.type,
        selection.type === "station" && selection.stationId
          ? Number(selection.stationId)
          : undefined,
      );
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function confirmApproval() {
    if (!preview?.valid || !preview.preview_token) return;
    setBusy(true);
    setError(null);
    try {
      await approveHeadscaleNode(
        preview.node_id,
        preview.device_type,
        preview.station_id ?? undefined,
        preview.preview_token,
      );
      setPreview(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  }

  async function reject(node: HeadscaleNode) {
    if (!window.confirm(`Reject Headscale node #${node.id} (${node.hostname})?`)) return;
    setBusy(true);
    setError(null);
    try {
      await rejectHeadscaleNode(node.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rejection failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Topbar
        title="Headscale Inventory"
        subtitle={`${linkedCount} linked station nodes · ${pendingCount} pending in current view`}
      />
      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {error && <div className="glass p-4 text-destructive">{error}</div>}
        <div className="glass flex flex-wrap items-end justify-between gap-4 rounded-xl p-4">
          <div>
            <div className="font-medium">Device inventory</div>
            <div className="text-xs text-muted-foreground">
              A device counts as a station only after an administrator approves and links it.
            </div>
          </div>
          {isAdmin && (
            <button
              disabled={busy}
              onClick={sync}
              className="inline-flex h-9 items-center gap-2 rounded border border-border px-3 text-xs"
            >
              <RefreshCw className={`size-4 ${busy ? "animate-spin" : ""}`} /> Sync now
            </button>
          )}
        </div>

        <div className="glass grid gap-3 rounded-xl p-4 sm:grid-cols-2 xl:grid-cols-5">
          <Filter
            label="Approval"
            value={filters.approval}
            onChange={(approval) =>
              setFilters((f) => ({ ...f, approval: approval as Filters["approval"] }))
            }
          >
            <option value="">All approvals</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </Filter>
          <Filter
            label="Link"
            value={filters.linked}
            onChange={(linked) =>
              setFilters((f) => ({ ...f, linked: linked as Filters["linked"] }))
            }
          >
            <option value="">All links</option>
            <option value="true">Linked</option>
            <option value="false">Unlinked</option>
          </Filter>
          <Filter
            label="Device type"
            value={filters.deviceType}
            onChange={(deviceType) =>
              setFilters((f) => ({ ...f, deviceType: deviceType as Filters["deviceType"] }))
            }
          >
            <option value="">All device types</option>
            {DEVICE_TYPES.map((type) => (
              <option key={type} value={type}>
                {type.replaceAll("_", " ")}
              </option>
            ))}
          </Filter>
          <Filter
            label="Connectivity"
            value={filters.online}
            onChange={(online) =>
              setFilters((f) => ({ ...f, online: online as Filters["online"] }))
            }
          >
            <option value="">All connectivity</option>
            <option value="true">Online</option>
            <option value="false">Offline</option>
          </Filter>
          <button
            onClick={() => setFilters(INITIAL_FILTERS)}
            className="h-9 self-end rounded border border-border px-3 text-xs"
          >
            Clear filters
          </button>
        </div>

        <div className="glass overflow-x-auto rounded-xl">
          <table className="w-full min-w-[1320px] text-sm">
            <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Node</th>
                <th>Hostname / name</th>
                <th>VPN IP</th>
                <th>OS</th>
                <th>Online</th>
                <th>Device type</th>
                <th>Approval</th>
                <th>Linked station</th>
                <th>Last seen</th>
                {isAdmin && <th className="p-3 text-right">Review</th>}
              </tr>
            </thead>
            <tbody>
              {nodes.map((node) => {
                const selection = selections[node.id] ?? {
                  type: node.device_type,
                  stationId: node.station_id ? String(node.station_id) : "",
                };
                return (
                  <tr key={node.id} className="border-t border-border align-top">
                    <td className="p-3 font-mono text-xs">#{node.id}</td>
                    <td>
                      <div className="font-medium">{node.hostname}</div>
                      <div className="text-xs text-muted-foreground">{node.given_name ?? "—"}</div>
                    </td>
                    <td className="font-mono text-xs">
                      {node.vpn_ip ?? "—"}
                      {node.duplicate_vpn_ip && (
                        <div className="mt-1 flex items-center gap-1 text-destructive">
                          <AlertTriangle className="size-3" /> duplicate
                          {node.duplicate_vpn_node_ids.length
                            ? ` with #${node.duplicate_vpn_node_ids.join(", #")}`
                            : ""}
                        </div>
                      )}
                    </td>
                    <td>{node.operating_system ?? "—"}</td>
                    <td>{node.online ? "Online" : "Offline"}</td>
                    <td className="capitalize">{node.device_type.replaceAll("_", " ")}</td>
                    <td className="capitalize">{node.approval_status}</td>
                    <td>
                      {node.linked_station_code ? (
                        <>
                          <div>{node.linked_station_code}</div>
                          <div className="text-xs text-muted-foreground">
                            {node.linked_station_name}
                          </div>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="text-xs">
                      {node.last_seen_at ? new Date(node.last_seen_at).toLocaleString() : "—"}
                    </td>
                    {isAdmin && (
                      <td className="p-3">
                        {node.approval_status === "pending" ? (
                          <div className="flex justify-end gap-2">
                            <select
                              value={selection.type}
                              onChange={(event) =>
                                setSelections((current) => ({
                                  ...current,
                                  [node.id]: {
                                    ...selection,
                                    type: event.target.value as DeviceType,
                                    stationId:
                                      event.target.value === "station" ? selection.stationId : "",
                                  },
                                }))
                              }
                              className="h-8 rounded border border-border bg-input text-xs"
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
                                className="h-8 max-w-52 rounded border border-border bg-input text-xs"
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
                              disabled={
                                busy || (selection.type === "station" && !selection.stationId)
                              }
                              onClick={() => openApprovalPreview(node)}
                              className="grid size-8 place-items-center rounded border border-success/40 text-success disabled:opacity-40"
                              title="Preview approval"
                            >
                              <ShieldCheck className="size-4" />
                            </button>
                            <button
                              disabled={busy}
                              onClick={() => reject(node)}
                              className="grid size-8 place-items-center rounded border border-destructive/40 text-destructive"
                              title="Reject"
                            >
                              <XCircle className="size-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="text-right text-xs text-muted-foreground">Reviewed</div>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
              {nodes.length === 0 && (
                <tr>
                  <td
                    colSpan={isAdmin ? 10 : 9}
                    className="py-14 text-center text-muted-foreground"
                  >
                    No nodes match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {preview && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-background/80 p-4 backdrop-blur-sm">
          <div className="glass w-full max-w-xl rounded-xl p-5 shadow-2xl">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h2 className="font-semibold">Confirm Headscale approval</h2>
                <p className="text-xs text-muted-foreground">
                  Review the exact node and station mapping before applying.
                </p>
              </div>
              <button onClick={() => setPreview(null)}>
                <X className="size-5" />
              </button>
            </div>
            <dl className="grid grid-cols-[10rem_1fr] gap-2 text-sm">
              <dt className="text-muted-foreground">Node</dt>
              <dd>
                #{preview.node_id} · {preview.node_hostname}
              </dd>
              <dt className="text-muted-foreground">VPN IP</dt>
              <dd className="font-mono">{preview.vpn_ip ?? "—"}</dd>
              <dt className="text-muted-foreground">Current station VPN</dt>
              <dd className="font-mono">{preview.station_vpn_ip ?? "—"}</dd>
              <dt className="text-muted-foreground">Device type</dt>
              <dd>{preview.device_type.replaceAll("_", " ")}</dd>
              <dt className="text-muted-foreground">Station</dt>
              <dd>
                {preview.station_code
                  ? `${preview.station_code} · ${preview.station_name}`
                  : "Not linked"}
              </dd>
              <dt className="text-muted-foreground">District</dt>
              <dd>{preview.district ?? "—"}</dd>
              <dt className="text-muted-foreground">Existing links</dt>
              <dd>
                {preview.node_existing_station_id || preview.station_existing_node_id
                  ? `node→${preview.node_existing_station_id ?? "none"}; station→node #${preview.station_existing_node_id ?? "none"}`
                  : "None"}
              </dd>
            </dl>
            {preview.vpn_replacement_warning && (
              <div className="mt-4 rounded border border-warning/40 p-3 text-sm text-warning">
                <AlertTriangle className="mr-2 inline size-4" />
                {preview.vpn_replacement_warning}
              </div>
            )}
            {preview.errors.length > 0 && (
              <div className="mt-4 rounded border border-destructive/40 p-3 text-sm text-destructive">
                {preview.errors.join(" · ")}
              </div>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setPreview(null)}
                className="h-9 rounded border border-border px-4 text-xs"
              >
                Cancel
              </button>
              <button
                disabled={busy || !preview.valid || !preview.preview_token}
                onClick={confirmApproval}
                className="h-9 rounded bg-primary px-4 text-xs text-primary-foreground disabled:opacity-40"
              >
                Approve and link
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Filter({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="space-y-1 text-xs text-muted-foreground">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="block h-9 w-full rounded border border-border bg-input px-2 text-foreground"
      >
        {children}
      </select>
    </label>
  );
}
