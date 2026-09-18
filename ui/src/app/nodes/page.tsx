import Link from "next/link";
import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError, NOT_AVAILABLE } from "@/components/ApiUnreachable";
import { StatusBadge } from "@/components/StatusBadge";
import type { VanguardNode } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function NodesPage() {
  const result = await apiGet<VanguardNode[]>("/nodes");

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg text-neutral-200">NODES</h1>

      {!result.ok ? (
        result.unreachable ? (
          <ApiUnreachable error={result.error} />
        ) : (
          <ApiError status={result.status} error={result.error} />
        )
      ) : result.data.length === 0 ? (
        <p className="font-mono text-sm text-neutral-500">
          No nodes registered. Register the local machine with{" "}
          <code className="text-neutral-400">vanguard scan</code> / the register API.
        </p>
      ) : (
        <div className="overflow-x-auto rounded border border-[var(--border)]">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[var(--border)] bg-[var(--surface)] text-neutral-500">
              <tr>
                <th className="px-3 py-2 font-normal">Node ID</th>
                <th className="px-3 py-2 font-normal">Hostname</th>
                <th className="px-3 py-2 font-normal">Locality</th>
                <th className="px-3 py-2 font-normal">OS</th>
                <th className="px-3 py-2 font-normal">Status</th>
                <th className="px-3 py-2 font-normal">Capabilities</th>
                <th className="px-3 py-2 font-normal">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {result.data.map((n) => (
                <tr key={n.node_id} className="border-b border-[var(--border)] last:border-0 hover:bg-neutral-900/50">
                  <td className="px-3 py-2">
                    <Link href={`/nodes/${encodeURIComponent(n.node_id)}`} className="font-mono text-sky-400 hover:underline">
                      {n.node_id}
                    </Link>
                  </td>
                  <td className="px-3 py-2 font-mono text-neutral-300">{n.hostname}</td>
                  <td className="px-3 py-2 text-neutral-400">{n.locality}</td>
                  <td className="px-3 py-2 text-neutral-400">
                    {n.os_name} {n.os_version || NOT_AVAILABLE}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={n.status} />
                  </td>
                  <td className="px-3 py-2 text-neutral-500">
                    {n.capabilities.length ? n.capabilities.join(", ") : NOT_AVAILABLE}
                  </td>
                  <td className="px-3 py-2 font-mono text-neutral-500">{n.last_seen}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
