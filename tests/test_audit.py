from vanguard.audit.writer import AuditWriter
from vanguard.core.db import Database
from vanguard.core.models import AuditEntry


def test_write_and_list(tmp_path):
    db = Database(str(tmp_path / "audit.db"))
    writer = AuditWriter(db)
    written = writer.write(AuditEntry(
        actor="operator", action="node.register", target="n1", source="api",
        before=None, after={"node_id": "n1"}, reason="initial registration",
    ))
    assert written.entry_id is not None

    entries = writer.list()
    assert len(entries) == 1
    assert entries[0].action == "node.register"
    assert entries[0].after == {"node_id": "n1"}


def test_filter_by_actor_action_target(tmp_path):
    db = Database(str(tmp_path / "audit.db"))
    writer = AuditWriter(db)
    writer.write(AuditEntry(actor="operator", action="node.register", target="n1", source="api"))
    writer.write(AuditEntry(actor="operator", action="process.start", target="dispatch", source="api"))
    writer.write(AuditEntry(actor="job-worker", action="process.start", target="n2", source="api"))

    by_action = writer.list(action="process.start")
    assert {e.target for e in by_action} == {"dispatch", "n2"}

    by_actor = writer.list(actor="job-worker")
    assert len(by_actor) == 1
    assert by_actor[0].target == "n2"

    by_target = writer.list(target="dispatch")
    assert len(by_target) == 1
    assert by_target[0].action == "process.start"

    combined = writer.list(action="process.start", actor="operator")
    assert len(combined) == 1
    assert combined[0].target == "dispatch"


def test_filter_by_time_range(tmp_path):
    db = Database(str(tmp_path / "audit.db"))
    writer = AuditWriter(db)
    writer.write(AuditEntry(actor="a", action="x", target="1", source="api", created_at="2026-01-01T00:00:00+00:00"))
    writer.write(AuditEntry(actor="a", action="x", target="2", source="api", created_at="2026-06-01T00:00:00+00:00"))
    writer.write(AuditEntry(actor="a", action="x", target="3", source="api", created_at="2026-12-01T00:00:00+00:00"))

    since_mid = writer.list(since="2026-06-01T00:00:00+00:00")
    assert {e.target for e in since_mid} == {"2", "3"}

    until_mid = writer.list(until="2026-06-01T00:00:00+00:00")
    assert {e.target for e in until_mid} == {"1", "2"}

    windowed = writer.list(since="2026-01-02T00:00:00+00:00", until="2026-11-30T00:00:00+00:00")
    assert {e.target for e in windowed} == {"2"}


def test_pagination_limit_offset_and_count(tmp_path):
    db = Database(str(tmp_path / "audit.db"))
    writer = AuditWriter(db)
    for i in range(5):
        writer.write(AuditEntry(actor="a", action="x", target=str(i), source="api"))

    assert writer.count() == 5

    page1 = writer.list(limit=2, offset=0)
    page2 = writer.list(limit=2, offset=2)
    assert [e.target for e in page1] == ["4", "3"]
    assert [e.target for e in page2] == ["2", "1"]
