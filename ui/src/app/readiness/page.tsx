import Link from "next/link";
import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError } from "@/components/ApiUnreachable";
import { Panel } from "@/components/Panel";
import { StatusBadge } from "@/components/StatusBadge";
import type { ReadinessOverview } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ReadinessPage() {
  const result = await apiGet<ReadinessOverview>("/readiness");

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">READINESS</h1>

      {!result.ok ? (
        result.unreachable ? (
          <ApiUnreachable error={result.error} />
        ) : (
          <ApiError status={result.status} error={result.error} />
        )
      ) : (
        <>
          <Panel title="Built-in profiles">
            <ul className="flex flex-wrap gap-2">
              {result.data.profiles.map((p) => (
                <li
                  key={p}
                  className="rounded border border-[var(--border)] px-2 py-1 font-mono text-xs text-neutral-300"
                >
                  {p}
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Recent results" subtitle={`${result.data.recent_results.length}`}>
            {result.data.recent_results.length === 0 ? (
              <p className="text-xs text-neutral-500">
                No readiness evaluations recorded yet. Evaluate a node from its detail page to record one.
              </p>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="text-neutral-500">
                  <tr>
                    <th className="pb-1 font-normal">Node</th>
                    <th className="pb-1 font-normal">Profile</th>
                    <th className="pb-1 font-normal">State</th>
                    <th className="pb-1 font-normal">Checks</th>
                    <th className="pb-1 font-normal">Evaluated</th>
                  </tr>
                </thead>
                <tbody>
                  {result.data.recent_results.map((r, i) => (
                    <tr key={`${r.node_id}-${r.profile_id}-${i}`} className="border-t border-[var(--border)]">
                      <td className="py-1.5">
                        <Link href={`/nodes/${encodeURIComponent(r.node_id)}?profile=${r.profile_id}`} className="font-mono text-sky-400 hover:underline">
                          {r.node_id}
                        </Link>
                      </td>
                      <td className="py-1.5 font-mono text-neutral-400">{r.profile_id}</td>
                      <td className="py-1.5">
                        <StatusBadge status={r.state} />
                      </td>
                      <td className="py-1.5 text-neutral-500">
                        {r.evidence.filter((e) => e.passed).length}/{r.evidence.length} passed
                      </td>
                      <td className="py-1.5 text-neutral-500">{r.evaluated_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
