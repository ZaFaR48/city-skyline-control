import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Topbar } from "@/components/Topbar";
import { Endpoints } from "@/lib/api";
import { Monitor, Copy, Loader2 } from "lucide-react";

export const Route = createFileRoute("/rustdesk")({
  head: () => ({ meta: [{ title: "RustDesk · City Parking Control Center" }, { name: "description", content: "Remote desktop IDs for every station with one-click RustDesk connect." }] }),
  component: RustDeskPage,
});

const REFETCH_MS = 30_000;

function fmtId(id: string | null) {
  if (!id) return "—";
  return id.replace(/(\d{3})(\d{3})(\d+)/, "$1 $2 $3");
}

function RustDeskPage() {
  const q = useQuery({ queryKey: ["stations"], queryFn: Endpoints.stations, refetchInterval: REFETCH_MS });
  const stations = q.data ?? [];
  return (
    <>
      <Topbar title="RustDesk" subtitle={`${stations.length} registered devices`} />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="glass rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-panel/60 text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="text-left font-medium px-4 py-3">Station</th>
                <th className="text-left font-medium px-4 py-3">Region</th>
                <th className="text-left font-medium px-4 py-3">RustDesk ID</th>
                <th className="text-left font-medium px-4 py-3">VPN IP</th>
                <th className="text-right font-medium px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {q.isLoading && (
                <tr><td colSpan={5} className="px-4 py-10 text-center text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin inline-block mr-2" /> Loading…</td></tr>
              )}
              {stations.map((s) => (
                <tr key={s.id} className="border-t border-border">
                  <td className="px-4 py-3 font-medium">{s.name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{s.region}</td>
                  <td className="px-4 py-3 font-mono">{fmtId(s.rustdesk_id)}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{s.vpn_ip}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button
                        title="Copy ID"
                        onClick={() => s.rustdesk_id && navigator.clipboard?.writeText(s.rustdesk_id)}
                        className="size-7 grid place-items-center rounded-md border border-border bg-accent/40 hover:bg-accent text-muted-foreground hover:text-foreground"
                      ><Copy className="size-3.5" /></button>
                      <button className="inline-flex items-center gap-1.5 h-7 px-3 text-xs rounded-md bg-primary/20 border border-primary/40 text-primary hover:bg-primary/30">
                        <Monitor className="size-3.5" /> Connect
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!q.isLoading && stations.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-10 text-center text-sm text-muted-foreground">No stations registered.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
