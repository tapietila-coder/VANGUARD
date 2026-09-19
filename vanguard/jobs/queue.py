"""Real job execution: a small ThreadPoolExecutor picks up submitted jobs and
actually runs their registered callable (vanguard/jobs/job_types.py) on a
worker thread, capturing real progress/result/error into the jobs table
(vanguard/jobs/store.py). Cancellation is cooperative — a job callable checks
for it every time it calls report_progress — and retry re-queues a real rerun
of a FAILED job, up to max_retries.
"""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from ..core.db import Database
from ..core.models import Job, JobState
from .job_types import JOB_REGISTRY, JobCallable, JobDeps, JobRunContext
from .store import JobStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobCanceled(Exception):
    """Raised inside report_progress() when a job's cancellation flag is set;
    caught by the worker loop and turned into a real CANCELED state."""


class JobQueue:
    def __init__(
        self,
        db: Database,
        deps: JobDeps,
        registry: dict[str, JobCallable] | None = None,
        worker_count: int = 2,
    ):
        self.store = JobStore(db)
        self.deps = deps
        self.registry = registry if registry is not None else JOB_REGISTRY
        self.executor = ThreadPoolExecutor(
            max_workers=max(1, worker_count), thread_name_prefix="vanguard-job"
        )
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ submission
    def submit(self, job_type: str, params: dict, requested_by: str = "", max_retries: int = 1) -> Job:
        if job_type not in self.registry:
            raise ValueError(
                f"Unknown job_type '{job_type}'; registered types: {sorted(self.registry)}"
            )
        job = Job(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            params=params,
            state=JobState.QUEUED,
            requested_by=requested_by,
            max_retries=max_retries,
        )
        self.store.create(job)
        self._dispatch(job.job_id)
        return job

    def _dispatch(self, job_id: str) -> None:
        with self._lock:
            self._cancel_events[job_id] = threading.Event()
        self.executor.submit(self._run, job_id)

    # ------------------------------------------------------------- execution
    def _run(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if job is None:
            return
        # A job canceled before a worker thread picked it up: honor that now
        # instead of running it at all.
        event = self._cancel_events.get(job_id)
        if event is not None and event.is_set():
            self.store.update(
                job_id, state=JobState.CANCELED, finished_at=_now(), progress="canceled before start"
            )
            with self._lock:
                self._cancel_events.pop(job_id, None)
            return

        callable_ = self.registry.get(job.job_type)
        self.store.update(job_id, state=JobState.RUNNING, started_at=_now(), progress="starting")

        def report_progress(text: str) -> None:
            self.store.update(job_id, progress=text)
            ev = self._cancel_events.get(job_id)
            if ev is not None and ev.is_set():
                raise JobCanceled(job_id)

        ctx = JobRunContext(job_id=job_id, params=job.params, report_progress=report_progress, deps=self.deps)
        try:
            result = callable_(ctx)
            self.store.update(
                job_id,
                state=JobState.COMPLETED,
                result=result,
                error=None,
                finished_at=_now(),
                progress="completed",
            )
        except JobCanceled:
            self.store.update(
                job_id, state=JobState.CANCELED, finished_at=_now(), progress="canceled"
            )
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any job callable may raise
            detail = f"{exc.__class__.__name__}: {exc}"
            self.store.update(
                job_id, state=JobState.FAILED, error=detail, finished_at=_now(), progress="failed"
            )
        finally:
            with self._lock:
                self._cancel_events.pop(job_id, None)

    # --------------------------------------------------------------- control
    def cancel(self, job_id: str) -> Job:
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.state not in (JobState.QUEUED, JobState.RUNNING, JobState.RETRYING):
            return job  # not cancelable from a terminal state; no-op
        event = self._cancel_events.get(job_id)
        if event is not None:
            event.set()
            return self.store.get(job_id)
        # No live cancel event (job hasn't been dispatched to a worker slot
        # yet, or already finished between the check above and here) —
        # cancel it directly.
        return self.store.update(
            job_id, state=JobState.CANCELED, finished_at=_now(), progress="canceled before start"
        )

    def retry(self, job_id: str) -> Job:
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.state != JobState.FAILED:
            raise ValueError(f"Only FAILED jobs can be retried (current state: {job.state.value})")
        if job.retries >= job.max_retries:
            raise ValueError(f"max_retries ({job.max_retries}) already reached for this job")
        self.store.update(
            job_id,
            state=JobState.RETRYING,
            retries=job.retries + 1,
            error=None,
            result=None,
            finished_at=None,
            progress="re-queued",
        )
        self._dispatch(job_id)
        return self.store.get(job_id)

    def shutdown(self, wait: bool = False) -> None:
        self.executor.shutdown(wait=wait, cancel_futures=True)
