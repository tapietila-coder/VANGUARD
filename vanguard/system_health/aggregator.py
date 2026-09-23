"""System Health aggregation: one real check per real subsystem, assembled
into a single SystemHealthReport for the `/system-health` operator page.

This module deliberately does the aggregation server-side (rather than making
the UI call 6+ separate routes and merge them client-side) because every row
here is cheap to compute from objects the API process already holds live in
memory (the exact same `db`/`processes`/`jobs`/`mesh`/adapters/`readiness_store`
instances wired in vanguard/api/app.py) — a single `GET
/api/v1/vanguard/system-health` call gives an operator (and this UI page) one
atomic, honestly-timestamped snapshot instead of six requests that could race
each other and disagree about "right now". No row here is proxied from a
cached value; every call below is a real check executed during this request.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..audit.writer import AuditWriter
from ..core.db import Database
from ..core.models import SystemHealthReport, SystemHealthRow
from ..incidents.store import IncidentStore
from ..integrations.adapters import DispatchAdapter, MarshalAdapter, StewardAdapter, WatchtowerAdapter
from ..jobs.queue import JobQueue
from ..mesh.provider import MeshProvider
from ..metrics.collector import MetricsCollector
from ..metrics.store import MetricsStore
from ..process_control.manager import ProcessController
from ..readiness.engine import ReadinessStore
from ..readiness.profiles import BUILTIN_PROFILES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _api_row() -> SystemHealthRow:
    # Trivially true if this request executed at all — reported structurally
    # so System Health always has a first, "the API answered" row rather than
    # implying that answering somehow proves everything else.
    return SystemHealthRow(
        subsystem="api",
        status="OK",
        detail="FastAPI process handled this request.",
        checked_at=_now(),
    )


def _database_row(db: Database) -> SystemHealthRow:
    ok, detail = db.check_read_write()
    return SystemHealthRow(
        subsystem="database",
        status="OK" if ok else "FAILED",
        detail=detail,
        checked_at=_now(),
    )


def _jobs_row(jobs: JobQueue) -> SystemHealthRow:
    ws = jobs.worker_status()
    # A stuck queue (work waiting, nothing alive to run it) is the one real
    # signal this local in-process pool can honestly detect; an idle queue
    # with 0 alive threads and 0 queued/running is normal (ThreadPoolExecutor
    # spawns threads lazily on first submission).
    degraded = ws["queued"] > 0 and ws["alive_threads"] == 0
    detail = (
        f"{ws['configured_workers']} workers configured, {ws['alive_threads']} alive, "
        f"{ws['queued']} queued, {ws['running']} running"
    )
    return SystemHealthRow(
        subsystem="jobs",
        status="DEGRADED" if degraded else "OK",
        detail=detail,
        checked_at=_now(),
    )


def _service_control_row(processes: ProcessController) -> SystemHealthRow:
    configs = processes.list_configs()
    if not configs:
        return SystemHealthRow(
            subsystem="service_control",
            status="NOT_CONNECTED",
            detail="No managed process registered with Service Control on this deployment "
            "(e.g. VANGUARD_DISPATCH_DIR/VANGUARD_DISPATCH_PYTHON not pointed at a real install).",
            checked_at=_now(),
        )
    parts = []
    single_state = None
    worst = "OK"
    for cfg in configs:
        status = processes.status(cfg.service_id, check_health=True)
        state = status.state.value
        single_state = state
        parts.append(f"{cfg.service_id}: {state}" + (f" (pid {status.pid})" if status.pid else ""))
        if state == "RUNNING" and status.healthy is False:
            worst = "DEGRADED" if worst == "OK" else worst
        elif state == "FAILED":
            worst = "FAILED"
        elif state in ("STOPPED", "UNKNOWN") and worst == "OK":
            worst = state
    # Prefer the single real process's own ProcessState as the row status when
    # there's exactly one (the common case today — only Dispatch), so the UI
    # shows the same vocabulary as the /services page; fall back to the
    # aggregated `worst` above once more than one process is ever registered.
    status_value = single_state if len(configs) == 1 else worst
    return SystemHealthRow(
        subsystem="service_control",
        status=status_value,
        detail="; ".join(parts),
        checked_at=_now(),
    )


def _mesh_row(mesh: MeshProvider) -> SystemHealthRow:
    health = mesh.health()
    return SystemHealthRow(
        subsystem="mesh",
        status=health.status.value,
        detail=health.detail,
        checked_at=health.checked_at,
    )


def _integrations_row(
    steward: StewardAdapter, watchtower: WatchtowerAdapter, marshal: MarshalAdapter, dispatch: DispatchAdapter
) -> SystemHealthRow:
    reports = {
        "steward": steward.status(),
        "watchtower": watchtower.status(),
        "marshal": marshal.status(),
        "dispatch": dispatch.status(),
    }
    connected = [name for name, r in reports.items() if r.status.value == "CONNECTED"]
    if len(connected) == len(reports):
        status = "CONNECTED"
    elif not connected:
        status = "NOT_CONNECTED"
    else:
        status = "DEGRADED"  # mixed: some real integrations up, some not
    detail = ", ".join(f"{name}={r.status.value}" for name, r in reports.items())
    return SystemHealthRow(subsystem="integrations", status=status, detail=detail, checked_at=_now())


def _readiness_row(readiness_store: ReadinessStore) -> SystemHealthRow:
    results = readiness_store.all_latest()
    if not results:
        return SystemHealthRow(
            subsystem="readiness",
            status="UNKNOWN",
            detail=f"No readiness evaluations recorded yet. Profiles available: "
            f"{', '.join(BUILTIN_PROFILES.keys())}.",
            checked_at=_now(),
        )
    # Latest result per (node_id, profile_id) — all_latest() returns up to the
    # 200 most recent rows across all nodes/profiles, so de-dupe to "current".
    latest: dict[tuple[str, str], str] = {}
    for r in results:
        key = (r.node_id, r.profile_id)
        if key not in latest:
            latest[key] = r.state.value
    total = len(latest)
    ready = sum(1 for s in latest.values() if s == "READY")
    not_ready = sum(1 for s in latest.values() if s in ("NOT_READY", "DEGRADED"))
    if not_ready:
        status = "NOT_READY" if any(s == "NOT_READY" for s in latest.values()) else "DEGRADED"
    elif ready < total:
        status = "READY_WITH_WARNING"
    else:
        status = "READY"
    return SystemHealthRow(
        subsystem="readiness",
        status=status,
        detail=f"{ready}/{total} node×profile evaluations currently READY",
        checked_at=_now(),
    )


def _audit_row(audit: AuditWriter) -> SystemHealthRow:
    try:
        total = audit.count()
        return SystemHealthRow(
            subsystem="audit_log",
            status="OK",
            detail=f"audit_log table reachable ({total} entries recorded).",
            checked_at=_now(),
        )
    except Exception as exc:  # noqa: BLE001 - report the real failure, never fabricate success
        return SystemHealthRow(
            subsystem="audit_log",
            status="FAILED",
            detail=f"{exc.__class__.__name__}: {exc}",
            checked_at=_now(),
        )


def _metrics_row(metrics: MetricsStore, collector: MetricsCollector) -> SystemHealthRow:
    """Reuses the real collector state (is it actually running right now?)
    and the real store (how many samples, how recent the latest one) — never
    a fake "collecting" status independent of whether the background thread
    is actually alive."""
    count = metrics.count()
    latest = metrics.latest()
    if collector.is_running():
        status = "OK"
        detail = f"collecting every {collector.interval_seconds}s, {count} sample(s) stored"
    elif count > 0:
        # Real samples exist but the background thread isn't currently
        # running (e.g. this process was constructed without the ASGI
        # lifespan protocol ever starting it, or it was explicitly stopped) —
        # worth flagging, since an operator relying on /metrics would want to
        # know collection has stalled.
        status = "DEGRADED"
        detail = f"collector not running; {count} sample(s) previously collected"
    else:
        status = "UNKNOWN"
        detail = "collector not running, no samples collected yet"
    if latest is not None:
        detail += f", last sample at {latest.sampled_at}"
    return SystemHealthRow(subsystem="metrics", status=status, detail=detail, checked_at=_now())


def _incidents_row(incidents: IncidentStore) -> SystemHealthRow:
    open_count = incidents.count_open()
    return SystemHealthRow(
        subsystem="incidents",
        status="DEGRADED" if open_count > 0 else "OK",
        detail=f"{open_count} open incident(s)" if open_count else "no open incidents",
        checked_at=_now(),
    )


def build_report(
    *,
    db: Database,
    processes: ProcessController,
    jobs: JobQueue,
    mesh: MeshProvider,
    steward: StewardAdapter,
    watchtower: WatchtowerAdapter,
    marshal: MarshalAdapter,
    dispatch: DispatchAdapter,
    readiness_store: ReadinessStore,
    audit: AuditWriter,
    incidents: IncidentStore,
    metrics: MetricsStore,
    metrics_collector: MetricsCollector,
) -> SystemHealthReport:
    """Runs every real subsystem check right now and assembles the report.
    Never returns a cached/previous result — every row's checked_at is set
    during this call."""
    rows = [
        _api_row(),
        _database_row(db),
        _jobs_row(jobs),
        _service_control_row(processes),
        _mesh_row(mesh),
        _integrations_row(steward, watchtower, marshal, dispatch),
        _readiness_row(readiness_store),
        _audit_row(audit),
        _incidents_row(incidents),
        _metrics_row(metrics, metrics_collector),
    ]
    return SystemHealthReport(rows=rows, generated_at=_now())
