"""Real-time incident detection: this module is wired directly into the exact
state-transition points that already exist in vanguard/readiness/,
vanguard/process_control/, vanguard/jobs/, and vanguard/integrations/ — not a
periodic poll. Each subsystem's one real persistence/computation choke point
(ReadinessStore.save(), ProcessController's status builder,
JobQueue._run()'s terminal-state update, DispatchAdapter.status()) takes an
optional callback that vanguard/api/app.py wires to the methods below. This
was chosen over polling because every signal here already fires at the exact
moment the underlying condition is known — a poll loop would only add latency
and duplicate work the app is already doing on every real state change; see
README.md/CAPABILITY_MATRIX.md for the honest tradeoff (a periodic poll would
have caught a failure even if nothing ever asks for that subsystem's status
again, which a hook cannot).

Only three permanently-stubbed integrations (Steward/Watchtower/Marshal) are
deliberately NEVER wired here: they always report NOT_CONNECTED because they
don't exist anywhere in this environment, so that status is steady-state, not
a new failure — alerting on it would be pure noise. Dispatch is the one real
exception (see observe_dispatch below): it can genuinely transition between
CONNECTED and NOT_CONNECTED as the real local process starts/stops, so only a
CONNECTED -> NOT_CONNECTED transition is a real signal, never the initial or
steady NOT_CONNECTED state.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..core.models import (
    Incident,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
    IntegrationReport,
    IntegrationStatus,
    Job,
    JobState,
    ManagedProcessStatus,
    ProcessState,
    ReadinessResult,
    ReadinessState,
)
from .store import IncidentStore

_SEVERITY_RANK = {
    IncidentSeverity.INFO: 0,
    IncidentSeverity.WARNING: 1,
    IncidentSeverity.DEGRADED: 2,
    IncidentSeverity.MAJOR: 3,
    IncidentSeverity.CRITICAL: 4,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentDetector:
    def __init__(self, store: IncidentStore):
        self.store = store
        # In-memory only: the last real IntegrationStatus observed for
        # Dispatch, so a CONNECTED->NOT_CONNECTED transition can be told apart
        # from Dispatch's steady, expected NOT_CONNECTED state (e.g. right
        # after this process starts, before anyone has ever seen it
        # CONNECTED). Documented, honest limitation: this resets on process
        # restart — a restart that happens to land while Dispatch is down
        # will not retroactively open an incident for a transition it never
        # witnessed, which is the correct, honest behavior for a "detected a
        # real transition" signal rather than a guess.
        self._last_dispatch_status: IntegrationStatus | None = None

    # ------------------------------------------------------------- internals
    def _open_or_update(self, *, correlation_key: str, title: str, severity: IncidentSeverity,
                         source: str, detail: str) -> Incident:
        now = _now()
        existing = self.store.get_ungrouped_open(correlation_key)
        if existing is None:
            incident = Incident(
                incident_id=str(uuid.uuid4()),
                title=title,
                severity=severity,
                status=IncidentStatus.OPEN,
                source=source,
                correlation_key=correlation_key,
                first_seen=now,
                last_seen=now,
                occurrence_count=1,
                timeline=[IncidentEvent(kind="detected", detail=detail, created_at=now)],
            )
            return self.store.create(incident)

        existing.last_seen = now
        existing.occurrence_count += 1
        existing.title = title  # keep the summary current (e.g. "2 nodes DEGRADED" -> "3 nodes DEGRADED")
        existing.timeline.append(IncidentEvent(kind="recurred", detail=detail, created_at=now))
        # Severity can escalate on a recurrence (e.g. a service that was just
        # unhealthy is now fully FAILED) but never silently de-escalates here
        # — a real de-escalation only happens via auto-resolve or a manual
        # acknowledge/resolve, both of which leave an honest timeline entry.
        if _SEVERITY_RANK[severity] > _SEVERITY_RANK[existing.severity]:
            existing.severity = severity
            existing.timeline.append(
                IncidentEvent(kind="condition_changed", detail=f"severity escalated to {severity.value}", created_at=now)
            )
        return self.store.update(existing)

    def _auto_resolve(self, *, correlation_key: str, detail: str) -> Incident | None:
        existing = self.store.get_ungrouped_open(correlation_key)
        if existing is None or existing.status == IncidentStatus.RESOLVED:
            return existing
        now = _now()
        existing.status = IncidentStatus.RESOLVED
        existing.resolved_at = now
        existing.last_seen = now
        existing.timeline.append(IncidentEvent(kind="auto_resolved", detail=detail, created_at=now))
        return self.store.update(existing)

    # -------------------------------------------------------------- readiness
    def observe_readiness(self, result: ReadinessResult) -> Incident | None:
        """Wired into ReadinessStore.save() — fires on every real readiness
        evaluation persisted (both the single-node API route and the
        readiness_sweep job type go through that one method)."""
        correlation_key = f"readiness:{result.node_id}:{result.profile_id}"
        if result.state == ReadinessState.NOT_READY:
            return self._open_or_update(
                correlation_key=correlation_key,
                title=f"Node '{result.node_id}' NOT_READY for profile {result.profile_id}",
                severity=IncidentSeverity.MAJOR,
                source=f"readiness:{result.profile_id}",
                detail=f"evaluated_at={result.evaluated_at}; failing checks: "
                f"{', '.join(e.check_id for e in result.evidence if not e.passed) or 'none listed'}",
            )
        if result.state == ReadinessState.DEGRADED:
            return self._open_or_update(
                correlation_key=correlation_key,
                title=f"Node '{result.node_id}' DEGRADED for profile {result.profile_id}",
                severity=IncidentSeverity.WARNING,
                source=f"readiness:{result.profile_id}",
                detail=f"evaluated_at={result.evaluated_at}; failing checks: "
                f"{', '.join(e.check_id for e in result.evidence if not e.passed) or 'none listed'}",
            )
        # READY / READY_WITH_WARNING / UNKNOWN: the condition that would have
        # opened an incident is no longer present — auto-resolve if one is
        # still open for this exact node+profile.
        return self._auto_resolve(
            correlation_key=correlation_key,
            detail=f"readiness returned to {result.state.value} at {result.evaluated_at}",
        )

    # ---------------------------------------------------------- service control
    def observe_process_status(self, status: ManagedProcessStatus) -> Incident | None:
        """Wired into ProcessController's status builder — fires on every
        real ManagedProcessStatus produced by start/stop/restart/status()."""
        correlation_key = f"service_control:{status.service_id}"
        if status.state == ProcessState.FAILED:
            return self._open_or_update(
                correlation_key=correlation_key,
                title=f"Service '{status.service_id}' process FAILED",
                severity=IncidentSeverity.CRITICAL,
                source=f"service_control:{status.service_id}",
                detail=status.health_detail or f"last_exit_code={status.last_exit_code}",
            )
        if status.state == ProcessState.RUNNING and status.healthy is False:
            return self._open_or_update(
                correlation_key=correlation_key,
                title=f"Service '{status.service_id}' health check failing",
                severity=IncidentSeverity.WARNING,
                source=f"service_control:{status.service_id}",
                detail=status.health_detail or "health check failed",
            )
        if status.state == ProcessState.RUNNING and status.healthy in (True, None):
            return self._auto_resolve(
                correlation_key=correlation_key,
                detail=f"process is RUNNING and healthy as of {status.last_checked}",
            )
        # STOPPED/STOPPING/STARTING/UNKNOWN: an operator-initiated or
        # in-progress transition, not itself a failure signal — leave any
        # existing incident's status untouched (no-op).
        return None

    # ---------------------------------------------------------------- jobs
    def observe_job(self, job: Job) -> Incident | None:
        """Wired into JobQueue._run() at the exact point a job reaches a
        terminal state. Correlates on job_type (a FAILED service_health_check
        for the same reason repeatedly is one incident; a later COMPLETED run
        of that same job_type auto-resolves it)."""
        correlation_key = f"job_queue:{job.job_type}"
        if job.state == JobState.FAILED:
            return self._open_or_update(
                correlation_key=correlation_key,
                title=f"Job type '{job.job_type}' failed",
                severity=IncidentSeverity.WARNING,
                source=f"job_queue:{job.job_type}",
                detail=f"job_id={job.job_id}; error={job.error}",
            )
        if job.state == JobState.COMPLETED:
            return self._auto_resolve(
                correlation_key=correlation_key,
                detail=f"job_id={job.job_id} completed successfully at {job.finished_at}",
            )
        # CANCELED/RETRYING/QUEUED/RUNNING: not a completion signal either way.
        return None

    # --------------------------------------------------------- integrations
    def observe_dispatch(self, report: IntegrationReport) -> Incident | None:
        """Wired ONLY to DispatchAdapter.status() (never Steward/Watchtower/
        Marshal — see module docstring). Only a real CONNECTED->NOT_CONNECTED
        transition opens an incident; the initial/steady NOT_CONNECTED state
        never does."""
        if report.integration != "dispatch":
            return None  # defensive; this detector is only ever wired to the Dispatch adapter
        previous = self._last_dispatch_status
        self._last_dispatch_status = report.status
        correlation_key = "integration:dispatch"

        if previous == IntegrationStatus.CONNECTED and report.status == IntegrationStatus.NOT_CONNECTED:
            return self._open_or_update(
                correlation_key=correlation_key,
                title="Dispatch integration lost connection",
                severity=IncidentSeverity.MAJOR,
                source="integration:dispatch",
                detail=report.detail,
            )
        if report.status == IntegrationStatus.CONNECTED and previous is not None and previous != IntegrationStatus.CONNECTED:
            return self._auto_resolve(
                correlation_key=correlation_key,
                detail=f"Dispatch reconnected: {report.detail}",
            )
        return None
