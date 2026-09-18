import Link from "next/link";
import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError, NOT_AVAILABLE } from "@/components/ApiUnreachable";
import { Panel, KeyValueRow } from "@/components/Panel";
import { StatusBadge } from "@/components/StatusBadge";
import type { VanguardNode, ReadinessResult } from "@/lib/types";

export const dynamic = "force-dynamic";

const PROFILES = ["GENERAL_WORKER", "D27_CONTROL_HOST", "CLASSIFIED_GPU"];

export default async function NodeDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ profile?: string }>;
}) {
  const { id } = await params;
  const { profile = "GENERAL_WORKER" } = await searchParams;

  const [node, readiness] = await Promise.all([
    apiGet<VanguardNode>(`/nodes/${encodeURIComponent(id)}`),
    apiGet<ReadinessResult>(`/nodes/${encodeURIComponent(id)}/readiness`, { profile }),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="font-mono text-lg text-neutral-200">
          NODE <span className="text-neutral-500">/</span> {id}
        </h1>
        <Link href="/nodes" className="text-xs text-neutral-500 underline hover:text-neutral-300">
          ← all nodes
        </Link>
      </div>

      {!node.ok ? (
        node.unreachable ? (
          <ApiUnreachable error={node.error} />
        ) : (
          <ApiError status={node.status} error={node.error} />
        )
      ) : (
        <Panel title="Inventory">
          <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
            <div>
              <KeyValueRow label="Hostname" value={node.data.hostname} />
              <KeyValueRow label="Status" value={<StatusBadge status={node.data.status} />} />
              <KeyValueRow label="Locality" value={node.data.locality} />
              <KeyValueRow label="OS" value={`${node.data.os_name} ${node.data.os_version || ""}`.trim() || NOT_AVAILABLE} />
              <KeyValueRow label="Architecture" value={node.data.architecture || NOT_AVAILABLE} />
            </div>
            <div>
              <KeyValueRow label="CPU" value={node.data.cpu_model || NOT_AVAILABLE} />
              <KeyValueRow label="CPU cores (logical)" value={node.data.cpu_cores_logical || NOT_AVAILABLE} />
              <KeyValueRow
                label="Memory"
                value={node.data.memory_total_mb ? `${node.data.memory_total_mb} MB` : NOT_AVAILABLE}
              />
              <KeyValueRow label="GPU" value={node.data.gpu_model ?? NOT_AVAILABLE} />
              <KeyValueRow
                label="GPU VRAM"
                value={node.data.gpu_vram_mb != null ? `${node.data.gpu_vram_mb} MB` : NOT_AVAILABLE}
              />
            </div>
          </div>
          <div className="mt-3 border-t border-[var(--border)] pt-3">
            <span className="text-xs text-neutral-500">Capabilities: </span>
            <span className="font-mono text-xs text-neutral-300">
              {node.data.capabilities.length ? node.data.capabilities.join(", ") : NOT_AVAILABLE}
            </span>
          </div>
          <div className="mt-2">
            <KeyValueRow label="Last seen" value={node.data.last_seen} />
            <KeyValueRow label="Registered" value={node.data.registered_at} />
          </div>
          {node.data.notes ? (
            <p className="mt-3 border-t border-[var(--border)] pt-3 text-xs text-neutral-500">
              {node.data.notes}
            </p>
          ) : null}
        </Panel>
      )}

      <Panel title="Readiness" subtitle={`profile: ${profile}`}>
        <div className="mb-3 flex gap-2">
          {PROFILES.map((p) => (
            <Link
              key={p}
              href={`/nodes/${encodeURIComponent(id)}?profile=${p}`}
              className={`rounded border px-2 py-1 font-mono text-[11px] ${
                p === profile
                  ? "border-sky-800 bg-sky-950 text-sky-300"
                  : "border-[var(--border)] text-neutral-500 hover:text-neutral-300"
              }`}
            >
              {p}
            </Link>
          ))}
        </div>

        {!readiness.ok ? (
          readiness.unreachable ? (
            <ApiUnreachable error={readiness.error} />
          ) : (
            <ApiError status={readiness.status} error={readiness.error} />
          )
        ) : (
          <div className="space-y-3">
            <KeyValueRow label="State" value={<StatusBadge status={readiness.data.state} />} />
            <KeyValueRow label="Evaluated at" value={readiness.data.evaluated_at} />
            <table className="mt-2 w-full text-left text-xs">
              <thead className="text-neutral-500">
                <tr>
                  <th className="pb-1 font-normal">Check</th>
                  <th className="pb-1 font-normal">Passed</th>
                  <th className="pb-1 font-normal">Detail</th>
                </tr>
              </thead>
              <tbody>
                {readiness.data.evidence.map((e) => (
                  <tr key={e.check_id} className="border-t border-[var(--border)]">
                    <td className="py-1.5 font-mono text-neutral-300">{e.check_id}</td>
                    <td className="py-1.5">
                      {e.passed ? (
                        <span className="text-emerald-400">yes</span>
                      ) : (
                        <span className="text-red-400">no</span>
                      )}
                    </td>
                    <td className="py-1.5 text-neutral-500">{e.detail || NOT_AVAILABLE}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
