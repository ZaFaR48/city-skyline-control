import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { getRegistrations, reviewRegistration } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import type { RegistrationRequest, Role, User } from "@/lib/types";

export const Route = createFileRoute("/telegram")({ component: TelegramPage });
function TelegramPage() {
  const user = getStoredUser<User>();
  const [rows, setRows] = useState<RegistrationRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [roles, setRoles] = useState<Record<number, Role>>({});
  const load = useCallback(() => {
    if (user?.role !== "admin") return;
    getRegistrations()
      .then(setRows)
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
              <table className="w-full min-w-[900px] text-sm">
                <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="p-3">Telegram ID</th>
                    <th>User</th>
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
                        ) : (
                          (row.assigned_role?.toUpperCase() ?? "—")
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
                      </td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-14 text-center text-muted-foreground">
                        No registration requests.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  );
}
