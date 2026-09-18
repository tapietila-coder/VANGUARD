import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError, NOT_AVAILABLE } from "@/components/ApiUnreachable";
import { Panel } from "@/components/Panel";
import { ServiceResolver } from "@/components/ServiceResolver";
import { ProcessControlPanel } from "@/components/ProcessControlPanel";
import type { VanguardService } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ServicesPage() {
  const result = await apiGet<VanguardService[]>("/services");

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">SERVICES</h1>

      <Panel title="Registered services">
        {!result.ok ? (
          result.unreachable ? (
            <ApiUnreachable error={result.error} />
          ) : (
            <ApiError status={result.status} error={result.error} />
          )
        ) : result.data.length === 0 ? (
          <p className="text-xs text-neutral-500">No services registered in the service map.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="text-neutral-500">
              <tr>
                <th className="pb-1 font-normal">Service ID</th>
                <th className="pb-1 font-normal">Name</th>
                <th className="pb-1 font-normal">Kind</th>
                <th className="pb-1 font-normal">Node</th>
                <th className="pb-1 font-normal">Base URL</th>
                <th className="pb-1 font-normal">Owner</th>
                <th className="pb-1 font-normal">Updated</th>
              </tr>
            </thead>
            <tbody>
              {result.data.map((s) => (
                <tr key={s.service_id} className="border-t border-[var(--border)]">
                  <td className="py-1.5 font-mono text-neutral-200">{s.service_id}</td>
                  <td className="py-1.5 text-neutral-300">{s.name}</td>
                  <td className="py-1.5 text-neutral-400">{s.kind}</td>
                  <td className="py-1.5 font-mono text-neutral-400">{s.node_id ?? NOT_AVAILABLE}</td>
                  <td className="py-1.5 font-mono text-neutral-500">{s.base_url ?? NOT_AVAILABLE}</td>
                  <td className="py-1.5 text-neutral-500">{s.owner || NOT_AVAILABLE}</td>
                  <td className="py-1.5 text-neutral-500">{s.updated_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="Resolve by name" subtitle="GET /services/{id}">
        <p className="mb-3 text-xs text-neutral-500">
          Resolves by service_id first, falling back to an exact registered name match. Returns
          &quot;not found&quot; rather than a guess when nothing matches.
        </p>
        <ServiceResolver />
      </Panel>

      <Panel
        title="Service control — dispatch"
        subtitle="real start/stop/restart of the local Dispatch process"
      >
        <p className="mb-3 text-neutral-500 text-xs">
          The only real process VANGUARD can control in this pass is the local D27HQ Dispatch API.
          Start/stop/restart here spawn or terminate an actual local OS process — Stop and Restart
          ask for confirmation first.
        </p>
        <ProcessControlPanel serviceId="dispatch" />
      </Panel>
    </div>
  );
}
