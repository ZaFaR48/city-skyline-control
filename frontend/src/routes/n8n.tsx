import { createFileRoute } from "@tanstack/react-router";
import { Topbar } from "@/components/Topbar";
import { Workflow } from "lucide-react";

export const Route = createFileRoute("/n8n")({
  head: () => ({ meta: [{ title: "n8n · City Parking Control Center" }, { name: "description", content: "Send station events to n8n workflows via webhook." }] }),
  component: N8nPage,
});

const EVENTS = ["station.online", "station.offline", "station.warning", "camera.offline", "alert.created", "alert.resolved"];

function N8nPage() {
  return (
    <>
      <Topbar title="n8n" subtitle="Workflow webhook bridge" />
      <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold flex items-center gap-2"><Workflow className="size-4 text-primary" /> Webhook</h2>
          <label className="block">
            <span className="text-xs uppercase tracking-wider text-muted-foreground">URL</span>
            <input defaultValue="https://n8n.example.tj/webhook/parking-events" className="mt-1 w-full h-9 px-3 rounded-md bg-input/60 border border-border font-mono text-xs" />
          </label>
          <div>
            <span className="text-xs uppercase tracking-wider text-muted-foreground">Events</span>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {EVENTS.map((e) => (
                <label key={e} className="flex items-center gap-2 p-2 rounded-md border border-border bg-accent/30 text-xs">
                  <input type="checkbox" defaultChecked className="accent-primary" /><span className="font-mono">{e}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="h-9 px-4 rounded-md bg-primary/20 border border-primary/40 text-primary hover:bg-primary/30 text-sm">Save</button>
            <button className="h-9 px-4 rounded-md border border-border bg-accent/40 hover:bg-accent text-sm">Send test</button>
          </div>
        </div>
        <div className="glass rounded-xl p-5">
          <h2 className="text-sm font-semibold mb-3">Example payload</h2>
          <pre className="font-mono text-xs whitespace-pre rounded-lg border border-border bg-panel/60 p-4 overflow-x-auto">
{`{
  "event": "station.offline",
  "station": {
    "id": "STN-15",
    "name": "Dushanbe-15",
    "region": "Dushanbe",
    "vpn_ip": "100.64.0.15"
  },
  "severity": "critical",
  "timestamp": "${new Date().toISOString()}"
}`}
          </pre>
        </div>
      </div>
    </>
  );
}
