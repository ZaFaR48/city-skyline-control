import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Server,
  Video,
  Map as MapIcon,
  BellRing,
  BarChart3,
  Monitor,
  Network,
  Send,
  Workflow,
  Settings as SettingsIcon,
  ShieldCheck,
  ClipboardCheck,
} from "lucide-react";
import { getStoredUser } from "@/lib/auth";
import type { User } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

type NavItem = { to: string; key: string; icon: typeof LayoutDashboard; exact?: boolean };
const NAV: NavItem[] = [
  { to: "/", key: "nav.dashboard", icon: LayoutDashboard, exact: true },
  { to: "/stations", key: "nav.stations", icon: Server },
  { to: "/cameras", key: "nav.cameras", icon: Video },
  { to: "/map", key: "nav.map", icon: MapIcon },
  { to: "/alerts", key: "nav.alerts", icon: BellRing },
  { to: "/analytics", key: "nav.reports", icon: BarChart3 },
  { to: "/rustdesk", key: "nav.rustdesk", icon: Monitor },
  { to: "/headscale", key: "nav.headscale", icon: Network },
  { to: "/onboarding", key: "nav.onboarding", icon: ClipboardCheck },
  { to: "/telegram", key: "nav.telegram", icon: Send },
  { to: "/n8n", key: "nav.n8n", icon: Workflow },
  { to: "/settings", key: "nav.settings", icon: SettingsIcon },
];

export function Sidebar() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const user = getStoredUser<User>();
  const { t } = useI18n();
  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-panel/60 backdrop-blur-xl">
      <div className="h-16 flex items-center gap-2 px-5 border-b border-border">
        <div className="size-9 rounded-md grid place-items-center bg-gradient-to-br from-info to-primary shadow-lg shadow-primary/30">
          <ShieldCheck className="size-5 text-primary-foreground" />
        </div>
        <div className="leading-tight">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            City Parking
          </div>
          <div className="text-sm font-semibold text-gradient">Control Center</div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {NAV.filter((item) => item.to !== "/onboarding" || user?.role === "admin").map((item) => {
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
              <span>{t(item.key)}</span>
              {active && <span className="ml-auto size-1.5 rounded-full bg-primary" />}
            </Link>
          );
        })}
      </nav>
      <div className="p-3 border-t border-border text-[11px] text-muted-foreground">
        <div className="flex items-center justify-between">
          <span>v1.0.0 · TJ-NOC</span>
          <span className="flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-success" /> healthy
          </span>
        </div>
      </div>
    </aside>
  );
}
