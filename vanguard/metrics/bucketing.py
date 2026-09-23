"""Optional downsampling for GET /metrics/history so a long time range
doesn't hand back thousands of raw rows to chart. Deliberately simple: fixed-
width time buckets (`interval` seconds), one averaged MetricSample per
bucket. No interpolation, no fabricated points — a bucket with no real
samples in it is simply absent from the result, never filled in with a guess.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..core.models import MetricSample


def _epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def _bucket_start_iso(epoch_seconds: float, interval_seconds: int) -> str:
    bucket_epoch = (int(epoch_seconds) // interval_seconds) * interval_seconds
    return datetime.fromtimestamp(bucket_epoch, tz=timezone.utc).isoformat()


def bucket_samples(samples: list[MetricSample], interval_seconds: int) -> list[MetricSample]:
    """Groups already-time-ordered `samples` into fixed `interval_seconds`
    buckets and averages each numeric field across the real samples that fell
    in that bucket (None fields, e.g. cpu/ram without psutil, are averaged
    only across the samples that actually had a value, and stay None if none
    did). disk_path is taken from the bucket's last real sample."""
    if interval_seconds <= 0 or not samples:
        return list(samples)

    buckets: dict[str, list[MetricSample]] = {}
    order: list[str] = []
    for s in samples:
        key = _bucket_start_iso(_epoch(s.sampled_at), interval_seconds)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(s)

    def _avg(values: list[float | int | None]) -> float | None:
        present = [v for v in values if v is not None]
        if not present:
            return None
        return sum(present) / len(present)

    result: list[MetricSample] = []
    for key in order:
        group = buckets[key]
        cpu = _avg([s.cpu_percent for s in group])
        ram_used = _avg([s.ram_used_mb for s in group])
        ram_total = _avg([s.ram_total_mb for s in group])
        disk_used = _avg([s.disk_used_mb for s in group])
        disk_total = _avg([s.disk_total_mb for s in group])
        result.append(
            MetricSample(
                cpu_percent=round(cpu, 2) if cpu is not None else None,
                ram_used_mb=int(ram_used) if ram_used is not None else None,
                ram_total_mb=int(ram_total) if ram_total is not None else None,
                disk_used_mb=int(disk_used) if disk_used is not None else 0,
                disk_total_mb=int(disk_total) if disk_total is not None else 0,
                disk_path=group[-1].disk_path,
                sampled_at=key,
            )
        )
    return result
