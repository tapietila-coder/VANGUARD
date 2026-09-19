# VANGUARD Capability Matrix

Honest audit of every capability named in the 15-subsystem operations-command-center
spec, against what actually exists in this codebase as of 2026-09-19. Updated after
each vertical slice — do not let this drift from reality.

Status legend: **LIVE** (real, verified, operator-usable) · **PARTIAL** (real backend,
incomplete UI or vice versa) · **STUB** (contract exists, honestly reports
NOT_CONNECTED/UNKNOWN) · **NONE** (nothing built).

| Capability | Backend | Operator UI | Status | Missing Pieces |
|---|---|---|---|---|
| Node inventory (local machine) | `vanguard/nodeops/` | `/nodes`, `/nodes/[id]` | LIVE | Remote/Windows/GPU node enrollment; only ever inspects the machine VANGUARD runs on |
| Readiness evaluation | `vanguard/readiness/` | `/readiness`, node detail | LIVE | More profiles as real workloads need them |
| Service registry | `vanguard/service_map/` | `/services` | LIVE | — |
| Service control (start/stop/restart) | `vanguard/process_control/` | `/services` control panel | LIVE | Only one process managed (Dispatch); no fleet, no systemd/Docker adapters |
| Job queue / workers | `vanguard/jobs/` *(in progress — see add-job-queue branch)* | `/jobs` *(in progress)* | IN PROGRESS | Only 3 job types wired to real existing logic; no distributed workers, no external broker |
| Audit log | `vanguard/audit/` | `GET /audit` (no dedicated UI page yet) | PARTIAL | No `/audit` UI page — only reachable via raw API today |
| Mesh networking (NetBird) | `vanguard/mesh/` (`NullMeshProvider` + `NetBirdMeshProvider` contract) | `/mesh` | STUB | No real NetBird deployment anywhere; requires separate authorization to touch production infra |
| Machines (remote) | — | — | NONE | No remote agent protocol; VANGUARD only ever sees its own host |
| Browser automation fleet | — | — | NONE | Not attempted; would require Playwright + a real browser-pool design |
| Media/Instagram ingestion | — | — | NONE | This capability lives in **CLASSIFIED's Reel Scout**, a separate project — not part of VANGUARD |
| Repository sync / Expat integration | — | — | NONE | Expat exists as a separate real system; VANGUARD has no integration with it yet |
| Deployments / rollback | — | — | NONE | Not attempted |
| Incidents / alerting | — | — | NONE | Not attempted; would likely correlate audit + readiness + job-failure events once those are richer |
| Secrets management UI | — | — | NONE | Secrets are env-var only today (`.env`), no VANGUARD-level secrets surface |
| Backups / restore | — | — | NONE | Not attempted; SQLite file backup would be the honest starting point |
| RBAC / approvals | Bearer-token, single shared secret | — | STUB | No per-user roles; anyone with the token can do everything mutating routes allow |
| Steward integration | `StewardAdapter` | Overview page shows real NOT_CONNECTED | STUB | Steward doesn't exist anywhere in this environment |
| Watchtower integration | `WatchtowerAdapter` | Overview page shows real NOT_CONNECTED | STUB | Watchtower doesn't exist anywhere in this environment |
| Marshal integration | `MarshalAdapter` | Overview page shows real NOT_CONNECTED | STUB | Marshal doesn't exist anywhere in this environment |
| Dispatch integration | `DispatchAdapter` — real `/health` probe | Overview page shows real live status | LIVE | Read-only; Service Control (above) now covers the write side for this one process |
| Logs (centralized) | Per-service log files under `data/logs/` (via process_control) | Inline log viewer on Service Control panel only | PARTIAL | No cross-service `/logs` page, no search/filter, no correlation IDs |
| Metrics / observability | — | — | NONE | Not attempted; CPU/RAM/GPU exist in `nodeops` detection but aren't graphed anywhere |
| System Health (aggregate) | Implicit via `/health` + `/integrations` | Overview page aggregates some of this | PARTIAL | No single first-class System Health page covering every subsystem's own health check |

## Sequencing so far

1. Core (nodes/readiness/service-map/mesh-stub/integrations-stub) — LIVE, `v0.1.0`.
2. UI dashboard — LIVE.
3. Service Control (real Dispatch process control) — LIVE.
4. Job Queue + Jobs UI — IN PROGRESS.

## What this matrix deliberately does not claim

Everything marked NONE above was in the original spec but was explicitly descoped by
the project owner's decision to build one real vertical slice at a time rather than
attempt all 15 subsystems simultaneously. This file exists so that decision, and its
real current state, stays visible and auditable — not so every NONE row becomes an
implicit backlog demand.
