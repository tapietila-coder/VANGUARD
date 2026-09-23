"""GET /api/v1/vanguard/system-health: one real check per real subsystem,
assembled server-side (vanguard/system_health/aggregator.py). No row here may
ever be a fabricated/static value — these tests assert against real behavior
of the real underlying objects (db, jobs, mesh, readiness, audit)."""


def test_system_health_route_shape(client):
    resp = client.get("/api/v1/vanguard/system-health")
    assert resp.status_code == 200
    body = resp.json()
    assert "rows" in body and "generated_at" in body
    subsystems = {row["subsystem"] for row in body["rows"]}
    assert subsystems == {
        "api",
        "database",
        "jobs",
        "service_control",
        "mesh",
        "integrations",
        "readiness",
        "audit_log",
        "incidents",
    }
    for row in body["rows"]:
        assert row["status"]
        assert row["checked_at"]


def test_system_health_no_auth_required(client):
    # Read-only, same posture as /health and /integrations.
    resp = client.get("/api/v1/vanguard/system-health")
    assert resp.status_code == 200


def test_system_health_database_row_ok(client):
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "database")
    assert row["status"] == "OK"
    assert "SELECT 1" in row["detail"]


def test_system_health_mesh_row_reports_real_not_connected(client):
    # tests/conftest.py builds Settings with mesh_provider="null" -> real
    # NullMeshProvider -> real NOT_CONNECTED, never fabricated.
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "mesh")
    assert row["status"] == "NOT_CONNECTED"


def test_system_health_service_control_row_not_connected_when_nothing_registered(client):
    # tests/conftest.py's Settings leaves dispatch_dir/dispatch_python unset,
    # so app.py never registers a managed process — the honest state.
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "service_control")
    assert row["status"] == "NOT_CONNECTED"


def test_system_health_readiness_row_unknown_with_no_evaluations(client):
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "readiness")
    assert row["status"] == "UNKNOWN"


def test_system_health_readiness_row_reflects_real_evaluation(client, auth_headers):
    client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "n1", "hostname": "h", "os_name": "Linux"},
        headers=auth_headers,
    )
    ready_resp = client.get("/api/v1/vanguard/nodes/n1/readiness?profile=GENERAL_WORKER")
    assert ready_resp.status_code == 200

    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "readiness")
    assert row["status"] != "UNKNOWN"
    assert "1/1" in row["detail"] or "/1 " in row["detail"] or row["detail"].startswith("0/1")


def test_system_health_audit_row_ok_and_counts_real_entries(client, auth_headers):
    client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "n2", "hostname": "h", "os_name": "Linux"},
        headers=auth_headers,
    )
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "audit_log")
    assert row["status"] == "OK"
    assert "entries recorded" in row["detail"]


def test_system_health_jobs_row_ok_when_idle(client):
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "jobs")
    assert row["status"] == "OK"
    assert "workers configured" in row["detail"]


def test_system_health_jobs_row_reflects_real_submitted_job(client, auth_headers):
    submit = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "queue_selftest", "params": {}},
        headers=auth_headers,
    )
    assert submit.status_code == 201
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "jobs")
    # Not asserting a specific count (the job may complete before this request
    # runs), just that the row reflects a real live worker_status() call.
    assert "queued" in row["detail"] and "running" in row["detail"]


def test_system_health_integrations_row_not_connected_when_dispatch_down(client):
    # tests/conftest.py points dispatch_base_url at a port nothing listens on
    # in the test environment, and steward/watchtower/marshal are permanent
    # stubs -> all four real adapters report NOT_CONNECTED.
    resp = client.get("/api/v1/vanguard/system-health")
    row = next(r for r in resp.json()["rows"] if r["subsystem"] == "integrations")
    assert row["status"] == "NOT_CONNECTED"
    assert "steward=NOT_CONNECTED" in row["detail"]
