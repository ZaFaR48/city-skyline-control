import { createFileRoute } from "@tanstack/react-router";
import { Topbar } from "@/components/Topbar";

export const Route = createFileRoute("/settings")({ component: SettingsPage });
const matrix = [
  ["Dashboard, map, stations, cameras, alerts, reports", "Yes", "Yes", "Read-only"],
  ["Create/update station information", "Yes", "Yes", "No"],
  ["Approve Headscale devices and users", "Yes", "No", "No"],
  ["Manage users, roles, regions, and security", "Yes", "No", "No"],
  ["Acknowledge alerts", "Yes", "Yes", "No"],
  ["Archive stations and resolve alerts", "Yes", "No", "No"],
];
function SettingsPage() {
  return (
    <>
      <Topbar title="Settings" subtitle="Server-managed security and monitoring policy" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <section className="glass rounded-xl p-5">
          <h2 className="text-sm font-semibold">Monitoring configuration</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Thresholds and integration credentials are configured server-side. Secret values are
            never displayed in the dashboard.
          </p>
        </section>
        <section className="glass rounded-xl overflow-x-auto">
          <table className="w-full min-w-[700px] text-sm">
            <thead className="bg-panel text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="p-3">Permission</th>
                <th>ADMIN</th>
                <th>OPERATOR</th>
                <th>VIEWER</th>
              </tr>
            </thead>
            <tbody>
              {matrix.map((row) => (
                <tr key={row[0]} className="border-t border-border">
                  <td className="p-3">{row[0]}</td>
                  <td>{row[1]}</td>
                  <td>{row[2]}</td>
                  <td>{row[3]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </>
  );
}
