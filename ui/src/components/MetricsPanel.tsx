"use client";

import { useState } from "react";
import type { MetricSample, MetricsCurrentResponse, MetricsHistoryResponse } from "@/lib/types";
import { ApiUnreachable, ApiError, NOT_AVAILABLE } from "@/components/ApiUnreachable";

type FetchState =
  | { state: "ready"; current: MetricsCurrentResponse; history: MetricsHistoryResponse }
  | { state: "unreachable"; error: string }
  | { state: "error"; status: number; error: string };

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

function pct(used: number | null, total: number | null): number | null {
  if (used === null || total === null || total <= 0) return null;
  return (used / total) * 100;
}

function fmtMb(mb: number | null): string {
  if (mb === null) return NOT_AVAILABLE;
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb} MB`;
}

// Real sparkline: plots the actual sampled values, one polyline point per
// real sample — no interpolation between samples that don't exist, no
// synthetic smoothing. A series with fewer than 2 real points renders no
// line at all (an honest "not enough data yet" rather than a flat guess).
function Sparkline({ values, color, height = 40 }: { values: (number | null)[]; color: string; height?: number }) {
  const width = 240;
  const real = values.map((v, i) => (v === null ? null : { i, v }));
  const points = real.filter((p): p is { i: number; v: number } => p !== null);

  if (points.length < 2) {
    return (
      <div
        className="flex items-center justify-center rounded border border-[var(--border)] bg-black/20 font-mono text-[10px] text-neutral-600"
        style={{ width, height }}
      >
        not enough samples yet
      </div>
    );
  }

  const maxV = Math.max(100, ...points.map((p) => p.v));
  const minV = 0;
  const n = values.length;
  const coords = points
    .map(({ i, v }) => {
      const x = n > 1 ? (i / (n - 1)) * width : width / 2;
      const y = height - ((v - minV) / (maxV - minV || 1)) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className="rounded border border-[var(--border)] bg-black/20">
      <polyline points={coords} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

function ReadoutCard({
  label,
  valueLabel,
  percent,
  sparkColor,
  sparkValues,
}: {
  label: string;
  valueLabel: string;
  percent: number | null;
  sparkColor: string;
  sparkValues: (number | null)[];
}) {
  return (
    <div className="rounded border border-[var(--border)] bg-black/20 p-3">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-xs uppercase tracking-widest text-neutral-500">{label}</span>
        <span className="font-mono text-sm text-neutral-200">
          {percent === null ? NOT_AVAILABLE : `${percent.toFixed(1)}%`}
        </span>
      </div>
      <div className="mt-1 font-mono text-[11px] text-neutral-500">{valueLabel}</div>
      <div className="mt-2">
        <Sparkline values={sparkValues} color={sparkColor} />
      </div>
    </div>
  );
}

async function fetchBoth(): Promise<FetchState> {
  const [curRes, histRes] = await Promise.all([
    fetch("/api/metrics/current", { cache: "no-store" }),
    fetch("/api/metrics/history?interval=60", { cache: "no-store" }),
  ]);

  if (curRes.status === 503 || histRes.status === 503) {
    const body = await (curRes.status === 503 ? curRes : histRes).json().catch(() => ({}));
    return { state: "unreachable", error: body?.error ?? "VANGUARD API not reachable" };
  }
  if (!curRes.ok) {
    const body = await curRes.json().catch(() => ({}));
    return { state: "error", status: curRes.status, error: body?.error ?? `HTTP ${curRes.status}` };
  }
  if (!histRes.ok) {
    const body = await histRes.json().catch(() => ({}));
    return { state: "error", status: histRes.status, error: body?.error ?? `HTTP ${histRes.status}` };
  }
  const current = (await curRes.json()) as MetricsCurrentResponse;
  const history = (await histRes.json()) as MetricsHistoryResponse;
  return { state: "ready", current, history };
}

export function MetricsPanel({ initial }: { initial: FetchState }) {
  const [fetchState, setFetchState] = useState<FetchState>(initial);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      setFetchState(await fetchBoth());
    } catch {
      setFetchState({ state: "unreachable", error: "VANGUARD API not reachable" });
    } finally {
      setLoading(false);
    }
  }

  if (fetchState.state === "unreachable") {
    return (
      <div className="space-y-4">
        <ApiUnreachable error={fetchState.error} />
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
        <ApiError status={fetchState.status} error={fetchState.error} />
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

  const { current, history } = fetchState;
  const sample = current.sample;
  const recent = history.samples.slice(-60);

  const cpuValues = recent.map((s) => s.cpu_percent);
  const ramValues = recent.map((s) => pct(s.ram_used_mb, s.ram_total_mb));
  const diskValues = recent.map((s) => pct(s.disk_used_mb, s.disk_total_mb));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-xs text-neutral-500">
          collector:{" "}
          <span className={current.collector_running ? "text-emerald-400" : "text-neutral-500"}>
            {current.collector_running ? "running" : "not running"}
          </span>{" "}
          · every {current.interval_seconds}s · {current.sample_count} sample(s) stored
          {sample ? (
            <>
              {" "}
              · last sample <span className="text-neutral-300">{secondsAgo(sample.sampled_at)}</span>
            </>
          ) : null}
        </span>
        <button
          onClick={refresh}
          disabled={loading}
          className="rounded border border-sky-800 bg-sky-950 px-3 py-1.5 font-mono text-[11px] text-sky-300 hover:bg-sky-900 disabled:opacity-50"
        >
          {loading ? "refreshing…" : "refresh"}
        </button>
      </div>

      {!sample ? (
        <div className="rounded border border-[var(--border)] bg-black/20 px-4 py-3 font-mono text-sm text-neutral-500">
          No samples collected yet. {current.collector_running
            ? "The collector is running — check back shortly."
            : "The collector background thread isn't running in this process (it starts under uvicorn/`vanguard serve`, not this dev preview by default)."}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-3">
          <ReadoutCard
            label="CPU"
            valueLabel={sample.cpu_percent === null ? "psutil not installed" : "of all logical cores"}
            percent={sample.cpu_percent}
            sparkColor="#38bdf8"
            sparkValues={cpuValues}
          />
          <ReadoutCard
            label="RAM"
            valueLabel={`${fmtMb(sample.ram_used_mb)} / ${fmtMb(sample.ram_total_mb)}`}
            percent={pct(sample.ram_used_mb, sample.ram_total_mb)}
            sparkColor="#34d399"
            sparkValues={ramValues}
          />
          <ReadoutCard
            label="Disk"
            valueLabel={`${fmtMb(sample.disk_used_mb)} / ${fmtMb(sample.disk_total_mb)} (${sample.disk_path})`}
            percent={pct(sample.disk_used_mb, sample.disk_total_mb)}
            sparkColor="#f59e0b"
            sparkValues={diskValues}
          />
        </div>
      )}

      <div className="rounded border border-[var(--border)] bg-black/10 px-3 py-2 font-mono text-[11px] text-neutral-600">
        GPU utilization/VRAM are not sampled here — there is no portable stdlib/psutil way to read them
        honestly on this machine (same limitation vanguard/nodeops/detect.py already documents for node
        registration). CPU/RAM/disk only.
      </div>

      <div>
        <div className="mb-2 font-mono text-xs uppercase tracking-widest text-neutral-500">
          Recent samples ({history.bucketed ? "60s buckets" : "raw"})
        </div>
        {recent.length === 0 ? (
          <div className="rounded border border-[var(--border)] bg-black/20 px-4 py-3 font-mono text-sm text-neutral-500">
            No historical samples in range yet.
          </div>
        ) : (
          <div className="max-h-80 overflow-y-auto rounded border border-[var(--border)]">
            <table className="w-full font-mono text-[11px]">
              <thead className="sticky top-0 bg-[var(--surface)] text-neutral-500">
                <tr>
                  <th className="px-3 py-1.5 text-left">Sampled At</th>
                  <th className="px-3 py-1.5 text-right">CPU %</th>
                  <th className="px-3 py-1.5 text-right">RAM</th>
                  <th className="px-3 py-1.5 text-right">Disk</th>
                </tr>
              </thead>
              <tbody>
                {[...recent].reverse().map((s: MetricSample) => (
                  <tr key={s.sampled_at} className="border-t border-[var(--border)] text-neutral-300">
                    <td className="px-3 py-1 text-left text-neutral-500">{s.sampled_at}</td>
                    <td className="px-3 py-1 text-right">
                      {s.cpu_percent === null ? NOT_AVAILABLE : s.cpu_percent.toFixed(1)}
                    </td>
                    <td className="px-3 py-1 text-right">{fmtMb(s.ram_used_mb)}</td>
                    <td className="px-3 py-1 text-right">{fmtMb(s.disk_used_mb)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
