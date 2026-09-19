"""SQLite-backed job records. Follows core/db.py's connection pattern exactly
(one Database instance, a cursor() context manager per statement, JSON blobs
for structured columns)."""
from __future__ import annotations

from datetime import datetime, timezone

from ..core.db import Database, dumps, loads
from ..core.models import Job, JobState


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, db: Database):
        self.db = db

    def create(self, job: Job) -> Job:
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO jobs (job_id, job_type, params, state, progress, result, error,
                   retries, max_retries, requested_by, created_at, started_at, finished_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.job_id,
                    job.job_type,
                    dumps(job.params),
                    job.state.value,
                    job.progress,
                    dumps(job.result) if job.result is not None else None,
                    job.error,
                    job.retries,
                    job.max_retries,
                    job.requested_by,
                    job.created_at,
                    job.started_at,
                    job.finished_at,
                    job.created_at,
                ),
            )
        return job

    def _row_to_job(self, row) -> Job:
        return Job(
            job_id=row["job_id"],
            job_type=row["job_type"],
            params=loads(row["params"]),
            state=JobState(row["state"]),
            progress=row["progress"] or "",
            result=loads(row["result"]) if row["result"] else None,
            error=row["error"],
            retries=row["retries"],
            max_retries=row["max_retries"],
            requested_by=row["requested_by"] or "",
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def get(self, job_id: str) -> Job | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
        return self._row_to_job(row) if row else None

    def list(self, state: str | None = None, job_type: str | None = None) -> list[Job]:
        query = "SELECT * FROM jobs WHERE 1=1"
        args: list[str] = []
        if state:
            query += " AND state = ?"
            args.append(state)
        if job_type:
            query += " AND job_type = ?"
            args.append(job_type)
        query += " ORDER BY created_at DESC, job_id DESC"
        with self.db.cursor() as cur:
            cur.execute(query, args)
            rows = cur.fetchall()
        return [self._row_to_job(r) for r in rows]

    def update(self, job_id: str, **fields) -> Job | None:
        """Partial update. `state` may be a JobState or a plain string;
        `result` (a dict) is JSON-encoded automatically."""
        if not fields:
            return self.get(job_id)
        sets: list[str] = []
        args: list = []
        for key, value in fields.items():
            if key == "state" and isinstance(value, JobState):
                value = value.value
            if key == "result" and value is not None:
                value = dumps(value)
            sets.append(f"{key} = ?")
            args.append(value)
        sets.append("updated_at = ?")
        args.append(_now())
        args.append(job_id)
        with self.db.cursor() as cur:
            cur.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?", args)
        return self.get(job_id)
