# VANGUARD Readiness Engine

Deterministic, no randomness, no network calls. `readiness.engine.evaluate(node,
profile)` walks a `ReadinessProfile`'s ordered `ReadinessCheckSpec` list against a
`Node`'s declared capabilities and current status, and returns the worst
(highest-severity) state across all failed checks, with per-check evidence.

## States

`READY` < `READY_WITH_WARNING` < `DEGRADED` < `NOT_READY` < `UNKNOWN` (severity order).
A profile with zero failing checks evaluates to `READY`.

## Built-in profiles (`readiness/profiles.py`)

- **D27_CONTROL_HOST** — requires `PYTHON_RUNTIME` and a recognized OS build
  capability (`WINDOWS_BUILD`/`LINUX_BUILD`/`MACOS_BUILD`); a stale heartbeat
  degrades rather than fails.
- **CLASSIFIED_GPU** — requires `GPU_INFERENCE`; missing `CUDA` or `HIGH_MEMORY`
  only warns (`READY_WITH_WARNING`), doesn't fail the node.
- **GENERAL_WORKER** — requires `PYTHON_RUNTIME` only; a stale heartbeat warns.

These are intentionally conservative and don't check for anything this codebase
can't actually verify (e.g. there is no check for "GPU Governor" or "ComfyUI" —
those aren't real systems here per `VANGUARD_DISCOVERY.md`).

## Evidence and storage

Every evaluation is persisted to the `readiness_results` SQLite table via
`ReadinessStore.save`. `GET /api/v1/vanguard/nodes/{id}/readiness?profile=...`
evaluates fresh and stores the result; `GET /api/v1/vanguard/readiness` returns
the most recent stored results across all nodes plus the list of available
profile ids.

## Adding a profile

Add a `ReadinessProfile` to `readiness/profiles.py` and register it in
`BUILTIN_PROFILES`. If a check needs logic beyond "is this capability declared,"
add a named branch in `readiness/engine.py::evaluate` (see `recent_heartbeat` and
`os_build_capability` for examples) — don't invent a check that can't be
evaluated against real, currently-collectible data.
