"""Real backup/restore of VANGUARD's own SQLite database.

Backup creation uses `Database.backup_to_file()` (the real SQLite online
backup API, `sqlite3.Connection.backup()`) to get a consistent copy even
while the app is handling other requests, then zips that copy into a
self-contained `backup-<timestamp>.zip` bundle under `backup_dir`. Real
size/sha256/source-path metadata is written as a JSON sidecar file
(`<backup_id>.json`) next to the bundle — NOT a SQLite table in VANGUARD's own
db. That was tried first and discarded for a real reason: a restore replaces
the *entire* live db file with an older snapshot's bytes, which would also
silently roll back a `backups` table living in that same db — erasing the
metadata row for the very backup just restored from, and for the pre-restore
safety snapshot taken moments earlier, even though both bundles are real,
untouched files sitting right there in `backup_dir`. Storing metadata outside
the db file that gets restored avoids that problem entirely instead of
patching it after the fact. Nothing here is ever fabricated: every field on a
`BackupRecord` is computed from the actual bundle bytes on disk at creation
time.

Restore is the one genuinely dangerous operation in this module, so it is
deliberately synchronous and does, in order:
  1. Look the backup up and confirm its file still exists on disk.
  2. Verify the bundle's sha256 checksum BEFORE touching anything live — a
     mismatch aborts immediately with no live-db change at all.
  3. Take a real safety snapshot of the CURRENT live db (via the same
     `create_backup()` path used for a normal backup) so a bad restore can
     always be undone.
  4. Extract the target bundle's db file to a temp path and swap it in via
     `Database.restore_from()`, which closes/reopens the app's one shared
     SQLite connection under its lock (see core/db.py for the exact, honestly
     documented limitation of what that can and cannot serialize against).

This is a local reference service backing up ITS OWN db — not a general
backup product, not cloud storage.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ..core.db import Database
from ..core.models import BackupRecord, RestoreResult

# Reason string used for the automatic pre-restore safety snapshot. Backups
# with this reason are excluded from retention pruning (see _apply_retention)
# so an operator can never lose their one guaranteed undo point to a manual
# backup's retention limit.
SAFETY_SNAPSHOT_REASON = "pre_restore_safety_snapshot"

DB_ENTRY_NAME = "vanguard.db"
BUNDLE_GLOB = "backup-*.zip"


class ChecksumMismatchError(Exception):
    """Raised when a backup bundle's on-disk sha256 no longer matches its
    recorded metadata. Restore aborts immediately on this — nothing live is
    ever touched."""


class BackupFileMissingError(Exception):
    """Raised when a backup's sidecar metadata exists but its bundle file is
    gone from disk."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def _parse_timestamp_from_id(backup_id: str) -> str | None:
    """Best-effort recovery of a real creation timestamp from a
    `backup-<timestamp>` id, used only as a last-resort fallback if a
    bundle's sidecar file is itself missing/corrupt (see list_backups).
    Returns None (never a guess) if the id doesn't match the format this
    module always generates."""
    prefix = "backup-"
    if not backup_id.startswith(prefix):
        return None
    raw = backup_id[len(prefix):]
    try:
        dt = datetime.strptime(raw, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return None


class BackupManager:
    def __init__(self, db: Database, backup_dir: str, retain_count: int):
        self.db = db
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.retain_count = retain_count

    # ------------------------------------------------------------- paths
    def _bundle_path(self, backup_id: str) -> Path:
        return self.backup_dir / f"{backup_id}.zip"

    def _sidecar_path(self, backup_id: str) -> Path:
        return self.backup_dir / f"{backup_id}.json"

    def _write_sidecar(self, record: BackupRecord) -> None:
        data = record.model_dump(exclude={"file_exists"})
        self._sidecar_path(record.backup_id).write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _read_sidecar(self, backup_id: str) -> BackupRecord | None:
        path = self._sidecar_path(backup_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        try:
            return BackupRecord.model_validate(data)
        except Exception:  # noqa: BLE001 - a corrupt sidecar falls back below, never crashes a list/get
            return None

    def _record_for_bundle(self, zip_path: Path) -> BackupRecord:
        """The sidecar is normally authoritative (written once, at creation
        time, and never edited). If it's missing or unreadable — e.g. an
        operator dropped a stray zip into backup_dir by hand, or a sidecar
        write failed independently of its bundle — every field here is
        recomputed from the real bytes on disk instead of being fabricated."""
        backup_id = zip_path.stem
        record = self._read_sidecar(backup_id)
        if record is not None:
            return record
        created_at = _parse_timestamp_from_id(backup_id) or datetime.fromtimestamp(
            zip_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
        return BackupRecord(
            backup_id=backup_id,
            filename=zip_path.name,
            path=str(zip_path),
            size_bytes=zip_path.stat().st_size,
            sha256=sha256_of_file(zip_path),
            source_db_path=self.db.db_path,
            reason="unknown (sidecar metadata missing)",
            created_at=created_at,
        )

    # ------------------------------------------------------------- creation
    def create_backup(self, reason: str = "manual") -> BackupRecord:
        """Real, consistent backup: online-backup the live db to a temp file,
        zip it, hash the real zip bytes, write a real sidecar. Applies
        retention afterward (skipped for safety snapshots — see module doc)."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_id = f"backup-{timestamp}"
        filename = f"{backup_id}.zip"
        zip_path = self.backup_dir / filename

        with tempfile.TemporaryDirectory() as tmp:
            tmp_db_path = Path(tmp) / DB_ENTRY_NAME
            self.db.backup_to_file(str(tmp_db_path))
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(tmp_db_path, arcname=DB_ENTRY_NAME)

        record = BackupRecord(
            backup_id=backup_id,
            filename=filename,
            path=str(zip_path),
            size_bytes=zip_path.stat().st_size,
            sha256=sha256_of_file(zip_path),
            source_db_path=self.db.db_path,
            reason=reason,
            created_at=_now(),
        )
        self._write_sidecar(record)

        if reason != SAFETY_SNAPSHOT_REASON:
            self._apply_retention()

        return record

    def _apply_retention(self) -> list[str]:
        """Keep the most recent `retain_count` MANUAL/job-triggered backups;
        delete the rest (bundle + sidecar). Safety snapshots are never
        counted or touched here. Returns the ids actually deleted."""
        manual = [b for b in self.list_backups() if b.reason != SAFETY_SNAPSHOT_REASON]
        excess = manual[self.retain_count:]
        deleted: list[str] = []
        for record in excess:
            if self.delete_backup(record.backup_id):
                deleted.append(record.backup_id)
        return deleted

    # ------------------------------------------------------------- reading
    def list_backups(self) -> list[BackupRecord]:
        """Every real bundle actually present in backup_dir, most recent
        first — derived live from the filesystem each call (see module doc
        for why this isn't a db table), so it can never drift from what's
        really on disk."""
        records = [
            self._record_for_bundle(p).model_copy(update={"file_exists": True})
            for p in sorted(self.backup_dir.glob(BUNDLE_GLOB))
        ]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records

    def get_backup(self, backup_id: str) -> BackupRecord | None:
        zip_path = self._bundle_path(backup_id)
        sidecar_path = self._sidecar_path(backup_id)
        if not zip_path.exists() and not sidecar_path.exists():
            return None
        if not zip_path.exists():
            # Sidecar survives with no bundle — report it honestly rather
            # than pretending the backup is still restorable.
            record = self._read_sidecar(backup_id)
            if record is None:
                return None
            return record.model_copy(update={"file_exists": False})
        return self._record_for_bundle(zip_path).model_copy(update={"file_exists": True})

    # ------------------------------------------------------------- deletion
    def delete_backup(self, backup_id: str) -> bool:
        zip_path = self._bundle_path(backup_id)
        sidecar_path = self._sidecar_path(backup_id)
        existed = zip_path.exists() or sidecar_path.exists()
        if zip_path.exists():
            zip_path.unlink()
        if sidecar_path.exists():
            sidecar_path.unlink()
        return existed

    # -------------------------------------------------------------- restore
    def restore_backup(self, backup_id: str, reason: str = "") -> RestoreResult:
        record = self.get_backup(backup_id)
        if record is None:
            raise FileNotFoundError(f"Backup '{backup_id}' not found")

        bundle_path = Path(record.path)
        if not record.file_exists or not bundle_path.exists():
            raise BackupFileMissingError(
                f"Backup '{backup_id}' has metadata but its bundle file is missing "
                f"on disk at {bundle_path} — refusing to restore from nothing"
            )

        # Step 1: verify checksum BEFORE touching anything live. A tampered or
        # truncated bundle is rejected here and the live db is never touched.
        actual_sha256 = sha256_of_file(bundle_path)
        if not _constant_time_eq(actual_sha256, record.sha256):
            raise ChecksumMismatchError(
                f"Checksum mismatch for backup '{backup_id}': expected {record.sha256}, "
                f"got {actual_sha256} — bundle may be corrupted or tampered with; "
                "restore refused, live database left untouched"
            )

        # Step 2: real safety snapshot of the CURRENT live db, taken before
        # any destructive action, so this restore can always be undone. Its
        # sidecar is written to backup_dir independently of the live db file
        # about to be overwritten, so it survives step 3 intact.
        safety_snapshot = self.create_backup(reason=SAFETY_SNAPSHOT_REASON)

        # Step 3: extract the verified bundle's db file and swap it in under
        # the shared Database's lock (see core/db.py restore_from()).
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(bundle_path, "r") as zf:
                zf.extract(DB_ENTRY_NAME, path=tmp)
            extracted_path = Path(tmp) / DB_ENTRY_NAME
            self.db.restore_from(str(extracted_path))

        return RestoreResult(
            restored_backup_id=backup_id,
            safety_snapshot_id=safety_snapshot.backup_id,
            verified_sha256=actual_sha256,
            restored_at=_now(),
        )
