"""MeshProvider: the abstract interface VANGUARD uses for overlay-network operations,
shaped after NetBird's REST API (peers / setup-keys / groups / networks / policies /
routes / dns). See docs/MESH.md for the endpoint mapping and version policy.

NETBIRD_TARGET_VERSION is the only version this codebase is written to assume once a
real deployment happens. Deployment scripts/docs must reject "latest" and prerelease
tags — see docs/MESH.md "Version policy". No deployment script exists here; this
module only defines the provider contract and two implementations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from ..core.models import (
    Enrollment,
    MeshConnectionStatus,
    MeshPeer,
    MeshPolicy,
    MeshRoute,
    MeshStatus,
)

NETBIRD_TARGET_VERSION = "v0.78.2"  # pinned stable target; never "latest" or a prerelease tag


class MeshProvider(ABC):
    """Contract mirroring NetBird's real REST resources. Every method must return
    honest data or raise/return NOT_CONNECTED — never fabricated peers/routes."""

    @abstractmethod
    def health(self) -> MeshStatus: ...

    @abstractmethod
    def list_nodes(self) -> list[MeshPeer]: ...

    @abstractmethod
    def get_node(self, peer_id: str) -> MeshPeer | None: ...

    @abstractmethod
    def enroll_node(self, name: str, expires_at: str | None = None) -> Enrollment: ...

    @abstractmethod
    def revoke_node(self, peer_id: str) -> bool: ...

    @abstractmethod
    def create_enrollment(self, name: str, expires_at: str | None = None) -> Enrollment: ...

    @abstractmethod
    def list_groups(self) -> list[str]: ...

    @abstractmethod
    def list_policies(self) -> list[MeshPolicy]: ...

    @abstractmethod
    def list_routes(self) -> list[MeshRoute]: ...

    @abstractmethod
    def get_dns(self) -> dict: ...

    @abstractmethod
    def resolve_node(self, name_or_id: str) -> MeshPeer | None: ...

    @abstractmethod
    def get_events(self) -> list[dict]: ...


class NullMeshProvider(MeshProvider):
    """The honest default: no real mesh is deployed, so every call reports
    NOT_CONNECTED / empty rather than inventing peers. This is the provider used
    until a real NetBird management server exists and is configured."""

    def health(self) -> MeshStatus:
        return MeshStatus(
            provider="null",
            status=MeshConnectionStatus.NOT_CONNECTED,
            detail="No mesh provider configured. Set VANGUARD_MESH_PROVIDER=netbird and "
            "NETBIRD_BASE_URL/NETBIRD_API_TOKEN once a real NetBird deployment exists.",
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

    def list_nodes(self) -> list[MeshPeer]:
        return []

    def get_node(self, peer_id: str) -> MeshPeer | None:
        return None

    def enroll_node(self, name: str, expires_at: str | None = None) -> Enrollment:
        raise RuntimeError("No mesh provider configured; cannot enroll nodes")

    def revoke_node(self, peer_id: str) -> bool:
        return False

    def create_enrollment(self, name: str, expires_at: str | None = None) -> Enrollment:
        raise RuntimeError("No mesh provider configured; cannot create enrollments")

    def list_groups(self) -> list[str]:
        return []

    def list_policies(self) -> list[MeshPolicy]:
        return []

    def list_routes(self) -> list[MeshRoute]:
        return []

    def get_dns(self) -> dict:
        return {}

    def resolve_node(self, name_or_id: str) -> MeshPeer | None:
        return None

    def get_events(self) -> list[dict]:
        return []


class NetBirdMeshProvider(MeshProvider):
    """Real NetBird Management API client. Base URL and token come from env
    (NETBIRD_BASE_URL, NETBIRD_API_TOKEN) — never hardcoded, never committed.

    Endpoint shapes below follow NetBird's documented Management REST API
    (https://docs.netbird.io/api) as of the pinned NETBIRD_TARGET_VERSION.
    Nothing in this class has been exercised against a live server; there is
    no NetBird deployment in this environment. Treat this as the contract
    implementation, verify against a real server before trusting it.
    """

    def __init__(self, base_url: str, api_token: str, timeout_seconds: float = 5.0):
        if not base_url or not api_token:
            raise ValueError("NetBirdMeshProvider requires base_url and api_token")
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict:
        return {"Authorization": f"Token {self.api_token}", "Accept": "application/json"}

    def _get(self, path: str):
        import urllib.request
        import json as _json

        req = urllib.request.Request(f"{self.base_url}{path}", headers=self._headers())
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            return _json.loads(resp.read().decode("utf-8"))

    def health(self) -> MeshStatus:
        try:
            self._get("/api/peers")
            return MeshStatus(
                provider="netbird",
                status=MeshConnectionStatus.CONNECTED,
                detail=f"Reached {self.base_url}/api/peers",
            )
        except Exception as exc:  # noqa: BLE001 - report, never fabricate success
            return MeshStatus(
                provider="netbird",
                status=MeshConnectionStatus.UNKNOWN,
                detail=f"Could not reach NetBird management API: {exc}",
            )

    def list_nodes(self) -> list[MeshPeer]:
        data = self._get("/api/peers")
        return [
            MeshPeer(
                peer_id=p.get("id", ""),
                name=p.get("name", ""),
                ip=p.get("ip"),
                connected=bool(p.get("connected", False)),
                last_seen=p.get("last_seen"),
                os=p.get("os"),
                groups=[g.get("name", "") for g in p.get("groups", [])],
            )
            for p in data
        ]

    def get_node(self, peer_id: str) -> MeshPeer | None:
        try:
            p = self._get(f"/api/peers/{peer_id}")
        except Exception:
            return None
        return MeshPeer(
            peer_id=p.get("id", ""),
            name=p.get("name", ""),
            ip=p.get("ip"),
            connected=bool(p.get("connected", False)),
            last_seen=p.get("last_seen"),
            os=p.get("os"),
            groups=[g.get("name", "") for g in p.get("groups", [])],
        )

    def enroll_node(self, name: str, expires_at: str | None = None) -> Enrollment:
        return self.create_enrollment(name, expires_at)

    def revoke_node(self, peer_id: str) -> bool:
        raise NotImplementedError("Peer deletion requires a verified live NetBird deployment")

    def create_enrollment(self, name: str, expires_at: str | None = None) -> Enrollment:
        raise NotImplementedError("Setup-key creation requires a verified live NetBird deployment")

    def list_groups(self) -> list[str]:
        data = self._get("/api/groups")
        return [g.get("name", "") for g in data]

    def list_policies(self) -> list[MeshPolicy]:
        data = self._get("/api/policies")
        return [
            MeshPolicy(policy_id=p.get("id", ""), name=p.get("name", ""), enabled=p.get("enabled", True),
                       description=p.get("description", ""))
            for p in data
        ]

    def list_routes(self) -> list[MeshRoute]:
        data = self._get("/api/routes")
        return [
            MeshRoute(route_id=r.get("id", ""), network=r.get("network", ""), peer_id=r.get("peer"),
                      enabled=r.get("enabled", True), groups=r.get("groups", []))
            for r in data
        ]

    def get_dns(self) -> dict:
        return self._get("/api/dns/settings")

    def resolve_node(self, name_or_id: str) -> MeshPeer | None:
        for peer in self.list_nodes():
            if peer.peer_id == name_or_id or peer.name == name_or_id:
                return peer
        return None

    def get_events(self) -> list[dict]:
        try:
            return self._get("/api/events/audit")
        except Exception:
            return []


def build_mesh_provider(settings) -> MeshProvider:
    if settings.mesh_provider == "netbird" and settings.netbird_base_url and settings.netbird_api_token:
        return NetBirdMeshProvider(settings.netbird_base_url, settings.netbird_api_token)
    return NullMeshProvider()
