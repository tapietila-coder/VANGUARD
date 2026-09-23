"use client";

import { useState } from "react";
import type { Incident } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { KeyValueRow } from "@/components/Panel";
import { NOT_AVAILABLE } from "@/components/ApiUnreachable";

const EVENT_LABELS: Record<string, string> = {
  detected: "Detected",
  recurred: "Recurred",
  condition_changed: "Condition changed",
  acknowledged: "Acknowledged",
  auto_resolved: "Auto-resolved",
  resolved: "Resolved",
};

export function IncidentDetailPanel({ initial }: { initial: Incident }) {
  const [incident, setIncident] = useState(initial);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<"acknowledge" | "resolve" | null>(null);

  async function runAction(kind: "acknowledge" | "resolve") {
    setPending(true);
    setError(null);
    try {
      const res = await fetch(`/api/incidents/${encodeURIComponent(incident.incident_id)}/${kind}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: `operator ${kind} via /incidents UI` }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(body?.error ?? `${kind} failed: HTTP ${res.status}`);
        return;
      }
      setIncident(body as Incident);
    } catch {
      setError(`${kind} failed: VANGUARD API not reachable`);
    } finally {
      setPending(false);
      setConfirming(null);
    }
  }

  return (
    <div className="space-y-4 text-xs">
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={incident.severity} />
        <StatusBadge status={incident.status} />
        <span className="font-mono text-neutral-500">{incident.correlation_key}</span>
      </div>

      <div>
        <KeyValueRow label="Title" value={incident.title} />
        <KeyValueRow label="Source" value={incident.source} />
        <KeyValueRow label="First seen" value={incident.first_seen} />
        <KeyValueRow label="Last seen" value={incident.last_seen} />
        <KeyValueRow label="Occurrences" value={incident.occurrence_count} />
        <KeyValueRow label="Acknowledged by" value={incident.acknowledged_by ?? NOT_AVAILABLE} />
        <KeyValueRow label="Acknowledged at" value={incident.acknowledged_at ?? NOT_AVAILABLE} />
        <KeyValueRow label="Resolved at" value={incident.resolved_at ?? NOT_AVAILABLE} />
      </div>

      {error ? <p className="text-red-400">{error}</p> : null}

      {incident.status !== "RESOLVED" ? (
        confirming ? (
          <div className="flex flex-col items-start gap-1">
            <span className="text-amber-400">
              {confirming === "acknowledge" ? "acknowledge this incident?" : "mark this incident resolved?"}
            </span>
            <span className="flex gap-1">
              <button
                onClick={() => runAction(confirming)}
                disabled={pending}
                className="rounded border border-amber-800 bg-amber-950 px-3 py-1.5 font-mono text-[11px] text-amber-400"
              >
                {pending ? "working…" : "confirm"}
              </button>
              <button
                onClick={() => setConfirming(null)}
                className="rounded border border-[var(--border)] px-3 py-1.5 font-mono text-[11px] text-neutral-400"
              >
                cancel
              </button>
            </span>
          </div>
        ) : (
          <div className="flex gap-2">
            {incident.status === "OPEN" ? (
              <button
                onClick={() => setConfirming("acknowledge")}
                disabled={pending}
                className="rounded border border-amber-800 bg-amber-950 px-3 py-1.5 font-mono text-[11px] text-amber-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
              >
                acknowledge
              </button>
            ) : null}
            <button
              onClick={() => setConfirming("resolve")}
              disabled={pending}
              className="rounded border border-emerald-800 bg-emerald-950 px-3 py-1.5 font-mono text-[11px] text-emerald-400 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:bg-transparent disabled:text-neutral-600"
            >
              resolve
            </button>
          </div>
        )
      ) : null}

      <div>
        <h3 className="mb-2 font-mono text-xs font-semibold uppercase tracking-widest text-neutral-400">
          Timeline
        </h3>
        <ol className="space-y-2 border-l border-[var(--border)] pl-4">
          {incident.timeline.map((event, idx) => (
            <li key={idx} className="relative">
              <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-neutral-600" />
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-mono text-neutral-200">{EVENT_LABELS[event.kind] ?? event.kind}</span>
                <span className="text-[11px] text-neutral-600">{event.created_at}</span>
                {event.actor ? <span className="text-[11px] text-neutral-500">by {event.actor}</span> : null}
              </div>
              {event.detail ? <div className="mt-0.5 text-neutral-400">{event.detail}</div> : null}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
