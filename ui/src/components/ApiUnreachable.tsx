import { VANGUARD_API_BASE } from "@/lib/api";

export function ApiUnreachable({ error }: { error: string }) {
  return (
    <div className="rounded border border-red-900 bg-red-950/40 px-4 py-3 font-mono text-sm text-red-400">
      <div className="font-semibold">API UNREACHABLE</div>
      <div className="mt-1 text-red-300">{error}</div>
      <div className="mt-2 text-xs text-neutral-500">
        Expected base: <span className="text-neutral-400">{VANGUARD_API_BASE}</span> — start it with{" "}
        <code className="text-neutral-400">.\.venv\Scripts\python.exe -m vanguard serve</code> from the
        VANGUARD project root.
      </div>
    </div>
  );
}

export function ApiError({ status, error }: { status: number; error: string }) {
  return (
    <div className="rounded border border-amber-900 bg-amber-950/40 px-4 py-3 font-mono text-sm text-amber-400">
      <div className="font-semibold">API ERROR ({status})</div>
      <div className="mt-1 text-amber-300">{error}</div>
    </div>
  );
}

export const NOT_AVAILABLE = "—";
