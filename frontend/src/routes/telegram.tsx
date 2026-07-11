import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, KeyRound, Link2, X } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import {
  getRegistrations,
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
