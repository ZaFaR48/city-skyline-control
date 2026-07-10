import { createFileRoute } from "@tanstack/react-router";
import { Topbar } from "@/components/Topbar";
import { getDataset } from "@/lib/mock-data";
import { Monitor, Copy } from "lucide-react";

export const Route = createFileRoute("/rustdesk")({
  head: () => ({ meta: [{ title: "RustDesk · City Parking Control Center" }, { name: "description", content: "Remote desktop IDs for every station with one-click RustDesk connect." }] }),
  component: RustDeskPage,
});

function RustDeskPage() {
  const { stations } = getDataset();
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
              {stations.map((s) => (
                <tr key={s.id} className="border-t border-border">
                  <td className="px-4 py-3 font-medium">{s.name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{s.region}</td>
                  <td className="px-4 py-3 font-mono">{s.rustdeskId.replace(/(\d{3})(\d{3})(\d+)/, "$1 $2 $3")}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{s.vpnIp}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button title="Copy ID" className="size-7 grid place-items-center rounded-md border border-border bg-accent/40 hover:bg-accent text-muted-foreground hover:text-foreground"><Copy className="size-3.5" /></button>
                      <button className="inline-flex items-center gap-1.5 h-7 px-3 text-xs rounded-md bg-primary/20 border border-primary/40 text-primary hover:bg-primary/30">
                        <Monitor className="size-3.5" /> Connect
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
