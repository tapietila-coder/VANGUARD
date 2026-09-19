import Link from "next/link";
import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError, NOT_AVAILABLE } from "@/components/ApiUnreachable";
import { Panel } from "@/components/Panel";
import { StatusBadge } from "@/components/StatusBadge";
import { JobSubmitForm } from "@/components/JobSubmitForm";
import type { Job } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function JobsPage() {
  const result = await apiGet<Job[]>("/jobs");

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">JOBS</h1>

      <Panel title="Job queue" subtitle="local ThreadPoolExecutor — real execution, no simulated states">
        {!result.ok ? (
          result.unreachable ? (
            <ApiUnreachable error={result.error} />
          ) : (
            <ApiError status={result.status} error={result.error} />
          )
        ) : result.data.length === 0 ? (
          <p className="text-xs text-neutral-500">No jobs yet — submit one below.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="text-neutral-500">
              <tr>
                <th className="pb-1 font-normal">Job ID</th>
                <th className="pb-1 font-normal">Type</th>
                <th className="pb-1 font-normal">State</th>
                <th className="pb-1 font-normal">Progress</th>
                <th className="pb-1 font-normal">Created</th>
                <th className="pb-1 font-normal">Started</th>
                <th className="pb-1 font-normal">Finished</th>
              </tr>
            </thead>
            <tbody>
              {result.data.map((j) => (
                <tr key={j.job_id} className="border-t border-[var(--border)]">
                  <td className="py-1.5 font-mono text-neutral-200">
                    <Link href={`/jobs/${encodeURIComponent(j.job_id)}`} className="underline hover:text-sky-300">
                      {j.job_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="py-1.5 font-mono text-neutral-300">{j.job_type}</td>
                  <td className="py-1.5">
                    <StatusBadge status={j.state} />
                  </td>
                  <td className="py-1.5 text-neutral-400">{j.progress || NOT_AVAILABLE}</td>
                  <td className="py-1.5 text-neutral-500">{j.created_at}</td>
                  <td className="py-1.5 text-neutral-500">{j.started_at ?? NOT_AVAILABLE}</td>
                  <td className="py-1.5 text-neutral-500">{j.finished_at ?? NOT_AVAILABLE}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="Submit a job" subtitle="POST /api/v1/vanguard/jobs">
        <p className="mb-3 text-xs text-neutral-500">
          Every job type here runs real VANGUARD logic against real state — no simulated result is ever
          returned.
        </p>
        <JobSubmitForm />
      </Panel>
    </div>
  );
}
