"""SQLite storage helper. Single-node reference implementation, same posture as Dispatch."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS services (
    service_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readiness_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    node_id TEXT,
    service_id TEXT,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS managed_processes (
    service_id TEXT PRIMARY KEY,
    config TEXT NOT NULL,
    runtime TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    params TEXT NOT NULL,
    state TEXT NOT NULL,
    progress TEXT NOT NULL DEFAULT '',
    result TEXT,
    error TEXT,
    retries INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 1,
    requested_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs (state);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs (job_type);

CREATE TABLE IF NOT EXISTS audit_log (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT,
    source TEXT,
    before TEXT,
    after TEXT,
    reason TEXT,
    created_at TEXT NOT NULL
);

-- A single-row table used only as a real read/write liveness probe (System
-- Health). No operational data lives here; see Database.check_read_write().
CREATE TABLE IF NOT EXISTS health_probe (
    id INTEGER PRIMARY KEY,
    checked_at TEXT NOT NULL
);
"""


class Database:
    """A tiny thread-safe wrapper. One connection per instance, guarded by a lock —
    adequate for the local single-node reference this project is; not a concurrency
    story for multi-process deployment."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    @contextmanager
    def cursor(self):
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    def close(self) -> None:
        self._conn.close()

    def check_read_write(self) -> tuple[bool, str]:
        """Real, lightweight liveness check used by System Health: a real
        `SELECT 1` plus a real write (upsert) against a dedicated single-row
        probe table, executed against the actual live connection/file right
        now — never a cached or assumed-good value."""
        try:
            with self.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.execute(
                    "INSERT INTO health_probe (id, checked_at) VALUES (1, ?) "
                    "ON CONFLICT(id) DO UPDATE SET checked_at = excluded.checked_at",
                    (datetime.now(timezone.utc).isoformat(),),
                )
            return True, f"SELECT 1 + write probe ok against {self.db_path}"
        except Exception as exc:  # noqa: BLE001 - report the real failure, never fabricate success
            return False, f"{exc.__class__.__name__}: {exc}"


def dumps(obj) -> str:
    return json.dumps(obj, default=str)


def loads(text: str):
    return json.loads(text)
