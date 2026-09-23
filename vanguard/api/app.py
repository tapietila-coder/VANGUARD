"""FastAPI app. Read-only routes are unauthenticated (documented dev-only posture,
matching Dispatch's local-token pattern); mutating routes require a bearer token."""
import hmac
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException

from ..audit.writer import AuditWriter
from ..backup.manager import BackupFileMissingError, BackupManager, ChecksumMismatchError
from ..core.config import Settings
from ..core.db import Database
from ..core.models import (
    AuditEntry,
    BackupCreateRequest,
    IncidentActionRequest,
    IncidentEvent,
    IncidentStatus,
    JobSubmit,
    ManagedProcessConfig,
    MetricsCurrentResponse,
    MetricsHistoryResponse,
    NodeRegister,
    ServiceRegister,
    utcnow,
)
from ..incidents.detector import IncidentDetector
from ..incidents.store import IncidentStore
from ..integrations.adapters import DispatchAdapter, MarshalAdapter, StewardAdapter, WatchtowerAdapter
from ..jobs.job_types import JOB_REGISTRY, JobDeps
from ..jobs.queue import JobQueue
from ..mesh.provider import build_mesh_provider
from ..metrics.bucketing import bucket_samples
from ..metrics.collector import MetricsCollector
from ..metrics.store import MetricsStore
from ..nodeops.inventory import NodeInventory
from ..process_control.manager import ProcessController
from ..readiness.engine import ReadinessStore, evaluate
from ..readiness.profiles import BUILTIN_PROFILES
from ..service_map.registry import ServiceRegistry, resolveService
from ..system_health.aggregator import build_report as build_system_health_report


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    cfg.validate()
    db = Database(cfg.db_path)
    nodes = NodeInventory(db, stale_after_seconds=cfg.node_stale_after_seconds)
    services = ServiceRegistry(db)
    audit = AuditWriter(db)

    # Incidents / alerting: real-time correlation of real failure signals
    # already produced elsewhere (readiness, Service Control, Job Queue, the
    # Dispatch integration adapter) — see vanguard/incidents/detector.py for
    # exactly which signals and why. Constructed before the subsystems below
    # so its observe_* methods can be wired straight into their real
    # state-transition points (ReadinessStore.save(), ProcessController's
    # status builder, JobQueue's terminal-state update, DispatchAdapter.status())
    # rather than polling any of them after the fact.
    incident_store = IncidentStore(db)
    incidents = IncidentDetector(incident_store)

    readiness_store = ReadinessStore(db, on_save=incidents.observe_readiness)
    mesh = build_mesh_provider(cfg)
    dispatch_adapter = DispatchAdapter(cfg.dispatch_base_url, on_status=incidents.observe_dispatch)
    steward_adapter = StewardAdapter()
    watchtower_adapter = WatchtowerAdapter()
    marshal_adapter = MarshalAdapter()

    # Service Control: real start/stop/restart of actual local processes.
    # One real managed process is registered for this pass — the local Dispatch
    # API. Registration only happens when dispatch_dir/dispatch_python are set
    # (Settings.from_env() always computes real defaults; directly-constructed
    # Settings, as in tests, default them to "" so nothing is auto-registered).
    log_dir = os.path.join(os.path.dirname(cfg.db_path) or ".", "logs")
    processes = ProcessController(db, services, log_dir=log_dir, on_status=incidents.observe_process_status)
    if cfg.dispatch_dir and cfg.dispatch_python:
        processes.register(
            ManagedProcessConfig(
                service_id="dispatch",
                name="D27HQ Dispatch",
                working_dir=cfg.dispatch_dir,
                command=[cfg.dispatch_python, "-m", "dispatch", "serve"],
                health_url=f"{cfg.dispatch_base_url}/health",
            )
        )

    # Backups / restore: real sqlite3-online-backup bundles of VANGUARD's own
    # db under data/backups/. Creation is wired into the Job Queue below
    # (job_type "backup_create"); restore is deliberately its own synchronous,
    # bearer-token-protected route — too destructive for the background queue.
    backups = BackupManager(db, backup_dir=cfg.backup_dir, retain_count=cfg.backup_retain_count)

    # Metrics / observability: real local CPU/RAM/disk sampling for this one
    # machine (vanguard/metrics/). The collector's background thread is
    # started/stopped from the lifespan handler below, not here — so
    # constructing an app (as every test does) never spawns a background
    # thread unless that app is actually served/run under the ASGI lifespan
    # protocol (uvicorn.run(), or `with TestClient(app) as client:`).
    metrics_store = MetricsStore(db)
    metrics_collector = MetricsCollector(
        metrics_store,
        db_path=cfg.db_path,
        interval_seconds=cfg.metrics_interval_seconds,
        retention_days=cfg.metrics_retention_days,
    )

    # Job Queue: real local ThreadPoolExecutor-backed execution of the
    # registered job types (vanguard/jobs/job_types.py), acting on the exact
    # same live nodes/services/processes/audit/backups objects wired above.
    job_deps = JobDeps(
        nodes=nodes,
        services=services,
        processes=processes,
        readiness_store=readiness_store,
        audit=audit,
        export_dir=cfg.job_export_dir,
        backups=backups,
    )
    jobs = JobQueue(
        db, job_deps, registry=JOB_REGISTRY, worker_count=cfg.job_worker_count,
        on_terminal=incidents.observe_job,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        metrics_collector.start()
        yield
        metrics_collector.stop(wait=False)
        jobs.shutdown(wait=False)
        db.close()

    app = FastAPI(
        title="VANGUARD",
        version="0.1.0",
        lifespan=lifespan,
        description="D27HQ Infrastructure & Operational Readiness Directorate — local reference service.",
    )
    app.state.db = db
    app.state.nodes = nodes
    app.state.services = services
    app.state.mesh = mesh
    app.state.processes = processes
    app.state.jobs = jobs
    app.state.backups = backups
    app.state.incidents = incident_store
    app.state.metrics = metrics_store
    app.state.metrics_collector = metrics_collector

    def operator(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer ") or not hmac.compare_digest(
            authorization[7:], cfg.api_token
        ):
            raise HTTPException(status_code=401, detail="Operator bearer token required")

    # ---------------------------------------------------------------- health
    @app.get("/api/v1/vanguard/health")
    def health():
        return {"status": "ok", "mode": "single-node-local", "environment": cfg.environment}

    # ---------------------------------------------------------------- nodes
    @app.get("/api/v1/vanguard/nodes")
    def list_nodes():
        return [n.model_dump() for n in nodes.list()]

    @app.post("/api/v1/vanguard/nodes", dependencies=[Depends(operator)], status_code=201)
    def register_node(body: NodeRegister):
        before = nodes.get(body.node_id)
        node = nodes.register(body)
        audit.write(
            AuditEntry(
                actor="operator",
                action="node.register",
                target=node.node_id,
                source="api",
                before=before.model_dump() if before else None,
                after=node.model_dump(),
            )
        )
        return node.model_dump()

    @app.get("/api/v1/vanguard/nodes/{node_id}")
    def get_node(node_id: str):
        node = nodes.get(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return node.model_dump()

    @app.get("/api/v1/vanguard/nodes/{node_id}/readiness")
    def node_readiness(node_id: str, profile: str = "GENERAL_WORKER"):
        node = nodes.get(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        prof = BUILTIN_PROFILES.get(profile)
        if not prof:
            raise HTTPException(status_code=404, detail=f"Unknown readiness profile '{profile}'")
        result = evaluate(node, prof)
        readiness_store.save(result)
        return result.model_dump()

    # ------------------------------------------------------------- services
    @app.get("/api/v1/vanguard/services")
    def list_services():
        return [s.model_dump() for s in services.list()]

    @app.post("/api/v1/vanguard/services", dependencies=[Depends(operator)], status_code=201)
    def register_service(body: ServiceRegister):
        before = services.get(body.service_id)
        service = services.register(body)
        audit.write(
            AuditEntry(
                actor="operator",
                action="service.register",
                target=service.service_id,
                source="api",
                before=before.model_dump() if before else None,
                after=service.model_dump(),
            )
        )
        return service.model_dump()

    @app.get("/api/v1/vanguard/services/{service_id}")
    def get_service(service_id: str):
        service = resolveService(services, service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        return service.model_dump()

    # ------------------------------------------------------- process control
    @app.get("/api/v1/vanguard/services/{service_id}/process")
    def get_process(service_id: str):
        try:
            return processes.status(service_id).model_dump()
        except KeyError:
            raise HTTPException(status_code=404, detail="No managed process registered for this service")

    @app.post("/api/v1/vanguard/services/{service_id}/start", dependencies=[Depends(operator)])
    def start_process(service_id: str, reason: str = ""):
        try:
            before = processes.status(service_id, check_health=False).model_dump()
        except KeyError:
            raise HTTPException(status_code=404, detail="No managed process registered for this service")
        after = processes.start(service_id)
        audit.write(
            AuditEntry(
                actor="operator", action="process.start", target=service_id, source="api",
                before=before, after=after.model_dump(), reason=reason,
            )
        )
        return after.model_dump()

    @app.post("/api/v1/vanguard/services/{service_id}/stop", dependencies=[Depends(operator)])
    def stop_process(service_id: str, reason: str = ""):
        try:
            before = processes.status(service_id, check_health=False).model_dump()
        except KeyError:
            raise HTTPException(status_code=404, detail="No managed process registered for this service")
        after = processes.stop(service_id)
        audit.write(
            AuditEntry(
                actor="operator", action="process.stop", target=service_id, source="api",
                before=before, after=after.model_dump(), reason=reason,
            )
        )
        return after.model_dump()

    @app.post("/api/v1/vanguard/services/{service_id}/restart", dependencies=[Depends(operator)])
    def restart_process(service_id: str, reason: str = ""):
        try:
            before = processes.status(service_id, check_health=False).model_dump()
        except KeyError:
            raise HTTPException(status_code=404, detail="No managed process registered for this service")
        after = processes.restart(service_id)
        audit.write(
            AuditEntry(
                actor="operator", action="process.restart", target=service_id, source="api",
                before=before, after=after.model_dump(), reason=reason,
            )
        )
        return after.model_dump()

    @app.get("/api/v1/vanguard/services/{service_id}/logs")
    def process_logs(service_id: str, lines: int = 100):
        try:
            entries = processes.logs(service_id, lines=lines)
        except KeyError:
            raise HTTPException(status_code=404, detail="No managed process registered for this service")
        return {"service_id": service_id, "lines": entries}

    # ------------------------------------------------------------------- logs
    @app.get("/api/v1/vanguard/logs")
    def list_log_sources():
        """Every real managed process and its actual `data/logs/*.log` file
        state (exists/size/last-modified/line count) — the cross-service index
        the /logs UI page renders. No fabricated services: this is exactly
        `processes.list_configs()`, which only ever contains processes that
        were really registered via Service Control."""
        return processes.log_sources()

    # ------------------------------------------------------------------ mesh
    @app.get("/api/v1/vanguard/mesh/status")
    def mesh_status():
        return mesh.health().model_dump()

    @app.get("/api/v1/vanguard/mesh/peers")
    def mesh_peers():
        return [p.model_dump() for p in mesh.list_nodes()]

    @app.get("/api/v1/vanguard/mesh/routes")
    def mesh_routes():
        return [r.model_dump() for r in mesh.list_routes()]

    @app.get("/api/v1/vanguard/mesh/policies")
    def mesh_policies():
        return [p.model_dump() for p in mesh.list_policies()]

    @app.post("/api/v1/vanguard/mesh/enrollments", dependencies=[Depends(operator)], status_code=201)
    def create_enrollment(name: str):
        enrollment = mesh.create_enrollment(name)
        audit.write(
            AuditEntry(actor="operator", action="mesh.enrollment.create", target=name, source="api")
        )
        return enrollment.model_dump()

    @app.delete("/api/v1/vanguard/mesh/enrollments/{enrollment_id}", dependencies=[Depends(operator)])
    def revoke_enrollment(enrollment_id: str):
        ok = mesh.revoke_node(enrollment_id)
        audit.write(
            AuditEntry(actor="operator", action="mesh.enrollment.revoke", target=enrollment_id, source="api")
        )
        return {"revoked": ok}

    @app.post("/api/v1/vanguard/nodes/{node_id}/revoke", dependencies=[Depends(operator)])
    def revoke_node(node_id: str):
        ok = mesh.revoke_node(node_id)
        audit.write(AuditEntry(actor="operator", action="node.revoke", target=node_id, source="api"))
        return {"revoked": ok}

    # -------------------------------------------------------------- readiness
    @app.get("/api/v1/vanguard/readiness")
    def readiness_overview():
        results = readiness_store.all_latest()
        return {
            "profiles": list(BUILTIN_PROFILES.keys()),
            "recent_results": [r.model_dump() for r in results],
        }

    # ------------------------------------------------------------ integrations
    @app.get("/api/v1/vanguard/integrations")
    def integrations_status():
        return {
            "steward": steward_adapter.status().model_dump(),
            "watchtower": watchtower_adapter.status().model_dump(),
            "marshal": marshal_adapter.status().model_dump(),
            "dispatch": dispatch_adapter.status().model_dump(),
        }

    # ------------------------------------------------------------ system health
    @app.get("/api/v1/vanguard/system-health")
    def system_health():
        """One real check per real internal subsystem (vanguard/system_health/
        aggregator.py), assembled server-side into a single honestly-timestamped
        snapshot for the /system-health operator page. Read-only, unauthenticated,
        same posture as /health and /integrations."""
        report = build_system_health_report(
            db=db,
            processes=processes,
            jobs=jobs,
            mesh=mesh,
            steward=steward_adapter,
            watchtower=watchtower_adapter,
            marshal=marshal_adapter,
            dispatch=dispatch_adapter,
            readiness_store=readiness_store,
            audit=audit,
            incidents=incident_store,
            metrics=metrics_store,
            metrics_collector=metrics_collector,
        )
        return report.model_dump()

    # ------------------------------------------------------------------ jobs
    @app.get("/api/v1/vanguard/jobs")
    def list_jobs(state: str | None = None, job_type: str | None = None):
        return [j.model_dump() for j in jobs.store.list(state=state, job_type=job_type)]

    @app.get("/api/v1/vanguard/jobs/{job_id}")
    def get_job(job_id: str):
        job = jobs.store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.model_dump()

    @app.post("/api/v1/vanguard/jobs", dependencies=[Depends(operator)], status_code=201)
    def submit_job(body: JobSubmit):
        if body.job_type not in jobs.registry:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown job_type '{body.job_type}'; registered types: {sorted(jobs.registry)}",
            )
        job = jobs.submit(
            job_type=body.job_type, params=body.params, requested_by="operator", max_retries=body.max_retries
        )
        audit.write(
            AuditEntry(
                actor="operator", action="job.submit", target=job.job_id, source="api",
                after=job.model_dump(),
            )
        )
        return job.model_dump()

    @app.post("/api/v1/vanguard/jobs/{job_id}/cancel", dependencies=[Depends(operator)])
    def cancel_job(job_id: str):
        try:
            before = jobs.store.get(job_id)
            if before is None:
                raise HTTPException(status_code=404, detail="Job not found")
            after = jobs.cancel(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Job not found")
        audit.write(
            AuditEntry(
                actor="operator", action="job.cancel", target=job_id, source="api",
                before=before.model_dump(), after=after.model_dump(),
            )
        )
        return after.model_dump()

    @app.post("/api/v1/vanguard/jobs/{job_id}/retry", dependencies=[Depends(operator)])
    def retry_job(job_id: str):
        before = jobs.store.get(job_id)
        if before is None:
            raise HTTPException(status_code=404, detail="Job not found")
        try:
            after = jobs.retry(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        audit.write(
            AuditEntry(
                actor="operator", action="job.retry", target=job_id, source="api",
                before=before.model_dump(), after=after.model_dump(),
            )
        )
        return after.model_dump()

    # --------------------------------------------------------------- backups
    @app.get("/api/v1/vanguard/backups")
    def list_backups():
        return [b.model_dump() for b in backups.list_backups()]

    @app.get("/api/v1/vanguard/backups/{backup_id}")
    def get_backup(backup_id: str):
        record = backups.get_backup(backup_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Backup not found")
        return record.model_dump()

    @app.post("/api/v1/vanguard/backups", dependencies=[Depends(operator)], status_code=202)
    def create_backup(body: BackupCreateRequest = BackupCreateRequest()):
        """Submits a real `backup_create` job to the existing Job Queue and
        returns the job (job-queue-based, not synchronous-direct, so an
        operator gets progress/result the same way every other real job type
        already reports it — see vanguard/jobs/job_types.py). Poll
        GET /jobs/{id} for completion; the finished job's `result` is the
        real BackupRecord."""
        job = jobs.submit(
            job_type="backup_create", params={"reason": body.reason}, requested_by="operator", max_retries=0
        )
        audit.write(
            AuditEntry(
                actor="operator", action="backup.create.submit", target=job.job_id, source="api",
                after=job.model_dump(), reason=body.reason,
            )
        )
        return job.model_dump()

    @app.post("/api/v1/vanguard/backups/{backup_id}/restore", dependencies=[Depends(operator)])
    def restore_backup(backup_id: str, reason: str = ""):
        """Synchronous, not job-queue-based — restore is destructive enough
        that it must run to completion (or fail) within this one request, not
        be picked up later by a background worker. See
        vanguard/backup/manager.py for the exact checksum-verify /
        safety-snapshot / connection-swap sequence."""
        before_record = backups.get_backup(backup_id)
        try:
            result = backups.restore_backup(backup_id, reason=reason)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Backup not found")
        except BackupFileMissingError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except ChecksumMismatchError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        audit.write(
            AuditEntry(
                actor="operator", action="backup.restore", target=backup_id, source="api",
                before=before_record.model_dump() if before_record else None,
                after=result.model_dump(), reason=reason,
            )
        )
        return result.model_dump()

    @app.delete("/api/v1/vanguard/backups/{backup_id}", dependencies=[Depends(operator)])
    def delete_backup(backup_id: str, reason: str = ""):
        before_record = backups.get_backup(backup_id)
        if before_record is None:
            raise HTTPException(status_code=404, detail="Backup not found")
        deleted = backups.delete_backup(backup_id)
        audit.write(
            AuditEntry(
                actor="operator", action="backup.delete", target=backup_id, source="api",
                before=before_record.model_dump(), reason=reason,
            )
        )
        return {"deleted": deleted, "backup_id": backup_id}

    # ----------------------------------------------------------------- audit
    @app.get("/api/v1/vanguard/audit", dependencies=[Depends(operator)])
    def audit_log(
        limit: int = 100,
        offset: int = 0,
        actor: str | None = None,
        action: str | None = None,
        target: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ):
        entries = audit.list(
            limit=limit, offset=offset, actor=actor, action=action, target=target, since=since, until=until
        )
        total = audit.count(actor=actor, action=action, target=target, since=since, until=until)
        return {
            "entries": [a.model_dump() for a in entries],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # ------------------------------------------------------------- incidents
    @app.get("/api/v1/vanguard/incidents")
    def list_incidents(status: str | None = None, severity: str | None = None):
        """Real incidents correlated by vanguard/incidents/detector.py from
        real readiness/Service Control/Job Queue/Dispatch-integration failure
        signals — never a fabricated alert source. Unauthenticated read, same
        posture as every other list route."""
        return [i.model_dump() for i in incident_store.list(status=status, severity=severity)]

    @app.get("/api/v1/vanguard/incidents/{incident_id}")
    def get_incident(incident_id: str):
        incident = incident_store.get(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return incident.model_dump()

    @app.post("/api/v1/vanguard/incidents/{incident_id}/acknowledge", dependencies=[Depends(operator)])
    def acknowledge_incident(incident_id: str, body: IncidentActionRequest = IncidentActionRequest()):
        incident = incident_store.get(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        before = incident.model_dump()
        now = utcnow()
        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_by = "operator"
        incident.acknowledged_at = now
        incident.last_seen = now
        incident.timeline.append(
            IncidentEvent(kind="acknowledged", detail=body.reason, actor="operator", created_at=now)
        )
        updated = incident_store.update(incident)
        audit.write(
            AuditEntry(
                actor="operator", action="incident.acknowledge", target=incident_id, source="api",
                before=before, after=updated.model_dump(), reason=body.reason,
            )
        )
        return updated.model_dump()

    @app.post("/api/v1/vanguard/incidents/{incident_id}/resolve", dependencies=[Depends(operator)])
    def resolve_incident(incident_id: str, body: IncidentActionRequest = IncidentActionRequest()):
        incident = incident_store.get(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        before = incident.model_dump()
        now = utcnow()
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now
        incident.last_seen = now
        incident.timeline.append(
            IncidentEvent(kind="resolved", detail=body.reason, actor="operator", created_at=now)
        )
        updated = incident_store.update(incident)
        audit.write(
            AuditEntry(
                actor="operator", action="incident.resolve", target=incident_id, source="api",
                before=before, after=updated.model_dump(), reason=body.reason,
            )
        )
        return updated.model_dump()

    # ------------------------------------------------------------------ metrics
    @app.get("/api/v1/vanguard/metrics/current")
    def metrics_current():
        """The most recent real local CPU/RAM/disk sample (vanguard/metrics/),
        plus honest collector status. `sample` is None in the real early-
        startup window before the very first sample has landed — never a
        fabricated placeholder. Read-only, unauthenticated, same posture as
        /system-health."""
        sample = metrics_store.latest()
        return MetricsCurrentResponse(
            sample=sample,
            collector_running=metrics_collector.is_running(),
            interval_seconds=metrics_collector.interval_seconds,
            sample_count=metrics_store.count(),
        ).model_dump()

    @app.get("/api/v1/vanguard/metrics/history")
    def metrics_history(since: str | None = None, until: str | None = None, interval: int | None = None):
        """Real stored samples in [since, until] (ISO-8601, same lexical-
        comparison convention as /audit's since/until), oldest-first. When
        `interval` (seconds) is given, samples are downsampled into that many
        real averaged buckets (vanguard/metrics/bucketing.py) so a long range
        doesn't hand back thousands of raw rows to chart; omit it to get the
        raw stored samples in range."""
        if interval is not None and interval < 1:
            raise HTTPException(status_code=400, detail="interval must be at least 1 second")
        raw = metrics_store.query(since=since, until=until)
        samples = bucket_samples(raw, interval) if interval else raw
        return MetricsHistoryResponse(
            samples=samples,
            bucketed=bool(interval),
            interval_seconds=interval,
            since=since,
            until=until,
        ).model_dump()

    return app


def app_factory():
    return create_app()
