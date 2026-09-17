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
