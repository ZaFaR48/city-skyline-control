import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, KeyRound, Link2, X } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import {
  getRegistrations,
  getOperatorActivity,
  getOperatorPresence,
  getUsers,
  initiateTelegramPasswordReset,
  linkRegistrationToExistingUser,
  previewExistingUserLink,
  previewTelegramPasswordReset,
  reviewRegistration,
} from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import type {
  PasswordResetPreview,
  OperatorActivity,
  OperatorPresence,
  RegistrationRequest,
  Role,
  TelegramLinkPreview,
  User,
} from "@/lib/types";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/telegram")({ component: TelegramPage });
function TelegramPage() {
  const { role: roleLabel } = useI18n();
  const user = getStoredUser<User>();
  const [rows, setRows] = useState<RegistrationRequest[]>([]);
  const [systemUsers, setSystemUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [roles, setRoles] = useState<Record<number, Role>>({});
  const [selectedUsers, setSelectedUsers] = useState<Record<number, string>>({});
  const [linkPreview, setLinkPreview] = useState<TelegramLinkPreview | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [resetPreview, setResetPreview] = useState<PasswordResetPreview | null>(null);
  const [resetConfirmation, setResetConfirmation] = useState("");
  const [tab, setTab] = useState<"registrations" | "activity">("registrations");
  const load = useCallback(() => {
    if (user?.role !== "admin") return;
    Promise.all([getRegistrations(), getUsers()])
      .then(([registrations, users]) => {
        setRows(registrations);
        setSystemUsers(users);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Registration requests unavailable"),
      );
  }, [user?.role]);
  useEffect(() => {
    load();
  }, [load]);
  async function review(id: number, action: "approve" | "reject") {
    try {
      await reviewRegistration(
        id,
        action,
        action === "approve" ? (roles[id] ?? "viewer") : undefined,
      );
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    }
  }
  async function previewLink(registrationId: number) {
    const userId = Number(selectedUsers[registrationId]);
    if (!userId) {
      setError("Select an existing system user first");
      return;
    }
    try {
      setLinkPreview(await previewExistingUserLink(registrationId, userId));
      setConfirmation("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Existing-user link preview failed");
    }
  }
  async function applyLink() {
    if (!linkPreview?.preview_token || confirmation !== linkPreview.confirmation_phrase) return;
    try {
      await linkRegistrationToExistingUser(
        linkPreview.registration_id,
        linkPreview.user_id,
        linkPreview.preview_token,
        confirmation,
      );
      setLinkPreview(null);
      setConfirmation("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Existing-user link failed");
    }
  }
  async function previewReset(registrationId: number) {
    try {
      setResetPreview(await previewTelegramPasswordReset(registrationId));
      setResetConfirmation("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password reset preview failed");
    }
  }
  async function applyReset() {
    if (!resetPreview?.preview_token || resetConfirmation !== resetPreview.confirmation_phrase)
      return;
    try {
      await initiateTelegramPasswordReset(
        resetPreview.registration_id,
        resetPreview.preview_token,
        resetConfirmation,
      );
      setResetPreview(null);
      setResetConfirmation("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password reset initiation failed");
    }
  }
  return (
    <>
      <Topbar title="Telegram Access" subtitle="Registration review and role assignment" />
      <div className="flex-1 overflow-y-auto p-6">
        {user?.role !== "admin" ? (
          <div className="glass rounded-xl py-16 text-center text-muted-foreground">
            Administrator access is required to review registrations.
          </div>
        ) : (
          <>
            {error && <div className="glass p-4 mb-4 text-destructive">{error}</div>}
            <div className="mb-4 inline-flex gap-1 rounded-xl glass p-2">
              <button
                onClick={() => setTab("registrations")}
                className={`rounded px-3 py-1 text-sm ${tab === "registrations" ? "bg-primary text-primary-foreground" : ""}`}
              >
                Registration review
              </button>
              <button
                onClick={() => setTab("activity")}
                className={`rounded px-3 py-1 text-sm ${tab === "activity" ? "bg-primary text-primary-foreground" : ""}`}
              >
                Operator Activity
              </button>
            </div>
            {tab === "activity" ? (
              <OperatorActivityPanel roleLabel={roleLabel} />
            ) : (
              <div className="glass rounded-xl overflow-x-auto">
                <table className="w-full min-w-[1200px] text-sm">
                  <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="p-3">Telegram ID</th>
                      <th>User</th>
                      <th>Existing user link</th>
                      <th>Requested</th>
                      <th>Status</th>
                      <th>Role</th>
                      <th className="text-right p-3">Review</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id} className="border-t border-border">
                        <td className="p-3 font-mono">{row.telegram_user_id}</td>
                        <td>
                          <div>
                            {[row.first_name, row.last_name].filter(Boolean).join(" ") ||
                              row.display_name ||
                              "—"}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {row.telegram_username ? `@${row.telegram_username}` : "—"}
                          </div>
                        </td>
                        <td>
                          {row.status === "pending" ? (
                            <div className="flex items-center gap-2 py-2">
                              <select
                                value={selectedUsers[row.id] ?? ""}
                                onChange={(event) =>
                                  setSelectedUsers((current) => ({
                                    ...current,
                                    [row.id]: event.target.value,
                                  }))
                                }
                                className="h-8 max-w-[220px] bg-input border border-border rounded"
                              >
                                <option value="">Select existing user…</option>
                                {systemUsers.map((systemUser) => (
                                  <option key={systemUser.id} value={systemUser.id}>
                                    {systemUser.username} · {roleLabel(systemUser.role)} ·{" "}
                                    {systemUser.is_active ? "active" : "inactive"}
                                  </option>
                                ))}
                              </select>
                              <button
                                onClick={() => previewLink(row.id)}
                                className="h-8 px-2 inline-flex items-center gap-1 border border-primary/40 text-primary rounded"
                              >
                                <Link2 className="size-3" /> Link to existing user
                              </button>
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>{new Date(row.requested_at).toLocaleString()}</td>
                        <td className="capitalize">{row.status.replaceAll("_", " ")}</td>
                        <td>
                          {row.status === "pending" ? (
                            <>
                              <select
                                value={roles[row.id] ?? "viewer"}
                                onChange={(event) =>
                                  setRoles((current) => ({
                                    ...current,
                                    [row.id]: event.target.value as Role,
                                  }))
                                }
                                className="h-8 bg-input border border-border rounded"
                              >
                                <option value="admin">ADMIN</option>
                                <option value="operator">OPERATOR</option>
                                <option value="viewer">VIEWER</option>
                              </select>
                              <div className="mt-1 max-w-56 text-xs text-muted-foreground">
                                {(roles[row.id] ?? "viewer") === "admin"
                                  ? "Full administration, approvals, access and security operations."
                                  : (roles[row.id] ?? "viewer") === "operator"
                                    ? "Register/update station data and use monitoring; no approvals, links, archives, roles or resets."
                                    : "Read-only dashboards, searches, summaries and reports."}
                              </div>
                            </>
                          ) : row.assigned_role ? (
                            roleLabel(row.assigned_role)
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="p-3 text-right">
                          {row.status === "pending" && (
                            <div className="inline-flex gap-2">
                              <button
                                onClick={() => review(row.id, "approve")}
                                className="size-8 grid place-items-center border border-success/40 text-success rounded"
                              >
                                <Check className="size-4" />
                              </button>
                              <button
                                onClick={() => review(row.id, "reject")}
                                className="size-8 grid place-items-center border border-destructive/40 text-destructive rounded"
                              >
                                <X className="size-4" />
                              </button>
                            </div>
                          )}
                          {row.status === "activated" && (
                            <button
                              onClick={() => previewReset(row.id)}
                              className="h-8 px-2 inline-flex items-center gap-1 border border-warning/40 text-warning rounded"
                            >
                              <KeyRound className="size-3" /> Send password reset
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                    {rows.length === 0 && (
                      <tr>
                        <td colSpan={7} className="py-14 text-center text-muted-foreground">
                          No registration requests.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
            {linkPreview && (
              <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center p-4">
                <div className="glass bg-background rounded-xl p-5 w-full max-w-xl">
                  <h2 className="font-semibold">Link Telegram to existing user</h2>
                  <p className="text-xs text-muted-foreground">
                    This does not create a user, change a password, or change a role.
                  </p>
                  <dl className="grid grid-cols-2 gap-3 text-sm my-5">
                    <PreviewValue
                      label="Telegram ID"
                      value={String(linkPreview.telegram_user_id)}
                    />
                    <PreviewValue
                      label="Telegram username"
                      value={
                        linkPreview.telegram_username ? `@${linkPreview.telegram_username}` : "—"
                      }
                    />
                    <PreviewValue label="System username" value={linkPreview.username} />
                    <PreviewValue label="Current role" value={roleLabel(linkPreview.role)} />
                    <PreviewValue
                      label="Active status"
                      value={linkPreview.is_active ? "Active" : "Inactive"}
                    />
                  </dl>
                  {linkPreview.warning && (
                    <div className="mb-4 p-3 border border-warning/40 text-warning rounded text-sm flex gap-2">
                      <AlertTriangle className="size-4 shrink-0" /> {linkPreview.warning}
                    </div>
                  )}
                  {linkPreview.errors.map((item) => (
                    <p key={item} className="text-sm text-destructive">
                      {item}
                    </p>
                  ))}
                  {linkPreview.valid && (
                    <label className="block text-xs">
                      Type <span className="font-mono">{linkPreview.confirmation_phrase}</span> to
                      confirm
                      <input
                        value={confirmation}
                        onChange={(event) => setConfirmation(event.target.value)}
                        className="block mt-1 w-full h-9 px-3 bg-input border border-border rounded"
                      />
                    </label>
                  )}
                  <div className="mt-4 flex justify-end gap-2">
                    <button
                      onClick={() => setLinkPreview(null)}
                      className="h-9 px-4 border border-border rounded"
                    >
                      Cancel
                    </button>
                    <button
                      disabled={
                        !linkPreview.valid || confirmation !== linkPreview.confirmation_phrase
                      }
                      onClick={applyLink}
                      className="h-9 px-4 border border-primary/40 text-primary rounded disabled:opacity-40"
                    >
                      Link to existing user
                    </button>
                  </div>
                </div>
              </div>
            )}
            {resetPreview && (
              <div className="fixed inset-0 z-50 bg-black/60 grid place-items-center p-4">
                <div className="glass bg-background rounded-xl p-5 w-full max-w-lg">
                  <h2 className="font-semibold">Password reset preview</h2>
                  <p className="text-xs text-muted-foreground">
                    A single-use reset link will be sent. No permanent password is sent.
                  </p>
                  <dl className="grid grid-cols-2 gap-3 text-sm my-5">
                    <PreviewValue label="System username" value={resetPreview.username} />
                    <PreviewValue label="Current role" value={roleLabel(resetPreview.role)} />
                    <PreviewValue
                      label="Active status"
                      value={resetPreview.is_active ? "Active" : "Inactive"}
                    />
                    <PreviewValue
                      label="Telegram ID"
                      value={String(resetPreview.telegram_user_id)}
                    />
                  </dl>
                  {resetPreview.errors.map((item) => (
                    <p key={item} className="text-sm text-destructive">
                      {item}
                    </p>
                  ))}
                  {resetPreview.valid && (
                    <label className="block text-xs">
                      Type <span className="font-mono">{resetPreview.confirmation_phrase}</span>
                      <input
                        value={resetConfirmation}
                        onChange={(event) => setResetConfirmation(event.target.value)}
                        className="block mt-1 w-full h-9 px-3 bg-input border border-border rounded"
                      />
                    </label>
                  )}
                  <div className="mt-4 flex justify-end gap-2">
                    <button
                      onClick={() => setResetPreview(null)}
                      className="h-9 px-4 border border-border rounded"
                    >
                      Cancel
                    </button>
                    <button
                      disabled={
                        !resetPreview.valid ||
                        resetConfirmation !== resetPreview.confirmation_phrase
                      }
                      onClick={applyReset}
                      className="h-9 px-4 border border-warning/40 text-warning rounded disabled:opacity-40"
                    >
                      Send single-use reset link
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}

function PreviewValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function OperatorActivityPanel({ roleLabel }: { roleLabel: (role: Role) => string }) {
  const [presence, setPresence] = useState<OperatorPresence[]>([]);
  const [events, setEvents] = useState<OperatorActivity[]>([]);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");
  const [presenceFilter, setPresenceFilter] = useState("");
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const [presenceRows, activityRows] = await Promise.all([
        getOperatorPresence({
          q: query || undefined,
          role: role || undefined,
          presence: presenceFilter || undefined,
        }),
        getOperatorActivity({
          q: query || undefined,
          role: role || undefined,
          status: status || undefined,
          source: source || undefined,
          start: startDate ? `${startDate}T00:00:00+05:00` : undefined,
          end: endDate ? `${endDate}T23:59:59.999+05:00` : undefined,
        }),
      ]);
      setPresence(presenceRows);
      setEvents(activityRows);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operator activity unavailable");
    }
  }, [endDate, presenceFilter, query, role, source, startDate, status]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 300);
    return () => window.clearTimeout(timer);
  }, [load]);
  return (
    <div className="space-y-4">
      {error && <div className="glass rounded p-3 text-destructive">{error}</div>}
      <div className="glass grid gap-3 rounded-xl p-4 md:grid-cols-6">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search operator, Telegram ID, station or action"
          className="h-9 rounded border border-border bg-input px-3 text-sm md:col-span-2"
        />
        <select
          value={role}
          onChange={(event) => setRole(event.target.value)}
          className="h-9 rounded border border-border bg-input px-2"
        >
          <option value="">All roles</option>
          <option value="admin">ADMIN</option>
          <option value="operator">OPERATOR</option>
          <option value="viewer">VIEWER</option>
        </select>
        <select
          value={presenceFilter}
          onChange={(event) => setPresenceFilter(event.target.value)}
          className="h-9 rounded border border-border bg-input px-2"
        >
          <option value="">All presence</option>
          <option value="online">Online</option>
          <option value="recently_active">Recently active</option>
          <option value="offline">Offline</option>
        </select>
        <select
          value={source}
          onChange={(event) => setSource(event.target.value)}
          className="h-9 rounded border border-border bg-input px-2"
        >
          <option value="">All sources</option>
          <option value="web">Web</option>
          <option value="telegram">Telegram</option>
          <option value="api">API</option>
        </select>
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className="h-9 rounded border border-border bg-input px-2"
        >
          <option value="">All workflow states</option>
          {["in_progress", "completed", "cancelled", "failed", "abandoned"].map((item) => (
            <option key={item} value={item}>
              {item.replaceAll("_", " ")}
            </option>
          ))}
        </select>
        <label className="text-xs text-muted-foreground">
          From (Dushanbe)
          <input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            className="mt-1 h-9 w-full rounded border border-border bg-input px-2 text-foreground"
          />
        </label>
        <label className="text-xs text-muted-foreground">
          To (Dushanbe)
          <input
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            className="mt-1 h-9 w-full rounded border border-border bg-input px-2 text-foreground"
          />
        </label>
      </div>
      <div className="glass overflow-x-auto rounded-xl">
        <table className="w-full min-w-[1100px] text-sm">
          <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="p-3">User</th>
              <th>Role</th>
              <th>Application presence</th>
              <th>Last activity</th>
              <th>Source</th>
              <th>Current workflow</th>
            </tr>
          </thead>
          <tbody>
            {presence.map((row) => (
              <tr key={row.user_id} className="border-t border-border">
                <td className="p-3">
                  <div>{row.display_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {row.username} · {row.telegram_username ? `@${row.telegram_username}` : "—"} ·{" "}
                    {row.telegram_user_id ?? "—"}
                  </div>
                </td>
                <td>{roleLabel(row.role)}</td>
                <td>
                  <span
                    className={`inline-flex items-center gap-2 ${row.presence === "online" ? "text-success" : row.presence === "recently_active" ? "text-warning" : "text-muted-foreground"}`}
                  >
                    <span className="size-2 rounded-full bg-current" />
                    {row.presence.replaceAll("_", " ")}
                  </span>
                  <div className="text-[10px] text-muted-foreground">
                    City Skyline activity, not Telegram presence
                  </div>
                </td>
                <td>{dushanbeTime(row.last_activity_at)}</td>
                <td>{row.last_activity_source ?? "—"}</td>
                <td>{row.current_workflow_state ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="space-y-2">
        {events.map((event) => (
          <div key={event.id} className="glass rounded-xl p-4 text-sm">
            <div className="flex flex-wrap justify-between gap-2">
              <div className="font-medium">
                {event.actor_username} · {event.action}
                {event.station_code && (
                  <a
                    href={`/stations?q=${encodeURIComponent(event.station_code)}`}
                    className="ml-1 text-primary hover:underline"
                  >
                    · Station {event.station_code}
                  </a>
                )}
              </div>
              <div>{dushanbeTime(event.timestamp)}</div>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>{roleLabel(event.actor_role)}</span>
              <span>{event.source}</span>
              <span
                className={`rounded-full border px-2 py-0.5 ${event.workflow_status === "completed" ? "border-success/40 text-success" : event.workflow_status === "failed" || event.workflow_status === "abandoned" ? "border-destructive/40 text-destructive" : event.workflow_status === "cancelled" ? "border-warning/40 text-warning" : "border-border"}`}
              >
                {event.workflow_status?.replaceAll("_", " ") ?? "—"}
              </span>
              <span>Step: {event.current_step ?? "—"}</span>
              {event.duration_seconds !== null && <span>{event.duration_seconds}s</span>}
            </div>
            {event.changed_fields.length > 0 && (
              <div className="mt-2 text-xs">Fields: {event.changed_fields.join(", ")}</div>
            )}
            {(event.before_data || event.after_data) && (
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <SafeDiff title="OLD" values={event.before_data} />
                <SafeDiff title="NEW" values={event.after_data} />
              </div>
            )}
            {event.failure_reason && (
              <div className="mt-2 text-xs text-destructive">{event.failure_reason}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function SafeDiff({ title, values }: { title: string; values: Record<string, unknown> | null }) {
  return (
    <div className="rounded border border-border p-2 text-xs">
      <div className="font-semibold">{title}</div>
      {values
        ? Object.entries(values).map(([key, value]) => (
            <div key={key}>
              <span className="text-muted-foreground">{key}:</span> {String(value ?? "—")}
            </div>
          ))
        : "—"}
    </div>
  );
}

function dushanbeTime(value: string | null): string {
  return value
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "medium",
        timeZone: "Asia/Dushanbe",
      }).format(new Date(value))
    : "—";
}
