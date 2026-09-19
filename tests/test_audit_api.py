"""API-level tests for the audit + logs routes added for the Audit/Logs UI
pass: GET /audit's filter/pagination query params, its bearer-token
requirement, and the new GET /logs cross-service index."""
import sys

from vanguard.core.models import ManagedProcessConfig


def test_audit_route_requires_bearer_token(client):
    r = client.get("/api/v1/vanguard/audit")
    assert r.status_code == 401


def test_audit_route_filters_and_paginates(client, auth_headers):
    # Generate a few real audit entries via real mutating routes.
    client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "n1", "hostname": "h", "os_name": "Linux"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "n2", "hostname": "h2", "os_name": "Linux"},
        headers=auth_headers,
    )

    r = client.get("/api/v1/vanguard/audit", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "entries" in body and "total" in body
    assert body["total"] >= 2

    r_filtered = client.get(
        "/api/v1/vanguard/audit", headers=auth_headers, params={"target": "n1", "action": "node.register"}
    )
    filtered = r_filtered.json()
    assert filtered["total"] == 1
    assert filtered["entries"][0]["target"] == "n1"

    r_page = client.get("/api/v1/vanguard/audit", headers=auth_headers, params={"limit": 1, "offset": 0})
    page = r_page.json()
    assert len(page["entries"]) == 1
    assert page["limit"] == 1
    assert page["offset"] == 0


def test_logs_route_lists_no_registered_processes_honestly(client):
    r = client.get("/api/v1/vanguard/logs")
    assert r.status_code == 200
    # Test app builds Settings without dispatch_dir/python set, so no managed
    # process is auto-registered — the honest answer is an empty list, never
    # a fabricated "dispatch" row.
    assert r.json() == []


def test_logs_route_reports_a_real_registered_process(client, app, tmp_path):
    script = tmp_path / "loop.py"
    script.write_text("import time\nwhile True:\n    time.sleep(0.2)\n", encoding="utf-8")
    app.state.processes.register(
        ManagedProcessConfig(
            service_id="looper", name="Test Looper", working_dir=str(tmp_path),
            command=[sys.executable, str(script)],
        )
    )

    r = client.get("/api/v1/vanguard/logs")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["service_id"] == "looper"
    # No process has been started yet, so no log file exists — honest, not fabricated.
    assert rows[0]["exists"] is False
    assert rows[0]["line_count"] is None
