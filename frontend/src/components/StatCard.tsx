import type { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: string | number;
  delta?: string;
  tone?: "default" | "success" | "warning" | "danger" | "info";
  icon: LucideIcon;
  hint?: string;
}

const TONE: Record<NonNullable<Props["tone"]>, string> = {
  default: "from-primary/20 to-primary/0 text-primary",
  success: "from-success/25 to-success/0 text-success",
  warning: "from-warning/25 to-warning/0 text-warning",
  danger: "from-destructive/25 to-destructive/0 text-destructive",
  info: "from-info/25 to-info/0 text-info",
};

export function StatCard({ label, value, delta, tone = "default", icon: Icon, hint }: Props) {
  return (
    <div className="glass rounded-xl p-5 relative overflow-hidden">
      <div
        className={`absolute -top-12 -right-12 size-40 rounded-full bg-gradient-to-br ${TONE[tone]} blur-2xl opacity-60 pointer-events-none`}
      />
      <div className="flex items-start justify-between relative">
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            {label}
          </div>
          <div className="mt-2 text-3xl font-semibold tabular-nums text-foreground">{value}</div>
          {delta && <div className="mt-1 text-xs text-muted-foreground">{delta}</div>}
        </div>
        <div
          className={`size-10 rounded-lg grid place-items-center bg-accent/60 border border-border ${TONE[tone].split(" ").pop()}`}
        >
          <Icon className="size-5" />
        </div>
      </div>
      {hint && <div className="mt-4 text-[11px] text-muted-foreground relative">{hint}</div>}
    </div>
  );
}
