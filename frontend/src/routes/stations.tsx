import { createFileRoute } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ArrowUpDown, ChevronLeft, ChevronRight, Eye, RefreshCw, Search, X } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { StatusBadge, pingTone } from "@/components/StatusBadge";
import { getRegions, getStation, getStations } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Station, StationDetail, StationStatus } from "@/lib/types";

export const Route = createFileRoute("/stations")({
  head: () => ({ meta: [{ title: "Stations · City Parking Control Center" }] }),
  component: StationsPage,
});

const PAGE_SIZE = 25;
type SortKey =
  | "station_code"
  | "name"
  | "district"
  | "status"
  | "ping"
  | "offline_duration"
  | "last_seen";

function useDebounced(value: string, delay = 350) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function StationsPage() {
  const { t } = useI18n();
  const [queryText, setQueryText] = useState("");
  const query = useDebounced(queryText);
  const [district, setDistrict] = useState("");
  const [status, setStatus] = useState("");
  const [monitoring, setMonitoring] = useState("");
  const [linked, setLinked] = useState("");
  const [recordState, setRecordState] = useState("active");
  const [sort, setSort] = useState<SortKey>("station_code");
  const [direction, setDirection] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);

  const regionsQuery = useQuery({
    queryKey: ["regions", "active"],
    queryFn: ({ signal }) => getRegions(true, signal),
    staleTime: 60_000,
  });
  useEffect(() => {
    setPage(1);
  }, [query, district, status, monitoring, linked, recordState, sort, direction]);
  const stationParams = useMemo(
    () => ({
      q: query,
      district_id: district || undefined,
      status: status || undefined,
      monitoring_configured:
        monitoring === "configured" ? true : monitoring === "unconfigured" ? false : undefined,
      headscale_linked: linked === "linked" ? true : linked === "unlinked" ? false : undefined,
      active: recordState === "active" ? true : recordState === "inactive" ? false : undefined,
      archived: recordState === "archived" ? true : recordState === "active" ? false : undefined,
      sort,
      direction,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [query, district, status, monitoring, linked, recordState, sort, direction, page],
  );
  const stationsQuery = useQuery({
    queryKey: ["stations", stationParams],
    queryFn: ({ signal }) => getStations(stationParams, signal),
    placeholderData: keepPreviousData,
  });
  const items = stationsQuery.data?.items ?? [];
  const total = stationsQuery.data?.total ?? 0;
  const loading = stationsQuery.isPending;

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const districts = useMemo(
    () => (regionsQuery.data ?? []).filter((region) => region.region_type === "district"),
    [regionsQuery.data],
  );
  function toggleSort(key: SortKey) {
    if (sort === key) setDirection((value) => (value === "asc" ? "desc" : "asc"));
    else {
      setSort(key);
      setDirection("asc");
    }
  }

  return (
    <>
      <Topbar
        title="Stations"
        subtitle={
          stationsQuery.data
            ? `${total} Dushanbe stations match current filters`
            : t("loading.stations")
        }
      />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="glass rounded-xl p-4 flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[260px]">
            <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={queryText}
              onChange={(event) => setQueryText(event.target.value)}
              placeholder="Search code, name, district, address, IP, hostname…"
              className="w-full h-9 pl-9 pr-3 rounded-md bg-input/60 border border-border text-sm"
            />
          </div>
          <Select
            value={district}
            setValue={setDistrict}
            options={[
              ["", "All districts"],
              ...districts.map((item) => [String(item.id), item.name] as [string, string]),
            ]}
          />
          <Select
            value={status}
            setValue={setStatus}
            options={[
              ["", "All statuses"],
              ["online", "Online"],
              ["degraded", "Degraded"],
              ["offline", "Offline"],
              ["unknown", "Unknown"],
            ]}
          />
          <Select
            value={monitoring}
            setValue={setMonitoring}
            options={[
              ["", "All monitoring"],
              ["configured", "Monitoring configured"],
              ["unconfigured", "Monitoring unconfigured"],
            ]}
          />
          <Select
            value={linked}
            setValue={setLinked}
            options={[
              ["", "All Headscale"],
              ["linked", "Headscale linked"],
              ["unlinked", "Headscale unlinked"],
            ]}
          />
          <Select
            value={recordState}
            setValue={setRecordState}
            options={[
              ["active", "Active stations"],
              ["inactive", "Inactive stations"],
              ["archived", "Archived stations"],
              ["all", "All records"],
            ]}
          />
        </div>
        {stationsQuery.error && (
          <div className="glass rounded-xl p-4 flex justify-between text-sm text-destructive">
            <span>
              {stationsQuery.error instanceof Error
                ? stationsQuery.error.message
                : t("api.unavailable")}
            </span>
            <button
              onClick={() => void stationsQuery.refetch()}
              className="inline-flex gap-2 items-center"
            >
              <RefreshCw className="size-4" /> {t("common.retry")}
            </button>
          </div>
        )}
        <div className="glass rounded-xl overflow-hidden">
          <div className="overflow-x-auto max-h-[calc(100vh-250px)]">
            <table className="w-full min-w-[1450px] table-fixed text-sm">
              <thead className="sticky top-0 z-10 bg-panel text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <Th width="110px" onClick={() => toggleSort("station_code")}>
                    Station Code
                  </Th>
                  <Th width="210px" onClick={() => toggleSort("name")}>
                    Station Name
                  </Th>
                  <Th width="150px" onClick={() => toggleSort("district")}>
                    District
                  </Th>
                  <th className="text-left px-3 py-3 w-[240px]">Address</th>
                  <th className="text-left px-3 py-3 w-[135px]">VPN IP</th>
                  <th className="text-left px-3 py-3 w-[135px]">Local IP</th>
                  <Th width="125px" onClick={() => toggleSort("status")}>
                    Status
                  </Th>
                  <Th width="90px" onClick={() => toggleSort("ping")}>
                    Ping
                  </Th>
                  <Th width="180px" onClick={() => toggleSort("last_seen")}>
                    Last Seen / Offline
                  </Th>
                  <th className="text-left px-3 py-3 w-[100px]">Cameras</th>
                  <th className="text-right px-3 py-3 w-[80px]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((station) => (
                  <StationRow
                    key={station.id}
                    station={station}
                    view={() => setSelected(station.id)}
                  />
                ))}
                {stationsQuery.isSuccess &&
                  !stationsQuery.isPlaceholderData &&
                  items.length === 0 && (
                    <tr>
                      <td colSpan={11} className="py-14 text-center text-muted-foreground">
                        No stations match these filters.
                      </td>
                    </tr>
                  )}
                {loading &&
                  items.length === 0 &&
                  Array.from({ length: 8 }).map((_, index) => (
                    <tr key={index} className="border-t border-border">
                      <td colSpan={11} className="h-12 animate-pulse bg-accent/10" />
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-3 border-t border-border flex justify-between text-xs text-muted-foreground">
            <span>
              {loading
                ? t("loading.stations")
                : total
                  ? `Showing ${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} of ${total}`
                  : "No records"}
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage((value) => value - 1)}
                className="p-1 border border-border rounded disabled:opacity-40"
              >
                <ChevronLeft className="size-4" />
              </button>
              <span>
                Page {page} / {pages}
              </span>
              <button
                disabled={page >= pages}
                onClick={() => setPage((value) => value + 1)}
                className="p-1 border border-border rounded disabled:opacity-40"
              >
                <ChevronRight className="size-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
      {selected !== null && <StationDrawer stationId={selected} close={() => setSelected(null)} />}
    </>
  );
}

function StationRow({ station, view }: { station: Station; view: () => void }) {
  const last =
    station.status === "offline"
      ? `Offline for ${elapsed(station.offline_since)}`
      : station.last_seen_at
        ? `Last seen ${elapsed(station.last_seen_at)} ago`
        : "—";
  return (
    <tr className="border-t border-border hover:bg-accent/20 h-14">
      <td className="px-3 font-mono font-semibold whitespace-nowrap">{station.station_code}</td>
      <td className="px-3 font-medium truncate" title={station.name}>
        {station.name}
      </td>
      <td className="px-3 truncate" title={station.district ?? undefined}>
        {station.district ?? "—"}
      </td>
      <td className="px-3 text-muted-foreground truncate" title={station.address || undefined}>
        {station.address || "—"}
      </td>
      <td className="px-3 font-mono text-xs">{station.vpn_ip ?? "—"}</td>
      <td className="px-3 font-mono text-xs text-muted-foreground">{station.local_ip ?? "—"}</td>
      <td className="px-3">
        <StatusBadge status={station.status} />
      </td>
      <td className={`px-3 text-right font-mono ${pingTone(station.last_ping_ms, station.status)}`}>
        {station.last_ping_ms === null ? "—" : `${station.last_ping_ms} ms`}
      </td>
      <td className="px-3 text-xs text-muted-foreground truncate" title={last}>
        {last}
      </td>
      <td className="px-3">
        {station.cameras_total ? `${station.cameras_online}/${station.cameras_total}` : "—"}
      </td>
      <td className="px-3 text-right">
        <button
          onClick={view}
          title="View station details"
          className="size-8 inline-grid place-items-center rounded border border-border hover:bg-accent"
        >
          <Eye className="size-4" />
        </button>
      </td>
    </tr>
  );
}

function StationDrawer({ stationId, close }: { stationId: number; close: () => void }) {
  const detailQuery = useQuery({
    queryKey: ["station", stationId],
    queryFn: ({ signal }) => getStation(stationId, signal),
  });
  const detail: StationDetail | undefined = detailQuery.data;
  const error = detailQuery.error instanceof Error ? detailQuery.error.message : null;
  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex justify-end"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) close();
      }}
    >
      <aside className="h-full w-full max-w-2xl bg-background border-l border-border overflow-y-auto p-6 space-y-5">
        <div className="flex justify-between">
          <div>
            <h2 className="font-semibold">
              {detail ? `${detail.station_code} · ${detail.name}` : "Station details"}
            </h2>
            <p className="text-xs text-muted-foreground">
              Identity, monitoring, alerts, and history
            </p>
          </div>
          <button onClick={close}>
            <X className="size-5" />
          </button>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!detail && !error && <div className="h-48 animate-pulse glass rounded-xl" />}
        {detail && (
          <>
            <DetailSection title="Identity">
              <Grid
                values={[
                  ["Status", detail.status],
                  ["District", detail.district ?? "—"],
                  ["Address", detail.address || "—"],
                  ["VPN IP", detail.vpn_ip ?? "—"],
                  ["Local IP", detail.local_ip ?? "—"],
                  ["Headscale", detail.headscale_node?.hostname ?? "Not configured"],
                ]}
              />
            </DetailSection>
            <DetailSection title="Current monitoring">
              <Grid
                values={[
                  [
                    "Last seen",
                    detail.last_seen_at ? new Date(detail.last_seen_at).toLocaleString() : "—",
                  ],
                  ["Last ping", detail.last_ping_ms === null ? "—" : `${detail.last_ping_ms} ms`],
                  ["CPU", detail.cpu === null ? "—" : `${detail.cpu}%`],
                  ["RAM", detail.ram === null ? "—" : `${detail.ram}%`],
                  ["Disk", detail.disk === null ? "—" : `${detail.disk}%`],
                  [
                    "Offline duration",
                    detail.status === "offline" ? elapsed(detail.offline_since) : "—",
                  ],
                ]}
              />
            </DetailSection>
            <DetailSection title={`Cameras (${detail.cameras.length})`}>
              {detail.cameras.length ? (
                detail.cameras.map((camera) => (
                  <div
                    key={camera.id}
                    className="text-sm py-2 border-b border-border flex justify-between"
                  >
                    <span>{camera.name}</span>
                    <StatusBadge status={camera.status} />
                  </div>
                ))
              ) : (
                <Empty />
              )}
            </DetailSection>
            <DetailSection title={`Open alerts (${detail.open_alerts.length})`}>
              {detail.open_alerts.length ? (
                detail.open_alerts.map((alert) => (
                  <div key={alert.id} className="text-sm py-2 border-b border-border">
                    <div>{alert.message}</div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(alert.created_at).toLocaleString()}
                    </div>
                  </div>
                ))
              ) : (
                <Empty />
              )}
            </DetailSection>
            <DetailSection title="Status timeline">
              {detail.status_timeline.length ? (
                detail.status_timeline.slice(0, 20).map((event) => (
                  <div
                    key={event.id}
                    className="py-2 border-b border-border flex justify-between gap-3 text-sm"
                  >
                    <span>
                      <StatusBadge status={event.new_status} />
                    </span>
                    <span className="flex-1 text-muted-foreground truncate">
                      {event.reason ?? event.source}
                    </span>
                    <span className="text-xs">{new Date(event.started_at).toLocaleString()}</span>
                  </div>
                ))
              ) : (
                <Empty />
              )}
            </DetailSection>
            <DetailSection title="Ping history">
              {detail.ping_history.length ? (
                detail.ping_history.slice(0, 20).map((ping, index) => (
                  <div
                    key={`${ping.checked_at}-${index}`}
                    className="py-1.5 text-xs flex justify-between border-b border-border"
                  >
                    <span>{new Date(ping.checked_at).toLocaleString()}</span>
                    <span>
                      {ping.success && ping.latency_ms !== null
                        ? `${Math.round(ping.latency_ms)} ms`
                        : (ping.error_type ?? "Failed")}
                    </span>
                  </div>
                ))
              ) : (
                <Empty />
              )}
            </DetailSection>
            <DetailSection title="Audit history">
              {detail.audit_history.length ? (
                detail.audit_history.map((audit) => (
                  <div key={audit.id} className="py-1.5 text-xs flex justify-between">
                    <span>{audit.action}</span>
                    <span>{new Date(audit.timestamp).toLocaleString()}</span>
                  </div>
                ))
              ) : (
                <Empty />
              )}
            </DetailSection>
          </>
        )}
      </aside>
    </div>
  );
}

function elapsed(value: string | null) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}
function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="glass rounded-xl p-4">
      <h3 className="text-sm font-semibold mb-3">{title}</h3>
      {children}
    </section>
  );
}
function Grid({ values }: { values: [string, string][] }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {values.map(([label, value]) => (
        <div key={label}>
          <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
          <div className="text-sm break-words">{value}</div>
        </div>
      ))}
    </div>
  );
}
function Empty() {
  return <p className="text-sm text-muted-foreground py-3">No data</p>;
}
function Select({
  value,
  setValue,
  options,
}: {
  value: string;
  setValue: (value: string) => void;
  options: [string, string][];
}) {
  return (
    <select
      value={value}
      onChange={(event) => setValue(event.target.value)}
      className="h-9 px-3 rounded-md bg-input/60 border border-border text-sm"
    >
      {options.map(([key, label]) => (
        <option key={key} value={key}>
          {label}
        </option>
      ))}
    </select>
  );
}
function Th({
  children,
  width,
  onClick,
}: {
  children: React.ReactNode;
  width: string;
  onClick: () => void;
}) {
  return (
    <th className="text-left px-3 py-3" style={{ width }}>
      <button onClick={onClick} className="inline-flex items-center gap-1 whitespace-nowrap">
        {children}
        <ArrowUpDown className="size-3" />
      </button>
    </th>
  );
}
