import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard, Server, Video, Map as MapIcon, BellRing,
  BarChart3, Monitor, Network, Send, Workflow, Settings as SettingsIcon, ShieldCheck, LogOut,
} from "lucide-react";
import { clearAuth } from "@/lib/auth";

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard; exact?: boolean };
const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/stations", label: "Stations", icon: Server },
  { to: "/cameras", label: "Cameras", icon: Video },
  { to: "/map", label: "Map", icon: MapIcon },
  { to: "/alerts", label: "Alerts", icon: BellRing },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/rustdesk", label: "RustDesk", icon: Monitor },
  { to: "/headscale", label: "Headscale", icon: Network },
  { to: "/telegram", label: "Telegram", icon: Send },
  { to: "/n8n", label: "n8n", icon: Workflow },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export function Sidebar() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  function handleLogout() {
    clearAuth();
    navigate({ to: "/login", replace: true });
  }
  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-panel/60 backdrop-blur-xl">
      <div className="h-16 flex items-center gap-2 px-5 border-b border-border">
        <div className="size-9 rounded-md grid place-items-center bg-gradient-to-br from-info to-primary shadow-lg shadow-primary/30">
          <ShieldCheck className="size-5 text-primary-foreground" />
        </div>
        <div className="leading-tight">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">City Parking</div>
          <div className="text-sm font-semibold text-gradient">Control Center</div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {NAV.map((item) => {
          const active = item.exact ? path === item.to : path.startsWith(item.to);
          const Icon = item.icon;
          return (
            <Link
              key={item.to}
              to={item.to as never}
              className={`group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-accent text-foreground border border-border shadow-inner"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
              }`}
            >
              <Icon className={`size-4 ${active ? "text-primary" : ""}`} />
              <span>{item.label}</span>
              {active && <span className="ml-auto size-1.5 rounded-full bg-primary" />}
            </Link>
          );
        })}
      </nav>
      <div className="p-3 border-t border-border space-y-2">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
        >
          <LogOut className="size-4" />
          <span>Sign out</span>
        </button>
        <div className="flex items-center justify-between text-[11px] text-muted-foreground px-1">
          <span>v1.0.0 · TJ-NOC</span>
          <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-success" /> healthy</span>
        </div>
      </div>
    </aside>
  );
}
