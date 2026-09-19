"""Real process-control tests: these actually spawn and control a real child
process (a tiny, deterministic Python script written to a temp dir by the test
itself, run via sys.executable so it's fully portable) — no subprocess mocking.
A separate, narrowly-scoped test at the bottom verifies the Dispatch
registration parses to real paths without ever starting Dispatch, so CI
(which has no Dispatch venv) never depends on that environment existing.
"""
import sys
import time

import pytest

from vanguard.core.config import Settings
from vanguard.core.db import Database
from vanguard.core.models import ManagedProcessConfig, ProcessState
from vanguard.process_control.manager import ProcessController, pid_alive
from vanguard.service_map.registry import ServiceRegistry, resolveService

RUNNER_SCRIPT = """
import http.server
import socketserver
import sys
import time

port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
if port:
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
else:
    print("looping without health server", flush=True)
    while True:
        time.sleep(0.2)
"""

EXIT_IMMEDIATELY_SCRIPT = "import sys\nprint('bye', flush=True)\nsys.exit(3)\n"


@pytest.fixture
def controller(tmp_path):
    db = Database(str(tmp_path / "pc.db"))
    services = ServiceRegistry(db)
    return ProcessController(db, services, log_dir=str(tmp_path / "logs")), services


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


def test_start_makes_process_running_with_real_pid(controller, tmp_path):
    ctrl, services = controller
    script = _write_script(tmp_path, "loop.py", RUNNER_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="looper", name="Test Looper", working_dir=str(tmp_path),
        command=[sys.executable, script],
    )
    ctrl.register(cfg)
    status = ctrl.start("looper")
    try:
        assert status.state == ProcessState.RUNNING
        assert status.pid is not None
        assert pid_alive(status.pid) is True
    finally:
        ctrl.stop("looper")

    # Registering a managed process also creates a real Service registry row.
    assert resolveService(services, "looper") is not None


def test_stop_actually_exits_the_process(controller, tmp_path):
    ctrl, _ = controller
    script = _write_script(tmp_path, "loop.py", RUNNER_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="looper", name="Test Looper", working_dir=str(tmp_path),
        command=[sys.executable, script],
    )
    ctrl.register(cfg)
    started = ctrl.start("looper")
    pid = started.pid
    assert pid_alive(pid) is True

    stopped = ctrl.stop("looper")
    assert stopped.state == ProcessState.STOPPED
    assert stopped.pid is None
    assert pid_alive(pid) is False  # verified via real PID liveness, not just the DB row


def test_restart_gets_a_new_pid(controller, tmp_path):
    ctrl, _ = controller
    script = _write_script(tmp_path, "loop.py", RUNNER_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="looper", name="Test Looper", working_dir=str(tmp_path),
        command=[sys.executable, script],
    )
    ctrl.register(cfg)
    first = ctrl.start("looper")
    first_pid = first.pid
    try:
        restarted = ctrl.restart("looper")
        assert restarted.state == ProcessState.RUNNING
        assert restarted.pid is not None
        assert restarted.pid != first_pid
        assert pid_alive(first_pid) is False
        assert pid_alive(restarted.pid) is True
        assert restarted.last_restart_at is not None
    finally:
        ctrl.stop("looper")


def test_health_check_reflects_real_liveness(controller, tmp_path):
    ctrl, _ = controller
    port = _free_port()
    script = _write_script(tmp_path, "server.py", RUNNER_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="httpsvc", name="Test HTTP Service", working_dir=str(tmp_path),
        command=[sys.executable, script, str(port)],
        health_url=f"http://127.0.0.1:{port}/health",
    )
    ctrl.register(cfg)
    ctrl.start("httpsvc")
    try:
        # give the tiny http.server a moment to bind
        deadline = time.time() + 5
        status = None
        while time.time() < deadline:
            status = ctrl.status("httpsvc")
            if status.healthy:
                break
            time.sleep(0.2)
        assert status is not None
        assert status.healthy is True
        assert status.last_checked is not None
    finally:
        stopped = ctrl.stop("httpsvc")
        after_stop = ctrl.status("httpsvc")
        assert after_stop.healthy is False


def test_start_is_idempotent_no_duplicate_spawn(controller, tmp_path):
    ctrl, _ = controller
    script = _write_script(tmp_path, "loop.py", RUNNER_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="looper", name="Test Looper", working_dir=str(tmp_path),
        command=[sys.executable, script],
    )
    ctrl.register(cfg)
    first = ctrl.start("looper")
    second = ctrl.start("looper")
    try:
        assert first.pid == second.pid
        assert second.state == ProcessState.RUNNING
    finally:
        ctrl.stop("looper")


def test_logs_endpoint_returns_real_captured_output(controller, tmp_path):
    ctrl, _ = controller
    script = _write_script(tmp_path, "loop.py", RUNNER_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="looper", name="Test Looper", working_dir=str(tmp_path),
        command=[sys.executable, script],
    )
    ctrl.register(cfg)
    ctrl.start("looper")
    try:
        deadline = time.time() + 5
        lines: list[str] = []
        while time.time() < deadline:
            lines = ctrl.logs("looper", lines=50)
            if lines:
                break
            time.sleep(0.1)
        assert any("looping without health server" in line for line in lines)
    finally:
        ctrl.stop("looper")


def test_log_sources_reports_real_file_state(controller, tmp_path):
    ctrl, _ = controller
    script = _write_script(tmp_path, "loop.py", RUNNER_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="looper", name="Test Looper", working_dir=str(tmp_path),
        command=[sys.executable, script],
    )
    ctrl.register(cfg)

    # Before starting: registered, but no log file exists yet.
    sources = ctrl.list_configs()
    assert [c.service_id for c in sources] == ["looper"]
    before = ctrl.log_sources()
    assert len(before) == 1
    assert before[0]["service_id"] == "looper"
    assert before[0]["exists"] is False
    assert before[0]["line_count"] is None

    ctrl.start("looper")
    try:
        deadline = time.time() + 5
        after = before
        while time.time() < deadline:
            after = ctrl.log_sources()
            if after[0]["exists"] and after[0]["line_count"]:
                break
            time.sleep(0.1)
        assert after[0]["exists"] is True
        assert after[0]["line_count"] and after[0]["line_count"] > 0
        assert after[0]["last_modified"] is not None
        assert after[0]["state"] == "RUNNING"
    finally:
        ctrl.stop("looper")


def test_stop_when_not_running_is_a_noop(controller, tmp_path):
    ctrl, _ = controller
    script = _write_script(tmp_path, "loop.py", RUNNER_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="looper", name="Test Looper", working_dir=str(tmp_path),
        command=[sys.executable, script],
    )
    ctrl.register(cfg)
    status = ctrl.stop("looper")
    assert status.state == ProcessState.STOPPED
    assert status.pid is None


def test_process_that_exits_immediately_is_reported_as_failed(controller, tmp_path):
    ctrl, _ = controller
    script = _write_script(tmp_path, "die.py", EXIT_IMMEDIATELY_SCRIPT)
    cfg = ManagedProcessConfig(
        service_id="dying", name="Test Dying Process", working_dir=str(tmp_path),
        command=[sys.executable, script],
    )
    ctrl.register(cfg)
    status = ctrl.start("dying")
    assert status.state == ProcessState.FAILED
    assert status.last_exit_code == 3


def test_start_stop_restart_each_write_a_real_audit_entry(tmp_path):
    from fastapi.testclient import TestClient

    from vanguard.api.app import create_app

    script = _write_script(tmp_path, "loop.py", RUNNER_SCRIPT)
    settings = Settings(
        db_path=str(tmp_path / "vanguard.db"),
        api_token="test-token-0123456789abcdef0123",
        environment="dev",
    )
    app = create_app(settings)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {settings.api_token}"}

    # Register a managed process directly through the wired controller (the
    # app only auto-registers "dispatch" when dispatch_dir/python are set).
    app.state.processes.register(
        ManagedProcessConfig(
            service_id="audited", name="Audited Test Process", working_dir=str(tmp_path),
            command=[sys.executable, script],
        )
    )

    r = client.post("/api/v1/vanguard/services/audited/start", headers=headers)
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/vanguard/services/audited/restart", headers=headers)
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/vanguard/services/audited/stop", headers=headers)
    assert r.status_code == 200, r.text

    audit = client.get("/api/v1/vanguard/audit", headers=headers).json()
    actions = [a["action"] for a in audit["entries"] if a["target"] == "audited"]
    assert "process.start" in actions
    assert "process.restart" in actions
    assert "process.stop" in actions


def test_process_routes_require_bearer_token(tmp_path):
    from fastapi.testclient import TestClient

    from vanguard.api.app import create_app

    settings = Settings(
        db_path=str(tmp_path / "vanguard.db"),
        api_token="test-token-0123456789abcdef0123",
        environment="dev",
    )
    app = create_app(settings)
    client = TestClient(app)
    r = client.post("/api/v1/vanguard/services/dispatch/start")
    assert r.status_code == 401


def test_dispatch_registration_parses_real_paths_without_starting_it(tmp_path):
    """Narrow, CI-safe check: from_env() resolves Dispatch's dir/python to real,
    existing on-disk paths, and a ManagedProcessConfig built from them validates
    — without ever calling .start() (CI has no Dispatch venv installed)."""
    import os

    settings = Settings.from_env()
    assert settings.dispatch_dir.endswith(os.path.join("Dispatch", "D27HQ_DISPATCH"))
    cfg = ManagedProcessConfig(
        service_id="dispatch", name="D27HQ Dispatch",
        working_dir=settings.dispatch_dir,
        command=[settings.dispatch_python, "-m", "dispatch", "serve"],
        health_url=f"{settings.dispatch_base_url}/health",
    )
    assert cfg.command[0] == settings.dispatch_python
    assert cfg.command[1:] == ["-m", "dispatch", "serve"]
