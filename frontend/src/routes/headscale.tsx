import { createFileRoute } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import {
  approveHeadscaleNode,
  applyHeadscaleClassification,
  getHeadscaleNodes,
  getHeadscaleStationOptions,
  previewHeadscaleApproval,
  previewHeadscaleClassification,
  rejectHeadscaleNode,
  syncHeadscale,
} from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type {
  ApprovalStatus,
  DeviceType,
  HeadscaleApprovalPreview,
  HeadscaleClassificationPreview,
  HeadscaleNode,
  HeadscaleStationOption,
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
const PAGE_SIZE = 25;

function useDebounced(value: string, delay = 350) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function HeadscalePage() {
  const { t } = useI18n();
  const user = getStoredUser<User>();
  const isAdmin = user?.role === "admin";
  const [filters, setFilters] = useState<Filters>(INITIAL_FILTERS);
  const [queryText, setQueryText] = useState("");
  const query = useDebounced(queryText);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selections, setSelections] = useState<Record<number, Selection>>({});
  const [preview, setPreview] = useState<HeadscaleApprovalPreview | null>(null);
  const [classificationPreview, setClassificationPreview] =
    useState<HeadscaleClassificationPreview | null>(null);
  const [classificationConfirmation, setClassificationConfirmation] = useState("");

  const nodeParams = useMemo(
    () => ({
      q: query,
      approval_status: filters.approval || undefined,
      device_type: filters.deviceType || undefined,
      online: filters.online || undefined,
      linked: filters.linked || undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [filters, query, page],
  );
  useEffect(() => setPage(1), [filters, query]);
  const nodesQuery = useQuery({
    queryKey: ["headscale", "nodes", nodeParams],
    queryFn: ({ signal }) => getHeadscaleNodes(nodeParams, signal),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
  const stationsQuery = useQuery({
    queryKey: ["headscale", "station-options"],
    queryFn: ({ signal }) => getHeadscaleStationOptions(signal),
    staleTime: 30_000,
  });
  const nodes: HeadscaleNode[] = nodesQuery.data?.items ?? [];
  const stations: HeadscaleStationOption[] = stationsQuery.data ?? [];

  async function load() {
    await Promise.all([nodesQuery.refetch(), stationsQuery.refetch()]);
  }

  const pendingCount = nodesQuery.data?.pending_count ?? 0;
  const linkedCount = nodesQuery.data?.linked_count ?? 0;
  const pages = Math.max(1, Math.ceil((nodesQuery.data?.total ?? 0) / PAGE_SIZE));

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

  async function openClassificationPreview(node: HeadscaleNode) {
    const selection = selections[node.id] ?? {
      type: node.device_type,
      stationId: node.station_id ? String(node.station_id) : "",
    };
    setBusy(true);
    setError(null);
    setClassificationConfirmation("");
    try {
      setClassificationPreview(
        await previewHeadscaleClassification(
          node.id,
          selection.type,
          selection.type === "station" && selection.stationId
            ? Number(selection.stationId)
            : undefined,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Classification preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function confirmClassification() {
    if (
      !classificationPreview?.valid ||
      !classificationPreview.preview_token ||
      classificationConfirmation !== classificationPreview.confirmation_phrase
    )
      return;
    setBusy(true);
    setError(null);
    try {
      await applyHeadscaleClassification(
        classificationPreview.node_id,
        classificationPreview.proposed_device_type,
        classificationPreview.proposed_station_id ?? undefined,
        classificationPreview.preview_token,
        classificationConfirmation,
      );
      setClassificationPreview(null);
      setClassificationConfirmation("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Classification update failed");
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
        subtitle={
          nodesQuery.data
            ? `${linkedCount} linked station nodes · ${pendingCount} pending in current view`
            : t("loading.headscale")
        }
      />
      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {(error || nodesQuery.error || stationsQuery.error) && (
          <div className="glass p-4 text-destructive flex justify-between gap-3">
            <span>
              {error ||
                (nodesQuery.error instanceof Error ? nodesQuery.error.message : null) ||
                (stationsQuery.error instanceof Error ? stationsQuery.error.message : null) ||
                t("api.unavailable")}
            </span>
            <button onClick={() => void load()} className="inline-flex items-center gap-2">
              <RefreshCw className="size-4" /> {t("common.retry")}
            </button>
          </div>
        )}
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

        <div className="glass grid gap-3 rounded-xl p-4 sm:grid-cols-2 xl:grid-cols-6">
          <label className="relative self-end">
            <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <input
              value={queryText}
              onChange={(event) => setQueryText(event.target.value)}
              placeholder="Search node, VPN, or station"
              className="h-9 w-full rounded border border-border bg-input pl-9 pr-3 text-sm"
            />
          </label>
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
                        ) : node.approval_status === "approved" ? (
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
                              onClick={() => openClassificationPreview(node)}
                              className="grid size-8 place-items-center rounded border border-primary/40 text-primary disabled:opacity-40"
                              title="Edit classification / Link station"
                            >
                              <Settings2 className="size-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="text-right text-xs text-muted-foreground">Rejected</div>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
              {nodesQuery.isSuccess && !nodesQuery.isPlaceholderData && nodes.length === 0 && (
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
          <div className="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-muted-foreground">
            <span>
              {nodesQuery.data
                ? `Showing ${nodesQuery.data.offset + (nodes.length ? 1 : 0)}–${nodesQuery.data.offset + nodes.length} of ${nodesQuery.data.total}`
                : t("loading.headscale")}
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage((value) => value - 1)}
                className="rounded border border-border p-1 disabled:opacity-40"
              >
                <ChevronLeft className="size-4" />
              </button>
              <span>
                Page {page} / {pages}
              </span>
              <button
                disabled={page >= pages}
                onClick={() => setPage((value) => value + 1)}
                className="rounded border border-border p-1 disabled:opacity-40"
              >
                <ChevronRight className="size-4" />
              </button>
            </div>
          </div>
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
      {classificationPreview && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-background/80 p-4 backdrop-blur-sm">
          <div className="glass w-full max-w-2xl rounded-xl p-5 shadow-2xl">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h2 className="font-semibold">Edit classification / Link station</h2>
                <p className="text-xs text-muted-foreground">
                  Approval remains approved. Linking does not publish the station.
                </p>
              </div>
              <button onClick={() => setClassificationPreview(null)}>
                <X className="size-5" />
              </button>
            </div>
            <dl className="grid grid-cols-[11rem_1fr] gap-2 text-sm">
              <dt className="text-muted-foreground">Node</dt>
              <dd>
                #{classificationPreview.node_id} · {classificationPreview.hostname}
              </dd>
              <dt className="text-muted-foreground">VPN IP</dt>
              <dd className="font-mono">{classificationPreview.vpn_ip ?? "—"}</dd>
              <dt className="text-muted-foreground">Connectivity</dt>
              <dd>{classificationPreview.online ? "Online" : "Offline"}</dd>
              <dt className="text-muted-foreground">Approval</dt>
              <dd>{classificationPreview.approval_status}</dd>
              <dt className="text-muted-foreground">Device type</dt>
              <dd>
                {classificationPreview.current_device_type} →{" "}
                {classificationPreview.proposed_device_type}
              </dd>
              <dt className="text-muted-foreground">Station link</dt>
              <dd>
                {classificationPreview.current_station_code ?? "None"} →{" "}
                {classificationPreview.proposed_station_code ?? "None"}
              </dd>
              <dt className="text-muted-foreground">Station VPN</dt>
              <dd className="font-mono">
                {classificationPreview.station_vpn_ip ?? "—"} →{" "}
                {classificationPreview.proposed_station_vpn_ip ?? "—"}
              </dd>
            </dl>
            {classificationPreview.vpn_replacement_warning && (
              <div className="mt-4 rounded border border-warning/40 p-3 text-sm text-warning">
                <AlertTriangle className="mr-2 inline size-4" />
                {classificationPreview.vpn_replacement_warning}
              </div>
            )}
            {classificationPreview.errors.length > 0 && (
              <div className="mt-4 rounded border border-destructive/40 p-3 text-sm text-destructive">
                {classificationPreview.errors.join(" · ")}
              </div>
            )}
            {classificationPreview.valid && (
              <label className="mt-4 block text-xs">
                Type <code>{classificationPreview.confirmation_phrase}</code> to confirm
                <input
                  value={classificationConfirmation}
                  onChange={(event) => setClassificationConfirmation(event.target.value)}
                  className="mt-1 block h-9 w-full rounded border border-border bg-input px-3"
                />
              </label>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setClassificationPreview(null)}
                className="h-9 rounded border border-border px-4 text-xs"
              >
                Cancel
              </button>
              <button
                disabled={
                  busy ||
                  !classificationPreview.valid ||
                  classificationConfirmation !== classificationPreview.confirmation_phrase
                }
                onClick={confirmClassification}
                className="h-9 rounded bg-primary px-4 text-xs text-primary-foreground disabled:opacity-40"
              >
                Apply classification
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
