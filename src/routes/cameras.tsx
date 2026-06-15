import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Camera, Image as ImageIcon, Move, Settings2, Video, Search } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { StatusBadge } from "@/components/StatusBadge";
import { getDataset, type StationStatus } from "@/lib/mock-data";

export const Route = createFileRoute("/cameras")({
  head: () => ({
    meta: [
      { title: "Cameras · City Parking Control Center" },
      { name: "description", content: "Grid view of all RTSP cameras across parking stations with PTZ controls and live snapshots." },
    ],
  }),
  component: CamerasPage,
});

function CamerasPage() {
  const { cameras } = getDataset();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | StationStatus>("all");

  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return cameras.filter((c) =>
      (status === "all" || c.status === status) &&
      (ql === "" || c.name.toLowerCase().includes(ql) || c.stationName.toLowerCase().includes(ql) || c.ip.includes(ql))
    );
  }, [cameras, q, status]);

  return (
    <>
      <Topbar title="Cameras" subtitle={`${cameras.length} streams · ${filtered.length} shown`} />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="glass rounded-xl p-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="size-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search cameras…"
              className="w-full h-9 pl-9 pr-3 rounded-md bg-input/60 border border-border text-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
            />
          </div>
          <div className="flex gap-1 p-1 rounded-md bg-input/40 border border-border">
            {(["all", "online", "warning", "offline"] as const).map((s) => (
              <button key={s} onClick={() => setStatus(s)}
                className={`px-3 h-7 text-xs rounded capitalize ${status === s ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4">
          {filtered.map((cam) => (
            <div key={cam.id} className="glass rounded-xl overflow-hidden group">
              <div className="aspect-video relative bg-gradient-to-br from-slate-900 to-slate-800 overflow-hidden">
                <div className="absolute inset-0 opacity-30" style={{
                  backgroundImage:
                    "repeating-linear-gradient(0deg, rgba(255,255,255,0.05) 0 1px, transparent 1px 3px), repeating-linear-gradient(90deg, rgba(255,255,255,0.05) 0 1px, transparent 1px 3px)",
                }} />
                <div className="absolute inset-0 grid place-items-center text-muted-foreground">
                  {cam.status === "offline" ? (
                    <div className="text-center"><Video className="size-8 mx-auto opacity-50" /><div className="mt-2 text-xs uppercase tracking-wider text-destructive">Stream lost</div></div>
                  ) : (
                    <Camera className="size-10 opacity-30" />
                  )}
                </div>
                <div className="absolute top-2 left-2 flex items-center gap-2">
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/60 text-foreground border border-border">{cam.resolution} · {cam.fps}fps</span>
                </div>
                <div className="absolute top-2 right-2"><StatusBadge status={cam.status} pulse /></div>
                {cam.status !== "offline" && (
                  <div className="absolute bottom-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded bg-destructive/90 text-destructive-foreground text-[10px] font-semibold">
                    <span className="size-1.5 rounded-full bg-white animate-pulse" /> LIVE
                  </div>
                )}
                {cam.ptz && <span className="absolute bottom-2 right-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-info/80 text-primary-foreground">PTZ</span>}
              </div>
              <div className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium truncate">{cam.name}</div>
                    <div className="text-xs text-muted-foreground truncate">{cam.stationName} · {cam.ip}</div>
                  </div>
                </div>
                <div className="mt-2 font-mono text-[11px] text-muted-foreground truncate" title={cam.rtsp}>{cam.rtsp}</div>
                <div className="mt-3 grid grid-cols-4 gap-1.5">
                  <CamBtn icon={Video} label="Live" primary />
                  <CamBtn icon={Move} label="PTZ" disabled={!cam.ptz} />
                  <CamBtn icon={ImageIcon} label="Snap" />
                  <CamBtn icon={Settings2} label="Cfg" />
                </div>
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full text-center text-sm text-muted-foreground py-10">No cameras match.</div>
          )}
        </div>
      </div>
    </>
  );
}

function CamBtn({ icon: Icon, label, primary, disabled }: { icon: typeof Camera; label: string; primary?: boolean; disabled?: boolean }) {
  return (
    <button
      disabled={disabled}
      className={`h-8 inline-flex items-center justify-center gap-1 rounded-md text-xs border transition-colors ${
        primary
          ? "bg-primary/20 border-primary/40 text-primary hover:bg-primary/30"
          : "bg-accent/40 border-border text-muted-foreground hover:text-foreground hover:bg-accent"
      } disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      <Icon className="size-3.5" /> {label}
    </button>
  );
}
