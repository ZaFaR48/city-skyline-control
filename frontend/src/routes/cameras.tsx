import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Camera as CameraIcon, Search } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { StatusBadge } from "@/components/StatusBadge";
import { getCameras } from "@/lib/api";
import type { Camera, StationStatus } from "@/lib/types";

export const Route = createFileRoute("/cameras")({ component: CamerasPage });
function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<StationStatus | "">("");
  useEffect(() => {
    getCameras()
      .then(setCameras)
      .catch((err) => setError(err instanceof Error ? err.message : "Cameras could not be loaded"));
  }, []);
  const filtered = useMemo(
    () =>
      cameras.filter(
        (camera) =>
          (!status || camera.status === status) &&
          (!q || camera.name.toLowerCase().includes(q.toLowerCase()) || camera.ip.includes(q)),
      ),
    [cameras, q, status],
  );
  return (
    <>
      <Topbar
        title="Cameras"
        subtitle={cameras.length ? `${cameras.length} configured cameras` : "Not configured"}
      />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {error && <div className="glass p-4 text-destructive">{error}</div>}
        <div className="glass rounded-xl p-4 flex gap-3">
          <div className="relative flex-1">
            <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Search cameras…"
              className="w-full h-9 pl-9 rounded-md bg-input/60 border border-border"
            />
          </div>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as StationStatus | "")}
            className="h-9 px-3 rounded-md bg-input border border-border"
          >
            <option value="">All statuses</option>
            <option value="online">Online</option>
            <option value="degraded">Degraded</option>
            <option value="offline">Offline</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((camera) => (
            <article key={camera.id} className="glass rounded-xl p-4">
              <div className="aspect-video rounded-lg bg-panel grid place-items-center mb-3">
                <CameraIcon className="size-10 text-muted-foreground" />
              </div>
              <div className="flex justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-medium truncate">{camera.name}</div>
                  <div className="font-mono text-xs text-muted-foreground">{camera.ip}</div>
                </div>
                <StatusBadge status={camera.status} />
              </div>
              <div className="mt-3 text-xs text-muted-foreground">
                Last seen:{" "}
                {camera.last_seen_at ? new Date(camera.last_seen_at).toLocaleString() : "—"}
              </div>
            </article>
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full glass rounded-xl py-16 text-center text-muted-foreground">
              {cameras.length ? "No cameras match." : "Camera monitoring is not configured."}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
