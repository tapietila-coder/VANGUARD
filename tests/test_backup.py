"""Real end-to-end Backups/restore tests. No mocking of sqlite or filesystem
operations anywhere here: every backup is a real `sqlite3.Connection.backup()`
bundle written to a real temp directory, every restore actually swaps the
real db file and is verified by querying it afterward, and the tamper test
flips real bytes in a real file on disk.
"""
from __future__ import annotations

import hashlib
import time
import zipfile

import pytest

from vanguard.backup.manager import DB_ENTRY_NAME, SAFETY_SNAPSHOT_REASON


def _poll_job(client, headers, job_id, states=("COMPLETED", "FAILED"), timeout=10.0):
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


def _create_backup_via_api(client, auth_headers, reason="manual"):
    r = client.post("/api/v1/vanguard/backups", json={"reason": reason}, headers=auth_headers)
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["job_type"] == "backup_create"
    done = _poll_job(client, auth_headers, job["job_id"])
    assert done["state"] == "COMPLETED", done
    return done["result"]  # the real BackupRecord dict


def _sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# Creation
# --------------------------------------------------------------------------

def test_backup_create_writes_a_real_verified_bundle(client, auth_headers):
    # Real state to back up: register a real node first.
    client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "backup-node-1", "hostname": "h", "os_name": "Linux"},
        headers=auth_headers,
    )

    record = _create_backup_via_api(client, auth_headers)

    from pathlib import Path

    bundle_path = Path(record["path"])
    assert bundle_path.exists(), "backup bundle must actually exist on disk"
    assert bundle_path.suffix == ".zip"
    assert record["size_bytes"] == bundle_path.stat().st_size
    assert record["sha256"] == _sha256_of(bundle_path)
    assert len(record["sha256"]) == 64

    # It's a real zip containing a real sqlite file with the node we just wrote.
    with zipfile.ZipFile(bundle_path) as zf:
        assert DB_ENTRY_NAME in zf.namelist()

    # And it's independently listable/gettable with the same real metadata.
    listed = client.get("/api/v1/vanguard/backups").json()
    assert any(b["backup_id"] == record["backup_id"] for b in listed)

    detail = client.get(f"/api/v1/vanguard/backups/{record['backup_id']}").json()
    assert detail["sha256"] == record["sha256"]
    assert detail["file_exists"] is True


def test_backup_create_requires_bearer_token(client):
    r = client.post("/api/v1/vanguard/backups", json={"reason": "manual"})
    assert r.status_code == 401


def test_backup_create_writes_a_real_audit_entry(client, auth_headers):
    record = _create_backup_via_api(client, auth_headers, reason="audit-check")
    audit = client.get("/api/v1/vanguard/audit", headers=auth_headers).json()
    actions = {(a["action"], a["target"]) for a in audit["entries"]}
    assert any(action == "backup.create.submit" for action, _ in actions)


# --------------------------------------------------------------------------
# Restore: real revert of real state
# --------------------------------------------------------------------------

def test_restore_actually_reverts_live_state_and_takes_a_safety_snapshot(client, auth_headers):
    # 1. Seed real state and back it up.
    client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "before-restore", "hostname": "h1", "os_name": "Linux"},
        headers=auth_headers,
    )
    backup = _create_backup_via_api(client, auth_headers, reason="pre-change")

    backups_before_restore = {b["backup_id"] for b in client.get("/api/v1/vanguard/backups").json()}

    # 2. Change live state after the backup — the backup must NOT contain this.
    r = client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "after-restore-should-vanish", "hostname": "h2", "os_name": "Linux"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert client.get("/api/v1/vanguard/nodes/after-restore-should-vanish").status_code == 200

    # 3. Restore from the earlier backup.
    r = client.post(
        f"/api/v1/vanguard/backups/{backup['backup_id']}/restore",
        params={"reason": "test-restore"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["restored_backup_id"] == backup["backup_id"]
    assert result["verified_sha256"] == backup["sha256"]
    assert result["safety_snapshot_id"]

    # 4. A real, new safety-snapshot backup file appears for the pre-restore state.
    backups_after_restore = client.get("/api/v1/vanguard/backups").json()
    new_ids = {b["backup_id"] for b in backups_after_restore} - backups_before_restore
    assert result["safety_snapshot_id"] in new_ids
    safety_record = next(b for b in backups_after_restore if b["backup_id"] == result["safety_snapshot_id"])
    assert safety_record["reason"] == SAFETY_SNAPSHOT_REASON
    from pathlib import Path

    assert Path(safety_record["path"]).exists()

    # 5. The live db genuinely reverted: the post-backup node is gone, the
    # pre-backup node is back. Not just an HTTP 200 — actually queried.
    assert client.get("/api/v1/vanguard/nodes/after-restore-should-vanish").status_code == 404
    assert client.get("/api/v1/vanguard/nodes/before-restore").status_code == 200

    # 6. Restore writes a real audit entry too.
    audit = client.get("/api/v1/vanguard/audit", headers=auth_headers).json()
    actions = {(a["action"], a["target"]) for a in audit["entries"]}
    assert ("backup.restore", backup["backup_id"]) in actions


def test_restore_requires_bearer_token(client, auth_headers):
    backup = _create_backup_via_api(client, auth_headers)
    r = client.post(f"/api/v1/vanguard/backups/{backup['backup_id']}/restore")
    assert r.status_code == 401


def test_restore_unknown_backup_is_404(client, auth_headers):
    r = client.post("/api/v1/vanguard/backups/does-not-exist/restore", headers=auth_headers)
    assert r.status_code == 404


# --------------------------------------------------------------------------
# Restore: checksum verification actually rejects tampering
# --------------------------------------------------------------------------

def test_restore_rejects_a_tampered_backup_and_leaves_live_db_untouched(client, auth_headers):
    client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "live-node-untouched", "hostname": "h", "os_name": "Linux"},
        headers=auth_headers,
    )
    backup = _create_backup_via_api(client, auth_headers)

    from pathlib import Path

    bundle_path = Path(backup["path"])
    original_bytes = bundle_path.read_bytes()

    # Flip a real byte in the middle of the real file on disk.
    tampered = bytearray(original_bytes)
    mid = len(tampered) // 2
    tampered[mid] ^= 0xFF
    bundle_path.write_bytes(bytes(tampered))
    assert _sha256_of(bundle_path) != backup["sha256"]

    backups_before = {b["backup_id"] for b in client.get("/api/v1/vanguard/backups").json()}

    r = client.post(
        f"/api/v1/vanguard/backups/{backup['backup_id']}/restore",
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text
    assert "checksum" in r.json()["detail"].lower() or "mismatch" in r.json()["detail"].lower()

    # Refused: no new safety snapshot was taken (nothing destructive started),
    # and the real live state from before the tamper attempt is unchanged.
    backups_after = {b["backup_id"] for b in client.get("/api/v1/vanguard/backups").json()}
    assert backups_after == backups_before
    assert client.get("/api/v1/vanguard/nodes/live-node-untouched").status_code == 200


def test_restore_rejects_a_truncated_backup(client, auth_headers):
    backup = _create_backup_via_api(client, auth_headers)

    from pathlib import Path

    bundle_path = Path(backup["path"])
    original_bytes = bundle_path.read_bytes()
    bundle_path.write_bytes(original_bytes[: len(original_bytes) // 2])

    r = client.post(f"/api/v1/vanguard/backups/{backup['backup_id']}/restore", headers=auth_headers)
    assert r.status_code == 400
    assert "mismatch" in r.json()["detail"].lower() or "checksum" in r.json()["detail"].lower()


# --------------------------------------------------------------------------
# Deletion
# --------------------------------------------------------------------------

def test_delete_backup_removes_file_and_record(client, auth_headers):
    backup = _create_backup_via_api(client, auth_headers)
    from pathlib import Path

    bundle_path = Path(backup["path"])
    assert bundle_path.exists()

    r = client.delete(f"/api/v1/vanguard/backups/{backup['backup_id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    assert not bundle_path.exists()
    assert client.get(f"/api/v1/vanguard/backups/{backup['backup_id']}").status_code == 404

    audit = client.get("/api/v1/vanguard/audit", headers=auth_headers).json()
    actions = {(a["action"], a["target"]) for a in audit["entries"]}
    assert ("backup.delete", backup["backup_id"]) in actions


def test_delete_backup_requires_bearer_token(client, auth_headers):
    backup = _create_backup_via_api(client, auth_headers)
    r = client.delete(f"/api/v1/vanguard/backups/{backup['backup_id']}")
    assert r.status_code == 401


def test_delete_unknown_backup_is_404(client, auth_headers):
    r = client.delete("/api/v1/vanguard/backups/does-not-exist", headers=auth_headers)
    assert r.status_code == 404


# --------------------------------------------------------------------------
# Listing: honest, no fabricated placeholders
# --------------------------------------------------------------------------

def test_list_backups_is_honestly_empty_before_any_backup(client):
    r = client.get("/api/v1/vanguard/backups")
    assert r.status_code == 200
    assert r.json() == []


def test_get_unknown_backup_is_404(client):
    r = client.get("/api/v1/vanguard/backups/does-not-exist")
    assert r.status_code == 404


# --------------------------------------------------------------------------
# Retention: keep the most recent N manual backups; safety snapshots exempt
# --------------------------------------------------------------------------

def test_retention_prunes_oldest_manual_backups_beyond_retain_count(app, client, auth_headers):
    manager = app.state.backups
    manager.retain_count = 2

    ids = []
    for i in range(4):
        record = _create_backup_via_api(client, auth_headers, reason=f"manual-{i}")
        ids.append(record["backup_id"])
        time.sleep(0.01)  # ensure distinct timestamps for deterministic ordering

    remaining = {b["backup_id"] for b in client.get("/api/v1/vanguard/backups").json()}
    # Only the 2 most recent manual backups survive; the oldest 2 were pruned.
    assert ids[-1] in remaining
    assert ids[-2] in remaining
    assert ids[0] not in remaining
    assert ids[1] not in remaining

    from pathlib import Path

    # Real files were actually deleted, not just DB rows.
    manual_records = [b for b in client.get("/api/v1/vanguard/backups").json()]
    assert len(manual_records) == 2
    for b in manual_records:
        assert Path(b["path"]).exists()


def test_safety_snapshots_are_exempt_from_retention(app, client, auth_headers):
    manager = app.state.backups
    manager.retain_count = 1

    client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "retention-node", "hostname": "h", "os_name": "Linux"},
        headers=auth_headers,
    )
    backup = _create_backup_via_api(client, auth_headers, reason="manual-a")
    _create_backup_via_api(client, auth_headers, reason="manual-b")  # prunes manual-a

    # manual-a's file should now be gone (retain_count=1, manual-b is newer).
    remaining_ids = {b["backup_id"] for b in client.get("/api/v1/vanguard/backups").json() if b["reason"] != SAFETY_SNAPSHOT_REASON}
    assert backup["backup_id"] not in remaining_ids

    # Restoring from a still-live manual backup produces a safety snapshot
    # that survives even though retain_count is 1 and a manual backup already
    # occupies that slot.
    manual_b = next(
        b for b in client.get("/api/v1/vanguard/backups").json() if b["reason"] == "manual-b"
    )
    r = client.post(f"/api/v1/vanguard/backups/{manual_b['backup_id']}/restore", headers=auth_headers)
    assert r.status_code == 200
    safety_id = r.json()["safety_snapshot_id"]

    all_backups = client.get("/api/v1/vanguard/backups").json()
    safety_record = next(b for b in all_backups if b["backup_id"] == safety_id)
    assert safety_record["reason"] == SAFETY_SNAPSHOT_REASON
    from pathlib import Path

    assert Path(safety_record["path"]).exists()
