"""Real end-to-end Incidents/alerting tests, driven through the HTTP API
against the real wired app (same posture as test_jobs.py/test_process_control.py)
— nothing mocked. These actually trigger real failure conditions (a
service_health_check job against a nonexistent service, a node genuinely
missing a required readiness capability, a real child process that exits
immediately) and assert on the real Incident records vanguard/incidents/
produces: correlation into one growing incident rather than duplicates, real
auto-resolve on real recovery, and that the permanently-NOT_CONNECTED
Steward/Watchtower/Marshal stubs never spawn incidents.
"""
import sys
import time

import pytest

from vanguard.core.models import ManagedProcessConfig

EXIT_IMMEDIATELY_SCRIPT = "import sys\nprint('bye', flush=True)\nsys.exit(3)\n"

RUNNING_HEALTH_SCRIPT = """
import http.server
import socketserver
import sys

port = int(sys.argv[1])

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

    def log_message(self, *a):
        pass

with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
    print(f"listening on {port}", flush=True)
    httpd.serve_forever()
"""


def _poll_job_until(client, job_id, states, timeout=5.0):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        r = client.get(f"/api/v1/vanguard/jobs/{job_id}")
        assert r.status_code == 200
        job = r.json()
        if job["state"] in states:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not reach {states} within {timeout}s (last: {job})")


def _submit_health_check(client, auth_headers, service_id):
    r = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "service_health_check", "params": {"service_id": service_id}, "max_retries": 0},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["job_id"]


def _free_port() -> int:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _write_script(tmp_path, name: str, body: str) -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


# --------------------------------------------------------------- job queue
def test_failed_job_creates_incident_then_correlates_not_duplicates(client, auth_headers):
    job_id_1 = _submit_health_check(client, auth_headers, "totally-nonexistent-service-a")
    failed_1 = _poll_job_until(client, job_id_1, {"FAILED", "COMPLETED"})
    assert failed_1["state"] == "FAILED", failed_1

    listing = client.get("/api/v1/vanguard/incidents", params={"status": "OPEN"})
    assert listing.status_code == 200
    incidents = [i for i in listing.json() if i["source"] == "job_queue:service_health_check"]
    assert len(incidents) == 1, incidents
    incident = incidents[0]
    assert incident["severity"] == "WARNING"
    assert incident["occurrence_count"] == 1
    assert len(incident["timeline"]) == 1
    assert incident["timeline"][0]["kind"] == "detected"

    # Trigger the SAME kind of failure again (different bad service_id, same
    # job_type) — this must grow the existing incident's timeline, not spawn
    # a second one.
    job_id_2 = _submit_health_check(client, auth_headers, "totally-nonexistent-service-b")
    failed_2 = _poll_job_until(client, job_id_2, {"FAILED", "COMPLETED"})
    assert failed_2["state"] == "FAILED", failed_2

    detail = client.get(f"/api/v1/vanguard/incidents/{incident['incident_id']}")
    assert detail.status_code == 200
    grown = detail.json()
    assert grown["incident_id"] == incident["incident_id"]  # same incident, not a new one
    assert grown["occurrence_count"] == 2
    assert len(grown["timeline"]) == 2
    assert grown["timeline"][1]["kind"] == "recurred"

    listing_after = client.get("/api/v1/vanguard/incidents", params={"status": "OPEN"})
    still_one = [i for i in listing_after.json() if i["source"] == "job_queue:service_health_check"]
    assert len(still_one) == 1, still_one

    # Fix the condition: submit the SAME job_type but against a real,
    # resolvable target (process-control status of a registered process),
    # so this run genuinely COMPLETEs. Register a trivial managed process
    # first via the real ProcessController the app is wired with.
    app = client.app
    cfg = ManagedProcessConfig(
        service_id="incidents-test-proc", name="Incidents Test Proc",
        working_dir=".", command=[sys.executable, "-c", "print('noop')"],
    )
    app.state.processes.register(cfg)
    job_id_3 = _submit_health_check(client, auth_headers, "incidents-test-proc")
    completed = _poll_job_until(client, job_id_3, {"FAILED", "COMPLETED"})
    assert completed["state"] == "COMPLETED", completed

    resolved = client.get(f"/api/v1/vanguard/incidents/{incident['incident_id']}")
    resolved_body = resolved.json()
    assert resolved_body["status"] == "RESOLVED", resolved_body
    assert resolved_body["resolved_at"] is not None
    assert resolved_body["timeline"][-1]["kind"] == "auto_resolved"


# ----------------------------------------------------------------- readiness
def test_readiness_not_ready_creates_incident_and_auto_resolves_on_fix(client, auth_headers):
    node_id = "incidents-test-node"
    # Register a node missing the PYTHON_RUNTIME capability GENERAL_WORKER
    # requires — a real, deterministic NOT_READY.
    r = client.post(
        "/api/v1/vanguard/nodes",
        json={
            "node_id": node_id, "hostname": "test-host", "os_name": "TestOS",
            "capabilities": [],
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text

    eval_resp = client.get(f"/api/v1/vanguard/nodes/{node_id}/readiness", params={"profile": "GENERAL_WORKER"})
    assert eval_resp.status_code == 200
    assert eval_resp.json()["state"] == "NOT_READY", eval_resp.json()

    listing = client.get("/api/v1/vanguard/incidents", params={"status": "OPEN"})
    matches = [i for i in listing.json() if i["correlation_key"] == f"readiness:{node_id}:GENERAL_WORKER"]
    assert len(matches) == 1, matches
    incident = matches[0]
    assert incident["severity"] == "MAJOR"
    assert incident["status"] == "OPEN"
    assert node_id in incident["title"]

    # Fix the node: register it again with PYTHON_RUNTIME declared.
    r2 = client.post(
        "/api/v1/vanguard/nodes",
        json={
            "node_id": node_id, "hostname": "test-host", "os_name": "TestOS",
            "capabilities": ["PYTHON_RUNTIME"],
        },
        headers=auth_headers,
    )
    assert r2.status_code == 201, r2.text
    eval_resp2 = client.get(f"/api/v1/vanguard/nodes/{node_id}/readiness", params={"profile": "GENERAL_WORKER"})
    assert eval_resp2.json()["state"] in ("READY", "READY_WITH_WARNING"), eval_resp2.json()

    detail = client.get(f"/api/v1/vanguard/incidents/{incident['incident_id']}")
    body = detail.json()
    assert body["status"] == "RESOLVED", body
    assert body["timeline"][-1]["kind"] == "auto_resolved"


# ------------------------------------------------------------ service control
def test_process_failure_creates_incident(client, tmp_path):
    app = client.app
    script = _write_script(tmp_path, "exits.py", EXIT_IMMEDIATELY_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="incidents-crash-proc", name="Crashy Proc",
        working_dir=str(tmp_path), command=[sys.executable, script],
    )
    app.state.processes.register(cfg)
    status = app.state.processes.start("incidents-crash-proc")
    assert status.state.value == "FAILED", status

    listing = client.get("/api/v1/vanguard/incidents", params={"status": "OPEN"})
    matches = [i for i in listing.json() if i["correlation_key"] == "service_control:incidents-crash-proc"]
    assert len(matches) == 1, matches
    assert matches[0]["severity"] == "CRITICAL"


# ------------------------------------------------------------ manual actions
def test_manual_acknowledge_and_resolve_via_api(client, auth_headers):
    job_id = _submit_health_check(client, auth_headers, "manual-ack-target-missing")
    failed = _poll_job_until(client, job_id, {"FAILED", "COMPLETED"})
    assert failed["state"] == "FAILED"

    listing = client.get("/api/v1/vanguard/incidents", params={"status": "OPEN"})
    matches = [i for i in listing.json() if i["source"] == "job_queue:service_health_check"]
    assert matches, matches
    incident_id = matches[0]["incident_id"]

    # No token: refused.
    no_auth = client.post(f"/api/v1/vanguard/incidents/{incident_id}/acknowledge")
    assert no_auth.status_code == 401

    ack = client.post(
        f"/api/v1/vanguard/incidents/{incident_id}/acknowledge",
        json={"reason": "investigating"},
        headers=auth_headers,
    )
    assert ack.status_code == 200, ack.text
    ack_body = ack.json()
    assert ack_body["status"] == "ACKNOWLEDGED"
    assert ack_body["acknowledged_by"] == "operator"
    assert ack_body["timeline"][-1]["kind"] == "acknowledged"
    assert ack_body["timeline"][-1]["detail"] == "investigating"

    resolve = client.post(
        f"/api/v1/vanguard/incidents/{incident_id}/resolve",
        json={"reason": "manually confirmed fixed"},
        headers=auth_headers,
    )
    assert resolve.status_code == 200, resolve.text
    resolve_body = resolve.json()
    assert resolve_body["status"] == "RESOLVED"
    assert resolve_body["resolved_at"] is not None
    assert resolve_body["timeline"][-1]["kind"] == "resolved"

    # An audit entry was written for both mutating actions.
    audit = client.get(
        "/api/v1/vanguard/audit", params={"target": incident_id}, headers=auth_headers
    )
    assert audit.status_code == 200
    actions = {e["action"] for e in audit.json()["entries"]}
    assert "incident.acknowledge" in actions
    assert "incident.resolve" in actions


def test_unknown_incident_404s(client, auth_headers):
    assert client.get("/api/v1/vanguard/incidents/does-not-exist").status_code == 404
    assert (
        client.post(
            "/api/v1/vanguard/incidents/does-not-exist/acknowledge", headers=auth_headers
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/vanguard/incidents/does-not-exist/resolve", headers=auth_headers
        ).status_code
        == 404
    )


# ----------------------------------------------------- permanently-stubbed
def test_steward_watchtower_marshal_never_generate_incidents(client):
    # Hit /integrations several times — Steward/Watchtower/Marshal always
    # report NOT_CONNECTED (they don't exist anywhere in this environment).
    # That is steady-state, never a new failure, so it must never open an
    # incident, no matter how many times their status is checked.
    for _ in range(5):
        r = client.get("/api/v1/vanguard/integrations")
        assert r.status_code == 200
        body = r.json()
        assert body["steward"]["status"] == "NOT_CONNECTED"
        assert body["watchtower"]["status"] == "NOT_CONNECTED"
        assert body["marshal"]["status"] == "NOT_CONNECTED"

    listing = client.get("/api/v1/vanguard/incidents").json()
    sources = {i["source"] for i in listing}
    assert "integration:steward" not in sources
    assert "integration:watchtower" not in sources
    assert "integration:marshal" not in sources


def test_dispatch_steady_not_connected_never_generates_incident(client):
    # Dispatch is not running in this test environment either, but its
    # steady/initial NOT_CONNECTED is not itself a transition and must not
    # open an incident — only a real CONNECTED -> NOT_CONNECTED transition
    # would (see IncidentDetector.observe_dispatch).
    for _ in range(5):
        r = client.get("/api/v1/vanguard/integrations")
        assert r.status_code == 200
        assert r.json()["dispatch"]["status"] == "NOT_CONNECTED"

    listing = client.get("/api/v1/vanguard/incidents").json()
    sources = {i["source"] for i in listing}
    assert "integration:dispatch" not in sources


def test_incidents_filterable_by_status_and_severity(client, auth_headers):
    job_id = _submit_health_check(client, auth_headers, "filter-test-missing-service")
    _poll_job_until(client, job_id, {"FAILED", "COMPLETED"})

    open_listing = client.get("/api/v1/vanguard/incidents", params={"status": "OPEN"}).json()
    assert any(i["source"] == "job_queue:service_health_check" for i in open_listing)

    resolved_listing = client.get("/api/v1/vanguard/incidents", params={"status": "RESOLVED"}).json()
    for i in resolved_listing:
        assert i["status"] == "RESOLVED"

    warning_listing = client.get("/api/v1/vanguard/incidents", params={"severity": "WARNING"}).json()
    for i in warning_listing:
        assert i["severity"] == "WARNING"


def test_system_health_reports_open_incident_count(client, auth_headers):
    job_id = _submit_health_check(client, auth_headers, "system-health-missing-service")
    _poll_job_until(client, job_id, {"FAILED", "COMPLETED"})

    health = client.get("/api/v1/vanguard/system-health")
    assert health.status_code == 200
    rows = {row["subsystem"]: row for row in health.json()["rows"]}
    assert "incidents" in rows
    assert rows["incidents"]["status"] == "DEGRADED"
    assert "open incident" in rows["incidents"]["detail"]
