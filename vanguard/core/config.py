"""Runtime configuration. Never hardcode secrets; everything comes from the environment."""
import os
from dataclasses import dataclass
from pathlib import Path


def _default_dispatch_dir() -> str:
    """Sibling-project layout on this machine: NCTIAPP/VANGUARD and
    NCTIAPP/Dispatch/D27HQ_DISPATCH live next to each other. Computed relative
    to this file's own location so it isn't tied to one absolute path."""
    return str(Path(__file__).resolve().parents[3] / "Dispatch" / "D27HQ_DISPATCH")


def _default_dispatch_python(dispatch_dir: str) -> str:
    if os.name == "nt":
        return str(Path(dispatch_dir) / ".venv" / "Scripts" / "python.exe")
    return str(Path(dispatch_dir) / ".venv" / "bin" / "python")


@dataclass(frozen=True)
class Settings:
    db_path: str
    api_token: str
    environment: str = "dev"
    dispatch_base_url: str = "http://127.0.0.1:8787"
    mesh_provider: str = "null"  # "null" or "netbird"
    netbird_base_url: str | None = None
    netbird_api_token: str | None = None
    node_stale_after_seconds: int = 300
    # Service Control: where the real local Dispatch process lives and which
    # interpreter runs it. Left blank by default on directly-constructed
    # Settings (e.g. in tests) so no managed process is auto-registered unless
    # from_env() (or the caller) explicitly supplies real paths.
    dispatch_dir: str = ""
    dispatch_python: str = ""
    # Job Queue: how many worker threads run queued jobs concurrently. A small
    # in-process ThreadPoolExecutor is the right size for this single-node
    # reference service — not a distributed queue.
    job_worker_count: int = 2
    job_export_dir: str = "./data/exports"
    # Backups: where real backup bundles land, and how many MANUAL backups to
    # keep before older ones are pruned (safety snapshots taken automatically
    # before a restore are not counted against this limit — see
    # vanguard/backup/manager.py).
    backup_dir: str = "./data/backups"
    backup_retain_count: int = 10
    # Metrics / observability: how often the background collector takes a real
    # local CPU/RAM/disk sample, and how many days of samples to keep before
    # older ones are pruned (see vanguard/metrics/collector.py).
    metrics_interval_seconds: int = 30
    metrics_retention_days: int = 7

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.environ.get("VANGUARD_API_TOKEN", "")
        environment = os.getenv("VANGUARD_ENVIRONMENT", "dev")
        if environment != "dev" and (len(token) < 24 or token == "REPLACE_WITH_RANDOM_SECRET"):
            raise RuntimeError(
                "Set VANGUARD_API_TOKEN to a random 24+ character secret outside dev; see README"
            )
        if not token:
            # dev-only fallback so the service can boot with zero config; mutating
            # routes still require this exact token, so it is not a real auth bypass.
            token = "dev-local-only-insecure-token-000000"
        dispatch_dir = os.getenv("VANGUARD_DISPATCH_DIR", "") or _default_dispatch_dir()
        dispatch_python = os.getenv("VANGUARD_DISPATCH_PYTHON", "") or _default_dispatch_python(dispatch_dir)
        return cls(
            db_path=os.getenv("VANGUARD_DB_PATH", "./data/vanguard.db"),
            api_token=token,
            environment=environment,
            dispatch_base_url=os.getenv("VANGUARD_DISPATCH_BASE_URL", "http://127.0.0.1:8787"),
            mesh_provider=os.getenv("VANGUARD_MESH_PROVIDER", "null"),
            netbird_base_url=os.environ.get("NETBIRD_BASE_URL") or None,
            netbird_api_token=os.environ.get("NETBIRD_API_TOKEN") or None,
            node_stale_after_seconds=int(os.getenv("VANGUARD_NODE_STALE_SECONDS", "300")),
            dispatch_dir=dispatch_dir,
            dispatch_python=dispatch_python,
            job_worker_count=int(os.getenv("VANGUARD_JOB_WORKERS", "2")),
            job_export_dir=os.getenv("VANGUARD_JOB_EXPORT_DIR", "./data/exports"),
            backup_dir=os.getenv("VANGUARD_BACKUP_DIR", "./data/backups"),
            backup_retain_count=int(os.getenv("VANGUARD_BACKUP_RETAIN_COUNT", "10")),
            metrics_interval_seconds=int(os.getenv("VANGUARD_METRICS_INTERVAL_SECONDS", "30")),
            metrics_retention_days=int(os.getenv("VANGUARD_METRICS_RETENTION_DAYS", "7")),
        )

    def validate(self) -> None:
        if len(self.api_token) < 24:
            raise ValueError("api_token must be at least 24 characters")
        if self.mesh_provider not in ("null", "netbird"):
            raise ValueError("mesh_provider must be 'null' or 'netbird'")
        if self.job_worker_count < 1:
            raise ValueError("job_worker_count must be at least 1")
        if self.backup_retain_count < 1:
            raise ValueError("backup_retain_count must be at least 1")
        if self.metrics_interval_seconds < 5:
            raise ValueError("metrics_interval_seconds must be at least 5")
        if self.metrics_retention_days < 1:
            raise ValueError("metrics_retention_days must be at least 1")
