import { createFileRoute } from "@tanstack/react-router";
import { Topbar } from "@/components/Topbar";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings · City Parking Control Center" }, { name: "description", content: "Authentication, roles, ping thresholds and integrations." }] }),
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <>
      <Topbar title="Settings" subtitle="System configuration" />
      <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Section title="Authentication">
          <Row label="JWT issuer" value="parking-control.tj" />
          <Row label="Access token TTL" value="60 minutes" />
          <Row label="Refresh token TTL" value="30 days" />
        </Section>
        <Section title="Roles">
          <Row label="Admin" value="Full access · 2 users" />
          <Row label="Operator" value="Manage stations & alerts · 8 users" />
          <Row label="Viewer" value="Read-only · 14 users" />
        </Section>
        <Section title="Ping thresholds">
          <Row label="Green" value="< 50 ms" />
          <Row label="Yellow" value="50 – 150 ms" />
          <Row label="Red" value="> 150 ms" />
          <Row label="Check interval" value="30 seconds" />
        </Section>
        <Section title="System">
          <Row label="Database" value="PostgreSQL 16 · primary + replica" />
          <Row label="Backend" value="FastAPI 0.115 · 4 workers" />
          <Row label="Version" value="v1.0.0" />
        </Section>
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass rounded-xl p-5">
      <h2 className="text-sm font-semibold mb-3">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm py-2 border-b border-border last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
