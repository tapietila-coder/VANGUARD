"use client";

import { useState } from "react";
import type { LogSource, ProcessLogsResponse } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { NOT_AVAILABLE } from "@/components/ApiUnreachable";

function formatBytes(n: number | null): string {
  if (n === null) return NOT_AVAILABLE;
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function LogsExplorer({ sources }: { sources: LogSource[] }) {
  const withLogs = sources.filter((s) => s.exists);
  const [selected, setSelected] = useState<string | null>(withLogs[0]?.service_id ?? sources[0]?.service_id ?? null);
  const [lines, setLines] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tailCount, setTailCount] = useState("200");
  const [filter, setFilter] = useState("");

  async function loadTail(serviceId: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/services/${encodeURIComponent(serviceId)}/logs?lines=${encodeURIComponent(tailCount)}`,
        { cache: "no-store" }
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(body?.error ?? `HTTP ${res.status}`);
        setLines(null);
      } else {
        setLines((body as ProcessLogsResponse).lines ?? []);
      }
    } catch {
      setError("VANGUARD API not reachable");
      setLines(null);
    } finally {
      setLoading(false);
    }
  }

  function select(serviceId: string) {
    setSelected(serviceId);
    setLines(null);
    setFilter("");
    loadTail(serviceId);
  }

  const visibleLines = filter.trim()
    ? (lines ?? []).filter((l) => l.toLowerCase().includes(filter.trim().toLowerCase()))
    : lines;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
      <div className="space-y-1">
        {sources.map((s) => (
          <button
            key={s.service_id}
            onClick={() => select(s.service_id)}
            className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left text-xs transition-colors ${
              selected === s.service_id
                ? "border-sky-800 bg-sky-950/40"
                : "border-[var(--border)] hover:bg-neutral-900/60"
            }`}
          >
            <span className="flex flex-col">
              <span className="font-mono text-neutral-200">{s.service_id}</span>
              <span className="text-neutral-500">{s.name}</span>
            </span>
            <span className="flex flex-col items-end gap-1">
              <StatusBadge status={s.state} />
              {!s.exists ? <span className="text-[10px] text-neutral-600">no log yet</span> : null}
            </span>
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {selected === null ? (
          <p className="text-xs text-neutral-500">Select a service on the left.</p>
        ) : (
          <>
            {(() => {
              const src = sources.find((s) => s.service_id === selected);
              if (!src) return null;
              return (
                <div className="flex flex-wrap items-center gap-3 text-xs text-neutral-500">
                  <span>
                    path: <span className="font-mono text-neutral-400">{src.log_path}</span>
                  </span>
                  <span>size: {formatBytes(src.size_bytes)}</span>
                  <span>total lines: {src.line_count ?? NOT_AVAILABLE}</span>
                  <span>last modified: {src.last_modified ?? NOT_AVAILABLE}</span>
                </div>
              );
            })()}

            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs text-neutral-500">tail</label>
              <input
                value={tailCount}
                onChange={(e) => setTailCount(e.target.value)}
                inputMode="numeric"
                className="w-20 rounded border border-[var(--border)] bg-black/40 px-2 py-1 font-mono text-xs text-neutral-200"
              />
              <button
                onClick={() => selected && loadTail(selected)}
                className="rounded border border-[var(--border)] px-2 py-1 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800"
              >
                {loading ? "loading…" : "refresh"}
              </button>
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="filter loaded tail (substring)"
                className="min-w-[220px] flex-1 rounded border border-[var(--border)] bg-black/40 px-2 py-1 font-mono text-xs text-neutral-200"
              />
              {filter.trim() && lines ? (
                <span className="text-[11px] text-neutral-600">
                  {visibleLines?.length ?? 0} / {lines.length} lines match
                </span>
              ) : null}
            </div>

            {error ? <p className="text-red-400">{error}</p> : null}

            <pre className="max-h-[28rem] overflow-y-auto whitespace-pre-wrap rounded border border-[var(--border)] bg-black/40 p-3 font-mono text-[11px] text-neutral-400">
              {lines === null
                ? loading
                  ? "loading…"
                  : "(not loaded yet — click refresh)"
                : visibleLines && visibleLines.length > 0
                  ? visibleLines.join("\n")
                  : lines.length === 0
                    ? "(no captured output yet)"
                    : "(no lines match the filter)"}
            </pre>
          </>
        )}
      </div>
    </div>
  );
}
