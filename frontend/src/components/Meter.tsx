import { meterColor } from "./StatusBadge";

export function Meter({ value, label }: { value: number; label?: string }) {
  return (
    <div className="min-w-[64px]">
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        {label && <span>{label}</span>}
        <span className="tabular-nums text-foreground">{value}%</span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-accent/70 overflow-hidden">
        <div
          className={`h-full ${meterColor(value)} transition-all`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}
