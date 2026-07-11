import { UserCircle2, LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { clearAuth, getStoredUser } from "@/lib/auth";
import type { User } from "@/lib/types";

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  const [now, setNow] = useState(() => new Date());
  const user = getStoredUser<User>();

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  function logout() {
    clearAuth();
    window.location.href = "/login";
  }

  return (
    <header className="h-16 shrink-0 border-b border-border bg-panel/40 backdrop-blur-xl flex items-center px-6 gap-6">
      <div className="min-w-0">
        <h1 className="text-base font-semibold text-foreground truncate">{title}</h1>

        {subtitle && <p className="text-xs text-muted-foreground truncate">{subtitle}</p>}
      </div>

      <div className="ml-auto flex items-center gap-4">
        <div className="hidden md:flex flex-col items-end leading-tight font-mono">
          <span className="text-xs text-muted-foreground">UTC+5 · Dushanbe</span>

          <span className="text-sm text-foreground tabular-nums">
            {now.toLocaleString("en-GB", {
              timeZone: "Asia/Dushanbe",
              hour12: false,
            })}
          </span>
        </div>

        <div className="flex items-center gap-2 pl-3 border-l border-border">
          <UserCircle2 className="size-7 text-muted-foreground" />

          <div className="hidden sm:block leading-tight">
            <div className="text-sm text-foreground">{user?.username ?? "—"}</div>

            <div className="text-[11px] text-muted-foreground">
              {user?.role?.toUpperCase() ?? "—"}
            </div>
          </div>

          <button onClick={logout} className="ml-2 p-2 rounded-md hover:bg-accent" title="Logout">
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
