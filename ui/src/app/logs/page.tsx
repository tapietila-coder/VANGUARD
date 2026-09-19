import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError } from "@/components/ApiUnreachable";
import { Panel } from "@/components/Panel";
import { LogsExplorer } from "@/components/LogsExplorer";
import type { LogSource } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function LogsPage() {
  const result = await apiGet<LogSource[]>("/logs");

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">LOGS</h1>

      <Panel
        title="Service logs"
        subtitle="real data/logs/*.log content via Service Control — no aggregation service"
      >
        {!result.ok ? (
          result.unreachable ? (
            <ApiUnreachable error={result.error} />
          ) : (
            <ApiError status={result.status} error={result.error} />
          )
        ) : result.data.length === 0 ? (
          <p className="text-xs text-neutral-500">
            No services have a real captured log yet — nothing is registered with Service Control on this
            machine (e.g. Dispatch registration requires <code className="text-neutral-400">VANGUARD_DISPATCH_DIR</code>{" "}
            to point at a real on-disk install).
          </p>
        ) : (
          <LogsExplorer sources={result.data} />
        )}
      </Panel>
    </div>
  );
}
