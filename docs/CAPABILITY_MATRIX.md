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
| Job queue / workers | `vanguard/jobs/` | `/jobs` | LIVE | Only 3 job types wired to real existing logic; no distributed workers, no external broker |
| Audit log | `vanguard/audit/` (now with actor/action/target/since/until filtering + limit/offset pagination) | `/audit` | LIVE | Filters are exact-match, not fuzzy search; single shared operator token, no per-user actor identity yet |
| Mesh networking (NetBird) | `vanguard/mesh/` (`NullMeshProvider` + `NetBirdMeshProvider` contract) | `/mesh` | STUB | No real NetBird deployment anywhere; requires separate authorization to touch production infra |
| Machines (remote) | — | — | NONE | No remote agent protocol; VANGUARD only ever sees its own host |
| Browser automation fleet | — | — | NONE | Not attempted; would require Playwright + a real browser-pool design |
| Media/Instagram ingestion | — | — | NONE | This capability lives in **CLASSIFIED's Reel Scout**, a separate project — not part of VANGUARD |
| Repository sync / Expat integration | — | — | NONE | Expat exists as a separate real system; VANGUARD has no integration with it yet |
| Deployments / rollback | — | — | NONE | Not attempted |
| Incidents / alerting | `vanguard/incidents/` — real-time correlation wired directly into the existing state-transition points: `ReadinessStore.save()`, `ProcessController`'s status builder, `JobQueue`'s terminal-state update, `DispatchAdapter.status()` (never a periodic poll — see `detector.py`'s module docstring for why) | `/incidents`, `/incidents/[id]` — list (filterable by status/severity), Acknowledge/Resolve actions, full timeline, added to top nav; a real "N open incidents" row also appears on `/system-health` | LIVE | Correlation key is per-subsystem+target (e.g. `readiness:<node>:<profile>`, `service_control:<service_id>`) except Job Queue, which correlates per `job_type` only (not per job params) — two different failure *reasons* for the same job_type still land in one incident; the Dispatch CONNECTED→NOT_CONNECTED transition tracker is in-memory only and resets on process restart (documented, honest — a restart while Dispatch happens to be down never retroactively opens an incident for a transition it didn't witness); single shared operator identity for acknowledge (`"operator"`), same as every other mutating route |
| Secrets management UI | — | — | NONE | Secrets are env-var only today (`.env`), no VANGUARD-level secrets surface |
| Backups / restore | `vanguard/backup/` — real `sqlite3.Connection.backup()` bundles, JSON-sidecar metadata (not a db table — see manager.py docstring for the real bug that caused that choice), `backup_create` job type, synchronous checksum-verified restore with automatic pre-restore safety snapshot | `/backups` — list, Create Backup, per-row Restore/Delete behind the same confirm-before-disrupt pattern as Service Control | PARTIAL | Only backs up VANGUARD's own db, not `data/logs/` (skipped — real log files can be open/appended-to on Windows, needs its own rotation-aware handling); restore's connection-swap safety only serializes against requests sharing this process's one `Database` instance, not a second OS process independently holding the db file open; no scheduled/automatic backups |
| RBAC / approvals | Bearer-token, single shared secret | — | STUB | No per-user roles; anyone with the token can do everything mutating routes allow |
| Steward integration | `StewardAdapter` | Overview page shows real NOT_CONNECTED | STUB | Steward doesn't exist anywhere in this environment |
| Watchtower integration | `WatchtowerAdapter` | Overview page shows real NOT_CONNECTED | STUB | Watchtower doesn't exist anywhere in this environment |
| Marshal integration | `MarshalAdapter` | Overview page shows real NOT_CONNECTED | STUB | Marshal doesn't exist anywhere in this environment |
| Dispatch integration | `DispatchAdapter` — real `/health` probe | Overview page shows real live status | LIVE | Read-only; Service Control (above) now covers the write side for this one process |
| Logs (centralized) | Per-service log files under `data/logs/` (via process_control), plus new `GET /logs` cross-service index (exists/size/last-modified/line-count per registered process) | `/logs` — pick any registered service, tail it, client-side substring filter on the loaded tail | LIVE | Only covers services registered with Service Control (just Dispatch today); no correlation IDs, no server-side full-text search — client-side substring filter on the currently-loaded tail only |
| Metrics / observability | — | — | NONE | Not attempted; CPU/RAM/GPU exist in `nodeops` detection but aren't graphed anywhere |
| System Health (aggregate) | `vanguard/system_health/` — real `GET /system-health` aggregation endpoint calling `db.check_read_write()`, `jobs.worker_status()`, `ProcessController.status()`, `MeshProvider.health()`, all four integration adapters, `ReadinessStore.all_latest()`, and `audit.count()` | `/system-health` — one dense row per subsystem, manual refresh, honest whole-page unreachable state | LIVE | Service Control row only reflects the one process registered today (Dispatch); Readiness row summarizes the 200 most-recent stored evaluations, not a full history; no push/streaming — an operator (or the manual refresh button) has to ask |

## Sequencing so far

1. Core (nodes/readiness/service-map/mesh-stub/integrations-stub) — LIVE, `v0.1.0`.
2. UI dashboard — LIVE.
3. Service Control (real Dispatch process control) — LIVE.
4. Job Queue + Jobs UI — LIVE.
5. Audit + Logs UI (`/audit`, `/logs`) — LIVE.
6. System Health aggregate (`/system-health`) — LIVE.
7. Backups / restore (`/backups`) — PARTIAL (see row above for the honest limitations).
8. Incidents / alerting (`/incidents`) — LIVE (see row above for the honest limitations).

## What this matrix deliberately does not claim

Everything marked NONE above was in the original spec but was explicitly descoped by
the project owner's decision to build one real vertical slice at a time rather than
attempt all 15 subsystems simultaneously. This file exists so that decision, and its
real current state, stays visible and auditable — not so every NONE row becomes an
implicit backlog demand.
