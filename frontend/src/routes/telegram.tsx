import { createFileRoute } from "@tanstack/react-router";
import { Topbar } from "@/components/Topbar";
import { Send } from "lucide-react";

export const Route = createFileRoute("/telegram")({
  head: () => ({ meta: [{ title: "Telegram · City Parking Control Center" }, { name: "description", content: "Configure Telegram alert channels and message templates." }] }),
  component: TelegramPage,
});

function TelegramPage() {
  return (
    <>
      <Topbar title="Telegram" subtitle="Operator notification channels" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold flex items-center gap-2"><Send className="size-4 text-primary" /> Bot Configuration</h2>
            <Field label="Bot token" placeholder="123456789:AAEx…" type="password" />
            <Field label="Default chat ID" placeholder="-1001234567890" />
            <div className="grid grid-cols-3 gap-2">
              <Toggle label="Offline station" defaultChecked />
              <Toggle label="Camera offline" defaultChecked />
              <Toggle label="VPN down" defaultChecked />
            </div>
            <button className="h-9 px-4 rounded-md bg-primary/20 border border-primary/40 text-primary hover:bg-primary/30 text-sm">Save</button>
          </div>
          <div className="glass rounded-xl p-5">
            <h2 className="text-sm font-semibold mb-3">Sample notification</h2>
            <pre className="font-mono text-xs whitespace-pre-wrap rounded-lg border border-border bg-panel/60 p-4 text-foreground">
{`🚨 Station Offline
Station: Dushanbe-01
VPN:     100.64.0.15
Region:  Dushanbe
Time:    ${new Date().toLocaleTimeString()}
Reason:  Ping timeout 4/4`}
            </pre>
          </div>
        </div>
      </div>
    </>
  );
}

function Field({ label, ...rest }: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-wider text-muted-foreground">{label}</span>
      <input {...rest} className="mt-1 w-full h-9 px-3 rounded-md bg-input/60 border border-border text-sm focus:outline-none focus:ring-2 focus:ring-ring/50" />
    </label>
  );
}

function Toggle({ label, defaultChecked }: { label: string; defaultChecked?: boolean }) {
  return (
    <label className="flex items-center justify-between gap-2 p-2 rounded-md border border-border bg-accent/30 cursor-pointer">
      <span className="text-xs">{label}</span>
      <input type="checkbox" defaultChecked={defaultChecked} className="accent-primary" />
    </label>
  );
}
