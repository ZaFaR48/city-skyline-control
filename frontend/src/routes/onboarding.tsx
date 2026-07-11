import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Download, ShieldCheck, Upload } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { StatusBadge } from "@/components/StatusBadge";
import {
  applyDistrictAssignments,
  applyStationApproval,
  applyDistrictCsv,
  applyDuplicateVpnAction,
  downloadDistrictTemplate,
  getDistrictOnboardingStations,
  getDuplicateAlertReport,
  getDuplicateVpnReport,
  getHeadscaleNodes,
  getStationApprovalInventory,
  previewDistrictAssignments,
  previewDistrictCsv,
  previewDuplicateVpnAction,
  previewStationApproval,
} from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import type {
  ActionPreview,
  DistrictAssignment,
  DistrictPreview,
  DuplicateAlertGroup,
  DuplicateVpnGroup,
  HeadscaleNode,
  Station,
  StationApprovalPreview,
  User,
} from "@/lib/types";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/onboarding")({
  head: () => ({ meta: [{ title: "Onboarding · City Parking Control Center" }] }),
  component: OnboardingPage,
});

const DISTRICTS = ["Ismoili Somoni", "Shohmansur", "Sino", "Firdavsi"];
type Tab = "approval" | "districts" | "vpn" | "alerts";
type VpnAction = {
  action: "unlink_node" | "clear_station_vpn" | "select_canonical_node" | "cancel";
  vpn_ip: string;
  station_id?: number;
  node_id?: number;
};

function OnboardingPage() {
  const user = getStoredUser<User>();
  const [tab, setTab] = useState<Tab>("approval");
  if (user?.role !== "admin") {
    return (
      <>
        <Topbar title="Production Onboarding" subtitle="Administrator access required" />
        <div className="flex-1 p-6">
          <div className="glass rounded-xl py-16 text-center text-muted-foreground">
            This workflow is restricted to ADMIN users.
          </div>
        </div>
      </>
    );
  }
  return (
    <>
      <Topbar
        title="Production Onboarding"
        subtitle="Explicit review and confirmation for Dushanbe stations"
      />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="glass rounded-xl p-2 inline-flex gap-1">
          <TabButton active={tab === "approval"} onClick={() => setTab("approval")}>
            Station approval
          </TabButton>
          <TabButton active={tab === "districts"} onClick={() => setTab("districts")}>
            District assignment
          </TabButton>
          <TabButton active={tab === "vpn"} onClick={() => setTab("vpn")}>
            Duplicate VPN report
          </TabButton>
          <TabButton active={tab === "alerts"} onClick={() => setTab("alerts")}>
            Duplicate alert dry-run
          </TabButton>
        </div>
        {tab === "approval" && <StationApprovalWorkflow />}
        {tab === "districts" && <DistrictWorkflow />}
        {tab === "vpn" && <DuplicateVpnWorkflow />}
        {tab === "alerts" && <DuplicateAlertWorkflow />}
      </div>
    </>
  );
}

function StationApprovalWorkflow() {
  const { district: districtName } = useI18n();
  const [filter, setFilter] = useState<"pending" | "approved" | "all">("pending");
  const [stations, setStations] = useState<Station[]>([]);
  const [preview, setPreview] = useState<StationApprovalPreview | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const load = useCallback(async () => {
    setError(null);
    try {
      setStations(await getStationApprovalInventory(filter));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Station approval inventory unavailable");
    }
  }, [filter]);
  useEffect(() => {
    void load();
  }, [load]);

  async function openPreview(station: Station) {
    const action = station.approved_at ? "revoke" : "approve";
    setConfirmation("");
    setMessage(null);
    try {
      setPreview(await previewStationApproval(station.id, action));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Station approval preview failed");
    }
  }

  async function apply() {
    if (!preview?.preview_token || confirmation !== preview.confirmation_phrase) return;
    try {
      await applyStationApproval(
        preview.station_id,
        preview.action,
        preview.preview_token,
        confirmation,
      );
      setMessage(
        preview.action === "approve"
          ? `Station ${preview.station_code} is now visible in production.`
          : `Station ${preview.station_code} was removed from production and returned to pending.`,
      );
      setPreview(null);
      setConfirmation("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Station approval action failed");
    }
  }

  return (
    <section className="space-y-4">
      {error && <Notice tone="error">{error}</Notice>}
      {message && <Notice>{message}</Notice>}
      <div className="glass rounded-xl p-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-semibold inline-flex items-center gap-2">
            <ShieldCheck className="size-4 text-primary" /> Production approval gate
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Stations enter production only after an individual administrator confirmation.
          </p>
        </div>
        <label className="text-xs">
          Approval status
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value as typeof filter)}
            className="block mt-1 h-9 px-3 rounded bg-input border border-border"
          >
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="all">All</option>
          </select>
        </label>
      </div>
      <div className="glass rounded-xl overflow-x-auto max-h-[600px]">
        <table className="w-full min-w-[1500px] text-sm">
          <thead className="sticky top-0 bg-panel text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="p-3">Station code</th>
              <th>Station name</th>
              <th>District</th>
              <th>Address</th>
              <th>VPN IP</th>
              <th>Local IP</th>
              <th>Headscale hostname</th>
              <th>Headscale approval</th>
              <th>Monitoring status</th>
              <th>Production approval</th>
              <th className="text-right p-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr key={station.id} className="border-t border-border">
                <td className="p-3 font-mono">{station.station_code}</td>
                <td>{station.name}</td>
                <td>{districtName(station.district)}</td>
                <td className="max-w-[260px] truncate" title={station.address}>
                  {station.address || "—"}
                </td>
                <td className="font-mono text-xs">{station.vpn_ip ?? "—"}</td>
                <td className="font-mono text-xs">{station.local_ip ?? "—"}</td>
                <td>{station.headscale_hostname ?? "—"}</td>
                <td className="capitalize">{station.headscale_approval_status ?? "—"}</td>
                <td>
                  <StatusBadge status={station.status} />
                </td>
                <td>{station.approved_at ? "Approved" : "Pending"}</td>
                <td className="p-3 text-right">
                  <button
                    onClick={() => openPreview(station)}
                    className={`h-8 px-3 rounded border ${station.approved_at ? "border-warning/40 text-warning" : "border-primary/40 text-primary"}`}
                  >
                    {station.approved_at ? "Remove from production" : "Approve station"}
                  </button>
                </td>
              </tr>
            ))}
            {stations.length === 0 && (
              <tr>
                <td colSpan={11} className="py-14 text-center text-muted-foreground">
                  No stations match this approval filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {preview && (
        <StationApprovalDialog
          preview={preview}
          confirmation={confirmation}
          setConfirmation={setConfirmation}
          apply={apply}
          close={() => {
            setPreview(null);
            setConfirmation("");
          }}
        />
      )}
    </section>
  );
}

function StationApprovalDialog({
  preview,
  confirmation,
  setConfirmation,
  apply,
  close,
}: {
  preview: StationApprovalPreview;
  confirmation: string;
  setConfirmation: (value: string) => void;
  apply: () => void;
  close: () => void;
}) {
  const { district: districtName } = useI18n();
  return (
    <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center p-4">
      <div className="glass bg-background rounded-xl p-5 w-full max-w-2xl max-h-[85vh] overflow-y-auto">
        <h2 className="font-semibold">
          {preview.action === "approve" ? "Station approval preview" : "Production removal preview"}
        </h2>
        <p className="text-xs text-muted-foreground">Read-only preview; no change has been made.</p>
        <dl className="grid grid-cols-2 gap-x-5 gap-y-3 text-sm my-5">
          <PreviewValue label="Station code" value={preview.station_code} mono />
          <PreviewValue label="Station name" value={preview.station_name} />
          <PreviewValue label="District" value={districtName(preview.district)} />
          <PreviewValue label="Address" value={preview.address} />
          <PreviewValue label="VPN IP" value={preview.vpn_ip} mono />
          <PreviewValue label="Linked Headscale node" value={preview.headscale_hostname} />
          <PreviewValue label="Headscale approval" value={preview.headscale_approval_status} />
          <PreviewValue label="Monitoring status" value={preview.monitoring_status} />
          <PreviewValue
            label="Monitoring readiness"
            value={preview.monitoring_ready ? "Ready" : "Not configured"}
          />
          <PreviewValue
            label="Production approval"
            value={preview.production_approved ? "Approved" : "Pending"}
          />
        </dl>
        {preview.warning && <Notice>{preview.warning}</Notice>}
        {preview.errors.map((item) => (
          <p key={item} className="mt-2 text-sm text-destructive">
            {item}
          </p>
        ))}
        {preview.valid && (
          <label className="block text-xs mt-4">
            Type <span className="font-mono">{preview.confirmation_phrase}</span> to confirm
            <input
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              className="block mt-1 w-full h-9 px-3 bg-input border border-border rounded"
            />
          </label>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={close} className="h-9 px-4 border border-border rounded">
            Cancel
          </button>
          <button
            disabled={!preview.valid || confirmation !== preview.confirmation_phrase}
            onClick={apply}
            className="h-9 px-4 border border-primary/40 text-primary rounded disabled:opacity-40"
          >
            {preview.action === "approve" ? "Approve station" : "Remove from production"}
          </button>
        </div>
      </div>
    </div>
  );
}

function PreviewValue({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string | null;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={mono ? "font-mono" : ""}>{value || "—"}</dd>
    </div>
  );
}

function DistrictWorkflow() {
  const { district: districtName } = useI18n();
  const [stations, setStations] = useState<Station[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [district, setDistrict] = useState(DISTRICTS[0]);
  const [preview, setPreview] = useState<DistrictPreview | null>(null);
  const [assignments, setAssignments] = useState<DistrictAssignment[]>([]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const load = useCallback(() => {
    setError(null);
    getDistrictOnboardingStations()
      .then(setStations)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Station inventory unavailable"),
      );
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function previewSelection() {
    const rows = stations
      .filter((station) => selected.has(station.id))
      .map((station) => ({ station_code: station.station_code, district }));
    if (!rows.length) {
      setError("Select at least one station");
      return;
    }
    setCsvFile(null);
    setAssignments(rows);
    setMessage(null);
    try {
      setPreview(await previewDistrictAssignments(rows));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    }
  }

  async function previewCsv(file: File) {
    setCsvFile(file);
    setAssignments([]);
    setMessage(null);
    setError(null);
    try {
      setPreview(await previewDistrictCsv(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "CSV preview failed");
    }
  }

  async function apply() {
    if (!preview?.preview_token || confirmation !== "ASSIGN DISTRICTS") return;
    try {
      const result = csvFile
        ? await applyDistrictCsv(csvFile, preview.preview_token)
        : await applyDistrictAssignments(assignments, preview.preview_token);
      setMessage(`${result.applied} assignments applied; ${result.unchanged} unchanged.`);
      setPreview(null);
      setSelected(new Set());
      setConfirmation("");
      setCsvFile(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assignment failed");
    }
  }

  async function downloadTemplate() {
    try {
      const blob = await downloadDistrictTemplate();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "dushanbe-district-assignment.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Template download failed");
    }
  }

  return (
    <section className="space-y-4">
      {error && <Notice tone="error">{error}</Notice>}
      {message && <Notice>{message}</Notice>}
      <div className="glass rounded-xl p-4 flex flex-wrap gap-3 items-end">
        <label className="text-xs">
          Assign selected to
          <select
            value={district}
            onChange={(event) => setDistrict(event.target.value)}
            className="block mt-1 h-9 px-3 rounded bg-input border border-border"
          >
            {DISTRICTS.map((item) => (
              <option key={item} value={item}>
                {districtName(item)}
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={previewSelection}
          className="h-9 px-4 rounded border border-primary/40 text-primary"
        >
          Preview selected ({selected.size})
        </button>
        <button
          onClick={downloadTemplate}
          className="h-9 px-3 rounded border border-border inline-flex gap-2 items-center"
        >
          <Download className="size-4" /> CSV template
        </button>
        <label className="h-9 px-3 rounded border border-border inline-flex gap-2 items-center cursor-pointer">
          <Upload className="size-4" /> Preview CSV
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(event) => event.target.files?.[0] && previewCsv(event.target.files[0])}
          />
        </label>
      </div>
      <div className="glass rounded-xl overflow-x-auto max-h-[520px]">
        <table className="w-full min-w-[1100px] text-sm">
          <thead className="sticky top-0 bg-panel text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="p-3">Select</th>
              <th>Station code</th>
              <th>Station name</th>
              <th>Address</th>
              <th>Current district</th>
              <th>VPN IP</th>
              <th>Headscale hostname</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr key={station.id} className="border-t border-border">
                <td className="p-3">
                  <input
                    type="checkbox"
                    checked={selected.has(station.id)}
                    onChange={(event) =>
                      setSelected((current) => {
                        const next = new Set(current);
                        if (event.target.checked) next.add(station.id);
                        else next.delete(station.id);
                        return next;
                      })
                    }
                  />
                </td>
                <td className="font-mono">{station.station_code}</td>
                <td>{station.name}</td>
                <td className="max-w-[260px] truncate" title={station.address}>
                  {station.address || "—"}
                </td>
                <td>{districtName(station.district)}</td>
                <td className="font-mono text-xs">{station.vpn_ip ?? "—"}</td>
                <td>{station.headscale_hostname ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {preview && (
        <PreviewDialog
          preview={preview}
          confirmation={confirmation}
          setConfirmation={setConfirmation}
          apply={apply}
          close={() => {
            setPreview(null);
            setConfirmation("");
          }}
        />
      )}
    </section>
  );
}

function PreviewDialog({
  preview,
  confirmation,
  setConfirmation,
  apply,
  close,
}: {
  preview: DistrictPreview;
  confirmation: string;
  setConfirmation: (value: string) => void;
  apply: () => void;
  close: () => void;
}) {
  const { district: districtName } = useI18n();
  return (
    <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center p-4">
      <div className="glass bg-background rounded-xl p-5 w-full max-w-4xl max-h-[85vh] overflow-y-auto">
        <h2 className="font-semibold">District assignment preview</h2>
        <p className="text-xs text-muted-foreground">No changes have been made.</p>
        {preview.errors.length > 0 && (
          <div className="my-3 text-sm text-destructive">
            {preview.errors.map((item) => (
              <div key={`${item.row}-${item.message}`}>
                Row {item.row}: {item.message}
              </div>
            ))}
          </div>
        )}
        <table className="w-full text-sm my-4">
          <thead className="text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th>Code</th>
              <th>Station</th>
              <th>Current</th>
              <th>Proposed</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row) => (
              <tr key={row.station_id} className="border-t border-border">
                <td className="py-2 font-mono">{row.station_code}</td>
                <td>{row.station_name}</td>
                <td>{districtName(row.current_district)}</td>
                <td>{districtName(row.proposed_district)}</td>
                <td>{row.changed ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {preview.valid && (
          <label className="block text-xs">
            Type <span className="font-mono">ASSIGN DISTRICTS</span> to confirm
            <input
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              className="block mt-1 w-full h-9 px-3 bg-input border border-border rounded"
            />
          </label>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={close} className="h-9 px-4 border border-border rounded">
            Cancel
          </button>
          <button
            disabled={!preview.valid || confirmation !== "ASSIGN DISTRICTS"}
            onClick={apply}
            className="h-9 px-4 border border-primary/40 text-primary rounded disabled:opacity-40"
          >
            Apply assignments
          </button>
        </div>
      </div>
    </div>
  );
}

function DuplicateVpnWorkflow() {
  const [groups, setGroups] = useState<DuplicateVpnGroup[]>([]);
  const [nodes, setNodes] = useState<HeadscaleNode[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ action: VpnAction; preview: ActionPreview } | null>(
    null,
  );
  const [confirmation, setConfirmation] = useState("");
  const [canonical, setCanonical] = useState<Record<number, string>>({});
  const load = useCallback(async () => {
    try {
      const [report, nodeRows] = await Promise.all([
        getDuplicateVpnReport(),
        getHeadscaleNodes({ approval_status: "approved", device_type: "station" }),
      ]);
      setGroups(report);
      setNodes(nodeRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Duplicate VPN report unavailable");
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  async function previewAction(action: VpnAction) {
    try {
      const result = await previewDuplicateVpnAction(action);
      setPending({ action, preview: result });
      setConfirmation("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action preview failed");
    }
  }
  async function applyAction() {
    if (!pending?.preview.preview_token || confirmation !== "APPLY VPN ACTION") return;
    try {
      await applyDuplicateVpnAction(pending.action, pending.preview.preview_token);
      setPending(null);
      setConfirmation("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "VPN action failed");
    }
  }
  return (
    <section className="space-y-4">
      {error && <Notice tone="error">{error}</Notice>}
      {groups.map((group) => (
        <article key={group.vpn_ip} className="glass rounded-xl p-5">
          <div className="flex justify-between">
            <div>
              <h2 className="font-mono font-semibold text-warning">{group.vpn_ip}</h2>
              <p className="text-xs text-muted-foreground">{group.recommended_remediation}</p>
            </div>
            <AlertTriangle className="size-5 text-warning" />
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[850px] text-sm">
              <thead className="text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th>Station</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Last seen</th>
                  <th>Linked node</th>
                  <th className="text-right">Safe actions</th>
                </tr>
              </thead>
              <tbody>
                {group.stations.map((station) => (
                  <tr key={station.station_id} className="border-t border-border">
                    <td className="py-3 font-mono">{station.station_code}</td>
                    <td>{station.station_name}</td>
                    <td>
                      <StatusBadge status={station.status} />
                    </td>
                    <td>
                      {station.last_seen_at ? new Date(station.last_seen_at).toLocaleString() : "—"}
                    </td>
                    <td>
                      {station.linked_node_id ? (
                        <>
                          <div>
                            #{station.linked_node_id} · {station.linked_node_hostname}
                          </div>
                          <div className="text-xs capitalize text-muted-foreground">
                            {station.linked_node_approval_status}
                          </div>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="text-right space-x-2">
                      {station.linked_node_id && (
                        <button
                          onClick={() =>
                            previewAction({
                              action: "unlink_node",
                              vpn_ip: group.vpn_ip,
                              node_id: station.linked_node_id!,
                            })
                          }
                          className="text-xs border border-border rounded px-2 py-1"
                        >
                          Unlink stale node
                        </button>
                      )}
                      <button
                        onClick={() =>
                          previewAction({
                            action: "clear_station_vpn",
                            vpn_ip: group.vpn_ip,
                            station_id: station.station_id,
                          })
                        }
                        className="text-xs border border-border rounded px-2 py-1"
                      >
                        Clear stale station IP
                      </button>
                      {nodes.some((node) => node.vpn_ip === group.vpn_ip) && (
                        <>
                          <select
                            value={canonical[station.station_id] ?? ""}
                            onChange={(event) =>
                              setCanonical((current) => ({
                                ...current,
                                [station.station_id]: event.target.value,
                              }))
                            }
                            className="h-7 bg-input border border-border rounded text-xs"
                          >
                            <option value="">Canonical node…</option>
                            {nodes
                              .filter((node) => node.vpn_ip === group.vpn_ip)
                              .map((node) => (
                                <option key={node.id} value={node.id}>
                                  #{node.id} {node.hostname}
                                </option>
                              ))}
                          </select>
                          <button
                            disabled={!canonical[station.station_id]}
                            onClick={() =>
                              previewAction({
                                action: "select_canonical_node",
                                vpn_ip: group.vpn_ip,
                                station_id: station.station_id,
                                node_id: Number(canonical[station.station_id]),
                              })
                            }
                            className="text-xs border border-border rounded px-2 py-1 disabled:opacity-40"
                          >
                            Select canonical
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => previewAction({ action: "cancel", vpn_ip: group.vpn_ip })}
                        className="text-xs border border-border rounded px-2 py-1"
                      >
                        Cancel / no change
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      ))}
      {groups.length === 0 && (
        <div className="glass rounded-xl py-14 text-center text-muted-foreground">
          No duplicated station VPN addresses.
        </div>
      )}
      {pending && (
        <ConfirmActionDialog
          title="VPN action preview"
          preview={pending.preview}
          phrase="APPLY VPN ACTION"
          confirmation={confirmation}
          setConfirmation={setConfirmation}
          apply={applyAction}
          close={() => setPending(null)}
        />
      )}
    </section>
  );
}

function DuplicateAlertWorkflow() {
  const [groups, setGroups] = useState<DuplicateAlertGroup[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getDuplicateAlertReport()
      .then(setGroups)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Duplicate alert report unavailable"),
      );
  }, []);
  const proposed = useMemo(
    () => groups.reduce((total, group) => total + group.proposed_resolve_alert_ids.length, 0),
    [groups],
  );
  return (
    <section className="space-y-4">
      {error && <Notice tone="error">{error}</Notice>}
      <Notice>
        Dry-run only: {groups.length} duplicate groups; {proposed} alerts proposed for resolution.
        No alerts are deleted.
      </Notice>
      <div className="glass rounded-xl overflow-x-auto">
        <table className="w-full min-w-[1050px] text-sm">
          <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="p-3">Station</th>
              <th>Type</th>
              <th>Open count</th>
              <th>Oldest</th>
              <th>Newest</th>
              <th>Canonical alert</th>
              <th>Proposed resolution</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => (
              <tr
                key={`${group.station_id}-${group.alert_type}`}
                className="border-t border-border"
              >
                <td className="p-3">
                  <div className="font-mono">{group.station_code}</div>
                  <div>{group.station_name}</div>
                </td>
                <td>{group.alert_type.replaceAll("_", " ")}</td>
                <td>{group.open_alert_count}</td>
                <td>{new Date(group.oldest_alert_at).toLocaleString()}</td>
                <td>{new Date(group.newest_alert_at).toLocaleString()}</td>
                <td className="font-mono">#{group.canonical_alert_id}</td>
                <td title={group.proposed_resolve_alert_ids.join(", ")}>
                  {group.proposed_resolve_alert_ids.length} alerts
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        The backend apply endpoint is confirmation-protected for a later administrator-approved
        cleanup phase. This page does not invoke it.
      </p>
    </section>
  );
}

function ConfirmActionDialog({
  title,
  preview,
  phrase,
  confirmation,
  setConfirmation,
  apply,
  close,
}: {
  title: string;
  preview: ActionPreview;
  phrase: string;
  confirmation: string;
  setConfirmation: (value: string) => void;
  apply: () => void;
  close: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center p-4">
      <div className="glass bg-background rounded-xl p-5 w-full max-w-lg">
        <h2 className="font-semibold">{title}</h2>
        <p className="my-3 text-sm">{preview.description}</p>
        {preview.errors.map((error) => (
          <p key={error} className="text-sm text-destructive">
            {error}
          </p>
        ))}
        {preview.valid && (
          <label className="text-xs">
            Type <span className="font-mono">{phrase}</span>
            <input
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              className="block w-full mt-1 h-9 px-3 bg-input border border-border rounded"
            />
          </label>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={close} className="h-9 px-4 border border-border rounded">
            Cancel
          </button>
          <button
            disabled={!preview.valid || confirmation !== phrase}
            onClick={apply}
            className="h-9 px-4 border border-primary/40 text-primary rounded disabled:opacity-40"
          >
            Apply confirmed action
          </button>
        </div>
      </div>
    </div>
  );
}
function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 h-9 rounded text-sm ${active ? "bg-accent text-foreground" : "text-muted-foreground"}`}
    >
      {children}
    </button>
  );
}
function Notice({
  children,
  tone = "normal",
}: {
  children: React.ReactNode;
  tone?: "normal" | "error";
}) {
  return (
    <div
      className={`glass rounded-xl p-4 text-sm ${tone === "error" ? "text-destructive border-destructive/30" : "text-foreground"}`}
    >
      {children}
    </div>
  );
}
