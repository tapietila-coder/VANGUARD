# VANGUARD — D27HQ Infrastructure & Operational Readiness Directorate

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
- Stub adapters for Steward/Watchtower/Marshal that always report
  `NOT_CONNECTED` (`vanguard/integrations/adapters.py`), because none of those
  systems exist anywhere in this environment (verified by repo search — see
  discovery doc). A `DispatchAdapter` that makes a real, read-only
  `GET http://127.0.0.1:8787/health` call against the actual local Dispatch
  service when it's running, and degrades gracefully to `NOT_CONNECTED` when it
  isn't.
- Append-only audit log (`vanguard/audit/`) recording actor/action/target/
  before/after/reason for every mutating API call.
- 18 pytest tests, all passing locally (see "Test results" below).

## What is NOT implemented / not claimed

- **No UI or dashboard.** No VANGUARD/RANGER preservation work, no D27HQ nav
  integration. Explicitly deferred — see "Follow-up" below.
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
18 passed, 2 warnings in 1.52s
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
```

Mutating, require `Authorization: Bearer <VANGUARD_API_TOKEN>`:

```
POST   /api/v1/vanguard/nodes
POST   /api/v1/vanguard/services
POST   /api/v1/vanguard/mesh/enrollments
DELETE /api/v1/vanguard/mesh/enrollments/{id}
POST   /api/v1/vanguard/nodes/{id}/revoke
GET    /api/v1/vanguard/audit
```

## Source tree

`vanguard/` = the installable package (`core`, `nodeops`, `readiness`,
`service_map`, `mesh`, `integrations`, `audit`, `api`). `tests/` = pytest suite.
`docs/` = architecture, mesh, readiness, and security notes. `VANGUARD_DISCOVERY.md`
= the Mission-0 ground-truth audit this build is based on.

## Follow-up (explicitly out of scope for this pass)

1. UI/dashboard for nodes, readiness, mesh status, and service map.
2. Real NetBird deployment (pinned to `v0.78.2`, never `latest` — see
   `docs/MESH.md`) once the user authorizes touching real infrastructure.
3. Real Steward/Marshal/Watchtower integrations once those systems exist.
4. Remote node enrollment (Windows/GPU workers beyond the local machine).
5. Multi-node storage (Postgres) if VANGUARD ever needs to run distributed.

## Safety and compatibility

- Never assume prior infrastructure is installed; this build re-verified ground
  truth against the actual filesystem before writing any code (see
  `VANGUARD_DISCOVERY.md`).
- No destructive or irreversible actions. No secrets committed anywhere.
- No git repository was initialized for this project during the build — ask the
  user before doing so, since `NCTIAPP` itself is not a git repo.
