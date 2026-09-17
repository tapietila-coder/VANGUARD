import Link from "next/link";
import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError, NOT_AVAILABLE } from "@/components/ApiUnreachable";
import { Panel, KeyValueRow } from "@/components/Panel";
import { StatusBadge } from "@/components/StatusBadge";
import type {
  HealthResponse,
  VanguardNode,
  VanguardService,
  MeshStatus,
  ReadinessOverview,
  IntegrationsOverview,
} from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const [health, nodes, services, mesh, readiness, integrations] = await Promise.all([
    apiGet<HealthResponse>("/health"),
    apiGet<VanguardNode[]>("/nodes"),
    apiGet<VanguardService[]>("/services"),
    apiGet<MeshStatus>("/mesh/status"),
    apiGet<ReadinessOverview>("/readiness"),
    apiGet<IntegrationsOverview>("/integrations"),
  ]);

  // If the API is entirely unreachable, health.ok is false with unreachable=true.
  // Show one clear banner rather than six repeated ones.
  if (!health.ok && health.unreachable) {
    return (
      <div className="space-y-4">
        <h1 className="font-mono text-lg text-neutral-200">OVERVIEW</h1>
        <ApiUnreachable error={health.error} />
      </div>
    );
  }

  const onlineCount = nodes.ok ? nodes.data.filter((n) => n.status === "ONLINE").length : null;
  const offlineCount = nodes.ok
    ? nodes.data.filter((n) => n.status === "OFFLINE" || n.status === "STALE").length
    : null;

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="font-mono text-lg text-neutral-200">OVERVIEW</h1>
        {health.ok ? (
          <span className="font-mono text-xs text-neutral-500">
            environment: <span className="text-neutral-300">{health.data.environment}</span> · mode:{" "}
            <span className="text-neutral-300">{health.data.mode}</span>
          </span>
        ) : (
          <ApiError status={health.status} error={health.error} />
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Panel title="Mesh">
          {mesh.ok ? (
            <div className="space-y-2">
              <KeyValueRow label="Provider" value={mesh.data.provider} />
              <KeyValueRow label="Status" value={<StatusBadge status={mesh.data.status} />} />
              <p className="pt-2 text-xs text-neutral-500">{mesh.data.detail || NOT_AVAILABLE}</p>
            </div>
          ) : mesh.unreachable ? (
            <ApiUnreachable error={mesh.error} />
          ) : (
            <ApiError status={mesh.status} error={mesh.error} />
          )}
          <Link href="/mesh" className="mt-3 inline-block text-xs text-neutral-500 underline hover:text-neutral-300">
            view mesh detail →
          </Link>
        </Panel>

        <Panel title="Nodes">
          {nodes.ok ? (
            <div className="space-y-2">
              <KeyValueRow label="Total" value={nodes.data.length} />
              <KeyValueRow
                label="Online"
                value={<span className="text-emerald-400">{onlineCount}</span>}
              />
              <KeyValueRow
                label="Offline / Stale"
                value={<span className="text-neutral-400">{offlineCount}</span>}
              />
            </div>
          ) : nodes.unreachable ? (
            <ApiUnreachable error={nodes.error} />
          ) : (
            <ApiError status={nodes.status} error={nodes.error} />
          )}
          <Link href="/nodes" className="mt-3 inline-block text-xs text-neutral-500 underline hover:text-neutral-300">
            view all nodes →
          </Link>
        </Panel>

        <Panel title="Services">
          {services.ok ? (
            <div className="space-y-2">
              <KeyValueRow label="Registered" value={services.data.length} />
              {services.data.length === 0 ? (
                <p className="pt-2 text-xs text-neutral-500">No services registered.</p>
              ) : (
                <ul className="space-y-1 pt-1">
                  {services.data.slice(0, 5).map((s) => (
                    <li key={s.service_id} className="flex justify-between text-xs">
                      <span className="font-mono text-neutral-300">{s.service_id}</span>
                      <span className="text-neutral-500">{s.kind}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : services.unreachable ? (
            <ApiUnreachable error={services.error} />
          ) : (
            <ApiError status={services.status} error={services.error} />
          )}
          <Link
            href="/services"
            className="mt-3 inline-block text-xs text-neutral-500 underline hover:text-neutral-300"
          >
            view all services →
          </Link>
        </Panel>
      </div>

      <Panel title="Readiness" subtitle={readiness.ok ? `${readiness.data.profiles.length} profiles` : undefined}>
        {readiness.ok ? (
          readiness.data.recent_results.length === 0 ? (
            <p className="text-xs text-neutral-500">
              No readiness evaluations recorded yet. Profiles available:{" "}
              {readiness.data.profiles.join(", ")}.
            </p>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="text-neutral-500">
                <tr>
                  <th className="pb-1 font-normal">Node</th>
                  <th className="pb-1 font-normal">Profile</th>
                  <th className="pb-1 font-normal">State</th>
                  <th className="pb-1 font-normal">Evaluated</th>
                </tr>
              </thead>
              <tbody>
                {readiness.data.recent_results.map((r, i) => (
                  <tr key={`${r.node_id}-${r.profile_id}-${i}`} className="border-t border-[var(--border)]">
                    <td className="py-1.5 font-mono text-neutral-300">{r.node_id}</td>
                    <td className="py-1.5 font-mono text-neutral-400">{r.profile_id}</td>
                    <td className="py-1.5">
                      <StatusBadge status={r.state} />
                    </td>
                    <td className="py-1.5 text-neutral-500">{r.evaluated_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : readiness.unreachable ? (
          <ApiUnreachable error={readiness.error} />
        ) : (
          <ApiError status={readiness.status} error={readiness.error} />
        )}
        <Link
          href="/readiness"
          className="mt-3 inline-block text-xs text-neutral-500 underline hover:text-neutral-300"
        >
          view readiness detail →
        </Link>
      </Panel>

      <Panel title="Integrations">
        {integrations.ok ? (
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
            {Object.values(integrations.data).map((report) => (
              <div key={report.integration} className="flex flex-col gap-1">
                <span className="font-mono text-xs uppercase tracking-wide text-neutral-400">
                  {report.integration}
                </span>
                <StatusBadge status={report.status} />
                {report.detail ? (
                  <span className="text-[11px] text-neutral-600">{report.detail}</span>
                ) : null}
              </div>
            ))}
          </div>
        ) : integrations.unreachable ? (
          <ApiUnreachable error={integrations.error} />
        ) : (
          <ApiError status={integrations.status} error={integrations.error} />
        )}
      </Panel>
    </div>
  );
}
