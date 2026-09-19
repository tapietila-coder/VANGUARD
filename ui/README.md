# VANGUARD UI

A minimal Next.js (App Router, TypeScript, Tailwind) console for the VANGUARD
API — no design system was imported from anywhere else in the D27HQ tree
(specifically not from `overseer/`, whose Cesium-based UI is a different kind
of app). Dark, dense, monospace-for-technical-values, no fabricated data: if a
value doesn't come back from a real API call it's rendered as `—`, never a
plausible-looking placeholder.

## Run it

This UI is a pure client of the VANGUARD backend — it has no database of its
own and does not run without the API.

```powershell
# Terminal 1 — from the VANGUARD project root, start the real backend:
cd VANGUARD
.\.venv\Scripts\python.exe -m vanguard serve
# API now at http://127.0.0.1:8788

# Terminal 2 — from VANGUARD/ui:
npm install
npm run dev
# UI now at http://localhost:3000 (or whatever port `next dev` picks)
```

If the backend isn't running, every page shows an explicit
"VANGUARD API not reachable at `<url>` — is the backend running?" panel
instead of crashing or spinning forever.

## Configuration

Copy `.env.local.example` to `.env.local` if you need to point at a
non-default API address:

```
VANGUARD_API_BASE=http://127.0.0.1:8788
```

## Pages

- `/` — Overview: mesh status, node online/offline counts, services summary,
  readiness summary, and every integration's real status (Steward/Watchtower/
  Marshal/Dispatch), including `NOT_CONNECTED` — never hidden behind a green
  light.
- `/nodes` — table of all registered nodes; click through to `/nodes/[id]`
  for full inventory + a readiness evaluation against any of the three
  built-in profiles (`GENERAL_WORKER`, `D27_CONTROL_HOST`, `CLASSIFIED_GPU`).
- `/mesh` — mesh provider status, peers, routes, policies. With the default
  `NullMeshProvider` this legitimately renders as empty/`NOT_CONNECTED` — that
  is the honest state, not a bug.
- `/services` — registered services table, a resolve-by-name form
  (`GET /services/{id}`, which resolves by `service_id` first and falls back
  to an exact name match), and a **Service Control** panel for the one real
  managed process this build supports (`dispatch`): live state/PID/uptime/
  health with a "checked Ns ago" freshness indicator, Start/Stop/Restart
  buttons (Stop/Restart ask for confirmation first — these are real actions on
  a real local process), and an expandable, manually-refreshed log tail.
- `/readiness` — the built-in readiness profiles and the most recent
  evaluation results recorded by the backend.

## What this UI does NOT do

- No login/token UI. Almost every page here only calls **read-only** VANGUARD
  routes, which the backend deliberately leaves unauthenticated for local dev
  (see `../docs/SECURITY.md`).
- No cloud deployment. This is a local `next dev` app only.
- The **only** write actions anywhere in the current page set are Service
  Control's Start/Stop/Restart on `/services` — everything else is a read of
  real backend state. Those three actions go through
  `src/app/api/services/[id]/process/[action]/route.ts`, a server-side proxy
  that holds `VANGUARD_API_TOKEN` (read from `.env.local`, never sent to the
  browser) — the same CORS-workaround pattern the resolve-by-name proxy
  established, extended to also carry the bearer token.

## Architecture notes

- `src/lib/api.ts` — the one `fetch` wrapper used by every server component;
  it distinguishes "API unreachable" (network/connection failure) from
  "API returned an error" (4xx/5xx with a body), and both render distinct,
  honest UI states.
- `src/lib/types.ts` — hand-written TypeScript mirrors of the Pydantic models
  in `../vanguard/core/models.py`. Keep these in sync if the backend contracts
  change.
- `src/app/api/services/[id]/route.ts` — a small server-side proxy used only
  by the client-side "resolve by name" form. It exists because the FastAPI
  backend has no CORS middleware, so a browser can't call it directly from a
  different origin/port; the proxy runs on the Next.js server and forwards to
  the real API.
- All five pages are server components using `export const dynamic =
  "force-dynamic"` so they always show live backend state, never a stale
  build-time snapshot.
