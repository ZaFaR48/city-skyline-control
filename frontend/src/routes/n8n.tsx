import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Workflow } from "lucide-react";
import { Topbar } from "@/components/Topbar";
import { apiFetch } from "@/lib/api";

export const Route = createFileRoute("/n8n")({ component: N8nPage });
function N8nPage() {
  const [result, setResult] = useState<string | null>(null);
  async function test() {
    try {
      const response = await apiFetch<{ sent: boolean }>("/api/webhooks/n8n/test", {
        method: "POST",
      });
      setResult(
        response.sent
          ? "Test event delivered."
          : "Integration is not configured or did not accept the event.",
      );
    } catch (err) {
      setResult(err instanceof Error ? err.message : "Test failed");
    }
  }
  return (
    <>
      <Topbar title="n8n" subtitle="Server-managed workflow bridge" />
      <div className="flex-1 overflow-y-auto p-6">
        <section className="glass rounded-xl p-5 max-w-2xl">
          <h2 className="text-sm font-semibold flex gap-2 items-center">
            <Workflow className="size-4 text-primary" /> Webhook integration
          </h2>
          <p className="my-3 text-sm text-muted-foreground">
            The endpoint and credentials are stored on the backend and are not exposed here.
          </p>
          <button onClick={test} className="h-9 px-4 border border-primary/40 text-primary rounded">
            Send test event
          </button>
          {result && <p className="mt-3 text-sm">{result}</p>}
        </section>
      </div>
    </>
  );
}
