"use client";

import { useEffect, useRef, useState } from "react";
import type { Job } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { NOT_AVAILABLE } from "@/components/ApiUnreachable";

const ACTIVE_STATES = new Set(["QUEUED", "RUNNING", "RETRYING"]);

export function JobDetailPanel({ initial }: { initial: Job }) {
  const [job, setJob] = useState<Job>(initial);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [pending, setPending] = useState<"cancel" | "retry" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function refresh() {
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(initial.job_id)}`, { cache: "no-store" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setFetchError(body?.error ?? `HTTP ${res.status}`);
        return;
      }
      setFetchError(null);
      setJob(body as Job);
    } catch {
      setFetchError("VANGUARD API not reachable");
    }
  }

  useEffect(() => {
    if (!ACTIVE_STATES.has(job.state)) return;
    timerRef.current = setInterval(refresh, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.state]);

  async function runAction(action: "cancel" | "retry") {
    setPending(action);
    setActionError(null);
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(job.job_id)}/${action}`, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setActionError(body?.error ?? `${action} failed: HTTP ${res.status}`);
      } else {
        setJob(body as Job);
      }
    } catch {
      setActionError(`${action} failed: VANGUARD API not reachable`);
    } finally {
      setPending(null);
      setConfirmingCancel(false);
    }
  }

  const canCancel = job.state === "QUEUED" || job.state === "RUNNING" || job.state === "RETRYING";
  const canRetry = job.state === "FAILED" && job.retries < job.max_retries;

  return (
    <div className="space-y-4 text-xs">
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={job.state} />
        <span className="text-neutral-500">
          progress: <span className="font-mono text-neutral-300">{job.progress || NOT_AVAILABLE}</span>
        </span>
        <span className="text-neutral-500">
          retries:{" "}
          <span className="font-mono text-neutral-300">
            {job.retries}/{job.max_retries}
          </span>
        </span>
        <button
          onClick={refresh}
          className="rounded border border-[var(--border)] px-2 py-0.5 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800"
        >
          refresh
        </button>
      </div>

      {fetchError ? <p className="text-red-400">{fetchError}</p> : null}

      <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
        <div>
          <Row label="Job ID" value={job.job_id} mono />
          <Row label="Type" value={job.job_type} mono />
          <Row label="Requested by" value={job.requested_by || NOT_AVAILABLE} />
        </div>
        <div>
          <Row label="Created" value={job.created_at} />
          <Row label="Started" value={job.started_at ?? NOT_AVAILABLE} />
          <Row label="Finished" value={job.finished_at ?? NOT_AVAILABLE} />
        </div>
      </div>

      <div>
        <div className="mb-1 text-neutral-500">Params</div>
        <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded border border-[var(--border)] bg-black/40 p-2 font-mono text-[11px] text-neutral-400">
          {JSON.stringify(job.params, null, 2)}
        </pre>
      </div>

      {job.result ? (
        <div>
          <div className="mb-1 text-neutral-500">Result</div>
          <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded border border-emerald-900 bg-emerald-950/20 p-2 font-mono text-[11px] text-emerald-300">
            {JSON.stringify(job.result, null, 2)}
          </pre>
        </div>
      ) : null}

      {job.error ? (
        <div>
          <div className="mb-1 text-neutral-500">Error</div>
          <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded border border-red-900 bg-red-950/20 p-2 font-mono text-[11px] text-red-300">
            {job.error}
          </pre>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 border-t border-[var(--border)] pt-3">
        {confirmingCancel ? (
          <span className="flex items-center gap-1">
            <span className="text-amber-400">cancel this job?</span>
            <button
              onClick={() => runAction("cancel")}
              disabled={pending !== null}
              className="rounded border border-red-800 bg-red-950 px-2 py-1 font-mono text-[11px] text-red-400"
            >
              confirm
            </button>
            <button
              onClick={() => setConfirmingCancel(false)}
              className="rounded border border-[var(--border)] px-2 py-1 font-mono text-[11px] text-neutral-400"
            >
              cancel
            </button>
          </span>
        ) : (
          <button
            disabled={!canCancel || pending !== null}
            onClick={() => setConfirmingCancel(true)}
            title={!canCancel ? `Disabled: job is ${job.state.toLowerCase()}` : undefined}
            className="rounded border border-red-800 bg-red-950 px-3 py-1.5 font-mono text-[11px] text-red-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
          >
            {pending === "cancel" ? "canceling…" : "cancel"}
          </button>
        )}

        <button
          disabled={!canRetry || pending !== null}
          onClick={() => runAction("retry")}
          title={!canRetry ? `Disabled: job is ${job.state.toLowerCase()} or max_retries reached` : undefined}
          className="rounded border border-amber-800 bg-amber-950 px-3 py-1.5 font-mono text-[11px] text-amber-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
        >
          {pending === "retry" ? "retrying…" : "retry"}
        </button>
      </div>

      {actionError ? <p className="text-red-400">{actionError}</p> : null}
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--border)] py-1.5 last:border-0">
      <span className="text-neutral-500">{label}</span>
      <span className={mono ? "font-mono text-neutral-200" : "text-neutral-300"}>{value}</span>
    </div>
  );
}
