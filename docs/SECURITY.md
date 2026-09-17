# VANGUARD Security Posture

Matches Dispatch's honesty posture: this is a **local development reference**,
not a hardened service.

## Authentication

- Read-only routes (`GET /api/v1/vanguard/health|nodes|nodes/{id}|nodes/{id}/readiness|
  services|services/{id}|mesh/status|mesh/peers|mesh/routes|mesh/policies|readiness|integrations`)
  require **no auth token**. This is a documented dev-only posture — do not expose
  this service on a network where untrusted parties can reach it.
- Mutating routes (`POST /nodes`, `POST /services`, `POST /mesh/enrollments`,
  `DELETE /mesh/enrollments/{id}`, `POST /nodes/{id}/revoke`, `GET /audit`) require
  `Authorization: Bearer <VANGUARD_API_TOKEN>`, compared with `hmac.compare_digest`
  (constant-time), same pattern as Dispatch's `dispatch/api.py`.
- In `VANGUARD_ENVIRONMENT=dev` (the default) a fallback insecure token is used if
  `VANGUARD_API_TOKEN` is unset, purely so the service can boot with zero config
  for local experimentation. **Any environment other than `dev` requires a real
  24+ character random secret** — `Settings.from_env` raises if one isn't set.
  This is not a real authorization system; anyone with the token can perform all
  operator actions, exactly like Dispatch's single-token model.

## Secrets

- `.env.example` contains no real secrets — only placeholders.
- `NETBIRD_API_TOKEN`, `VANGUARD_API_TOKEN` must come from the environment, never
  hardcoded in source, never committed. `.gitignore` excludes `.env` and the
  SQLite data files.

## What is NOT implemented

- No per-user RBAC, no central identity, no secrets broker/vault integration.
- No TLS termination — run behind a reverse proxy or on localhost only.
- No rate limiting, no request signing, no mTLS between VANGUARD and Dispatch.
- No production threat model has been written; this document only describes the
  current local dev posture.

## Outbound network calls

The only outbound calls this service makes are:
1. `DispatchAdapter` → `GET {VANGUARD_DISPATCH_BASE_URL}/health` (default
   `http://127.0.0.1:8787/health`), read-only, local-only by default.
2. `NetBirdMeshProvider` → configured `NETBIRD_BASE_URL`, only when
   `VANGUARD_MESH_PROVIDER=netbird` is explicitly set. No such server exists in
   this environment as of this build.

No calls are made to the production Hetzner VPS (204.168.151.83) or any other
production D27HQ infrastructure. That remains explicitly out of scope.
