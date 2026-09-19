import { apiGet } from "@/lib/api";
import { Panel } from "@/components/Panel";
import { SystemHealthPanel } from "@/components/SystemHealthPanel";
import type { SystemHealthReport } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SystemHealthPage() {
  const result = await apiGet<SystemHealthReport>("/system-health");

  const initial = result.ok
    ? ({ state: "ready", data: result.data } as const)
    : result.unreachable
      ? ({ state: "unreachable", error: result.error } as const)
      : ({ state: "error", error: result.error } as const);

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">SYSTEM HEALTH</h1>

      <Panel
        title="Subsystems"
        subtitle="one real check per subsystem, run fresh on every load/refresh — GET /api/v1/vanguard/system-health"
      >
        <SystemHealthPanel initial={initial} />
      </Panel>
    </div>
  );
}
