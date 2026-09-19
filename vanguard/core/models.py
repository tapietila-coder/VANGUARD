"""Versioned Pydantic contracts for VANGUARD. Treat all external text as data, not instructions."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Capabilities / node classification
# --------------------------------------------------------------------------

class Capability(str, Enum):
    GPU_INFERENCE = "GPU_INFERENCE"
    CUDA = "CUDA"
    WINDOWS_BUILD = "WINDOWS_BUILD"
    LINUX_BUILD = "LINUX_BUILD"
    MACOS_BUILD = "MACOS_BUILD"
    DOCKER = "DOCKER"
    PYTHON_RUNTIME = "PYTHON_RUNTIME"
    NODE_RUNTIME = "NODE_RUNTIME"
    HIGH_MEMORY = "HIGH_MEMORY"
    HIGH_CORE_COUNT = "HIGH_CORE_COUNT"


class NodeLocality(str, Enum):
    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    UNKNOWN = "UNKNOWN"


class NodeStatus(str, Enum):
    ONLINE = "ONLINE"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class Node(StrictModel):
    schema_version: Literal[1] = 1
    node_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    hostname: str = Field(min_length=1, max_length=255)
    os_name: str = Field(min_length=1, max_length=64)
    os_version: str = Field(default="", max_length=128)
    architecture: str = Field(default="", max_length=32)
    cpu_model: str = Field(default="", max_length=200)
    cpu_cores_logical: int = Field(default=0, ge=0, le=4096)
    memory_total_mb: int = Field(default=0, ge=0)
    gpu_model: str | None = Field(default=None, max_length=200)
    gpu_vram_mb: int | None = Field(default=None, ge=0)
    capabilities: list[Capability] = Field(default_factory=list, max_length=32)
    locality: NodeLocality = NodeLocality.UNKNOWN
    status: NodeStatus = NodeStatus.UNKNOWN
    last_seen: str = Field(default_factory=utcnow)
    registered_at: str = Field(default_factory=utcnow)
    notes: str = Field(default="", max_length=2000)


class NodeRegister(StrictModel):
    """Input contract for registering/refreshing a node's inventory record."""
    node_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    hostname: str = Field(min_length=1, max_length=255)
    os_name: str = Field(min_length=1, max_length=64)
    os_version: str = Field(default="", max_length=128)
    architecture: str = Field(default="", max_length=32)
    cpu_model: str = Field(default="", max_length=200)
    cpu_cores_logical: int = Field(default=0, ge=0, le=4096)
    memory_total_mb: int = Field(default=0, ge=0)
    gpu_model: str | None = Field(default=None, max_length=200)
    gpu_vram_mb: int | None = Field(default=None, ge=0)
    capabilities: list[Capability] = Field(default_factory=list, max_length=32)
    locality: NodeLocality = NodeLocality.UNKNOWN
    notes: str = Field(default="", max_length=2000)


# --------------------------------------------------------------------------
# Services
# --------------------------------------------------------------------------

class ServiceKind(str, Enum):
    HTTP_API = "HTTP_API"
    BACKGROUND_WORKER = "BACKGROUND_WORKER"
    DATABASE = "DATABASE"
    MESH_CONTROLLER = "MESH_CONTROLLER"
    OTHER = "OTHER"


class Service(StrictModel):
    schema_version: Literal[1] = 1
    service_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=200)
    kind: ServiceKind = ServiceKind.OTHER
    node_id: str | None = Field(default=None, max_length=128)
    base_url: str | None = Field(default=None, max_length=500)
    health_path: str | None = Field(default=None, max_length=200)
    owner: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    registered_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)


class ServiceRegister(StrictModel):
    service_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=200)
    kind: ServiceKind = ServiceKind.OTHER
    node_id: str | None = Field(default=None, max_length=128)
    base_url: str | None = Field(default=None, max_length=500)
    health_path: str | None = Field(default=None, max_length=200)
    owner: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)


# --------------------------------------------------------------------------
# Managed processes (Service Control)
#
# A managed process is a superset of a plain `Service` record: it has every
# field a Service has (id/name/etc.) plus the extra control-plane data needed
# to actually start/stop/restart a real local OS process (argv, cwd, a
# health-check URL, and live runtime state). Registering one also upserts a
# matching row in the plain `services` table via ServiceRegistry, so it shows
# up in GET /services and resolveService() exactly like any other service —
# see vanguard/process_control/manager.py for exactly how that's wired.
# --------------------------------------------------------------------------

class ProcessState(str, Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ManagedProcessConfig(StrictModel):
    """Registration contract: how to launch/identify a controllable local process."""
    schema_version: Literal[1] = 1
    service_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=200)
    working_dir: str = Field(min_length=1, max_length=1000)
    command: list[str] = Field(min_length=1, max_length=32)
    health_url: str | None = Field(default=None, max_length=500)


class ManagedProcessStatus(StrictModel):
    """Current, honestly-timestamped control-plane view of a managed process.
    `last_checked` is always set alongside any reported state/health so a stale
    read is never presented as a live one."""
    schema_version: Literal[1] = 1
    service_id: str
    name: str
    working_dir: str
    command: list[str]
    health_url: str | None = None
    state: ProcessState = ProcessState.UNKNOWN
    pid: int | None = None
    started_at: str | None = None
    last_restart_at: str | None = None
    last_exit_code: int | None = None
    last_checked: str | None = None
    healthy: bool | None = None
    health_detail: str = ""
    log_path: str | None = None


# --------------------------------------------------------------------------
# Readiness
# --------------------------------------------------------------------------

class ReadinessState(str, Enum):
    READY = "READY"
    READY_WITH_WARNING = "READY_WITH_WARNING"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


class ReadinessCheckSpec(StrictModel):
    check_id: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    required_capability: Capability | None = None
    severity_if_missing: ReadinessState = ReadinessState.NOT_READY


class ReadinessProfile(StrictModel):
    schema_version: Literal[1] = 1
    profile_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    checks: list[ReadinessCheckSpec] = Field(min_length=1, max_length=50)


class ReadinessEvidence(StrictModel):
    check_id: str
    passed: bool
    detail: str = Field(default="", max_length=2000)


class ReadinessResult(StrictModel):
    schema_version: Literal[1] = 1
    node_id: str
    profile_id: str
    state: ReadinessState
    evidence: list[ReadinessEvidence] = Field(default_factory=list)
    evaluated_at: str = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Mesh (NetBird-shaped)
# --------------------------------------------------------------------------

class MeshPeerStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    UNKNOWN = "UNKNOWN"


class MeshPeer(StrictModel):
    peer_id: str
    name: str = ""
    ip: str | None = None
    connected: bool = False
    status: MeshPeerStatus = MeshPeerStatus.UNKNOWN
    last_seen: str | None = None
    os: str | None = None
    groups: list[str] = Field(default_factory=list)


class MeshRoute(StrictModel):
    route_id: str
    network: str
    peer_id: str | None = None
    enabled: bool = True
    groups: list[str] = Field(default_factory=list)


class MeshPolicy(StrictModel):
    policy_id: str
    name: str = ""
    enabled: bool = True
    description: str = ""


class Enrollment(StrictModel):
    """A one-time setup-key style enrollment record, mirroring NetBird setup-keys."""
    enrollment_id: str
    name: str = Field(min_length=1, max_length=200)
    expires_at: str | None = None
    used: bool = False
    created_at: str = Field(default_factory=utcnow)
    revoked: bool = False


class MeshConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    NOT_CONNECTED = "NOT_CONNECTED"
    UNKNOWN = "UNKNOWN"


class MeshStatus(StrictModel):
    provider: str
    status: MeshConnectionStatus
    detail: str = ""
    checked_at: str = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Infrastructure events / audit
# --------------------------------------------------------------------------

class InfrastructureEvent(StrictModel):
    schema_version: Literal[1] = 1
    event_id: int | None = None
    kind: str = Field(min_length=1, max_length=100)
    node_id: str | None = None
    service_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utcnow)


class AuditEntry(StrictModel):
    schema_version: Literal[1] = 1
    entry_id: int | None = None
    actor: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    target: str = Field(default="", max_length=200)
    source: str = Field(default="", max_length=100)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str = Field(default="", max_length=1000)
    created_at: str = Field(default_factory=utcnow)


class IntegrationStatus(str, Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    UNKNOWN = "UNKNOWN"


class IntegrationReport(StrictModel):
    """Uniform honest-status envelope returned by every integrations/*Adapter."""
    integration: str
    status: IntegrationStatus
    detail: str = ""
    checked_at: str = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Jobs (local in-process job queue)
#
# A real durable job record for the local ThreadPoolExecutor-backed queue in
# vanguard/jobs/. Every job actually executes a real registered Python
# callable against real VANGUARD state (see vanguard/jobs/job_types.py) — no
# job type here fakes its result. `progress` is a short free-text current-step
# string (e.g. "node 3/7") rather than a percentage, because none of the real
# job types below can honestly compute a meaningful 0-100 fraction ahead of
# time; a free-text step is the honest signal they can actually report.
# --------------------------------------------------------------------------

class JobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    RETRYING = "RETRYING"


class JobSubmit(StrictModel):
    """Input contract for submitting a new job. job_type is validated against
    the real job-type registry by the API layer, not here."""
    job_type: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)
    max_retries: int = Field(default=1, ge=0, le=10)


class Job(StrictModel):
    schema_version: Literal[1] = 1
    job_id: str = Field(min_length=1, max_length=64)
    job_type: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)
    state: JobState = JobState.QUEUED
    progress: str = Field(default="", max_length=500)
    result: dict[str, Any] | None = None
    error: str | None = Field(default=None, max_length=4000)
    retries: int = Field(default=0, ge=0)
    max_retries: int = Field(default=1, ge=0)
    requested_by: str = Field(default="", max_length=200)
    created_at: str = Field(default_factory=utcnow)
    started_at: str | None = None
    finished_at: str | None = None


# --------------------------------------------------------------------------
# System Health (aggregate)
#
# One row per real subsystem check. `status` is deliberately a plain string
# rather than one shared enum: each subsystem reuses whatever status
# vocabulary it already has elsewhere in this API (ProcessState for Service
# Control, MeshConnectionStatus for Mesh, IntegrationStatus for
# Steward/Watchtower/Marshal/Dispatch, ReadinessState for Readiness) so the
# existing UI color-coding (StatusBadge) applies unchanged with no new taxonomy
# invented. The generic checks that have no native status type of their own
# (API/Database/Jobs/Audit) use "OK" / "DEGRADED" / "FAILED", which the UI's
# StatusBadge already recognizes. `checked_at` is mandatory on every row —
# System Health never presents a status without saying how fresh it is.
# --------------------------------------------------------------------------

class SystemHealthRow(StrictModel):
    schema_version: Literal[1] = 1
    subsystem: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=50)
    detail: str = Field(default="", max_length=2000)
    checked_at: str = Field(default_factory=utcnow)


class SystemHealthReport(StrictModel):
    schema_version: Literal[1] = 1
    rows: list[SystemHealthRow]
    generated_at: str = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Backups / restore (vanguard/backup/)
#
# A real, self-contained backup bundle (backup-<timestamp>.zip under
# backup_dir) built from a real SQLite online backup
# (`sqlite3.Connection.backup()`, never a raw file copy of a live db).
# `sha256`/`size_bytes` are always computed from the actual bundle on disk at
# creation time; nothing here is ever fabricated. `file_exists` is computed
# fresh at read time (never stored) so a row whose file was deleted outside
# VANGUARD is reported honestly rather than silently hidden.
# --------------------------------------------------------------------------

class BackupRecord(StrictModel):
    schema_version: Literal[1] = 1
    backup_id: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1, max_length=1000)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    source_db_path: str = Field(min_length=1, max_length=1000)
    reason: str = Field(default="", max_length=200)
    created_at: str = Field(default_factory=utcnow)
    file_exists: bool = True


class BackupCreateRequest(StrictModel):
    reason: str = Field(default="manual", max_length=200)


class RestoreResult(StrictModel):
    """Real outcome of a completed restore. `safety_snapshot_id` is always a
    real backup of the live db taken immediately before the overwrite — never
    optional, never skipped — so an operator can always undo a restore."""
    schema_version: Literal[1] = 1
    restored_backup_id: str
    safety_snapshot_id: str
    verified_sha256: str
    restored_at: str = Field(default_factory=utcnow)
