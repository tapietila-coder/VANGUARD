"""Stub integration adapters.

None of STEWARD, WATCHTOWER or MARSHAL exist anywhere in this environment today
(confirmed by repo search — see VANGUARD_DISCOVERY.md). Each adapter below defines
the contract VANGUARD expects once a real counterpart exists, and returns an
honest NOT_CONNECTED/UNKNOWN IntegrationReport rather than fabricated data.

DispatchAdapter is the one exception: D27HQ_DISPATCH is a real local service
(Dispatch/D27HQ_DISPATCH), so this adapter may optionally make a read-only HTTP
call to it if it happens to be running, and must degrade gracefully to
NOT_CONNECTED otherwise. It never writes to Dispatch and this project never
modifies Dispatch's own source.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable

from ..core.models import IntegrationReport, IntegrationStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StewardAdapter:
    """No real Steward exists yet; this adapter defines the contract VANGUARD
    expects once one does (a system that would presumably grant/attest node
    trust). Every method here is a documented no-op."""

    name = "steward"

    def status(self) -> IntegrationReport:
        return IntegrationReport(
            integration=self.name,
            status=IntegrationStatus.NOT_CONNECTED,
            detail="No Steward service exists in this environment. Contract-only stub.",
            checked_at=_now(),
        )


class WatchtowerAdapter:
    """No real Watchtower exists yet; this adapter defines the contract VANGUARD
    expects once one does (a monitoring/observability system). Every method here
    is a documented no-op."""

    name = "watchtower"

    def status(self) -> IntegrationReport:
        return IntegrationReport(
            integration=self.name,
            status=IntegrationStatus.NOT_CONNECTED,
            detail="No Watchtower service exists in this environment. Contract-only stub.",
            checked_at=_now(),
        )


class MarshalAdapter:
    """No real Marshal exists yet; this adapter defines the contract VANGUARD
    expects once one does (a mission-planning system upstream of Dispatch).
    Every method here is a documented no-op."""

    name = "marshal"

    def status(self) -> IntegrationReport:
        return IntegrationReport(
            integration=self.name,
            status=IntegrationStatus.NOT_CONNECTED,
            detail="No Marshal service exists in this environment. Contract-only stub.",
            checked_at=_now(),
        )


class DispatchAdapter:
    """Read-only capability/health probe against the real local D27HQ_DISPATCH
    service, if it happens to be running on `base_url`. Never modifies Dispatch,
    never writes to it, and reports NOT_CONNECTED (not an error) when it is
    unreachable — a stopped Dispatch process is an expected, common state."""

    name = "dispatch"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8787",
        timeout_seconds: float = 2.0,
        on_status: Callable[[IntegrationReport], None] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        # Real-time incident detection hook (vanguard/incidents/detector.py):
        # fired on every real status() call. Dispatch is the only integration
        # adapter this is ever wired to — Steward/Watchtower/Marshal are
        # permanently-stubbed NOT_CONNECTED and deliberately never wired here
        # (see IncidentDetector's module docstring for why alerting on their
        # steady-state would be noise).
        self.on_status = on_status

    def status(self) -> IntegrationReport:
        url = f"{self.base_url}/health"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            report = IntegrationReport(
                integration=self.name,
                status=IntegrationStatus.CONNECTED,
                detail=f"Dispatch reachable at {url}: {body}",
                checked_at=_now(),
            )
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            report = IntegrationReport(
                integration=self.name,
                status=IntegrationStatus.NOT_CONNECTED,
                detail=f"Dispatch not reachable at {url} ({exc.__class__.__name__}: {exc})",
                checked_at=_now(),
            )
        if self.on_status is not None:
            self.on_status(report)
        return report
