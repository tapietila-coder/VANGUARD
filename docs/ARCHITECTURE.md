# VANGUARD Architecture

## Layout

```
vanguard/
  core/          Pydantic contracts (models.py), Settings (config.py), SQLite wrapper (db.py)
  nodeops/       Local hardware/OS detection (detect.py), SQLite-backed node inventory (inventory.py)
  readiness/     Built-in profiles (profiles.py), deterministic evaluation engine (engine.py)
  service_map/   Service registry + resolveService() resolver (registry.py)
process_control/ Service Control: real subprocess start/stop/restart/health
               (manager.py) — see "Service Control" below
  mesh/          MeshProvider interface + NullMeshProvider + NetBirdMeshProvider (provider.py)
  integrations/  StewardAdapter, WatchtowerAdapter, MarshalAdapter, DispatchAdapter (adapters.py)
  audit/         Append-only audit log writer (writer.py)
  api/           FastAPI app wiring everything together (app.py)
tests/           pytest suite (18 tests as of initial build)
docs/            this file, MESH.md, READINESS.md, SECURITY.md
```

`service_map` is spelled with an underscore (valid Python package name); the
spec's `service-map/` naming is preserved in prose and docs.

## Data flow

1. A node (currently: this machine) is detected via `nodeops.detect.detect_local_node`
   (stdlib + optional psutil) and registered into SQLite via `nodeops.inventory.NodeInventory`.
2. `readiness.engine.evaluate(node, profile)` runs a named `ReadinessProfile`
   against that `Node` and returns a `ReadinessResult` with per-check `ReadinessEvidence`.
   Results are persisted via `ReadinessStore` for history.
3. `service_map.registry.ServiceRegistry` stores registered services in SQLite;
   `resolveService(registry, name)` looks up by id then by exact name — returns
   `None`, never a fabricated placeholder, when nothing is registered.
4. `mesh.provider.MeshProvider` is the abstract contract for overlay-network
   operations. `build_mesh_provider(settings)` returns `NullMeshProvider` unless
   `VANGUARD_MESH_PROVIDER=netbird` and both `NETBIRD_BASE_URL`/`NETBIRD_API_TOKEN`
   are set, in which case it returns `NetBirdMeshProvider`.
5. `integrations.adapters` exposes one `.status() -> IntegrationReport` per
   external system. Steward/Watchtower/Marshal always report `NOT_CONNECTED`
   (nothing to connect to). Dispatch attempts a real read-only HTTP call to
   `http://127.0.0.1:8787/health` and reports `CONNECTED`/`NOT_CONNECTED` honestly.
6. Every mutating API call writes an `AuditEntry` via `audit.writer.AuditWriter`.
7. `process_control.manager.ProcessController` owns real start/stop/restart of
   locally registered processes via `subprocess.Popen` (argv list, never a
   shell string). A managed process is a superset of a plain `Service` —
   registering one (`ProcessController.register`) also upserts a matching row
   in the `services` table via `ServiceRegistry`, so it's visible through the
   existing read-only `/services` routes unchanged; `process_control` owns a
   separate `managed_processes` SQLite table for the extra control-plane
   fields (argv, cwd, health probe URL, live runtime state: PID, state,
   started_at, last_exit_code, last_checked, health). This build registers
   exactly one real managed process: the local Dispatch API.

## What's real vs. stubbed

| Area | Status |
|---|---|
| Node inventory, capability model, local detection | Real, SQLite-backed, tested |
| Readiness engine + 3 built-in profiles | Real, deterministic, tested |
| Service registry + resolver | Real, SQLite-backed, tested |
| Audit log | Real, SQLite-backed, tested |
| FastAPI surface | Real, runnable locally, tested via `TestClient` |
| Mesh (NetBird) | Contract + Null provider real; `NetBirdMeshProvider` untested against a live server — none exists |
| Steward / Watchtower / Marshal | Contract-only stubs; no real systems exist |
| Dispatch integration | Real read-only probe; degrades gracefully when Dispatch isn't running |
| Service Control (start/stop/restart of the local Dispatch process) | Real, `subprocess.Popen`-backed, tested against real spawned processes; one process registered (Dispatch) |
| UI / dashboard (VANGUARD/RANGER, D27HQ nav) | Built (`ui/`); one real write action wired (Service Control) |

## Not built in this pass

- No UI/dashboard.
- No deployment automation (no scripts that install NetBird, provision servers, or touch DNS).
- No multi-node / distributed storage — SQLite is a single-node reference, same posture as Dispatch.
