import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { activateAccount } from "@/lib/api";

export const Route = createFileRoute("/activate")({ component: ActivatePage });
function ActivatePage() {
  const navigate = useNavigate();
  const initialCode =
    typeof window !== "undefined"
      ? (new URLSearchParams(window.location.search).get("code") ?? "")
      : "";
  const [code, setCode] = useState(initialCode);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    try {
      await activateAccount(code, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Activation failed");
    }
  }
  return (
    <div className="min-h-screen grid place-items-center p-4">
      <form onSubmit={submit} className="glass rounded-xl p-7 w-full max-w-md space-y-4">
        <ShieldCheck className="size-8 text-primary" />
        <h1 className="text-xl font-semibold">Activate City Parking account</h1>
        {done ? (
          <>
            <p className="text-sm text-success">Account activated. You can now sign in.</p>
            <button
              type="button"
              onClick={() => navigate({ to: "/login" })}
              className="h-10 px-4 bg-primary text-primary-foreground rounded"
            >
              Go to sign in
            </button>
          </>
        ) : (
          <>
            <label className="block text-xs">
              Activation code
              <input
                required
                value={code}
                onChange={(event) => setCode(event.target.value)}
                className="mt-1 w-full h-10 px-3 bg-input border border-border rounded"
              />
            </label>
            <label className="block text-xs">
              New password
              <input
                required
                minLength={12}
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-1 w-full h-10 px-3 bg-input border border-border rounded"
              />
            </label>
            <label className="block text-xs">
              Confirm password
              <input
                required
                minLength={12}
                type="password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                className="mt-1 w-full h-10 px-3 bg-input border border-border rounded"
              />
            </label>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <button className="w-full h-10 bg-primary text-primary-foreground rounded">
              Activate account
            </button>
          </>
        )}
      </form>
    </div>
  );
}
