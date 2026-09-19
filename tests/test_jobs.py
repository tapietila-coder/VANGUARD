"""Real end-to-end Job Queue tests, driven entirely through the HTTP API
(fastapi.testclient.TestClient against the real wired app — same posture as
test_process_control.py's audit/auth tests). Every job here actually executes
a real registered callable on a real worker thread; nothing is mocked. Polling
uses short sleeps (<=0.05s) with a generous deadline so the suite stays fast
without depending on exact timing.
"""
import time

import pytest


def _poll_until(client, headers, job_id, states, timeout=5.0):
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


def test_submit_readiness_sweep_runs_for_real_and_completes(client, auth_headers):
    r = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "readiness_sweep", "params": {}},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["job_type"] == "readiness_sweep"
    assert job["state"] in ("QUEUED", "RUNNING", "COMPLETED")

    done = _poll_until(client, auth_headers, job["job_id"], {"COMPLETED", "FAILED"})
    assert done["state"] == "COMPLETED", done
    assert done["error"] is None
    assert done["started_at"] is not None
    assert done["finished_at"] is not None
    # Real result shape: no nodes are registered in this fresh test DB, so the
    # sweep legitimately reports zero nodes evaluated — not a fabricated count.
    assert done["result"]["nodes_evaluated"] == 0
    assert isinstance(done["result"]["state_counts"], dict)
    assert set(done["result"]["profiles_evaluated"]) == {
        "D27_CONTROL_HOST",
        "CLASSIFIED_GPU",
        "GENERAL_WORKER",
    }


def test_unknown_job_type_is_rejected(client, auth_headers):
    r = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "not_a_real_job_type", "params": {}},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "not_a_real_job_type" in r.json()["detail"]


def test_service_health_check_fails_for_unknown_service_then_retries(client, auth_headers):
    r = client.post(
        "/api/v1/vanguard/jobs",
        json={
            "job_type": "service_health_check",
            "params": {"service_id": "totally-nonexistent-service"},
            "max_retries": 1,
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["job_id"]

    failed = _poll_until(client, auth_headers, job_id, {"FAILED", "COMPLETED"})
    assert failed["state"] == "FAILED", failed
    assert failed["error"] is not None
    assert "totally-nonexistent-service" in failed["error"]
    assert failed["retries"] == 0

    r = client.post(f"/api/v1/vanguard/jobs/{job_id}/retry", headers=auth_headers)
    assert r.status_code == 200, r.text
    retried = r.json()
    assert retried["retries"] == 1

    refailed = _poll_until(client, auth_headers, job_id, {"FAILED", "COMPLETED"})
    assert refailed["state"] == "FAILED"
    assert refailed["retries"] == 1

    # A COMPLETED job can never be retried.
    r2 = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "readiness_sweep", "params": {}, "max_retries": 1},
        headers=auth_headers,
    )
    ok_job_id = r2.json()["job_id"]
    _poll_until(client, auth_headers, ok_job_id, {"COMPLETED"})
    r3 = client.post(f"/api/v1/vanguard/jobs/{ok_job_id}/retry", headers=auth_headers)
    assert r3.status_code == 400


def test_retry_respects_max_retries(client, auth_headers):
    r = client.post(
        "/api/v1/vanguard/jobs",
        json={
            "job_type": "service_health_check",
            "params": {"service_id": "still-not-real"},
            "max_retries": 0,
        },
        headers=auth_headers,
    )
    job_id = r.json()["job_id"]
    _poll_until(client, auth_headers, job_id, {"FAILED"})
    r2 = client.post(f"/api/v1/vanguard/jobs/{job_id}/retry", headers=auth_headers)
    assert r2.status_code == 400
    assert "max_retries" in r2.json()["detail"]


def test_cancel_mid_flight_actually_stops_the_job(client, auth_headers):
    r = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "queue_selftest", "params": {"steps": 50, "delay_seconds": 0.1}},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["job_id"]

    # Let it actually start running before canceling.
    _poll_until(client, auth_headers, job_id, {"RUNNING", "COMPLETED"}, timeout=2.0)

    r2 = client.post(f"/api/v1/vanguard/jobs/{job_id}/cancel", headers=auth_headers)
    assert r2.status_code == 200, r2.text

    canceled = _poll_until(client, auth_headers, job_id, {"CANCELED", "COMPLETED"}, timeout=3.0)
    assert canceled["state"] == "CANCELED", canceled
    # It really stopped early: a 50-step, 0.1s/step job (5s total) canceled
    # this fast could not have completed all 50 steps.
    assert canceled["result"] is None
    steps_progress = canceled.get("progress", "")
    assert "step" in steps_progress or steps_progress in ("canceled", "starting")


def test_get_jobs_filtering_by_state_and_type(client, auth_headers):
    r1 = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "readiness_sweep", "params": {}},
        headers=auth_headers,
    )
    job1 = r1.json()["job_id"]
    _poll_until(client, auth_headers, job1, {"COMPLETED"})

    r2 = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "service_health_check", "params": {"service_id": "nope-nope"}},
        headers=auth_headers,
    )
    job2 = r2.json()["job_id"]
    _poll_until(client, auth_headers, job2, {"FAILED"})

    by_type = client.get("/api/v1/vanguard/jobs", params={"job_type": "readiness_sweep"}).json()
    assert all(j["job_type"] == "readiness_sweep" for j in by_type)
    assert any(j["job_id"] == job1 for j in by_type)

    by_state = client.get("/api/v1/vanguard/jobs", params={"state": "FAILED"}).json()
    assert all(j["state"] == "FAILED" for j in by_state)
    assert any(j["job_id"] == job2 for j in by_state)

    combined = client.get(
        "/api/v1/vanguard/jobs", params={"job_type": "readiness_sweep", "state": "FAILED"}
    ).json()
    assert all(j["job_type"] == "readiness_sweep" and j["state"] == "FAILED" for j in combined)


def test_get_single_job_detail_includes_progress_result_error(client, auth_headers):
    r = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "audit_log_export", "params": {}},
        headers=auth_headers,
    )
    job_id = r.json()["job_id"]
    done = _poll_until(client, auth_headers, job_id, {"COMPLETED"})
    assert done["result"]["exported_count"] >= 0
    assert done["result"]["path"]

    detail = client.get(f"/api/v1/vanguard/jobs/{job_id}").json()
    assert detail["job_id"] == job_id
    assert detail["result"] == done["result"]
    assert detail["error"] is None


def test_get_unknown_job_is_404(client):
    r = client.get("/api/v1/vanguard/jobs/does-not-exist")
    assert r.status_code == 404


def test_job_mutations_require_bearer_token(client):
    r = client.post("/api/v1/vanguard/jobs", json={"job_type": "readiness_sweep", "params": {}})
    assert r.status_code == 401

    r2 = client.post("/api/v1/vanguard/jobs/some-id/cancel")
    assert r2.status_code == 401

    r3 = client.post("/api/v1/vanguard/jobs/some-id/retry")
    assert r3.status_code == 401


def test_every_mutating_job_action_writes_a_real_audit_entry(client, auth_headers):
    r = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "queue_selftest", "params": {"steps": 20, "delay_seconds": 0.1}},
        headers=auth_headers,
    )
    job_id = r.json()["job_id"]
    _poll_until(client, auth_headers, job_id, {"RUNNING"}, timeout=2.0)
    client.post(f"/api/v1/vanguard/jobs/{job_id}/cancel", headers=auth_headers)
    _poll_until(client, auth_headers, job_id, {"CANCELED"}, timeout=3.0)

    r2 = client.post(
        "/api/v1/vanguard/jobs",
        json={"job_type": "service_health_check", "params": {"service_id": "audit-check-missing"}},
        headers=auth_headers,
    )
    job2 = r2.json()["job_id"]
    _poll_until(client, auth_headers, job2, {"FAILED"})
    client.post(f"/api/v1/vanguard/jobs/{job2}/retry", headers=auth_headers)

    audit = client.get("/api/v1/vanguard/audit", headers=auth_headers).json()
    actions_by_target = {(a["action"], a["target"]) for a in audit["entries"]}
    assert ("job.submit", job_id) in actions_by_target
    assert ("job.cancel", job_id) in actions_by_target
    assert ("job.submit", job2) in actions_by_target
    assert ("job.retry", job2) in actions_by_target
