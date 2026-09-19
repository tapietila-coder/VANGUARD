"use client";

import { useEffect, useState } from "react";
import type { BackupRecord, Job } from "@/lib/types";
import { NOT_AVAILABLE } from "@/components/ApiUnreachable";

type FetchState =
  | { state: "loading" }
  | { state: "ready"; data: BackupRecord[] }
  | { state: "unreachable"; error: string }
  | { state: "error"; error: string };

type ConfirmAction = { kind: "restore" | "delete"; backupId: string } | null;

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB"];
  let value = n / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}

function ageFrom(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return NOT_AVAILABLE;
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

async function pollJobUntilDone(jobId: string, timeoutMs = 20000): Promise<Job> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" });
    const job = (await res.json()) as Job;
    if (job.state === "COMPLETED" || job.state === "FAILED" || job.state === "CANCELED") {
      return job;
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`Backup job ${jobId} did not finish within ${timeoutMs}ms`);
}

export function BackupsPanel() {
  const [fetchState, setFetchState] = useState<FetchState>({ state: "loading" });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<ConfirmAction>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [restoreResult, setRestoreResult] = useState<string | null>(null);

  async function refresh() {
    try {
      const res = await fetch("/api/backups", { cache: "no-store" });
      if (res.status === 503) {
        const body = await res.json().catch(() => ({}));
        setFetchState({ state: "unreachable", error: body?.error ?? "unreachable" });
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setFetchState({ state: "error", error: body?.error ?? `HTTP ${res.status}` });
        return;
      }
      const data = (await res.json()) as BackupRecord[];
      setFetchState({ state: "ready", data });
    } catch {
      setFetchState({ state: "unreachable", error: "VANGUARD API not reachable" });
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/backups", { cache: "no-store" });
        if (cancelled) return;
        if (res.status === 503) {
          const body = await res.json().catch(() => ({}));
          setFetchState({ state: "unreachable", error: body?.error ?? "unreachable" });
          return;
        }
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setFetchState({ state: "error", error: body?.error ?? `HTTP ${res.status}` });
          return;
        }
        const data = (await res.json()) as BackupRecord[];
        setFetchState({ state: "ready", data });
      } catch {
        if (!cancelled) setFetchState({ state: "unreachable", error: "VANGUARD API not reachable" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function createBackup() {
    setCreating(true);
    setCreateError(null);
    setRestoreResult(null);
    try {
      const res = await fetch("/api/backups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "manual" }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setCreateError(body?.error ?? `create failed: HTTP ${res.status}`);
        return;
      }
      const job = body as Job;
      const finished = await pollJobUntilDone(job.job_id);
      if (finished.state !== "COMPLETED") {
        setCreateError(finished.error ?? `backup job ended in state ${finished.state}`);
        return;
      }
      await refresh();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "backup creation failed");
    } finally {
      setCreating(false);
    }
  }

  async function runRestore(backupId: string) {
    setPendingId(backupId);
    setActionError(null);
    setRestoreResult(null);
    try {
      const res = await fetch(`/api/backups/${encodeURIComponent(backupId)}/restore`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "operator restore via /backups UI" }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setActionError(body?.error ?? `restore failed: HTTP ${res.status}`);
        return;
      }
      setRestoreResult(
        `Restored from ${body.restored_backup_id}. A safety snapshot of the prior state was taken: ${body.safety_snapshot_id}.`
      );
      await refresh();
    } catch {
      setActionError("restore failed: VANGUARD API not reachable");
    } finally {
      setPendingId(null);
      setConfirming(null);
    }
  }

  async function runDelete(backupId: string) {
    setPendingId(backupId);
    setActionError(null);
    try {
      const res = await fetch(`/api/backups/${encodeURIComponent(backupId)}`, { method: "DELETE" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setActionError(body?.error ?? `delete failed: HTTP ${res.status}`);
        return;
      }
      await refresh();
    } catch {
      setActionError("delete failed: VANGUARD API not reachable");
    } finally {
      setPendingId(null);
      setConfirming(null);
    }
  }

  return (
    <div className="space-y-3 text-xs">
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={createBackup}
          disabled={creating}
          className="rounded border border-emerald-800 bg-emerald-950 px-3 py-1.5 font-mono text-[11px] text-emerald-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
        >
          {creating ? "creating backup…" : "create backup"}
        </button>
        <button
          onClick={refresh}
          className="rounded border border-[var(--border)] px-2 py-0.5 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800"
        >
          refresh
        </button>
      </div>

      {createError ? <p className="text-red-400">{createError}</p> : null}
      {restoreResult ? <p className="text-emerald-400">{restoreResult}</p> : null}
      {actionError ? <p className="text-red-400">{actionError}</p> : null}

      {fetchState.state === "loading" ? (
        <p className="text-neutral-500">loading backups…</p>
      ) : fetchState.state === "unreachable" ? (
        <p className="text-red-400">{fetchState.error}</p>
      ) : fetchState.state === "error" ? (
        <p className="text-amber-400">{fetchState.error}</p>
      ) : fetchState.data.length === 0 ? (
        <p className="text-neutral-500">No backups yet — create one above.</p>
      ) : (
        <table className="w-full text-left text-xs">
          <thead className="text-neutral-500">
            <tr>
              <th className="pb-1 font-normal">Backup ID</th>
              <th className="pb-1 font-normal">Reason</th>
              <th className="pb-1 font-normal">Created</th>
              <th className="pb-1 font-normal">Size</th>
              <th className="pb-1 font-normal">SHA-256</th>
              <th className="pb-1 font-normal">File</th>
              <th className="pb-1 font-normal">Actions</th>
            </tr>
          </thead>
          <tbody>
            {fetchState.data.map((b) => (
              <tr key={b.backup_id} className="border-t border-[var(--border)] align-top">
                <td className="py-1.5 font-mono text-neutral-200">{b.backup_id}</td>
                <td className="py-1.5 text-neutral-400">{b.reason || NOT_AVAILABLE}</td>
                <td className="py-1.5 text-neutral-500" title={b.created_at}>
                  {ageFrom(b.created_at)}
                </td>
                <td className="py-1.5 font-mono text-neutral-400">{formatBytes(b.size_bytes)}</td>
                <td className="py-1.5 font-mono text-neutral-600" title={b.sha256}>
                  {b.sha256.slice(0, 12)}…
                </td>
                <td className="py-1.5">
                  {b.file_exists ? (
                    <span className="text-emerald-400">on disk</span>
                  ) : (
                    <span className="text-red-400">missing</span>
                  )}
                </td>
                <td className="py-1.5">
                  {confirming?.backupId === b.backup_id ? (
                    <span className="flex flex-col items-start gap-1">
                      <span className="text-amber-400">
                        {confirming.kind === "restore"
                          ? "overwrite the live database with this backup? A safety snapshot is taken first."
                          : "permanently delete this backup file?"}
                      </span>
                      <span className="flex gap-1">
                        <button
                          onClick={() =>
                            confirming.kind === "restore" ? runRestore(b.backup_id) : runDelete(b.backup_id)
                          }
                          disabled={pendingId !== null}
                          className={
                            confirming.kind === "restore"
                              ? "rounded border border-amber-800 bg-amber-950 px-2 py-1 font-mono text-[11px] text-amber-400"
                              : "rounded border border-red-800 bg-red-950 px-2 py-1 font-mono text-[11px] text-red-400"
                          }
                        >
                          {pendingId === b.backup_id ? "working…" : "confirm"}
                        </button>
                        <button
                          onClick={() => setConfirming(null)}
                          className="rounded border border-[var(--border)] px-2 py-1 font-mono text-[11px] text-neutral-400"
                        >
                          cancel
                        </button>
                      </span>
                    </span>
                  ) : (
                    <span className="flex gap-2">
                      <button
                        disabled={!b.file_exists || pendingId !== null}
                        onClick={() => setConfirming({ kind: "restore", backupId: b.backup_id })}
                        title={!b.file_exists ? "Disabled: backup file is missing on disk" : undefined}
                        className="rounded border border-amber-800 bg-amber-950 px-2 py-1 font-mono text-[11px] text-amber-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
                      >
                        restore
                      </button>
                      <button
                        disabled={pendingId !== null}
                        onClick={() => setConfirming({ kind: "delete", backupId: b.backup_id })}
                        className="rounded border border-red-800 bg-red-950 px-2 py-1 font-mono text-[11px] text-red-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
                      >
                        delete
                      </button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
