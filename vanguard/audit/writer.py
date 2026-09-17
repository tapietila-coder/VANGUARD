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

    def list(self, limit: int = 100) -> list[AuditEntry]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM audit_log ORDER BY entry_id DESC LIMIT ?", (limit,))
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
