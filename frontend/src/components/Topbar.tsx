import { Bell, Search, UserCircle2, LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { clearAuth } from "@/lib/auth";

export function Topbar({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  const [now, setNow] = useState(() => new Date());

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
        <h1 className="text-base font-semibold text-foreground truncate">
          {title}
        </h1>

        {subtitle && (
          <p className="text-xs text-muted-foreground truncate">
            {subtitle}
          </p>
        )}
      </div>

      <div className="hidden lg:flex relative ml-4 flex-1 max-w-md">
        <Search className="size-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />

        <input
          placeholder="Search stations, cameras, alerts..."
          className="w-full h-9 pl-9 pr-3 rounded-md bg-input/60 border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50"
        />
      </div>

      <div className="ml-auto flex items-center gap-4">
        <div className="hidden md:flex flex-col items-end leading-tight font-mono">
          <span className="text-xs text-muted-foreground">
            UTC+5 · Dushanbe
          </span>

          <span className="text-sm text-foreground tabular-nums">
            {now.toLocaleString("en-GB", {
              timeZone: "Asia/Dushanbe",
              hour12: false,
            })}
          </span>
        </div>

        <button className="relative size-9 grid place-items-center rounded-md border border-border bg-accent/40 hover:bg-accent text-muted-foreground hover:text-foreground transition-colors">
          <Bell className="size-4" />

          <span className="absolute -top-1 -right-1 size-4 grid place-items-center rounded-full bg-destructive text-[10px] font-semibold text-destructive-foreground">
            3
          </span>
        </button>

        <div className="flex items-center gap-2 pl-3 border-l border-border">
          <UserCircle2 className="size-7 text-muted-foreground" />

          <div className="hidden sm:block leading-tight">
            <div className="text-sm text-foreground">
              admin
            </div>

            <div className="text-[11px] text-muted-foreground">
              Administrator
            </div>
          </div>

          <button
            onClick={logout}
            className="ml-2 p-2 rounded-md hover:bg-accent"
            title="Logout"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </header>
  );
}