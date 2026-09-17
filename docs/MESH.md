# VANGUARD Mesh Layer

## Status: no mesh is deployed

There is no NetBird installation anywhere in this environment (confirmed by
repo search — see `../VANGUARD_DISCOVERY.md`). `VANGUARD_MESH_PROVIDER` defaults
to `null`, and `mesh.provider.NullMeshProvider` is what actually runs: it reports
`MeshConnectionStatus.NOT_CONNECTED` from `/api/v1/vanguard/mesh/status`, and
returns empty lists from peers/routes/policies — never fabricated data.

## Provider contract

`mesh.provider.MeshProvider` is an abstract interface modeled on NetBird's
Management REST API resources: peers, setup-keys (`Enrollment` here), groups,
networks/routes, policies, and DNS. Methods:

`health`, `list_nodes`, `get_node`, `enroll_node`, `revoke_node`,
`create_enrollment`, `list_groups`, `list_policies`, `list_routes`, `get_dns`,
`resolve_node`, `get_events`.

`mesh.provider.NetBirdMeshProvider` implements this against a real NetBird
Management API base URL (`NETBIRD_BASE_URL`) and API token
(`NETBIRD_API_TOKEN`), both read from the environment — never hardcoded, never
committed. Endpoint shapes (`/api/peers`, `/api/groups`, `/api/policies`,
`/api/routes`, `/api/dns/settings`, `/api/events/audit`) follow NetBird's
documented Management API. **This implementation has not been exercised against
a live NetBird server** — there is none in this environment to test against.
Treat it as the contract, verify it for real before trusting it in production.
Peer/setup-key deletion and setup-key creation deliberately raise
`NotImplementedError` rather than pretending to succeed, since those are
destructive/security-sensitive operations that must not be faked.

## Version policy

`NETBIRD_TARGET_VERSION = "v0.78.2"` is defined in `mesh/provider.py` as the
pinned stable target for any future real deployment. Any deployment script or
doc written later for this project must:

- Install/reference that exact version tag.
- Never install or reference `latest`.
- Never install or reference a prerelease/RC tag.

No deployment script exists in this repository — VANGUARD only defines the
provider code and this policy, per the task's explicit scope boundary (no real
NetBird installation, no cloud deployment, no DNS).

## When a real NetBird management server exists

1. Set `VANGUARD_MESH_PROVIDER=netbird`, `NETBIRD_BASE_URL`, `NETBIRD_API_TOKEN` in `.env`.
2. Verify `GET /api/v1/vanguard/mesh/status` reports `CONNECTED`.
3. Re-run `tests/test_mesh_provider.py`-style tests against the real provider
   (a live-server test suite does not exist yet — write one before trusting this
   in anything beyond local experimentation).
