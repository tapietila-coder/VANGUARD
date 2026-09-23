import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError } from "@/components/ApiUnreachable";
import { Panel } from "@/components/Panel";
import { IncidentsPanel } from "@/components/IncidentsPanel";
import type { Incident } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function IncidentsPage() {
  // Server-rendered probe purely to drive this page's honest whole-page "API
  // unreachable" state, same pattern as every other page — the actual
  // list/filter/acknowledge/resolve interactions run client-side against the
  // /api/incidents/* proxy routes.
  const result = await apiGet<Incident[]>("/incidents", { status: "OPEN" });

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">INCIDENTS</h1>

      {!result.ok ? (
        result.unreachable ? (
          <ApiUnreachable error={result.error} />
        ) : (
          <ApiError status={result.status} error={result.error} />
        )
      ) : (
        <Panel
          title="Incidents — correlated real failure signals"
          subtitle="GET /incidents · POST /incidents/{id}/acknowledge · POST /incidents/{id}/resolve"
        >
          <p className="mb-3 text-neutral-500">
            Real incidents correlated from real readiness NOT_READY/DEGRADED evaluations, Service
            Control process FAILED/unhealthy states, Job Queue FAILED jobs, and Dispatch integration
            CONNECTED-&gt;NOT_CONNECTED transitions — never a synthetic alert source. Repeated
            occurrences of the same underlying condition grow one incident&apos;s timeline instead of
            spawning duplicates; a condition that recovers on its own auto-resolves with a real
            timeline event. Steward/Watchtower/Marshal are permanently NOT_CONNECTED stubs and never
            generate incidents — that steady state is not a new failure.
          </p>
          <IncidentsPanel />
        </Panel>
      )}
    </div>
  );
}
