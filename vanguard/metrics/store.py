"""SQLite-backed storage for MetricSample records. Follows the same
data-column-plus-a-queryable-column pattern as vanguard/incidents/store.py:
the full sample lives as one JSON blob in `data`, with `sampled_at`
duplicated into a real indexed column so range queries don't need to
deserialize every row just to filter.
"""
from __future__ import annotations

from ..core.db import Database, dumps, loads
from ..core.models import MetricSample


class MetricsStore:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, sample: MetricSample) -> MetricSample:
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO metrics_samples (data, sampled_at) VALUES (?, ?)",
                (dumps(sample.model_dump()), sample.sampled_at),
            )
        return sample

    def latest(self) -> MetricSample | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT data FROM metrics_samples ORDER BY sampled_at DESC, id DESC LIMIT 1")
            row = cur.fetchone()
        return MetricSample.model_validate(loads(row["data"])) if row else None

    def count(self) -> int:
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM metrics_samples")
            row = cur.fetchone()
        return int(row["c"])

    def query(self, since: str | None = None, until: str | None = None) -> list[MetricSample]:
        """Real stored samples in [since, until] (both optional, compared
        lexically against the ISO-8601 sampled_at column — same convention
        vanguard/audit uses for since/until), ordered oldest-first so a
        caller can chart/bucket them directly."""
        clauses: list[str] = []
        params: list = []
        if since:
            clauses.append("sampled_at >= ?")
            params.append(since)
        if until:
            clauses.append("sampled_at <= ?")
            params.append(until)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.db.cursor() as cur:
            cur.execute(f"SELECT data FROM metrics_samples {where} ORDER BY sampled_at ASC, id ASC", params)
            rows = cur.fetchall()
        return [MetricSample.model_validate(loads(row["data"])) for row in rows]

    def prune_older_than(self, cutoff_iso: str) -> int:
        """Deletes every sample with sampled_at strictly before cutoff_iso.
        Returns the real number of rows removed. Called after every insert by
        the collector (vanguard/metrics/collector.py) — see that module's
        docstring for why prune-on-insert was chosen over a separate
        scheduled sweep."""
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM metrics_samples WHERE sampled_at < ?", (cutoff_iso,))
            deleted = cur.rowcount if cur.rowcount is not None else 0
        return max(0, deleted)
