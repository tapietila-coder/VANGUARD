"""Append-only audit log: who did what, to what, and why."""
from ..core.db import Database, dumps, loads
from ..core.models import AuditEntry


class AuditWriter:
    def __init__(self, db: Database):
        self.db = db

    def write(self, entry: AuditEntry) -> AuditEntry:
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO audit_log (actor, action, target, source, before, after, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.actor,
                    entry.action,
                    entry.target,
                    entry.source,
                    dumps(entry.before) if entry.before is not None else None,
                    dumps(entry.after) if entry.after is not None else None,
                    entry.reason,
                    entry.created_at,
                ),
            )
            entry_id = cur.lastrowid
        return entry.model_copy(update={"entry_id": entry_id})

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        actor: str | None = None,
        action: str | None = None,
        target: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[AuditEntry]:
        """List entries, most recent first. All filters are exact/prefix
        matches on real stored columns — no fuzzy search. `since`/`until` are
        ISO-8601 timestamp bounds compared lexically against `created_at`
        (safe because it's always written via `datetime.isoformat()`, which
        sorts the same lexically and chronologically)."""
        clauses: list[str] = []
        params: list = []
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if target:
            clauses.append("target = ?")
            params.append(target)
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        if until:
            clauses.append("created_at <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM audit_log {where} ORDER BY entry_id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.db.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        out = []
        for row in rows:
            out.append(
                AuditEntry(
                    entry_id=row["entry_id"],
                    actor=row["actor"],
                    action=row["action"],
                    target=row["target"] or "",
                    source=row["source"] or "",
                    before=loads(row["before"]) if row["before"] else None,
                    after=loads(row["after"]) if row["after"] else None,
                    reason=row["reason"] or "",
                    created_at=row["created_at"],
                )
            )
        return out

    def count(
        self,
        actor: str | None = None,
        action: str | None = None,
        target: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list = []
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if target:
            clauses.append("target = ?")
            params.append(target)
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        if until:
            clauses.append("created_at <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.db.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS c FROM audit_log {where}", params)
            row = cur.fetchone()
        return int(row["c"])
