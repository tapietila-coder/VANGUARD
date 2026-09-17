# VANGUARD — Mission 0: Discovery

Date: 2026-09-17. Working root inspected: `C:\Users\bigpo\Desktop\NCTIAPP` (a plain
folder, not a git repo at the root). This document is the factual basis for
everything built in `VANGUARD/`. It was produced by actually reading the tree
(`ls`, `grep -ril`, and reading source files), not by trusting prior assumptions.

## What is real, on disk, right now

- **`Dispatch/D27HQ_DISPATCH/`** — a real, installable Python 3.11 / FastAPI /
  SQLite service. Has a working `dispatch/` package (api.py, config.py, db.py,
  models.py, policy.py, runner.py, service.py, nats_outbox.py), a `tests/` suite,
  `docs/`, a `Dockerfile`/`compose.yaml`, and `pyproject.toml`. Its own README and
  `CLAUDE.md` state explicitly: *"No real Claude Code session launch, autonomous
  shell access, browser execution, cloud provider or GPU orchestration, real OPA
  policy decision service, Foundry/Marshal/Slave Driver/Watchtower API
  integration..."* — i.e. Dispatch's docs reference MARSHAL, WATCHTOWER, STEWARD,
  SLAVE DRIVER, and Foundry only as **aspirational names in its own docs**, and say
  in plain text that none of them are actually integrated or running.
  VANGUARD does not modify anything under this path.
- A large number of unrelated sibling Next.js/Vercel/Expo apps exist under
  `NCTIAPP/` (classified, storyforge, relayos, overseer, todds-command-center,
  ai-adult-compatibility, zmod-portal, Sightline, 25-media-foundry-ar-studio,
  admin-portal, creator-growth-os, reimagine-it, relay-travel, research, and an
  Expo/React Native app at the NCTIAPP root itself). None of these were touched.
- A recursive case-insensitive search (`grep -ril "steward|marshal|watchtower|
  netbird|vanguard|ranger"` across `.md/.py/.ts/.txt` under `NCTIAPP/`, excluding
  `node_modules`) returned **no matches outside Dispatch's own docs**. This
  confirms: no prior VANGUARD project, no RANGER, no NetBird install/config, no
  ATLAS, no EXPAT-as-a-system, on this machine.
- Per user memory, there is a real production Hetzner VPS (204.168.151.83)
  running Expat's remote-agent and CLASSIFIED's control plane. It was not
  accessed, SSH'd into, or otherwise touched for this task — out of scope per the
  task instructions (shared production box, requires separate future
  authorization).

## What does NOT exist anywhere in this tree

STEWARD, MARSHAL, WATCHTOWER, ATLAS, EXPAT-as-a-running-service, RANGER, any
prior VANGUARD project, NetBird (no install, no config, no binaries), any D27
Linux cloud gateway repository, and any `d27hq.dev` DNS/deployment configuration.
These names appear only as forward references inside Dispatch's own
documentation, describing systems it expects to integrate with someday.

## What this means for VANGUARD's build

VANGUARD is built as a **local-only reference service** with the same honesty
posture as Dispatch: real code for what can actually run on this machine (node
inventory, readiness evaluation, service registry, audit log, a FastAPI surface),
and explicit `NOT_CONNECTED`/`UNKNOWN` stub adapters for Steward, Watchtower and
Marshal, since none of those systems exist to connect to. The one adapter that
can attempt a real call is `DispatchAdapter`, because Dispatch is a real,
runnable local service — that call is read-only, hits `/health`, and degrades to
`NOT_CONNECTED` when Dispatch isn't running. Mesh support follows the same
pattern: a `NullMeshProvider` that honestly reports `NOT_CONNECTED` (the default,
since there is no NetBird deployment), and a `NetBirdMeshProvider` that defines
the real API contract for when one exists, but which has never been exercised
against a live server.

No cloud deployment, DNS, NetBird install, or production server access is part
of this build — all of that remains explicitly out of scope pending future,
separate user authorization.
