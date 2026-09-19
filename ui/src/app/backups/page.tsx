import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError } from "@/components/ApiUnreachable";
import { Panel } from "@/components/Panel";
import { BackupsPanel } from "@/components/BackupsPanel";
import type { BackupRecord } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function BackupsPage() {
  // Server-rendered probe purely to drive this page's honest whole-page
  // "API unreachable" state, same pattern as every other page — the actual
  // list/create/restore/delete interactions below run client-side against
  // the /api/backups/* proxy routes so they can poll job status and show
  // per-row confirmations.
  const result = await apiGet<BackupRecord[]>("/backups");

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">BACKUPS</h1>

      {!result.ok ? (
        result.unreachable ? (
          <ApiUnreachable error={result.error} />
        ) : (
          <ApiError status={result.status} error={result.error} />
        )
      ) : (
        <Panel
          title="Backups — this VANGUARD instance's own SQLite database"
          subtitle="POST /backups (job-queued) · POST /backups/{id}/restore (synchronous) · DELETE /backups/{id}"
        >
          <p className="mb-3 text-neutral-500">
            Real, self-contained <code className="text-neutral-400">backup-&lt;timestamp&gt;.zip</code>{" "}
            bundles under <code className="text-neutral-400">data/backups/</code>, built from a real
            SQLite online backup — not a raw file copy. This backs up VANGUARD&apos;s own local database
            only; it is not a general backup product or cloud storage. Restore always takes a real safety
            snapshot of the current live database first, and verifies a bundle&apos;s SHA-256 checksum
            before touching anything — a tampered or truncated bundle is refused outright. Restore requires
            no other request racing it mid-swap for full safety; see README.md for the exact, honestly
            documented limitation.
          </p>
          <BackupsPanel />
        </Panel>
      )}
    </div>
  );
}
