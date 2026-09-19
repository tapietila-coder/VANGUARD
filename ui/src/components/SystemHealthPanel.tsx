"use client";

import { useState } from "react";
import type { SystemHealthReport } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { NOT_AVAILABLE } from "@/components/ApiUnreachable";

type FetchState =
  | { state: "ready"; data: SystemHealthReport }
  | { state: "unreachable"; error: string }
  | { state: "error"; error: string };

const SUBSYSTEM_LABELS: Record<string, string> = {
  api: "API",
  database: "Database",
  jobs: "Job Queue / Workers",
  service_control: "Service Control",
  mesh: "Mesh",
  integrations: "Integrations",
  readiness: "Readiness",
  audit_log: "Audit Log",
};

function secondsAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return NOT_AVAILABLE;
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 2) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

export function SystemHealthPanel({ initial }: { initial: FetchState }) {
  const [fetchState, setFetchState] = useState<FetchState>(initial);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const res = await fetch("/api/system-health", { cache: "no-store" });
      if (res.status === 503) {
        const body = await res.json().catch(() => ({}));
        setFetchState({ state: "unreachable", error: body?.error ?? "VANGUARD API not reachable" });
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setFetchState({ state: "error", error: body?.error ?? `HTTP ${res.status}` });
        return;
      }
      const data = (await res.json()) as SystemHealthReport;
      setFetchState({ state: "ready", data });
    } catch {
      setFetchState({ state: "unreachable", error: "VANGUARD API not reachable" });
    } finally {
      setLoading(false);
    }
  }

  // Honest whole-page failure: if the backend is unreachable, don't render a
  // partial table of rows next to a banner — say so, clearly, and nothing else.
  if (fetchState.state === "unreachable") {
    return (
      <div className="space-y-4">
        <div className="rounded border border-red-900 bg-red-950/40 px-4 py-3 font-mono text-sm text-red-400">
          <div className="font-semibold">VANGUARD UNREACHABLE</div>
          <div className="mt-1 text-red-300">{fetchState.error}</div>
          <div className="mt-2 text-xs text-neutral-500">
            No subsystem status can be shown while the API itself cannot be reached — start it with{" "}
            <code className="text-neutral-400">.\.venv\Scripts\python.exe -m vanguard serve</code> from the
            VANGUARD project root, then refresh.
          </div>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="rounded border border-[var(--border)] px-3 py-1.5 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800 disabled:opacity-50"
        >
          {loading ? "checking…" : "retry"}
        </button>
      </div>
    );
  }

  if (fetchState.state === "error") {
    return (
      <div className="space-y-4">
        <div className="rounded border border-amber-900 bg-amber-950/40 px-4 py-3 font-mono text-sm text-amber-400">
          <div className="font-semibold">API ERROR</div>
          <div className="mt-1 text-amber-300">{fetchState.error}</div>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="rounded border border-[var(--border)] px-3 py-1.5 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800 disabled:opacity-50"
        >
          {loading ? "checking…" : "retry"}
        </button>
      </div>
    );
  }

  const { data } = fetchState;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-xs text-neutral-500">
          snapshot generated: <span className="text-neutral-300">{secondsAgo(data.generated_at)}</span>{" "}
          <span className="text-neutral-600">({data.generated_at})</span>
        </span>
        <button
          onClick={refresh}
          disabled={loading}
          className="rounded border border-sky-800 bg-sky-950 px-3 py-1.5 font-mono text-[11px] text-sky-300 hover:bg-sky-900 disabled:opacity-50"
        >
          {loading ? "refreshing…" : "refresh"}
        </button>
      </div>

      <div className="space-y-2">
        {data.rows.map((row) => (
          <div
            key={row.subsystem}
            className="flex flex-col gap-2 rounded border border-[var(--border)] bg-black/20 p-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex min-w-[220px] items-center gap-3">
              <span className="font-mono text-sm text-neutral-200">
                {SUBSYSTEM_LABELS[row.subsystem] ?? row.subsystem}
              </span>
              <StatusBadge status={row.status} />
            </div>
            <div className="flex flex-1 flex-col text-xs text-neutral-500 sm:items-end sm:text-right">
              <span className="text-neutral-400">{row.detail || NOT_AVAILABLE}</span>
              <span className="text-[11px] text-neutral-600">checked {secondsAgo(row.checked_at)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
