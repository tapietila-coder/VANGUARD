import { apiGet } from "@/lib/api";
import { Panel } from "@/components/Panel";
import { MetricsPanel } from "@/components/MetricsPanel";
import type { MetricsCurrentResponse, MetricsHistoryResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function MetricsPage() {
  const [currentResult, historyResult] = await Promise.all([
    apiGet<MetricsCurrentResponse>("/metrics/current"),
    apiGet<MetricsHistoryResponse>("/metrics/history", { interval: "60" }),
  ]);

  let initial;
  if (!currentResult.ok) {
    initial = currentResult.unreachable
      ? ({ state: "unreachable", error: currentResult.error } as const)
      : ({ state: "error", status: currentResult.status, error: currentResult.error } as const);
  } else if (!historyResult.ok) {
    initial = historyResult.unreachable
      ? ({ state: "unreachable", error: historyResult.error } as const)
      : ({ state: "error", status: historyResult.status, error: historyResult.error } as const);
  } else {
    initial = { state: "ready", current: currentResult.data, history: historyResult.data } as const;
  }

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">METRICS</h1>

      <Panel
        title="Local resource usage"
        subtitle="real CPU/RAM/disk samples for this one machine — GET /api/v1/vanguard/metrics/current + /history"
      >
        <MetricsPanel initial={initial} />
      </Panel>
    </div>
  );
}
