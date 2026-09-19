"use client";

import { useEffect, useState } from "react";
import type { ManagedProcessStatus } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { NOT_AVAILABLE } from "@/components/ApiUnreachable";

type FetchState =
  | { state: "loading" }
  | { state: "ready"; data: ManagedProcessStatus }
  | { state: "not_registered" }
  | { state: "unreachable"; error: string }
  | { state: "error"; error: string };

type PendingAction = "start" | "stop" | "restart" | null;

function secondsAgo(iso: string | null): string {
  if (!iso) return NOT_AVAILABLE;
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

function uptime(startedAt: string | null): string {
  if (!startedAt) return NOT_AVAILABLE;
  const started = new Date(startedAt).getTime();
  if (Number.isNaN(started)) return NOT_AVAILABLE;
  const seconds = Math.max(0, Math.round((Date.now() - started) / 1000));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h > 0 ? `${h}h ${m}m ${s}s` : m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function ProcessControlPanel({ serviceId }: { serviceId: string }) {
  const [fetchState, setFetchState] = useState<FetchState>({ state: "loading" });
  const [pending, setPending] = useState<PendingAction>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<"stop" | "restart" | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [logLines, setLogLines] = useState<string[] | null>(null);
  const [logError, setLogError] = useState<string | null>(null);
  const [logLoading, setLogLoading] = useState(false);

  async function refresh() {
    try {
      const res = await fetch(`/api/services/${encodeURIComponent(serviceId)}/process`, {
        cache: "no-store",
      });
      if (res.status === 404) {
        setFetchState({ state: "not_registered" });
        return;
      }
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
      const data = (await res.json()) as ManagedProcessStatus;
      setFetchState({ state: "ready", data });
    } catch {
      setFetchState({ state: "unreachable", error: "VANGUARD API not reachable" });
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetch(`/api/services/${encodeURIComponent(serviceId)}/process`, {
        cache: "no-store",
      }).catch(() => null);
      if (cancelled) return;
      if (!res) {
        setFetchState({ state: "unreachable", error: "VANGUARD API not reachable" });
        return;
      }
      if (res.status === 404) {
        setFetchState({ state: "not_registered" });
        return;
      }
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
      const data = (await res.json()) as ManagedProcessStatus;
      setFetchState({ state: "ready", data });
    })();
    return () => {
      cancelled = true;
    };
  }, [serviceId]);

  async function runAction(action: "start" | "stop" | "restart") {
    setPending(action);
    setActionError(null);
    try {
      const res = await fetch(`/api/services/${encodeURIComponent(serviceId)}/process/${action}`, {
        method: "POST",
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setActionError(body?.error ?? `${action} failed: HTTP ${res.status}`);
      } else {
        setFetchState({ state: "ready", data: body as ManagedProcessStatus });
      }
    } catch {
      setActionError(`${action} failed: VANGUARD API not reachable`);
    } finally {
      setPending(null);
      setConfirming(null);
    }
  }

  async function loadLogs() {
    setLogLoading(true);
    setLogError(null);
    try {
      const res = await fetch(`/api/services/${encodeURIComponent(serviceId)}/logs?lines=50`, {
        cache: "no-store",
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setLogError(body?.error ?? `HTTP ${res.status}`);
      } else {
        setLogLines(body.lines ?? []);
      }
    } catch {
      setLogError("VANGUARD API not reachable");
    } finally {
      setLogLoading(false);
    }
  }

  if (fetchState.state === "loading") {
    return <p className="text-xs text-neutral-500">loading process state…</p>;
  }
  if (fetchState.state === "not_registered") {
    return (
      <p className="text-xs text-neutral-500">
        No managed process is registered for &quot;{serviceId}&quot; (e.g. VANGUARD_DISPATCH_DIR wasn&apos;t
        set and the default path doesn&apos;t exist on this machine).
      </p>
    );
  }
  if (fetchState.state === "unreachable") {
    return <p className="text-xs text-red-400">{fetchState.error}</p>;
  }
  if (fetchState.state === "error") {
    return <p className="text-xs text-amber-400">{fetchState.error}</p>;
  }

  const status = fetchState.data;
  const isRunning = status.state === "RUNNING";
  const isTransitioning = status.state === "STARTING" || status.state === "STOPPING";
  const canStart = !isRunning && !isTransitioning;
  const canStop = isRunning && !isTransitioning;
  const canRestart = isRunning && !isTransitioning;

  return (
    <div className="space-y-3 text-xs">
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={status.state} />
        <span className="text-neutral-500">
          pid: <span className="font-mono text-neutral-300">{status.pid ?? NOT_AVAILABLE}</span>
        </span>
        <span className="text-neutral-500">
          uptime: <span className="font-mono text-neutral-300">{isRunning ? uptime(status.started_at) : NOT_AVAILABLE}</span>
        </span>
        <span className="text-neutral-500">
          health:{" "}
          <span className={status.healthy === true ? "text-emerald-400" : status.healthy === false ? "text-red-400" : "text-neutral-400"}>
            {status.healthy === null ? "unknown" : status.healthy ? "ok" : "failing"}
          </span>
        </span>
        <span className="text-neutral-600">
          checked {secondsAgo(status.last_checked)}
        </span>
        <button
          onClick={refresh}
          className="rounded border border-[var(--border)] px-2 py-0.5 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800"
        >
          refresh
        </button>
      </div>

      {status.health_detail ? (
        <p className="text-neutral-500">{status.health_detail}</p>
      ) : null}
      {status.last_exit_code !== null ? (
        <p className="text-neutral-500">last exit code: <span className="font-mono text-neutral-300">{status.last_exit_code}</span></p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <button
          disabled={!canStart || pending !== null}
          onClick={() => runAction("start")}
          title={!canStart ? `Disabled: process is ${status.state.toLowerCase()}` : undefined}
          className="rounded border border-emerald-800 bg-emerald-950 px-3 py-1.5 font-mono text-[11px] text-emerald-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
        >
          {pending === "start" ? "starting…" : "start"}
        </button>

        {confirming === "stop" ? (
          <span className="flex items-center gap-1">
            <span className="text-amber-400">stop the real process?</span>
            <button
              onClick={() => runAction("stop")}
              disabled={pending !== null}
              className="rounded border border-red-800 bg-red-950 px-2 py-1 font-mono text-[11px] text-red-400"
            >
              confirm
            </button>
            <button
              onClick={() => setConfirming(null)}
              className="rounded border border-[var(--border)] px-2 py-1 font-mono text-[11px] text-neutral-400"
            >
              cancel
            </button>
          </span>
        ) : (
          <button
            disabled={!canStop || pending !== null}
            onClick={() => setConfirming("stop")}
            title={!canStop ? `Disabled: process is ${status.state.toLowerCase()}` : undefined}
            className="rounded border border-red-800 bg-red-950 px-3 py-1.5 font-mono text-[11px] text-red-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
          >
            {pending === "stop" ? "stopping…" : "stop"}
          </button>
        )}

        {confirming === "restart" ? (
          <span className="flex items-center gap-1">
            <span className="text-amber-400">restart the real process?</span>
            <button
              onClick={() => runAction("restart")}
              disabled={pending !== null}
              className="rounded border border-amber-800 bg-amber-950 px-2 py-1 font-mono text-[11px] text-amber-400"
            >
              confirm
            </button>
            <button
              onClick={() => setConfirming(null)}
              className="rounded border border-[var(--border)] px-2 py-1 font-mono text-[11px] text-neutral-400"
            >
              cancel
            </button>
          </span>
        ) : (
          <button
            disabled={!canRestart || pending !== null}
            onClick={() => setConfirming("restart")}
            title={!canRestart ? `Disabled: process is ${status.state.toLowerCase()}` : undefined}
            className="rounded border border-amber-800 bg-amber-950 px-3 py-1.5 font-mono text-[11px] text-amber-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
          >
            {pending === "restart" ? "restarting…" : "restart"}
          </button>
        )}

        <button
          onClick={() => {
            setShowLogs((v) => !v);
            if (!showLogs && logLines === null) loadLogs();
          }}
          className="rounded border border-[var(--border)] px-3 py-1.5 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800"
        >
          {showLogs ? "hide logs" : "show logs"}
        </button>
      </div>

      {actionError ? <p className="text-red-400">{actionError}</p> : null}

      {showLogs ? (
        <div className="rounded border border-[var(--border)] bg-black/40 p-2">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-neutral-500">last 50 lines — {status.log_path ?? NOT_AVAILABLE}</span>
            <button
              onClick={loadLogs}
              className="rounded border border-[var(--border)] px-2 py-0.5 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800"
            >
              {logLoading ? "loading…" : "refresh log"}
            </button>
          </div>
          {logError ? (
            <p className="text-red-400">{logError}</p>
          ) : (
            <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap font-mono text-[11px] text-neutral-400">
              {logLines && logLines.length > 0 ? logLines.join("\n") : "(no captured output yet)"}
            </pre>
          )}
        </div>
      ) : null}
    </div>
  );
}
