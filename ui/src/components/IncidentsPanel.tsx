"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Incident } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { NOT_AVAILABLE } from "@/components/ApiUnreachable";

type FetchState =
  | { state: "loading" }
  | { state: "ready"; data: Incident[] }
  | { state: "unreachable"; error: string }
  | { state: "error"; error: string };

type ConfirmAction = { kind: "acknowledge" | "resolve"; incidentId: string } | null;

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

const STATUS_FILTERS = ["ALL", "OPEN", "ACKNOWLEDGED", "RESOLVED"] as const;

export function IncidentsPanel() {
  const [fetchState, setFetchState] = useState<FetchState>({ state: "loading" });
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("OPEN");
  const [confirming, setConfirming] = useState<ConfirmAction>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function refresh(status: (typeof STATUS_FILTERS)[number] = statusFilter) {
    try {
      const qs = status === "ALL" ? "" : `?status=${encodeURIComponent(status)}`;
      const res = await fetch(`/api/incidents${qs}`, { cache: "no-store" });
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
      const data = (await res.json()) as Incident[];
      setFetchState({ state: "ready", data });
    } catch {
      setFetchState({ state: "unreachable", error: "VANGUARD API not reachable" });
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/incidents?status=OPEN", { cache: "no-store" });
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
        const data = (await res.json()) as Incident[];
        setFetchState({ state: "ready", data });
      } catch {
        if (!cancelled) setFetchState({ state: "unreachable", error: "VANGUARD API not reachable" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function selectFilter(status: (typeof STATUS_FILTERS)[number]) {
    setStatusFilter(status);
    setFetchState({ state: "loading" });
    refresh(status);
  }

  async function runAction(kind: "acknowledge" | "resolve", incidentId: string) {
    setPendingId(incidentId);
    setActionError(null);
    try {
      const res = await fetch(`/api/incidents/${encodeURIComponent(incidentId)}/${kind}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: `operator ${kind} via /incidents UI` }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setActionError(body?.error ?? `${kind} failed: HTTP ${res.status}`);
        return;
      }
      await refresh();
    } catch {
      setActionError(`${kind} failed: VANGUARD API not reachable`);
    } finally {
      setPendingId(null);
      setConfirming(null);
    }
  }

  return (
    <div className="space-y-3 text-xs">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => selectFilter(s)}
              className={`rounded border px-2 py-1 font-mono text-[11px] ${
                statusFilter === s
                  ? "border-sky-800 bg-sky-950 text-sky-300"
                  : "border-[var(--border)] text-neutral-400 hover:bg-neutral-800"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <button
          onClick={() => refresh()}
          className="rounded border border-[var(--border)] px-2 py-1 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800"
        >
          refresh
        </button>
      </div>

      {actionError ? <p className="text-red-400">{actionError}</p> : null}

      {fetchState.state === "loading" ? (
        <p className="text-neutral-500">loading incidents…</p>
      ) : fetchState.state === "unreachable" ? (
        <p className="text-red-400">{fetchState.error}</p>
      ) : fetchState.state === "error" ? (
        <p className="text-amber-400">{fetchState.error}</p>
      ) : fetchState.data.length === 0 ? (
        <p className="text-neutral-500">
          {statusFilter === "OPEN" || statusFilter === "ALL"
            ? "No incidents — everything's healthy."
            : `No ${statusFilter.toLowerCase()} incidents.`}
        </p>
      ) : (
        <table className="w-full text-left text-xs">
          <thead className="text-neutral-500">
            <tr>
              <th className="pb-1 font-normal">Title</th>
              <th className="pb-1 font-normal">Severity</th>
              <th className="pb-1 font-normal">Status</th>
              <th className="pb-1 font-normal">Source</th>
              <th className="pb-1 font-normal">First seen</th>
              <th className="pb-1 font-normal">Last seen</th>
              <th className="pb-1 font-normal">Occurrences</th>
              <th className="pb-1 font-normal">Actions</th>
            </tr>
          </thead>
          <tbody>
            {fetchState.data.map((i) => (
              <tr key={i.incident_id} className="border-t border-[var(--border)] align-top">
                <td className="py-1.5 text-neutral-200">
                  <Link
                    href={`/incidents/${encodeURIComponent(i.incident_id)}`}
                    className="underline hover:text-sky-300"
                  >
                    {i.title}
                  </Link>
                </td>
                <td className="py-1.5">
                  <StatusBadge status={i.severity} />
                </td>
                <td className="py-1.5">
                  <StatusBadge status={i.status} />
                </td>
                <td className="py-1.5 font-mono text-neutral-500">{i.source}</td>
                <td className="py-1.5 text-neutral-500" title={i.first_seen}>
                  {ageFrom(i.first_seen)}
                </td>
                <td className="py-1.5 text-neutral-500" title={i.last_seen}>
                  {ageFrom(i.last_seen)}
                </td>
                <td className="py-1.5 font-mono text-neutral-400">{i.occurrence_count}</td>
                <td className="py-1.5">
                  {i.status === "RESOLVED" ? (
                    <span className="text-neutral-600">{NOT_AVAILABLE}</span>
                  ) : confirming?.incidentId === i.incident_id ? (
                    <span className="flex flex-col items-start gap-1">
                      <span className="text-amber-400">
                        {confirming.kind === "acknowledge"
                          ? "acknowledge this incident?"
                          : "mark this incident resolved?"}
                      </span>
                      <span className="flex gap-1">
                        <button
                          onClick={() => runAction(confirming.kind, i.incident_id)}
                          disabled={pendingId !== null}
                          className="rounded border border-amber-800 bg-amber-950 px-2 py-1 font-mono text-[11px] text-amber-400"
                        >
                          {pendingId === i.incident_id ? "working…" : "confirm"}
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
                      {i.status === "OPEN" ? (
                        <button
                          disabled={pendingId !== null}
                          onClick={() => setConfirming({ kind: "acknowledge", incidentId: i.incident_id })}
                          className="rounded border border-amber-800 bg-amber-950 px-2 py-1 font-mono text-[11px] text-amber-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
                        >
                          acknowledge
                        </button>
                      ) : null}
                      <button
                        disabled={pendingId !== null}
                        onClick={() => setConfirming({ kind: "resolve", incidentId: i.incident_id })}
                        className="rounded border border-emerald-800 bg-emerald-950 px-2 py-1 font-mono text-[11px] text-emerald-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
                      >
                        resolve
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
