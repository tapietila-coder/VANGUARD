"""Real end-to-end Metrics/observability tests, driven through the HTTP API
against the real wired app (same posture as test_incidents.py/test_jobs.py)
— nothing mocked. Rather than waiting on the background collector's real
30s-scale timer, these call `app.state.metrics_collector.sample_now()`
directly (the same synchronous function the background loop itself calls) to
deterministically produce real samples, then assert on what the API and
store actually report.
"""
from datetime import datetime, timedelta, timezone

from vanguard.core.models import MetricSample


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def test_current_metrics_empty_before_any_sample(client):
    resp = client.get("/api/v1/vanguard/metrics/current")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample"] is None
    assert body["sample_count"] == 0
    # TestClient here (per tests/conftest.py) is never used as a `with`
    # context manager, so the ASGI lifespan protocol never runs and the
    # background thread was never started — an honest, real "not running"
    # rather than a fabricated "collecting".
    assert body["collector_running"] is False


def test_sample_now_produces_a_real_sane_sample(app, client):
    sample = app.state.metrics_collector.sample_now()

    # Real, sane values: CPU% between 0-100 (or honestly None without
    # psutil), RAM used never exceeds RAM total, disk used never exceeds
    # disk total.
    if sample.cpu_percent is not None:
        assert 0.0 <= sample.cpu_percent <= 100.0
    if sample.ram_used_mb is not None and sample.ram_total_mb is not None:
        assert sample.ram_used_mb <= sample.ram_total_mb
        assert sample.ram_total_mb > 0
    assert sample.disk_used_mb <= sample.disk_total_mb
    assert sample.disk_total_mb > 0
    assert sample.disk_path

    resp = client.get("/api/v1/vanguard/metrics/current")
    body = resp.json()
    assert body["sample"] is not None
    assert body["sample"]["sampled_at"] == sample.sampled_at
    assert body["sample_count"] == 1


def test_multiple_samples_land_in_store_and_current_is_the_latest(app, client):
    first = app.state.metrics_collector.sample_now()
    second = app.state.metrics_collector.sample_now()
    assert second.sampled_at >= first.sampled_at

    resp = client.get("/api/v1/vanguard/metrics/current")
    body = resp.json()
    assert body["sample"]["sampled_at"] == second.sampled_at
    assert body["sample_count"] == 2


def test_history_returns_real_samples_in_range(app, client):
    store = app.state.metrics
    now = datetime.now(timezone.utc)

    # Insert real MetricSample rows directly at controlled timestamps so the
    # since/until filtering can be asserted precisely, without depending on
    # real wall-clock timing between calls.
    old = MetricSample(
        cpu_percent=10.0, ram_used_mb=100, ram_total_mb=1000,
        disk_used_mb=10, disk_total_mb=100, disk_path="/tmp",
        sampled_at=_iso(now - timedelta(hours=2)),
    )
    recent = MetricSample(
        cpu_percent=20.0, ram_used_mb=200, ram_total_mb=1000,
        disk_used_mb=20, disk_total_mb=100, disk_path="/tmp",
        sampled_at=_iso(now - timedelta(minutes=1)),
    )
    store.insert(old)
    store.insert(recent)

    resp = client.get(
        "/api/v1/vanguard/metrics/history",
        params={"since": _iso(now - timedelta(hours=1))},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucketed"] is False
    sampled_ats = [s["sampled_at"] for s in body["samples"]]
    assert recent.sampled_at in sampled_ats
    assert old.sampled_at not in sampled_ats


def test_history_bucketing_averages_real_samples(app, client):
    store = app.state.metrics
    base = datetime.now(timezone.utc).replace(microsecond=0)

    # Two real samples 10s apart, both inside one 60s bucket.
    s1 = MetricSample(
        cpu_percent=10.0, ram_used_mb=100, ram_total_mb=1000,
        disk_used_mb=10, disk_total_mb=100, disk_path="/tmp",
        sampled_at=_iso(base),
    )
    s2 = MetricSample(
        cpu_percent=30.0, ram_used_mb=300, ram_total_mb=1000,
        disk_used_mb=30, disk_total_mb=100, disk_path="/tmp",
        sampled_at=_iso(base + timedelta(seconds=10)),
    )
    store.insert(s1)
    store.insert(s2)

    resp = client.get(
        "/api/v1/vanguard/metrics/history",
        params={
            "since": _iso(base - timedelta(seconds=5)),
            "until": _iso(base + timedelta(seconds=15)),
            "interval": 60,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucketed"] is True
    assert len(body["samples"]) == 1
    bucket = body["samples"][0]
    # Real average of the two real samples: (10+30)/2 = 20, (100+300)/2 = 200.
    assert bucket["cpu_percent"] == 20.0
    assert bucket["ram_used_mb"] == 200


def test_history_rejects_zero_interval(client):
    resp = client.get("/api/v1/vanguard/metrics/history", params={"interval": 0})
    assert resp.status_code == 400


def test_retention_prunes_old_samples(app):
    collector = app.state.metrics_collector
    store = app.state.metrics
    collector.retention_days = 1

    stale = MetricSample(
        cpu_percent=1.0, ram_used_mb=1, ram_total_mb=100,
        disk_used_mb=1, disk_total_mb=100, disk_path="/tmp",
        sampled_at=_iso(datetime.now(timezone.utc) - timedelta(days=5)),
    )
    store.insert(stale)
    assert store.count() == 1

    # A fresh real sample triggers prune-on-insert (see
    # vanguard/metrics/collector.py's module docstring for why pruning is
    # tied to insert rather than a separate scheduled sweep).
    collector.sample_now()

    remaining = store.query()
    assert all(s.sampled_at != stale.sampled_at for s in remaining)


def test_system_health_reports_metrics_row(app, client):
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "metrics")
    assert row["status"] == "UNKNOWN"  # collector never started via plain TestClient
    assert "no samples" in row["detail"]

    app.state.metrics_collector.sample_now()
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "metrics")
    assert row["status"] == "DEGRADED"
    assert "previously collected" in row["detail"]


def test_collector_start_and_stop_real_background_thread(app):
    collector = app.state.metrics_collector
    assert collector.is_running() is False
    collector.start()
    try:
        assert collector.is_running() is True
        # start() takes a real synchronous sample immediately, before the
        # loop's first wait — no need to sleep through a real interval.
        assert app.state.metrics.count() >= 1
    finally:
        collector.stop(wait=True)
    assert collector.is_running() is False
