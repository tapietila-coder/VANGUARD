import Link from "next/link";
import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError } from "@/components/ApiUnreachable";
import { Panel } from "@/components/Panel";
import { IncidentDetailPanel } from "@/components/IncidentDetailPanel";
import type { Incident } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function IncidentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await apiGet<Incident>(`/incidents/${encodeURIComponent(id)}`);

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="font-mono text-lg text-neutral-200">
          INCIDENT <span className="text-neutral-500">/</span> {id.slice(0, 8)}
        </h1>
        <Link href="/incidents" className="text-xs text-neutral-500 underline hover:text-neutral-300">
          ← all incidents
        </Link>
      </div>

      {!result.ok ? (
        result.unreachable ? (
          <ApiUnreachable error={result.error} />
        ) : (
          <ApiError status={result.status} error={result.error} />
        )
      ) : (
        <Panel title="Incident detail">
          <IncidentDetailPanel initial={result.data} />
        </Panel>
      )}
    </div>
  );
}
