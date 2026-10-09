import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Camera,
  ChevronRight,
  CircleDot,
  HardDrive,
  Image as ImageIcon,
  Info,
  Monitor,
  Move,
  Network,
  RotateCcw,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Video,
  X,
  Zap,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { StatusBadge } from "@/components/StatusBadge";
import { getDataset, type Camera as CameraItem, type StationStatus } from "@/lib/mock-data";

export const Route = createFileRoute("/cameras")({
  head: () => ({
    meta: [
      { title: "Cameras · City Parking Control Center" },
      { name: "description", content: "Grid view of all RTSP cameras across parking stations with PTZ controls and live snapshots." },
    ],
  }),
  component: CamerasPage,
});

const cameraMenu = [
  { id: "live", label: "Live View", icon: Monitor },
  { id: "stream", label: "Stream", icon: Video },
  { id: "camera", label: "Camera", icon: Camera },
  { id: "network", label: "Network", icon: Network },
  { id: "event", label: "Event", icon: Zap },
  { id: "storage", label: "Storage", icon: HardDrive },
  { id: "system", label: "System", icon: Settings2 },
  { id: "information", label: "Information", icon: Info },
] as const;

type CameraMenuId = (typeof cameraMenu)[number]["id"];

function CamerasPage() {
  const { cameras } = getDataset();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | StationStatus>("all");
  const [activeCamera, setActiveCamera] = useState<CameraItem | null>(null);
  const [activeMenu, setActiveMenu] = useState<CameraMenuId>("live");

  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return cameras.filter((c) =>
      (status === "all" || c.status === status) &&
      (ql === "" || c.name.toLowerCase().includes(ql) || c.stationName.toLowerCase().includes(ql) || c.ip.includes(ql))
    );
  }, [cameras, q, status]);

  const openCamera = (cam: CameraItem, menu: CameraMenuId = "live") => {
    setActiveCamera(cam);
    setActiveMenu(menu);
  };

  return (
    <>
      <Topbar title="Cameras" subtitle={`${cameras.length} streams · ${filtered.length} shown`} />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="glass rounded-xl p-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="size-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search cameras…"
              className="w-full h-9 pl-9 pr-3 rounded-md bg-input/60 border border-border text-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
            />
          </div>
          <div className="flex gap-1 p-1 rounded-md bg-input/40 border border-border">
            {(["all", "online", "warning", "offline"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`px-3 h-7 text-xs rounded capitalize ${status === s ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground"}`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4">
          {filtered.map((cam) => (
            <div key={cam.id} className="glass rounded-xl overflow-hidden group">
              <button
                type="button"
                onClick={() => openCamera(cam)}
                className="aspect-video relative bg-gradient-to-br from-slate-900 to-slate-800 overflow-hidden w-full text-left"
              >
                <div
                  className="absolute inset-0 opacity-30"
                  style={{
                    backgroundImage:
                      "repeating-linear-gradient(0deg, rgba(255,255,255,0.05) 0 1px, transparent 1px 3px), repeating-linear-gradient(90deg, rgba(255,255,255,0.05) 0 1px, transparent 1px 3px)",
                  }}
                />
                <div className="absolute inset-0 grid place-items-center text-muted-foreground">
                  {cam.status === "offline" ? (
                    <div className="text-center">
                      <Video className="size-8 mx-auto opacity-50" />
                      <div className="mt-2 text-xs uppercase tracking-wider text-destructive">Stream lost</div>
                    </div>
                  ) : (
                    <Camera className="size-10 opacity-30" />
                  )}
                </div>
                <div className="absolute top-2 left-2 flex items-center gap-2">
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/60 text-foreground border border-border">
                    {cam.resolution} · {cam.fps}fps
                  </span>
                </div>
                <div className="absolute top-2 right-2"><StatusBadge status={cam.status} pulse /></div>
                {cam.status !== "offline" && (
                  <div className="absolute bottom-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded bg-destructive/90 text-destructive-foreground text-[10px] font-semibold">
                    <span className="size-1.5 rounded-full bg-white animate-pulse" /> LIVE
                  </div>
                )}
                {cam.ptz && <span className="absolute bottom-2 right-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-info/80 text-primary-foreground">PTZ</span>}
              </button>

              <div className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium truncate">{cam.name}</div>
                    <div className="text-xs text-muted-foreground truncate">{cam.stationName} · {cam.ip}</div>
                  </div>
                </div>
                <div className="mt-2 font-mono text-[11px] text-muted-foreground truncate" title={cam.rtsp}>{cam.rtsp}</div>
                <div className="mt-3 grid grid-cols-4 gap-1.5">
                  <CamBtn icon={Video} label="Live" primary onClick={() => openCamera(cam, "live")} />
                  <CamBtn icon={Move} label="PTZ" disabled={!cam.ptz} onClick={() => openCamera(cam, "live")} />
                  <CamBtn icon={ImageIcon} label="Snap" onClick={() => openCamera(cam, "live")} />
                  <CamBtn icon={Settings2} label="Cfg" onClick={() => openCamera(cam, "camera")} />
                </div>
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full text-center text-sm text-muted-foreground py-10">No cameras match.</div>
          )}
        </div>
      </div>

      {activeCamera && (
        <CameraControlPanel
          camera={activeCamera}
          activeMenu={activeMenu}
          onMenu={setActiveMenu}
          onClose={() => setActiveCamera(null)}
        />
      )}
    </>
  );
}

function CameraControlPanel({
  camera,
  activeMenu,
  onMenu,
  onClose,
}: {
  camera: CameraItem;
  activeMenu: CameraMenuId;
  onMenu: (menu: CameraMenuId) => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/75 backdrop-blur-sm p-3 md:p-6">
      <div className="mx-auto h-full max-w-[1500px] overflow-hidden rounded-2xl border border-border bg-background shadow-2xl flex flex-col">
        <div className="h-16 border-b border-border px-4 md:px-6 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Camera className="size-5 text-primary" />
              <h2 className="font-semibold truncate">{camera.stationName}</h2>
              <StatusBadge status={camera.status} pulse />
            </div>
            <div className="text-xs text-muted-foreground mt-1 truncate">{camera.name} · {camera.ip}</div>
          </div>
          <button onClick={onClose} className="size-9 rounded-lg border border-border grid place-items-center hover:bg-accent" aria-label="Close camera panel">
            <X className="size-4" />
          </button>
        </div>

        <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)_320px]">
          <aside className="border-r border-border bg-card/40 p-3 overflow-y-auto hidden lg:block">
            <div className="text-xs uppercase tracking-wider text-muted-foreground px-3 py-2">Camera menu</div>
            <div className="space-y-1">
              {cameraMenu.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => onMenu(id)}
                  className={`w-full h-10 rounded-lg px-3 flex items-center gap-2 text-sm transition-colors ${activeMenu === id ? "bg-primary text-primary-foreground" : "hover:bg-accent text-muted-foreground hover:text-foreground"}`}
                >
                  <Icon className="size-4" />
                  <span>{label}</span>
                  <ChevronRight className="size-3.5 ml-auto opacity-60" />
                </button>
              ))}
            </div>
          </aside>

          <main className="min-w-0 overflow-y-auto p-4 md:p-5">
            <div className="lg:hidden mb-4 flex gap-2 overflow-x-auto pb-2">
              {cameraMenu.map(({ id, label }) => (
                <button
                  key={id}
                  onClick={() => onMenu(id)}
                  className={`shrink-0 h-8 rounded-md px-3 text-xs border ${activeMenu === id ? "bg-primary text-primary-foreground border-primary" : "border-border bg-card"}`}
                >
                  {label}
                </button>
              ))}
            </div>

            {activeMenu === "live" ? <LiveCameraView camera={camera} /> : <CameraSettingsView camera={camera} section={activeMenu} />}
          </main>

          <aside className="border-l border-border p-4 overflow-y-auto bg-card/30 hidden xl:block">
            <CameraFacts camera={camera} />
          </aside>
        </div>
      </div>
    </div>
  );
}

function LiveCameraView({ camera }: { camera: CameraItem }) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border overflow-hidden bg-slate-950">
        <div className="aspect-video relative grid place-items-center">
          <div className="absolute inset-0 opacity-30" style={{ backgroundImage: "linear-gradient(120deg,#0f172a,#1e293b,#0f172a)" }} />
          {camera.status === "offline" ? (
            <div className="relative z-10 text-center text-destructive">
              <Video className="size-10 mx-auto mb-2" />
              <div className="font-semibold">Camera stream is unavailable</div>
            </div>
          ) : (
            <div className="relative z-10 text-center text-slate-300">
              <Camera className="size-16 mx-auto opacity-25" />
              <div className="mt-3 text-xs font-mono">{camera.rtsp}</div>
            </div>
          )}
          <div className="absolute top-3 left-3 text-[11px] font-mono px-2 py-1 rounded bg-black/65 text-white">
            {camera.resolution} · {camera.fps} fps
          </div>
          {camera.status !== "offline" && (
            <div className="absolute top-3 right-3 text-[11px] px-2 py-1 rounded bg-destructive text-destructive-foreground flex items-center gap-1">
              <CircleDot className="size-3" /> LIVE
            </div>
          )}
        </div>
      </div>

      {camera.ptz && (
        <div className="glass rounded-xl p-4">
          <div className="flex items-center gap-2 font-medium mb-4"><Move className="size-4" /> PTZ control</div>
          <div className="grid md:grid-cols-[200px_1fr] gap-5 items-center">
            <div className="grid grid-cols-3 gap-2 w-36 mx-auto">
              <span />
              <PtzBtn icon={ArrowUp} label="Up" />
              <span />
              <PtzBtn icon={ArrowLeft} label="Left" />
              <PtzBtn icon={RotateCcw} label="Center" />
              <PtzBtn icon={ArrowRight} label="Right" />
              <span />
              <PtzBtn icon={ArrowDown} label="Down" />
              <span />
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              <PtzWide icon={ZoomIn} label="Zoom in" />
              <PtzWide icon={ZoomOut} label="Zoom out" />
            </div>
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <InfoCard title="Video parameters">
          <Fact label="Stream" value="Main Stream" />
          <Fact label="Resolution" value={camera.resolution} />
          <Fact label="Frame rate" value={`${camera.fps} fps`} />
          <Fact label="Codec" value="H.265" />
          <Fact label="Bitrate" value="4096 kbps" />
        </InfoCard>
        <InfoCard title="Connection">
          <Fact label="Status" value={camera.status} />
          <Fact label="IP" value={camera.ip} />
          <Fact label="Transport" value="RTSP / ONVIF" />
          <Fact label="Access" value="Headscale VPN" />
          <Fact label="PTZ" value={camera.ptz ? "Available" : "Not available"} />
        </InfoCard>
      </div>
    </div>
  );
}

function CameraSettingsView({ camera, section }: { camera: CameraItem; section: Exclude<CameraMenuId, "live"> }) {
  const content: Record<Exclude<CameraMenuId, "live">, { title: string; rows: [string, string][] }> = {
    stream: {
      title: "Stream configuration",
      rows: [["Main stream", camera.resolution], ["Frame rate", `${camera.fps} fps`], ["Codec", "H.265"], ["Bitrate", "4096 kbps"], ["RTSP", camera.rtsp]],
    },
    camera: {
      title: "Camera image settings",
      rows: [["Profile", "Day / Night automatic"], ["Exposure", "Automatic"], ["White balance", "Automatic"], ["WDR", "Enabled"], ["PTZ", camera.ptz ? "Supported" : "Not supported"]],
    },
    network: {
      title: "Network settings",
      rows: [["IPv4", camera.ip], ["HTTP", `http://${camera.ip}`], ["RTSP", "554/tcp"], ["ONVIF", `http://${camera.ip}/onvif/device_service`], ["Route", "Station LAN → Headscale VPN"]],
    },
    event: {
      title: "Events",
      rows: [["Motion detection", "Monitoring only"], ["Video loss", "Enabled"], ["Tamper", "Enabled"], ["Offline alert", "Enabled"], ["Event delivery", "Control Center"]],
    },
    storage: {
      title: "Storage",
      rows: [["Recording", "Station policy"], ["Snapshot", "Available"], ["Archive", "Managed by Control Center"], ["Retention", "Defined by station policy"], ["Disk health", "Read-only monitoring"]],
    },
    system: {
      title: "System",
      rows: [["Time sync", "NTP"], ["Timezone", "Asia/Dushanbe"], ["Maintenance", "Administrator only"], ["Reboot", "Protected action"], ["Configuration changes", "Audited"]],
    },
    information: {
      title: "Device information",
      rows: [["Name", camera.name], ["Station", camera.stationName], ["IP", camera.ip], ["Status", camera.status], ["Resolution", camera.resolution], ["PTZ", camera.ptz ? "Yes" : "No"]],
    },
  };

  const current = content[section];
  return (
    <div className="space-y-4">
      <div className="glass rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <SlidersHorizontal className="size-4 text-primary" />
          <h3 className="font-semibold">{current.title}</h3>
        </div>
        <div className="divide-y divide-border">
          {current.rows.map(([label, value]) => (
            <div key={label} className="py-3 grid sm:grid-cols-[180px_1fr] gap-2 text-sm">
              <span className="text-muted-foreground">{label}</span>
              <span className="font-mono break-all">{value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-muted-foreground">
        Configuration is read-only in this phase. Changes will be enabled only through audited administrator actions.
      </div>
    </div>
  );
}

function CameraFacts({ camera }: { camera: CameraItem }) {
  return (
    <div className="space-y-4">
      <InfoCard title="Camera information">
        <Fact label="Station" value={camera.stationName} />
        <Fact label="Camera" value={camera.name} />
        <Fact label="IP" value={camera.ip} />
        <Fact label="Resolution" value={camera.resolution} />
        <Fact label="FPS" value={String(camera.fps)} />
        <Fact label="PTZ" value={camera.ptz ? "Yes" : "No"} />
      </InfoCard>
      <div className="rounded-xl border border-success/30 bg-success/5 p-4">
        <div className="flex items-center gap-2 font-medium text-success">
          <ShieldCheck className="size-4" /> Protected access
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Camera actions are intended to pass through the Control Center and Headscale path, not direct public exposure.
        </p>
      </div>
    </div>
  );
}

function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="font-medium mb-3">{title}</div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 text-xs border-b border-border/60 pb-2 last:border-0 last:pb-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono text-right break-all">{value}</span>
    </div>
  );
}

function PtzBtn({ icon: Icon, label }: { icon: typeof ArrowUp; label: string }) {
  return (
    <button title={label} className="size-10 rounded-lg border border-border bg-accent/40 grid place-items-center hover:bg-accent">
      <Icon className="size-4" />
    </button>
  );
}

function PtzWide({ icon: Icon, label }: { icon: typeof ZoomIn; label: string }) {
  return (
    <button className="h-10 rounded-lg border border-border bg-accent/40 flex items-center justify-center gap-2 text-sm hover:bg-accent">
      <Icon className="size-4" /> {label}
    </button>
  );
}

function CamBtn({
  icon: Icon,
  label,
  primary,
  disabled,
  onClick,
}: {
  icon: typeof Camera;
  label: string;
  primary?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
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
