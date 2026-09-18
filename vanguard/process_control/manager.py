"""Real local process control: start/stop/restart/health-check for locally
registered processes (e.g. the Dispatch API). Uses `subprocess.Popen` with an
argv list — never `shell=True`, never a raw `taskkill` shell-out — and
captures the child's stdout/stderr to a rotating per-service log file under
`data/logs/`. Termination is graceful (`terminate()` then a timeout before
escalating to `kill()`), matching this repo's "no destructive/irreversible
surprises" posture as closely as killing a process can.

A managed process is a superset of a plain `Service` record (see
core/models.py for the exact rationale): this module owns a `managed_processes`
SQLite table with the extra control-plane fields (argv, cwd, health probe,
live runtime state), and upserts a matching row into the existing
`services` table via `ServiceRegistry` on registration so the process is
still visible through every read-only /services route unchanged.

`last_checked` is always refreshed alongside any reported state or health
result — this repo's existing honesty rule (no stale state presented as
live) applies here exactly as it does to node/readiness/mesh status.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..core.db import Database, dumps, loads
from ..core.models import (
    ManagedProcessConfig,
    ManagedProcessStatus,
    ProcessState,
    ServiceKind,
    ServiceRegister,
)
from ..service_map.registry import ServiceRegistry

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - exercised in envs without psutil
    psutil = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pid_alive(pid: int | None) -> bool:
    """Portable "is this PID still a live process" check. Prefers psutil
    (already an optional dependency of this project); falls back to a
    Windows-native OpenProcess probe, then to POSIX os.kill(pid, 0)."""
    if not pid or pid <= 0:
        return False
    if psutil is not None:
        return psutil.pid_exists(pid)
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _rotate_log(path: Path, max_bytes: int = 5_000_000, backups: int = 3) -> None:
    """Simple size-based rotation, run right before a fresh spawn: path ->
    path.1 -> path.2 -> ... so an operator can always see recent output
    after a restart without an unbounded log file."""
    if not path.exists() or path.stat().st_size < max_bytes:
        return
    for i in range(backups - 1, 0, -1):
        older = Path(f"{path}.{i}")
        newer = Path(f"{path}.{i + 1}")
        if older.exists():
            older.replace(newer)
    path.replace(Path(f"{path}.1"))


def _load_env_file(path: Path) -> dict[str, str]:
    """Best-effort parse of a KEY=VALUE .env file — used ONLY to build a
    spawned child's environment (mirrors what the target project's own README
    tells an operator to do by hand). Never modifies, logs, or persists the
    file's contents anywhere; the parsed values never enter VANGUARD's own
    audit log, database, or API responses."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    except OSError:
        pass
    return out


def _default_runtime() -> dict:
    return {
        "state": ProcessState.STOPPED.value,
        "pid": None,
        "started_at": None,
        "last_restart_at": None,
        "last_exit_code": None,
        "last_checked": None,
        "healthy": None,
        "health_detail": "",
    }


class ProcessController:
    def __init__(self, db: Database, services: ServiceRegistry, log_dir: str):
        self.db = db
        self.services = services
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._procs: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ registration
    def register(self, cfg: ManagedProcessConfig) -> ManagedProcessStatus:
        with self.db.cursor() as cur:
            cur.execute("SELECT runtime FROM managed_processes WHERE service_id = ?", (cfg.service_id,))
            row = cur.fetchone()
            runtime = loads(row["runtime"]) if row else _default_runtime()
            cur.execute(
                "INSERT INTO managed_processes (service_id, config, runtime, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(service_id) DO UPDATE SET config=excluded.config, updated_at=excluded.updated_at",
                (cfg.service_id, dumps(cfg.model_dump()), dumps(runtime), _now()),
            )
        # Superset relationship with the plain service registry (see module docstring).
        base_url = None
        health_path = None
        if cfg.health_url and cfg.health_url.endswith("/health"):
            base_url = cfg.health_url[: -len("/health")] or None
            health_path = "/health"
        self.services.register(
            ServiceRegister(
                service_id=cfg.service_id,
                name=cfg.name,
                kind=ServiceKind.HTTP_API if cfg.health_url else ServiceKind.OTHER,
                base_url=base_url,
                health_path=health_path,
                owner="vanguard.process_control",
                description=f"Managed local process: {' '.join(cfg.command)} (cwd={cfg.working_dir})",
            )
        )
        return self.status(cfg.service_id, check_health=False)

    def get_config(self, service_id: str) -> ManagedProcessConfig | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT config FROM managed_processes WHERE service_id = ?", (service_id,))
            row = cur.fetchone()
        return ManagedProcessConfig.model_validate(loads(row["config"])) if row else None

    def _get_runtime(self, service_id: str) -> dict:
        with self.db.cursor() as cur:
            cur.execute("SELECT runtime FROM managed_processes WHERE service_id = ?", (service_id,))
            row = cur.fetchone()
        return loads(row["runtime"]) if row else _default_runtime()

    def _save_runtime(self, service_id: str, runtime: dict) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE managed_processes SET runtime = ?, updated_at = ? WHERE service_id = ?",
                (dumps(runtime), _now(), service_id),
            )

    def _log_path(self, service_id: str) -> Path:
        return self.log_dir / f"{service_id}.log"

    def _is_running(self, service_id: str, runtime: dict) -> bool:
        proc = self._procs.get(service_id)
        if proc is not None:
            return proc.poll() is None
        return pid_alive(runtime.get("pid"))

    # ------------------------------------------------------------------ control
    def start(self, service_id: str) -> ManagedProcessStatus:
        cfg = self.get_config(service_id)
        if cfg is None:
            raise KeyError(service_id)
        with self._lock:
            runtime = self._get_runtime(service_id)
            if self._is_running(service_id, runtime):
                # Idempotent: already running, no duplicate spawn.
                runtime["state"] = ProcessState.RUNNING.value
                runtime["last_checked"] = _now()
                self._save_runtime(service_id, runtime)
                return self._build_status(cfg, runtime)

            log_path = self._log_path(service_id)
            _rotate_log(log_path)
            env = dict(os.environ)
            env.update(_load_env_file(Path(cfg.working_dir) / ".env"))

            try:
                logf = open(log_path, "ab", buffering=0)
                proc = subprocess.Popen(
                    cfg.command,
                    cwd=cfg.working_dir,
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    env=env,
                )
            except OSError as exc:
                now = _now()
                runtime.update(
                    state=ProcessState.FAILED.value,
                    pid=None,
                    last_checked=now,
                    healthy=False,
                    health_detail=f"spawn failed: {exc.__class__.__name__}: {exc}",
                )
                self._save_runtime(service_id, runtime)
                return self._build_status(cfg, runtime)

            self._procs[service_id] = proc
            # Give an immediately-crashing process a brief moment to fail so we
            # don't report RUNNING for something that already exited.
            time.sleep(0.25)
            exited = proc.poll()
            now = _now()
            if exited is not None:
                self._procs.pop(service_id, None)
                runtime.update(
                    state=ProcessState.FAILED.value,
                    pid=proc.pid,
                    started_at=now,
                    last_exit_code=exited,
                    last_checked=now,
                    healthy=False,
                    health_detail=f"process exited immediately with code {exited}; see {log_path}",
                )
            else:
                runtime.update(
                    state=ProcessState.RUNNING.value,
                    pid=proc.pid,
                    started_at=now,
                    last_exit_code=None,
                    last_checked=now,
                    healthy=None,
                    health_detail="",
                )
            self._save_runtime(service_id, runtime)
            return self._build_status(cfg, runtime)

    def stop(self, service_id: str, grace_seconds: float = 5.0) -> ManagedProcessStatus:
        cfg = self.get_config(service_id)
        if cfg is None:
            raise KeyError(service_id)
        with self._lock:
            runtime = self._get_runtime(service_id)
            if not self._is_running(service_id, runtime):
                # Idempotent: already stopped (or crashed), nothing to terminate.
                runtime["state"] = ProcessState.STOPPED.value
                runtime["pid"] = None
                runtime["last_checked"] = _now()
                self._save_runtime(service_id, runtime)
                return self._build_status(cfg, runtime)

            runtime["state"] = ProcessState.STOPPING.value
            self._save_runtime(service_id, runtime)

            proc = self._procs.get(service_id)
            pid = runtime.get("pid")
            exit_code = None
            if proc is not None:
                proc.terminate()
                try:
                    exit_code = proc.wait(timeout=grace_seconds)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    exit_code = proc.wait(timeout=grace_seconds)
                self._procs.pop(service_id, None)
            elif pid:
                self._terminate_by_pid(pid, grace_seconds)

            now = _now()
            still_alive = pid_alive(pid) if pid else False
            runtime.update(
                state=ProcessState.FAILED.value if still_alive else ProcessState.STOPPED.value,
                pid=pid if still_alive else None,
                last_exit_code=exit_code,
                last_checked=now,
                healthy=False,
                health_detail=(
                    "process did not exit after terminate()+kill()" if still_alive else ""
                ),
            )
            self._save_runtime(service_id, runtime)
            return self._build_status(cfg, runtime)

    def _terminate_by_pid(self, pid: int, grace_seconds: float) -> None:
        """Terminate a process VANGUARD doesn't hold a live Popen handle for
        (e.g. it was started by a prior VANGUARD run before this one restarted).
        Uses psutil when available; otherwise this is a documented limitation
        rather than falling back to a raw taskkill shell-out."""
        if psutil is None:
            return
        try:
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(timeout=grace_seconds)
            except psutil.TimeoutExpired:
                p.kill()
                p.wait(timeout=grace_seconds)
        except psutil.NoSuchProcess:
            pass

    def restart(self, service_id: str) -> ManagedProcessStatus:
        self.stop(service_id)
        self.start(service_id)
        with self._lock:
            runtime = self._get_runtime(service_id)
            runtime["last_restart_at"] = _now()
            self._save_runtime(service_id, runtime)
            return self._build_status(self.get_config(service_id), runtime)

    # ------------------------------------------------------------------- status
    def status(self, service_id: str, check_health: bool = True) -> ManagedProcessStatus:
        cfg = self.get_config(service_id)
        if cfg is None:
            raise KeyError(service_id)
        with self._lock:
            runtime = self._get_runtime(service_id)
            running = self._is_running(service_id, runtime)
            now = _now()
            if not running and runtime.get("state") == ProcessState.RUNNING.value:
                proc = self._procs.pop(service_id, None)
                exit_code = proc.poll() if proc is not None else None
                runtime.update(
                    state=ProcessState.FAILED.value,
                    pid=None,
                    last_exit_code=exit_code,
                    healthy=False,
                    health_detail="process is no longer alive (crashed or was killed outside VANGUARD)",
                )
            elif running:
                runtime["state"] = ProcessState.RUNNING.value

            if check_health:
                healthy, detail = self._check_health(cfg, running)
                runtime["healthy"] = healthy
                runtime["health_detail"] = detail
            runtime["last_checked"] = now
            self._save_runtime(service_id, runtime)
            return self._build_status(cfg, runtime)

    def _check_health(self, cfg: ManagedProcessConfig, running: bool) -> tuple[bool | None, str]:
        if not running:
            return False, "process not running"
        if cfg.health_url:
            try:
                req = urllib.request.Request(cfg.health_url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    resp.read()
                return True, f"health check ok at {cfg.health_url}"
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                return False, f"health check failed at {cfg.health_url}: {exc.__class__.__name__}: {exc}"
        return True, "no health_url configured; PID liveness used as the health signal"

    # -------------------------------------------------------------------- logs
    def logs(self, service_id: str, lines: int = 100) -> list[str]:
        cfg = self.get_config(service_id)
        if cfg is None:
            raise KeyError(service_id)
        log_path = self._log_path(service_id)
        if not log_path.exists():
            return []
        with open(log_path, "rb") as f:
            data = f.read()
        text = data.decode("utf-8", errors="replace")
        all_lines = text.splitlines()
        if lines <= 0:
            return all_lines
        return all_lines[-lines:]

    # ------------------------------------------------------------------- build
    def _build_status(self, cfg: ManagedProcessConfig, runtime: dict) -> ManagedProcessStatus:
        return ManagedProcessStatus(
            service_id=cfg.service_id,
            name=cfg.name,
            working_dir=cfg.working_dir,
            command=cfg.command,
            health_url=cfg.health_url,
            state=ProcessState(runtime.get("state") or ProcessState.UNKNOWN.value),
            pid=runtime.get("pid"),
            started_at=runtime.get("started_at"),
            last_restart_at=runtime.get("last_restart_at"),
            last_exit_code=runtime.get("last_exit_code"),
            last_checked=runtime.get("last_checked"),
            healthy=runtime.get("healthy"),
            health_detail=runtime.get("health_detail", ""),
            log_path=str(self._log_path(cfg.service_id)),
        )
