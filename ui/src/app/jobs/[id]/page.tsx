import Link from "next/link";
import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError } from "@/components/ApiUnreachable";
import { Panel } from "@/components/Panel";
import { JobDetailPanel } from "@/components/JobDetailPanel";
import type { Job } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await apiGet<Job>(`/jobs/${encodeURIComponent(id)}`);

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="font-mono text-lg text-neutral-200">
          JOB <span className="text-neutral-500">/</span> {id.slice(0, 8)}
        </h1>
        <Link href="/jobs" className="text-xs text-neutral-500 underline hover:text-neutral-300">
          ← all jobs
        </Link>
      </div>

      {!result.ok ? (
        result.unreachable ? (
          <ApiUnreachable error={result.error} />
        ) : (
          <ApiError status={result.status} error={result.error} />
        )
      ) : (
        <Panel title="Job detail">
          <JobDetailPanel initial={result.data} />
        </Panel>
      )}
    </div>
  );
}
