# VANGUARD — D27HQ Infrastructure & Operational Readiness Directorate

[![tests](https://github.com/tapietila-coder/VANGUARD/actions/workflows/tests.yml/badge.svg)](https://github.com/tapietila-coder/VANGUARD/actions/workflows/tests.yml)

**Status:** local reference build, September 17, 2026. Not deployed anywhere. Not production-certified.

VANGUARD tracks what infrastructure D27HQ actually has (nodes, services), how
ready each node is for a given kind of work, and — once a real mesh exists — how
they're networked together. It is built to the same honesty standard as its
neighbor `Dispatch/D27HQ_DISPATCH`: real code for what's real, and an explicit,
non-fabricated `NOT_CONNECTED`/`UNKNOWN` status for everything that isn't.

See `VANGUARD_DISCOVERY.md` for the Mission-0 discovery pass this build is based on.

## What is actually implemented

- Installable FastAPI service (`vanguard/api/app.py`) with the routes listed below.
- SQLite-backed node inventory (`vanguard/nodeops/`) with a real capability model
  (`GPU_INFERENCE`, `CUDA`, `WINDOWS_BUILD`, `LINUX_BUILD`, `DOCKER`, etc.) and
  local-machine-only hardware/OS detection via stdlib + optional `psutil`.
- Deterministic readiness engine (`vanguard/readiness/`) with three built-in
  profiles (`D27_CONTROL_HOST`, `CLASSIFIED_GPU`, `GENERAL_WORKER`), evidence
  storage, and states `READY`/`READY_WITH_WARNING`/`DEGRADED`/`NOT_READY`/`UNKNOWN`.
- SQLite-backed service registry with a `resolveService(name)` resolver
  (`vanguard/service_map/`) — no hardcoded fake services.
- A `MeshProvider` abstract interface shaped after NetBird's real REST API
  (`vanguard/mesh/provider.py`), with a `NullMeshProvider` (the honest default —
  reports `NOT_CONNECTED`, never fake peers) and a `NetBirdMeshProvider` contract
  implementation that has never been run against a live server.
- A minimal Next.js UI (`ui/`) — Overview, Nodes (+ per-node detail with
  readiness evaluation), Mesh, Services (+ resolve-by-name), Readiness, Jobs
  (+ submit/cancel/retry), Audit (filterable, paginated, real
  before/after/reason per entry), and Logs (cross-service list of every
  service with a real captured log file, pick one to tail + client-side
  substring filter) pages, all reading real data from the routes below with
  an honest "API unreachable" state and no fabricated values. No login UI
  (read-only routes need none locally), no cloud deployment — see
  `ui/README.md` for how to run it and what's still missing.
- Stub adapters for Steward/Watchtower/Marshal that always report
  `NOT_CONNECTED` (`vanguard/integrations/adapters.py`), because none of those
  systems exist anywhere in this environment (verified by repo search — see
  discovery doc). A `DispatchAdapter` that makes a real, read-only
  `GET http://127.0.0.1:8787/health` call against the actual local Dispatch
  service when it's running, and degrades gracefully to `NOT_CONNECTED` when it
  isn't.
- Append-only audit log (`vanguard/audit/`) recording actor/action/target/
  before/after/reason for every mutating API call, with real filtering
  (`actor`, `action`, `target`, `since`, `until`) and pagination
  (`limit`/`offset`) on both the query layer and `GET /audit`, plus a
  dedicated `/audit` UI page (reverse-chronological, filter form, real
  before/after diffs, honest "No audit entries yet" empty state).
- **Service Control** (`vanguard/process_control/`): real start/stop/restart of
  one actual local OS process — the local D27HQ Dispatch API
  (`Dispatch/D27HQ_DISPATCH`) — via `subprocess.Popen` (never a shell string,
  never a `taskkill` shell-out), with a real PID, a rotating per-service log
  file under `data/logs/`, and a real health check (HTTP GET when a
  `health_url` is configured, PID liveness otherwise). This is one
  controllable local process, not a general process-management platform —
  see "What is NOT implemented" below.
- **Job Queue** (`vanguard/jobs/`): a real local, in-process job system — a
  small `ThreadPoolExecutor` (default 2 workers, `VANGUARD_JOB_WORKERS`)
  actually runs submitted jobs on worker threads, with durable SQLite job
  records (state, progress, result, error, retry count), real cooperative
  cancel, and real retry of failed jobs. Three real job types are registered,
  each calling functionality that already exists elsewhere in this codebase —
  no job type fakes its result: `readiness_sweep` (re-runs the readiness
  engine for every node against every built-in profile), `service_health_check`
  (real process-control status or an HTTP probe for one service), and
  `audit_log_export` (writes a real JSON snapshot of the audit log to
  `data/exports/`). A fourth, `queue_selftest`, is a small diagnostic-only job
  type used by the test suite to exercise cancel/retry deterministically — not
  a claimed operator capability. This is a local in-process job queue, not a
  general workflow engine — see "What is NOT implemented" below.
- **Logs (centralized)**: a new `GET /api/v1/vanguard/logs` route lists every
  service registered with Service Control and its real `data/logs/*.log`
  state (whether the file exists yet, its size, last-modified time, and a
  real line count) — no fabricated services, honestly empty when nothing is
  registered. The new `/logs` UI page renders this list, lets an operator
  pick any service and tail its real captured output (reusing the existing
  per-service `GET /services/{id}/logs?lines=N` route), and applies a
  client-side substring filter to the currently-loaded tail. Still not a
  general log-aggregation system — one machine's local files, no
  correlation IDs, no server-side search.
- **System Health (aggregate)**: a new `GET /api/v1/vanguard/system-health`
  route (`vanguard/system_health/aggregator.py`) runs eight real, fresh checks
  on every call — API (trivially true if the request executed), Database (a
  real `SELECT 1` + write probe against the live SQLite file), Job Queue
  (real configured/alive worker counts and real queued/running job counts),
  Service Control (the real managed-process state, reusing
  `ProcessController.status()` — never a duplicate check), Mesh (the real
  `MeshProvider.health()`), Integrations (the real Steward/Watchtower/
  Marshal/Dispatch adapter statuses), Readiness (a summary of the latest real
  readiness evaluations), and Audit Log (a real `COUNT(*)` reachability
  check) — assembled server-side into one atomic, honestly-timestamped
  snapshot rather than six-plus separate client calls that could race each
  other. Every row carries its own real `checked_at` and reuses whichever
  status vocabulary that subsystem already has elsewhere in this API
  (ProcessState, MeshConnectionStatus, IntegrationStatus, ReadinessState, or
  `OK`/`DEGRADED`/`FAILED` for the generic checks) — no new taxonomy, so the
  existing UI color-coding applies unchanged. The new `/system-health` UI
  page (added to the top nav) renders one dense row per subsystem with a
  manual refresh control, and follows this project's honest "whole page says
  API unreachable" pattern exactly if the backend can't be reached.
- 58 pytest tests, all passing locally (see "Test results" below).

## What is NOT implemented / not claimed

- **Service Control only manages one process (Dispatch).** It is not a
  general process-management platform — no fleet of agents, no browser fleet,
  no ingest pipelines, no deployments/incidents/alerts/secrets/backups/mesh-wide
  RBAC. Those were explicitly descoped from this pass; see the original
  15-subsystem spec this build deliberately did not attempt.
- **The Job Queue is a local in-process ThreadPoolExecutor, not a distributed
  queue.** No Redis/external broker, no multi-node workers, no scheduled/
  recurring jobs, no priorities/queues-of-queues, no persistence across a
  process crash mid-job (a `RUNNING` job whose process dies stays `RUNNING`
  in the DB until an operator notices — no crash-recovery sweep exists yet).
  Only three real job types are registered; adding a new one always means
  wiring it to real existing VANGUARD logic, never a placeholder.
- **No D27HQ nav integration** for the new `ui/` dashboard, and no
  VANGUARD/RANGER preservation work bundled with it.
- **No real NetBird deployment.** No mesh is installed anywhere; `NullMeshProvider`
  is what actually runs by default. `NetBirdMeshProvider` is a written contract,
  untested against a live server.
- **No Steward, Marshal, or Watchtower integration** — those systems don't exist
  yet anywhere in this codebase or environment.
- **No cloud infrastructure, DNS, or production server access.** Nothing in this
  project touches the Hetzner VPS (204.168.151.83) or any `d27hq.dev` DNS/deploy
  config; that's explicitly out of scope pending separate future authorization.
- **No remote/Windows/GPU node enrollment.** Node detection only ever inspects
  the local machine it runs on.
- Single-node SQLite storage — same reference-implementation posture as Dispatch,
  not a distributed/multi-node system.

## Run it locally (PowerShell)

```powershell
cd VANGUARD
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,detect]"
Copy-Item .env.example .env
# dev mode boots with a built-in insecure fallback token; set a real
# VANGUARD_API_TOKEN in .env before using anything beyond localhost.
.\.venv\Scripts\python.exe -m vanguard serve
```

The API is then at `http://127.0.0.1:8788`. FastAPI's interactive docs are at
`/docs`.

## Run the tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### Test results (this build)

```
58 passed, 2 warnings in 32.43s
```

The 2 warnings are upstream FastAPI/Starlette deprecation notices unrelated to
this project's code (`httpx` TestClient deprecation, `anyio` alias deprecation).

## API surface

Read-only, no auth required (documented dev-only posture — see `docs/SECURITY.md`):

```
GET /api/v1/vanguard/health
GET /api/v1/vanguard/nodes
GET /api/v1/vanguard/nodes/{id}
GET /api/v1/vanguard/nodes/{id}/readiness?profile=GENERAL_WORKER
GET /api/v1/vanguard/services
GET /api/v1/vanguard/services/{id}
GET /api/v1/vanguard/mesh/status
GET /api/v1/vanguard/mesh/peers
GET /api/v1/vanguard/mesh/routes
GET /api/v1/vanguard/mesh/policies
GET /api/v1/vanguard/readiness
GET /api/v1/vanguard/integrations
GET /api/v1/vanguard/services/{id}/process
GET /api/v1/vanguard/services/{id}/logs?lines=100
GET /api/v1/vanguard/jobs?state=&job_type=
GET /api/v1/vanguard/jobs/{id}
GET /api/v1/vanguard/logs
GET /api/v1/vanguard/system-health
```

Mutating, require `Authorization: Bearer <VANGUARD_API_TOKEN>`:

```
POST   /api/v1/vanguard/nodes
POST   /api/v1/vanguard/services
POST   /api/v1/vanguard/mesh/enrollments
DELETE /api/v1/vanguard/mesh/enrollments/{id}
POST   /api/v1/vanguard/nodes/{id}/revoke
GET    /api/v1/vanguard/audit?limit=&offset=&actor=&action=&target=&since=&until=
POST   /api/v1/vanguard/services/{id}/start
POST   /api/v1/vanguard/services/{id}/stop
POST   /api/v1/vanguard/services/{id}/restart
POST   /api/v1/vanguard/jobs
POST   /api/v1/vanguard/jobs/{id}/cancel
POST   /api/v1/vanguard/jobs/{id}/retry
```

Service Control is only registered for `service_id=dispatch` in this build.
`VANGUARD_DISPATCH_DIR`/`VANGUARD_DISPATCH_PYTHON` (see `.env.example`) control
where it's launched from; both default to the real on-disk sibling layout
(`NCTIAPP/Dispatch/D27HQ_DISPATCH`).

The Job Queue's real registered `job_type` values are `readiness_sweep`,
`service_health_check` (params: `{"service_id": "..."}`), `audit_log_export`
(params: optional `{"limit": 1000}`), and the test-only diagnostic
`queue_selftest`. `POST /jobs` rejects any other `job_type` with `400`.
`VANGUARD_JOB_WORKERS`/`VANGUARD_JOB_EXPORT_DIR` (see `.env.example`) control
worker-pool size and where `audit_log_export` writes its snapshots.

`GET /jobs` returns a bare list of jobs. `GET /audit` returns
`{"entries": [...], "total": <int>, "limit": <int>, "offset": <int>}` — a
different shape from the other list routes, chosen so the `/audit` UI page
can paginate against a real total instead of guessing whether more entries
exist. All five filter params (`actor`/`action`/`target`/`since`/`until`)
are exact-match against real stored columns (`since`/`until` compare
lexically against the ISO-8601 `created_at` timestamp) — there is no fuzzy
or full-text search.

## Source tree

`vanguard/` = the installable package (`core`, `nodeops`, `readiness`,
`service_map`, `process_control`, `jobs`, `mesh`, `integrations`, `audit`,
`system_health`, `api`). `tests/` = pytest suite. `docs/` = architecture,
mesh, readiness, and security notes. `VANGUARD_DISCOVERY.md` = the Mission-0
ground-truth audit this build is based on.

## Follow-up (explicitly out of scope for this pass)

1. Real NetBird deployment (pinned to `v0.78.2`, never `latest` — see
   `docs/MESH.md`) once the user authorizes touching real infrastructure.
2. Real Steward/Marshal/Watchtower integrations once those systems exist.
3. Remote node enrollment (Windows/GPU workers beyond the local machine).
4. Multi-node storage (Postgres) if VANGUARD ever needs to run distributed.
5. UI follow-up: no login/token UI, no cloud deployment of `ui/`, and no
   D27HQ-wide nav shell integration — the `/services` and `/jobs` pages are
   the only ones with real write actions (Service Control's
   start/stop/restart, and Job Queue's submit/cancel/retry), see
   `ui/README.md` for the current page set and what it still doesn't do.
6. Service Control follow-up: only Dispatch is registered; no fleet of
   managed processes, no auto-restart-on-crash policy, no adoption of a
   process started outside VANGUARD without `psutil` installed (documented
   limitation in `vanguard/process_control/manager.py`), no process control
   for any node other than this local machine.
7. Job Queue follow-up: no crash-recovery sweep for a `RUNNING` job whose
   worker process died, no scheduled/recurring jobs, no per-job timeout, no
   job priorities, no distributed workers — see "What is NOT implemented"
   above. Real future consumers (ingest, repo sync, deployments) can register
   new job types once those capabilities themselves become real.

## Safety and compatibility

- Never assume prior infrastructure is installed; this build re-verified ground
  truth against the actual filesystem before writing any code (see
  `VANGUARD_DISCOVERY.md`).
- No destructive or irreversible actions. No secrets committed anywhere.
- No git repository was initialized for this project during the build — ask the
  user before doing so, since `NCTIAPP` itself is not a git repo.
