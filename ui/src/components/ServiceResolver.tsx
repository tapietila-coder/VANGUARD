"use client";

import { useState } from "react";
import type { VanguardService } from "@/lib/types";

type ResolveResult =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "found"; service: VanguardService }
  | { state: "not_found" }
  | { state: "unreachable"; error: string }
  | { state: "error"; error: string };

export function ServiceResolver() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<ResolveResult>({ state: "idle" });

  async function resolve(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setResult({ state: "loading" });
    try {
      const res = await fetch(`/api/services/${encodeURIComponent(query.trim())}`);
      if (res.status === 404) {
        setResult({ state: "not_found" });
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setResult({ state: "error", error: body?.error ?? `HTTP ${res.status}` });
        return;
      }
      const service = (await res.json()) as VanguardService;
      setResult({ state: "found", service });
    } catch {
      setResult({ state: "unreachable", error: "VANGUARD API not reachable — is the backend running?" });
    }
  }

  return (
    <div>
      <form onSubmit={resolve} className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="service_id or exact name"
          className="flex-1 rounded border border-[var(--border)] bg-black/30 px-2 py-1.5 font-mono text-xs text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:ring-1 focus:ring-sky-700"
        />
        <button
          type="submit"
          className="rounded border border-[var(--border)] px-3 py-1.5 font-mono text-xs text-neutral-300 hover:bg-neutral-800"
        >
          resolve
        </button>
      </form>

      <div className="mt-3">
        {result.state === "loading" && <p className="text-xs text-neutral-500">resolving…</p>}
        {result.state === "not_found" && (
          <p className="text-xs text-neutral-500">No service matched service_id or name &quot;{query}&quot;.</p>
        )}
        {result.state === "unreachable" && <p className="text-xs text-red-400">{result.error}</p>}
        {result.state === "error" && <p className="text-xs text-amber-400">{result.error}</p>}
        {result.state === "found" && (
          <div className="rounded border border-[var(--border)] p-3 text-xs">
            <div className="font-mono text-neutral-200">{result.service.service_id}</div>
            <div className="mt-1 grid grid-cols-2 gap-1 text-neutral-400">
              <span>name: {result.service.name}</span>
              <span>kind: {result.service.kind}</span>
              <span>node: {result.service.node_id ?? "—"}</span>
              <span>base_url: {result.service.base_url ?? "—"}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
