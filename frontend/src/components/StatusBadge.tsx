import type { StationStatus } from "@/lib/types";

const MAP: Record<StationStatus, { label: string; cls: string; dot: string }> = {
  online: {
    label: "Online",
    cls: "text-success border-success/30 bg-success/10",
    dot: "bg-success",
  },
  degraded: {
    label: "Degraded",
    cls: "text-warning border-warning/30 bg-warning/10",
    dot: "bg-warning",
  },
  offline: {
    label: "Offline",
    cls: "text-destructive border-destructive/30 bg-destructive/10",
    dot: "bg-destructive",
  },
  unknown: {
    label: "Unknown",
    cls: "text-muted-foreground border-border bg-accent/30",
    dot: "bg-muted-foreground",
  },
};

export function StatusBadge({ status, pulse = false }: { status: StationStatus; pulse?: boolean }) {
  const m = MAP[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider ${m.cls}`}
    >
      <span
        className={`size-1.5 rounded-full ${m.dot} ${pulse && status !== "offline" ? "pulse-dot" : ""}`}
        style={{ color: "currentColor" }}
      />
      {m.label}
    </span>
  );
}

export function pingTone(ms: number | null, status: StationStatus) {
  if (status === "offline") return "text-destructive";
  if (ms === null || ms === 0) return "text-muted-foreground";
  if (ms < 50) return "text-success";
  if (ms <= 150) return "text-warning";
  return "text-destructive";
}

export function meterColor(v: number) {
  if (v >= 85) return "bg-destructive";
  if (v >= 70) return "bg-warning";
  return "bg-success";
}
