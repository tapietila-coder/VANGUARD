# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `CONTRIBUTING.md` documenting the branch-protected PR workflow and local dev setup.

## [0.1.0] - 2026-09-17

### Added
- Initial VANGUARD core: FastAPI service, SQLite-backed node inventory (`nodeops`),
  deterministic readiness engine with `D27_CONTROL_HOST` / `CLASSIFIED_GPU` /
  `GENERAL_WORKER` profiles (`readiness`), service registry with `resolveService()`
  (`service_map`), `MeshProvider` abstraction shaped on NetBird's REST API with a
  `NullMeshProvider` default and `NetBirdMeshProvider` contract implementation (`mesh`),
  stub `Steward`/`Watchtower`/`Marshal` adapters that honestly report `NOT_CONNECTED`,
  and a `DispatchAdapter` with a real read-only health probe (`integrations`),
  append-only audit log (`audit`).
- `VANGUARD_DISCOVERY.md` — Mission-0 ground-truth audit of what infrastructure
  actually exists in the D27HQ tree before any code was written.
- 18 pytest tests covering all of the above.
- GitHub Actions CI workflow (`tests.yml`) running pytest on push/PR to `master`.
- CI status badge in `README.md`.
- `LICENSE` (all rights reserved).
- Branch protection on `master` requiring the `pytest` check to pass.

### Not implemented (see README "Follow-up")
- UI/dashboard, real NetBird deployment, real Steward/Marshal/Watchtower
  integrations, remote node enrollment, multi-node storage.
