import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError, NOT_AVAILABLE } from "@/components/ApiUnreachable";
import { Panel, KeyValueRow } from "@/components/Panel";
import { StatusBadge } from "@/components/StatusBadge";
import type { MeshStatus, MeshPeer, MeshRoute, MeshPolicy } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function MeshPage() {
  const [status, peers, routes, policies] = await Promise.all([
    apiGet<MeshStatus>("/mesh/status"),
    apiGet<MeshPeer[]>("/mesh/peers"),
    apiGet<MeshRoute[]>("/mesh/routes"),
    apiGet<MeshPolicy[]>("/mesh/policies"),
  ]);

  if (!status.ok && status.unreachable) {
    return (
      <div className="space-y-4">
        <h1 className="font-mono text-lg text-neutral-200">MESH</h1>
        <ApiUnreachable error={status.error} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">MESH</h1>

      <Panel title="Mesh provider status">
        {status.ok ? (
          <div className="space-y-2">
            <KeyValueRow label="Provider" value={status.data.provider} />
            <KeyValueRow label="Status" value={<StatusBadge status={status.data.status} />} />
            <p className="pt-2 text-xs text-neutral-500">
              {status.data.provider.toLowerCase() === "null"
                ? "Mesh provider: Null (no NetBird deployment configured)."
                : status.data.detail || NOT_AVAILABLE}
            </p>
            <p className="text-[11px] text-neutral-600">checked at {status.data.checked_at}</p>
          </div>
        ) : (
          <ApiError status={status.status} error={status.error} />
        )}
      </Panel>

      <Panel title="Peers" subtitle={peers.ok ? `${peers.data.length}` : undefined}>
        {!peers.ok ? (
          peers.unreachable ? <ApiUnreachable error={peers.error} /> : <ApiError status={peers.status} error={peers.error} />
        ) : peers.data.length === 0 ? (
          <p className="text-xs text-neutral-500">
            No mesh peers. Honest empty state — this environment has no real NetBird deployment.
          </p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="text-neutral-500">
              <tr>
                <th className="pb-1 font-normal">Peer</th>
                <th className="pb-1 font-normal">IP</th>
                <th className="pb-1 font-normal">OS</th>
                <th className="pb-1 font-normal">Status</th>
                <th className="pb-1 font-normal">Groups</th>
                <th className="pb-1 font-normal">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {peers.data.map((p) => (
                <tr key={p.peer_id} className="border-t border-[var(--border)]">
                  <td className="py-1.5 font-mono text-neutral-300">{p.name || p.peer_id}</td>
                  <td className="py-1.5 font-mono text-neutral-400">{p.ip ?? NOT_AVAILABLE}</td>
                  <td className="py-1.5 text-neutral-400">{p.os ?? NOT_AVAILABLE}</td>
                  <td className="py-1.5">
                    <StatusBadge status={p.status} />
                  </td>
                  <td className="py-1.5 text-neutral-500">{p.groups.length ? p.groups.join(", ") : NOT_AVAILABLE}</td>
                  <td className="py-1.5 font-mono text-neutral-500">{p.last_seen ?? NOT_AVAILABLE}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Panel title="Routes" subtitle={routes.ok ? `${routes.data.length}` : undefined}>
          {!routes.ok ? (
            routes.unreachable ? <ApiUnreachable error={routes.error} /> : <ApiError status={routes.status} error={routes.error} />
          ) : routes.data.length === 0 ? (
            <p className="text-xs text-neutral-500">No mesh routes configured.</p>
          ) : (
            <ul className="space-y-2 text-xs">
              {routes.data.map((r) => (
                <li key={r.route_id} className="flex justify-between border-b border-[var(--border)] pb-1 last:border-0">
                  <span className="font-mono text-neutral-300">{r.network}</span>
                  <span className={r.enabled ? "text-emerald-400" : "text-neutral-500"}>
                    {r.enabled ? "enabled" : "disabled"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Policies" subtitle={policies.ok ? `${policies.data.length}` : undefined}>
          {!policies.ok ? (
            policies.unreachable ? (
              <ApiUnreachable error={policies.error} />
            ) : (
              <ApiError status={policies.status} error={policies.error} />
            )
          ) : policies.data.length === 0 ? (
            <p className="text-xs text-neutral-500">No mesh policies configured.</p>
          ) : (
            <ul className="space-y-2 text-xs">
              {policies.data.map((p) => (
                <li key={p.policy_id} className="flex justify-between border-b border-[var(--border)] pb-1 last:border-0">
                  <span className="font-mono text-neutral-300">{p.name || p.policy_id}</span>
                  <span className={p.enabled ? "text-emerald-400" : "text-neutral-500"}>
                    {p.enabled ? "enabled" : "disabled"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
