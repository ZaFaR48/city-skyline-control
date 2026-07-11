import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Copy, Monitor } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { getRustdeskDevices } from "@/lib/api";

export const Route = createFileRoute("/rustdesk")({ component: RustDeskPage });
type Device = Awaited<ReturnType<typeof getRustdeskDevices>>[number];
function RustDeskPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getRustdeskDevices()
      .then(setDevices)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "RustDesk inventory unavailable"),
      );
  }, []);
  return (
    <>
      <Topbar title="RustDesk" subtitle={`${devices.length} linked devices`} />
      <div className="flex-1 overflow-y-auto p-6">
        {error && <div className="glass p-4 mb-4 text-destructive">{error}</div>}
        <div className="glass rounded-xl overflow-x-auto">
          <table className="w-full min-w-[700px] text-sm">
            <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Station code</th>
                <th>Station</th>
                <th>RustDesk ID</th>
                <th>VPN IP</th>
                <th className="text-right p-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => (
                <tr
                  key={`${device.station_code}-${device.rustdesk_id}`}
                  className="border-t border-border"
                >
                  <td className="p-3 font-mono">{device.station_code}</td>
                  <td>{device.station}</td>
                  <td className="font-mono">{device.rustdesk_id}</td>
                  <td className="font-mono text-xs">{device.vpn_ip ?? "—"}</td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => navigator.clipboard.writeText(device.rustdesk_id)}
                      className="inline-flex items-center gap-2 border border-border rounded px-2 py-1"
                    >
                      <Copy className="size-3.5" /> Copy
                    </button>
                  </td>
                </tr>
              ))}
              {devices.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-14 text-center text-muted-foreground">
                    <Monitor className="size-6 mx-auto mb-2" />
                    No linked RustDesk devices.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
