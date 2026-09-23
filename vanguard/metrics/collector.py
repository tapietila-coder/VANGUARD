"""Real periodic local resource-usage sampling.

`sample_now()` is the one real sampling function — it takes an actual reading
of this machine's CPU%, RAM used/total (via `psutil`, the same optional
dependency `vanguard/nodeops/detect.py` already uses — left None, never
guessed, when psutil isn't installed) and disk used/total for the volume
holding VANGUARD's own data directory (via the stdlib `shutil.disk_usage()`,
always available), stores it, and applies retention. It is exposed
separately from the background loop specifically so tests can call it
directly/synchronously instead of waiting on a real timer.

`start()`/`stop()` run that same function on a small background thread (the
same "one dedicated worker thread with a stop Event" shape as every other
long-running loop in this codebase) on a configurable interval
(`VANGUARD_METRICS_INTERVAL_SECONDS`, default 30s). The very first sample is
taken synchronously inside `start()` rather than only after the first
interval elapses, so an operator who just started VANGUARD sees real data on
`/metrics` immediately instead of staring at an empty page for 30s.

Retention: rather than a separate scheduled pruning sweep, this module prunes
samples older than `retention_days` (`VANGUARD_METRICS_RETENTION_DAYS`,
default 7) after every single insert — simple, real, and self-correcting even
if the collector was stopped for a while and only just resumed. This is a
deliberate, documented choice, not an oversight: a dedicated retention job
would be more precise about *when* pruning happens, but for a local
single-node reference service sampling at a 30s-scale cadence, "prune a
little after every insert" keeps the table bounded without adding a second
background thread.
"""
from __future__ import annotations

import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core.models import MetricSample
from .store import MetricsStore

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - exercised in envs without psutil
    psutil = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _disk_probe_path(db_path: str) -> str:
    """The volume actually worth reporting on: wherever VANGUARD's own SQLite
    file lives, not an arbitrary root — that's the disk an operator running
    this service actually cares about filling up."""
    directory = Path(db_path).resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory)


class MetricsCollector:
    def __init__(
        self,
        store: MetricsStore,
        db_path: str,
        interval_seconds: int = 30,
        retention_days: int = 7,
    ):
        self.store = store
        self.disk_path = _disk_probe_path(db_path)
        self.interval_seconds = max(5, interval_seconds)
        self.retention_days = max(1, retention_days)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------- sampling
    def sample_now(self) -> MetricSample:
        """Takes one real sample right now, stores it, applies retention, and
        returns it. Safe to call directly (as tests do) regardless of whether
        the background loop is running."""
        cpu_percent: float | None = None
        ram_used_mb: int | None = None
        ram_total_mb: int | None = None
        if psutil is not None:
            # interval=None: a real, non-blocking reading against psutil's own
            # internal last-call baseline — never sleeps the caller, unlike
            # interval=<seconds>. The very first call in a process's lifetime
            # can report 0.0 until a second call has a baseline to compare
            # against; that is psutil's own documented behavior, not a bug
            # introduced here.
            cpu_percent = float(psutil.cpu_percent(interval=None))
            vm = psutil.virtual_memory()
            ram_used_mb = int(vm.used / (1024 * 1024))
            ram_total_mb = int(vm.total / (1024 * 1024))

        usage = shutil.disk_usage(self.disk_path)
        disk_used_mb = int(usage.used / (1024 * 1024))
        disk_total_mb = int(usage.total / (1024 * 1024))

        sample = MetricSample(
            cpu_percent=cpu_percent,
            ram_used_mb=ram_used_mb,
            ram_total_mb=ram_total_mb,
            disk_used_mb=disk_used_mb,
            disk_total_mb=disk_total_mb,
            disk_path=self.disk_path,
            sampled_at=_now(),
        )
        self.store.insert(sample)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        self.store.prune_older_than(cutoff)
        return sample

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        # Real first sample synchronously, before the loop even starts, so
        # /metrics/current has real data the instant VANGUARD boots rather
        # than after a full interval has elapsed.
        self.sample_now()
        self._thread = threading.Thread(target=self._loop, name="vanguard-metrics", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            try:
                self.sample_now()
            except Exception:  # noqa: BLE001 - a failed sample must never kill the loop
                pass

    def stop(self, wait: bool = False) -> None:
        self._stop_event.set()
        if wait and self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 2)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
