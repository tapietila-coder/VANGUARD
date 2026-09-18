// Thin fetch wrapper against the local VANGUARD FastAPI service.
// No fake data: every failure surfaces as an explicit, typed error state
// instead of a crash or a silently-empty UI.

export const VANGUARD_API_BASE =
  process.env.VANGUARD_API_BASE ?? process.env.NEXT_PUBLIC_VANGUARD_API_BASE ?? "http://127.0.0.1:8788";

export const API_PREFIX = "/api/v1/vanguard";

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; unreachable: true; error: string }
  | { ok: false; unreachable: false; status: number; error: string };

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<ApiResult<T>> {
  const url = new URL(`${API_PREFIX}${path}`, VANGUARD_API_BASE);
  if (params) {
    for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  }

  let res: Response;
  try {
    res = await fetch(url.toString(), { cache: "no-store" });
  } catch {
    return {
      ok: false,
      unreachable: true,
      error: `VANGUARD API not reachable at ${VANGUARD_API_BASE} — is the backend running?`,
    };
  }

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body);
    } catch {
      detail = res.statusText;
    }
    return { ok: false, unreachable: false, status: res.status, error: detail || `HTTP ${res.status}` };
  }

  const data = (await res.json()) as T;
  return { ok: true, data };
}
