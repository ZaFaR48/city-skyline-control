import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ShieldCheck, Loader2, AlertOctagon } from "lucide-react";
import { login } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in · City Parking Control Center" },
      { name: "description", content: "Operator sign-in for the City Parking NOC." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated()) navigate({ to: "/" });
  }, [navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username.trim(), password);
      navigate({ to: "/" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen w-full grid place-items-center bg-background px-4">
      <div className="absolute inset-0 -z-10 opacity-40 pointer-events-none"
        style={{ backgroundImage:
          "radial-gradient(circle at 20% 20%, rgba(59,130,246,0.25), transparent 40%)," +
          "radial-gradient(circle at 80% 60%, rgba(168,85,247,0.18), transparent 45%)" }} />
      <form onSubmit={onSubmit} className="glass w-full max-w-sm rounded-2xl p-8 space-y-6">
        <div className="flex items-center gap-3">
          <div className="size-11 rounded-md grid place-items-center bg-gradient-to-br from-info to-primary shadow-lg shadow-primary/30">
            <ShieldCheck className="size-6 text-primary-foreground" />
          </div>
          <div className="leading-tight">
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">City Parking</div>
            <div className="text-base font-semibold text-gradient">Control Center</div>
          </div>
        </div>

        <div className="space-y-1">
          <h1 className="text-xl font-semibold">Sign in</h1>
          <p className="text-xs text-muted-foreground">Operator access to the NOC dashboard.</p>
        </div>

        <div className="space-y-3">
          <label className="block">
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground">Username</span>
            <input
              type="text" autoComplete="username" required autoFocus
              value={username} onChange={(e) => setUsername(e.target.value)}
              className="mt-1 w-full h-10 px-3 rounded-md bg-input/60 border border-border text-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
            />
          </label>
          <label className="block">
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground">Password</span>
            <input
              type="password" autoComplete="current-password" required
              value={password} onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full h-10 px-3 rounded-md bg-input/60 border border-border text-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
            />
          </label>
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            <AlertOctagon className="size-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <button type="submit" disabled={loading}
          className="w-full h-10 inline-flex items-center justify-center gap-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-60">
          {loading && <Loader2 className="size-4 animate-spin" />}
          {loading ? "Signing in…" : "Sign in"}
        </button>

        <p className="text-[11px] text-muted-foreground text-center">
          Secured with JWT · session stored locally
        </p>
      </form>
    </div>
  );
}
