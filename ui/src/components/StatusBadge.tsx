// Restrained status color-coding per the VANGUARD visual spec:
// green = healthy/connected/ready, amber = warning/stale, red = degraded/offline,
// gray = unknown/not-connected/not-applicable. No other hues are used for status.

type Tone = "green" | "amber" | "red" | "gray";

const TONE_CLASSES: Record<Tone, string> = {
  green: "bg-emerald-950 text-emerald-400 border-emerald-800",
  amber: "bg-amber-950 text-amber-400 border-amber-800",
  red: "bg-red-950 text-red-400 border-red-800",
  gray: "bg-neutral-800 text-neutral-400 border-neutral-700",
};

const STATUS_TONE: Record<string, Tone> = {
  // node status
  ONLINE: "green",
  STALE: "amber",
  OFFLINE: "red",
  // readiness
  READY: "green",
  READY_WITH_WARNING: "amber",
  DEGRADED: "red",
  NOT_READY: "red",
  // mesh / integrations
  CONNECTED: "green",
  DISCONNECTED: "red",
  NOT_CONNECTED: "gray",
  // shared fallback
  UNKNOWN: "gray",
  OK: "green",
  // jobs
  QUEUED: "gray",
  RUNNING: "amber",
  COMPLETED: "green",
  FAILED: "red",
  CANCELED: "gray",
  RETRYING: "amber",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONE[status] ?? "gray";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-xs uppercase tracking-wide ${TONE_CLASSES[tone]}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          tone === "green"
            ? "bg-emerald-400"
            : tone === "amber"
              ? "bg-amber-400"
              : tone === "red"
                ? "bg-red-400"
                : "bg-neutral-500"
        }`}
      />
      {status}
    </span>
  );
}
