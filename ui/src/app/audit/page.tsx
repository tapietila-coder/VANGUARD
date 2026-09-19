import Link from "next/link";
import { apiGet } from "@/lib/api";
import { ApiUnreachable, ApiError, NOT_AVAILABLE } from "@/components/ApiUnreachable";
import { Panel } from "@/components/Panel";
import type { AuditLogResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 25;

function str(v: string | string[] | undefined): string {
  return Array.isArray(v) ? (v[0] ?? "") : (v ?? "");
}

export default async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const actor = str(sp.actor).trim();
  const action = str(sp.action).trim();
  const target = str(sp.target).trim();
  const since = str(sp.since).trim();
  const until = str(sp.until).trim();
  const offset = Math.max(0, Number(str(sp.offset)) || 0);

  const params: Record<string, string> = { limit: String(PAGE_SIZE), offset: String(offset) };
  if (actor) params.actor = actor;
  if (action) params.action = action;
  if (target) params.target = target;
  if (since) params.since = since;
  if (until) params.until = until;

  // GET /audit requires the operator bearer token on the backend (verified
  // against vanguard/api/app.py — unlike most read routes, audit is not
  // open), so this server component calls it directly with auth:true rather
  // than going through the unauthenticated apiGet path.
  const result = await apiGet<AuditLogResponse>("/audit", params, { auth: true });

  const qs = (overrides: Record<string, string>) => {
    const merged = new URLSearchParams({ actor, action, target, since, until, offset: String(offset), ...overrides });
    for (const [k, v] of [...merged.entries()]) if (!v) merged.delete(k);
    const s = merged.toString();
    return s ? `?${s}` : "";
  };

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-lg text-neutral-200">AUDIT LOG</h1>

      <Panel title="Filters" subtitle="GET /api/v1/vanguard/audit">
        <form method="get" className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3 lg:grid-cols-5">
          <div>
            <label className="mb-1 block text-neutral-500">actor</label>
            <input
              name="actor"
              defaultValue={actor}
              placeholder="operator"
              className="w-full rounded border border-[var(--border)] bg-black/40 px-2 py-1.5 font-mono text-neutral-200"
            />
          </div>
          <div>
            <label className="mb-1 block text-neutral-500">action</label>
            <input
              name="action"
              defaultValue={action}
              placeholder="process.start"
              className="w-full rounded border border-[var(--border)] bg-black/40 px-2 py-1.5 font-mono text-neutral-200"
            />
          </div>
          <div>
            <label className="mb-1 block text-neutral-500">target</label>
            <input
              name="target"
              defaultValue={target}
              placeholder="dispatch"
              className="w-full rounded border border-[var(--border)] bg-black/40 px-2 py-1.5 font-mono text-neutral-200"
            />
          </div>
          <div>
            <label className="mb-1 block text-neutral-500">since (ISO-8601)</label>
            <input
              name="since"
              defaultValue={since}
              placeholder="2026-09-01T00:00:00Z"
              className="w-full rounded border border-[var(--border)] bg-black/40 px-2 py-1.5 font-mono text-neutral-200"
            />
          </div>
          <div>
            <label className="mb-1 block text-neutral-500">until (ISO-8601)</label>
            <input
              name="until"
              defaultValue={until}
              placeholder="2026-09-30T00:00:00Z"
              className="w-full rounded border border-[var(--border)] bg-black/40 px-2 py-1.5 font-mono text-neutral-200"
            />
          </div>
          <div className="col-span-2 flex items-end gap-2 sm:col-span-3 lg:col-span-5">
            <button
              type="submit"
              className="rounded border border-sky-800 bg-sky-950 px-3 py-1.5 font-mono text-[11px] text-sky-300"
            >
              apply filters
            </button>
            <Link
              href="/audit"
              className="rounded border border-[var(--border)] px-3 py-1.5 font-mono text-[11px] text-neutral-400 hover:bg-neutral-800"
            >
              clear
            </Link>
          </div>
        </form>
      </Panel>

      <Panel
        title="Entries"
        subtitle="append-only — real actor/action/target/before/after/reason per mutating call"
      >
        {!result.ok ? (
          result.unreachable ? (
            <ApiUnreachable error={result.error} />
          ) : (
            <ApiError status={result.status} error={result.error} />
          )
        ) : result.data.entries.length === 0 ? (
          <p className="text-xs text-neutral-500">
            No audit entries yet{actor || action || target || since || until ? " matching these filters" : ""}.
          </p>
        ) : (
          <>
            <div className="space-y-3">
              {result.data.entries.map((e) => (
                <div
                  key={e.entry_id ?? `${e.action}-${e.created_at}`}
                  className="rounded border border-[var(--border)] bg-black/20 p-3 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded border border-sky-800 bg-sky-950 px-2 py-0.5 font-mono text-[11px] text-sky-300">
                        {e.action}
                      </span>
                      <span className="text-neutral-500">
                        actor: <span className="font-mono text-neutral-300">{e.actor}</span>
                      </span>
                      <span className="text-neutral-500">
                        target: <span className="font-mono text-neutral-300">{e.target || NOT_AVAILABLE}</span>
                      </span>
                      <span className="text-neutral-500">
                        source: <span className="font-mono text-neutral-400">{e.source || NOT_AVAILABLE}</span>
                      </span>
                    </div>
                    <span className="font-mono text-[11px] text-neutral-500">{e.created_at}</span>
                  </div>

                  {e.reason ? <p className="mt-2 text-neutral-400">reason: {e.reason}</p> : null}

                  {e.before || e.after ? (
                    <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {e.before ? (
                        <div>
                          <div className="mb-1 text-neutral-500">before</div>
                          <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded border border-[var(--border)] bg-black/40 p-2 font-mono text-[11px] text-neutral-400">
                            {JSON.stringify(e.before, null, 2)}
                          </pre>
                        </div>
                      ) : null}
                      {e.after ? (
                        <div>
                          <div className="mb-1 text-neutral-500">after</div>
                          <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded border border-emerald-900 bg-emerald-950/20 p-2 font-mono text-[11px] text-emerald-300">
                            {JSON.stringify(e.after, null, 2)}
                          </pre>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>

            <div className="mt-4 flex items-center justify-between border-t border-[var(--border)] pt-3 text-xs text-neutral-500">
              <span>
                showing {offset + 1}–{offset + result.data.entries.length} of {result.data.total}
              </span>
              <div className="flex gap-2">
                <Link
                  href={offset > 0 ? `/audit${qs({ offset: String(Math.max(0, offset - PAGE_SIZE)) })}` : "#"}
                  aria-disabled={offset === 0}
                  className={`rounded border border-[var(--border)] px-2 py-1 font-mono text-[11px] ${
                    offset === 0
                      ? "cursor-not-allowed text-neutral-700"
                      : "text-neutral-400 hover:bg-neutral-800"
                  }`}
                >
                  ← newer
                </Link>
                <Link
                  href={
                    offset + PAGE_SIZE < result.data.total
                      ? `/audit${qs({ offset: String(offset + PAGE_SIZE) })}`
                      : "#"
                  }
                  aria-disabled={offset + PAGE_SIZE >= result.data.total}
                  className={`rounded border border-[var(--border)] px-2 py-1 font-mono text-[11px] ${
                    offset + PAGE_SIZE >= result.data.total
                      ? "cursor-not-allowed text-neutral-700"
                      : "text-neutral-400 hover:bg-neutral-800"
                  }`}
                >
                  older →
                </Link>
              </div>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
