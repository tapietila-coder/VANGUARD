"""SQLite-backed storage for Incident records. Follows the same
data-column-plus-a-few-queryable-columns pattern as every other store in this
codebase (see vanguard/jobs/store.py, vanguard/readiness/engine.py): the full
Incident (including its timeline) lives as one JSON blob in `data`, with
`status`/`severity`/`correlation_key` duplicated into real columns so they can
be filtered/indexed without deserializing every row."""
from __future__ import annotations

from ..core.db import Database, dumps, loads
from ..core.models import Incident, IncidentStatus


class IncidentStore:
    def __init__(self, db: Database):
        self.db = db

    def create(self, incident: Incident) -> Incident:
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO incidents
                   (incident_id, correlation_key, status, severity, data, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    incident.incident_id,
                    incident.correlation_key,
                    incident.status.value,
                    incident.severity.value,
                    dumps(incident.model_dump()),
                    incident.first_seen,
                    incident.last_seen,
                ),
            )
        return incident

    def update(self, incident: Incident) -> Incident:
        """Replaces the stored record wholesale — callers always mutate a
        fetched Incident (append to its timeline, change its status/severity)
        and pass the whole thing back, same pattern job store updates use for
        result/error/progress."""
        with self.db.cursor() as cur:
            cur.execute(
                """UPDATE incidents SET correlation_key = ?, status = ?, severity = ?, data = ?, updated_at = ?
                   WHERE incident_id = ?""",
                (
                    incident.correlation_key,
                    incident.status.value,
                    incident.severity.value,
                    dumps(incident.model_dump()),
                    incident.last_seen,
                    incident.incident_id,
                ),
            )
        return incident

    def get(self, incident_id: str) -> Incident | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT data FROM incidents WHERE incident_id = ?", (incident_id,))
            row = cur.fetchone()
        return Incident.model_validate(loads(row["data"])) if row else None

    def get_ungrouped_open(self, correlation_key: str) -> Incident | None:
        """The one real correlation lookup this module needs: the most recent
        non-RESOLVED incident sharing this correlation_key, if any — so a
        recurring failure of the same kind updates that incident's timeline
        instead of spawning a duplicate. RESOLVED incidents are deliberately
        excluded: once a condition has been marked fixed, a fresh occurrence
        of the same failure is a NEW incident, not a reopening of an old one."""
        with self.db.cursor() as cur:
            cur.execute(
                """SELECT data FROM incidents
                   WHERE correlation_key = ? AND status != ?
                   ORDER BY created_at DESC LIMIT 1""",
                (correlation_key, IncidentStatus.RESOLVED.value),
            )
            row = cur.fetchone()
        return Incident.model_validate(loads(row["data"])) if row else None

    def list(self, status: str | None = None, severity: str | None = None) -> list[Incident]:
        clauses: list[str] = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.db.cursor() as cur:
            cur.execute(f"SELECT data FROM incidents {where} ORDER BY created_at DESC", params)
            rows = cur.fetchall()
        return [Incident.model_validate(loads(row["data"])) for row in rows]

    def count_open(self) -> int:
        """Real count of non-RESOLVED incidents — used by the System Health
        aggregate row and the Overview page's "N open incidents" indicator."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM incidents WHERE status != ?", (IncidentStatus.RESOLVED.value,))
            row = cur.fetchone()
        return int(row["c"])
