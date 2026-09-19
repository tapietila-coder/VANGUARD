"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Job } from "@/lib/types";

// Only the three real, documented job types are offered here (see
// vanguard/jobs/job_types.py) — "queue_selftest" also exists in the real
// registry but is a queue diagnostic used by the test suite, not a real
// operator capability, so it's deliberately left out of this form.
const JOB_TYPES = [
  { value: "readiness_sweep", label: "readiness_sweep — re-evaluate every node against every profile" },
  { value: "service_health_check", label: "service_health_check — check one service's real health" },
  { value: "audit_log_export", label: "audit_log_export — snapshot the audit log to a JSON file" },
] as const;

export function JobSubmitForm() {
  const router = useRouter();
  const [jobType, setJobType] = useState<string>(JOB_TYPES[0].value);
  const [serviceId, setServiceId] = useState("");
  const [limit, setLimit] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const params: Record<string, unknown> = {};
    if (jobType === "service_health_check") {
      if (!serviceId.trim()) {
        setError("service_id is required for service_health_check");
        setSubmitting(false);
        return;
      }
      params.service_id = serviceId.trim();
    }
    if (jobType === "audit_log_export" && limit.trim()) {
      params.limit = Number(limit.trim());
    }

    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_type: jobType, params }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(body?.error ?? `submit failed: HTTP ${res.status}`);
        setSubmitting(false);
        return;
      }
      const job = body as Job;
      router.push(`/jobs/${job.job_id}`);
      router.refresh();
    } catch {
      setError("submit failed: VANGUARD API not reachable");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 text-xs">
      <div>
        <label className="mb-1 block text-neutral-500">job_type</label>
        <select
          value={jobType}
          onChange={(e) => setJobType(e.target.value)}
          className="w-full rounded border border-[var(--border)] bg-black/40 px-2 py-1.5 font-mono text-neutral-200"
        >
          {JOB_TYPES.map((jt) => (
            <option key={jt.value} value={jt.value}>
              {jt.label}
            </option>
          ))}
        </select>
      </div>

      {jobType === "service_health_check" ? (
        <div>
          <label className="mb-1 block text-neutral-500">service_id</label>
          <input
            value={serviceId}
            onChange={(e) => setServiceId(e.target.value)}
            placeholder="e.g. dispatch"
            className="w-full rounded border border-[var(--border)] bg-black/40 px-2 py-1.5 font-mono text-neutral-200"
          />
        </div>
      ) : null}

      {jobType === "audit_log_export" ? (
        <div>
          <label className="mb-1 block text-neutral-500">limit (optional, default 1000)</label>
          <input
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            placeholder="1000"
            inputMode="numeric"
            className="w-full rounded border border-[var(--border)] bg-black/40 px-2 py-1.5 font-mono text-neutral-200"
          />
        </div>
      ) : null}

      <button
        type="submit"
        disabled={submitting}
        className="rounded border border-sky-800 bg-sky-950 px-3 py-1.5 font-mono text-[11px] text-sky-300 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "submitting…" : "submit job"}
      </button>

      {error ? <p className="text-red-400">{error}</p> : null}
    </form>
  );
}
