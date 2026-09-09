"""Crash-recoverable session-journal writer with mirrored suggestion history."""

import errno
import hashlib
import json
import logging
import os
import secrets
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from .models import Suggestion
from .path_safety import PathSafetyError, ensure_contained
from .suggestion_limits import validate_session_suggestions

logger = logging.getLogger(__name__)
_PENDING_VERSION = 1
_MAX_PENDING_BYTES = 16 * 1024
_EMPTY_FILE_HASH = hashlib.sha256(b"").hexdigest()


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_rows(rows: list[tuple[str, str, str]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _hash_bytes(payload)


def _fsync_directory(directory: Path) -> None:
    """Persist directory entries, ignoring only unsupported-platform errors."""
    unsupported = {errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError as exc:
        if os.name == "nt" or exc.errno in unsupported:
            return
        raise
    try:
        os.fsync(descriptor)
    except OSError as exc:
        if os.name != "nt" and exc.errno not in unsupported:
            raise
    finally:
        os.close(descriptor)


class JournalWriter:
    """Write contained session notes while owning the matching DB transaction.

    The database write lock is retained until a failed file replacement has
    been restored. A durable pending record lets the next writer distinguish a
    committed update from a process death and reconcile the file accordingly.
    """

    def __init__(self, vault_path: Path, db: sqlite3.Connection):
        self.vault_path = vault_path.resolve(strict=True)
        self.db = db
        self.journal_dir = self.vault_path / "geist journal"
        if self.journal_dir.exists() and not self.db.in_transaction:
            ensure_contained(
                self.journal_dir,
                self.vault_path,
                must_exist=True,
                reject_symlinks=True,
            )
            self._recover_all_pending()

    def _safe_session_path(self, date: datetime, *, create_dir: bool) -> Path:
        ensure_contained(self.journal_dir, self.vault_path, reject_symlinks=True)
        if create_dir:
            self.journal_dir.mkdir(exist_ok=True)
        ensure_contained(self.journal_dir, self.vault_path, must_exist=True, reject_symlinks=True)
        path = self.journal_dir / f"{date:%Y-%m-%d}.md"
        if path.is_symlink():
            raise PathSafetyError(f"Session note must not be a symlink: {path}")
        ensure_contained(path, self.vault_path, reject_symlinks=True)
        return path

    def _pending_paths(self, session_path: Path) -> tuple[Path, Path]:
        return (
            self.journal_dir / f".{session_path.name}.pending",
            self.journal_dir / f".{session_path.name}.previous",
        )

    def _stage_sibling(
        self, path: Path, content: bytes, suffix: str, descriptor: int | None
    ) -> Path:
        """Create and fsync a temporary sibling through the stable directory handle."""
        if descriptor is None:
            fd, temporary_name = tempfile.mkstemp(
                dir=self.journal_dir, prefix=path.name, suffix=suffix
            )
            temporary_path = Path(temporary_name)
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            while True:
                temporary_path = self.journal_dir / (f".{path.name}.{secrets.token_hex(8)}{suffix}")
                try:
                    fd = os.open(temporary_path.name, flags, 0o600, dir_fd=descriptor)
                    break
                except FileExistsError:
                    continue
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            self._unlink_sibling(temporary_path, descriptor)
            raise
        return temporary_path

    def _atomic_write(
        self,
        path: Path,
        content: bytes,
        suffix: str,
        descriptor: int | None = None,
    ) -> None:
        temporary_path = self._stage_sibling(path, content, suffix, descriptor)
        try:
            self._replace_sibling(temporary_path, path, descriptor)
            self._fsync_journal(descriptor)
        finally:
            self._unlink_sibling(temporary_path, descriptor)

    def _open_journal_descriptor(self) -> int | None:
        """Open a no-follow directory handle where descriptor-relative I/O exists."""
        if os.name == "nt" or not hasattr(os, "O_DIRECTORY"):
            return None
        flags = os.O_RDONLY | os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        return os.open(self.journal_dir, flags)

    def _assert_journal_identity(self, descriptor: int | None) -> None:
        """Reject a managed-directory swap before the matching DB commit."""
        ensure_contained(
            self.journal_dir,
            self.vault_path,
            must_exist=True,
            reject_symlinks=True,
        )
        if descriptor is not None:
            opened = os.fstat(descriptor)
            current = os.stat(self.journal_dir, follow_symlinks=False)
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise PathSafetyError("Journal directory identity changed during write")

    def _read_sibling(self, path: Path, descriptor: int | None) -> bytes | None:
        """Read one journal sibling without following a replaced directory path."""
        try:
            if descriptor is None:
                return path.read_bytes()
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            file_descriptor = os.open(path.name, flags, dir_fd=descriptor)
        except FileNotFoundError:
            return None
        with os.fdopen(file_descriptor, "rb") as handle:
            return handle.read()

    def _unlink_sibling(self, path: Path, descriptor: int | None) -> None:
        """Remove one journal sibling relative to the verified directory handle."""
        try:
            if descriptor is None:
                path.unlink()
            else:
                os.unlink(path.name, dir_fd=descriptor)
        except FileNotFoundError:
            pass

    def _replace_sibling(self, source: Path, destination: Path, descriptor: int | None) -> None:
        """Replace sibling names without re-resolving a potentially swapped parent."""
        if descriptor is None:
            os.replace(source, destination)
        else:
            os.replace(
                source.name,
                destination.name,
                src_dir_fd=descriptor,
                dst_dir_fd=descriptor,
            )

    def _fsync_journal(self, descriptor: int | None) -> None:
        """Persist the opened journal directory even if its pathname was swapped."""
        if descriptor is None:
            _fsync_directory(self.journal_dir)
            return
        try:
            os.fsync(descriptor)
        except OSError as exc:
            unsupported = {
                errno.EINVAL,
                errno.ENOTSUP,
                getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
            }
            if exc.errno not in unsupported:
                raise

    def _install_staged_file(
        self,
        temporary_path: Path,
        session_path: Path,
        *,
        replace_existing: bool,
        descriptor: int | None,
        expected_destination_hash: str | None,
    ) -> None:
        """Install staged bytes after a final descriptor-relative snapshot check."""
        destination = self._read_sibling(session_path, descriptor)
        destination_hash = _hash_bytes(destination) if destination is not None else None
        if destination_hash != expected_destination_hash:
            raise RuntimeError(
                f"Journal changed immediately before replacement: {session_path}; "
                "preserving the edit"
            )
        unsupported = {
            errno.EPERM,
            errno.ENOTSUP,
            errno.ENOSYS,
            errno.EXDEV,
            getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
        }
        if replace_existing:
            if descriptor is not None:
                os.replace(
                    temporary_path.name,
                    session_path.name,
                    src_dir_fd=descriptor,
                    dst_dir_fd=descriptor,
                )
            else:
                os.replace(temporary_path, session_path)
            return
        try:
            if descriptor is not None:
                os.link(
                    temporary_path.name,
                    session_path.name,
                    src_dir_fd=descriptor,
                    dst_dir_fd=descriptor,
                    follow_symlinks=False,
                )
            else:
                os.link(temporary_path, session_path)
        except OSError as exc:
            if exc.errno not in unsupported:
                raise
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if descriptor is not None:
                reservation = os.open(session_path.name, flags, 0o600, dir_fd=descriptor)
            else:
                reservation = os.open(session_path, flags, 0o600)
            os.close(reservation)
            try:
                if descriptor is not None:
                    os.replace(
                        temporary_path.name,
                        session_path.name,
                        src_dir_fd=descriptor,
                        dst_dir_fd=descriptor,
                    )
                else:
                    os.replace(temporary_path, session_path)
                return
            except BaseException:
                if descriptor is not None:
                    os.unlink(session_path.name, dir_fd=descriptor)
                else:
                    session_path.unlink(missing_ok=True)
                raise
        if descriptor is not None:
            os.unlink(temporary_path.name, dir_fd=descriptor)
        else:
            temporary_path.unlink()

    def _database_state_hash(self, date_str: str) -> str:
        rows = [
            (str(geist_id), str(text), str(block_id))
            for geist_id, text, block_id in self.db.execute(
                """
                SELECT geist_id, suggestion_text, block_id
                FROM session_suggestions
                WHERE session_date = ?
                ORDER BY block_id
                """,
                (date_str,),
            ).fetchall()
        ]
        return _hash_rows(rows)

    def _expected_state_hash(self, date: datetime, suggestions: list[Suggestion]) -> str:
        rows = [
            (suggestion.geist_id, suggestion.text, self._generate_block_id(date, index))
            for index, suggestion in enumerate(suggestions, start=1)
        ]
        rows.sort(key=lambda row: row[2])
        return _hash_rows(rows)

    def _write_pending_record(
        self,
        session_path: Path,
        *,
        had_old_file: bool,
        expected_database_hash: str,
        expected_file_hash: str,
        old_file_hash: str | None,
        descriptor: int | None = None,
    ) -> tuple[Path, Path]:
        pending_path, backup_path = self._pending_paths(session_path)
        record = {
            "version": _PENDING_VERSION,
            "session": session_path.name,
            "had_old_file": had_old_file,
            "expected_database_hash": expected_database_hash,
            "expected_file_hash": expected_file_hash,
            "old_file_hash": old_file_hash,
        }
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self._atomic_write(pending_path, encoded, ".record", descriptor)
        return pending_path, backup_path

    def _read_pending_record(
        self, pending_path: Path, session_path: Path, descriptor: int | None = None
    ) -> dict[str, object]:
        if descriptor is None:
            ensure_contained(pending_path, self.vault_path, must_exist=True, reject_symlinks=True)
        raw = self._read_sibling(pending_path, descriptor)
        if raw is None:
            raise RuntimeError(f"Journal recovery record disappeared: {pending_path}")
        if len(raw) > _MAX_PENDING_BYTES:
            raise RuntimeError(f"Journal recovery record is oversized: {pending_path}")
        try:
            record = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid journal recovery record: {pending_path}") from exc
        if not isinstance(record, dict) or any(not isinstance(key, str) for key in record):
            raise RuntimeError(f"Invalid journal recovery record: {pending_path}")
        if record.get("version") != _PENDING_VERSION or record.get("session") != session_path.name:
            raise RuntimeError(f"Unsupported journal recovery record: {pending_path}")
        if not isinstance(record.get("had_old_file"), bool):
            raise RuntimeError(f"Invalid journal recovery record: {pending_path}")
        for key in ("expected_database_hash", "expected_file_hash"):
            value = record.get(key)
            if not isinstance(value, str) or len(value) != 64:
                raise RuntimeError(f"Invalid journal recovery record: {pending_path}")
        old_file_hash = record.get("old_file_hash")
        if old_file_hash is not None and (
            not isinstance(old_file_hash, str) or len(old_file_hash) != 64
        ):
            raise RuntimeError(f"Invalid journal recovery record: {pending_path}")
        return record

    def _recover_pending_locked(self, session_path: Path, descriptor: int | None = None) -> None:
        """Reconcile one pending write while this connection owns the DB lock."""
        pending_path, backup_path = self._pending_paths(session_path)
        if self._read_sibling(pending_path, descriptor) is None:
            return
        record = self._read_pending_record(pending_path, session_path, descriptor)
        expected_database_hash = record["expected_database_hash"]
        expected_file_hash = record["expected_file_hash"]
        old_file_hash = record["old_file_hash"]
        assert isinstance(expected_database_hash, str)
        assert isinstance(expected_file_hash, str)
        assert old_file_hash is None or isinstance(old_file_hash, str)
        date_str = session_path.stem
        current_content = self._read_sibling(session_path, descriptor)
        current_file_hash = _hash_bytes(current_content) if current_content is not None else None
        database_committed = self._database_state_hash(date_str) == expected_database_hash
        if not database_committed:
            had_old_file = record["had_old_file"]
            assert isinstance(had_old_file, bool)
            if current_file_hash == expected_file_hash:
                if had_old_file:
                    backup_content = self._read_sibling(backup_path, descriptor)
                    if backup_content is None:
                        raise RuntimeError(
                            f"Journal recovery backup disappeared: {backup_path}; "
                            "preserving the generated journal and recovery record"
                        )
                    if _hash_bytes(backup_content) != old_file_hash:
                        raise RuntimeError(
                            f"Journal recovery backup is corrupt: {backup_path}; "
                            "preserving the generated journal and recovery record"
                        )
                    self._replace_sibling(backup_path, session_path, descriptor)
                else:
                    self._unlink_sibling(session_path, descriptor)
            elif had_old_file and current_file_hash == old_file_hash:
                # The process died before replacing the journal; it is already old.
                pass
            elif not had_old_file and current_file_hash in {None, _EMPTY_FILE_HASH}:
                # Exclusive-create fallback may die after its empty reservation.
                self._unlink_sibling(session_path, descriptor)
            else:
                raise RuntimeError(
                    f"Journal recovery conflict: {session_path} was edited after an "
                    "uncommitted write; preserving the file and recovery record"
                )
        # Remove the backup first: a pending record without its backup fails
        # safely, while a backup without its discovery record is orphaned.
        self._unlink_sibling(backup_path, descriptor)
        self._unlink_sibling(pending_path, descriptor)
        self._fsync_journal(descriptor)

    def _recover_all_pending(self) -> None:
        descriptor = self._open_journal_descriptor()
        try:
            self._assert_journal_identity(descriptor)
            if descriptor is None:
                pending_paths = sorted(self.journal_dir.glob(".*.md.pending"))
            else:
                pending_paths = [
                    self.journal_dir / name
                    for name in sorted(os.listdir(descriptor))
                    if name.startswith(".") and name.endswith(".md.pending")
                ]
            if not pending_paths:
                return
            self.db.execute("BEGIN IMMEDIATE")
            try:
                for pending_path in pending_paths:
                    session_name = pending_path.name[1 : -len(".pending")]
                    session_path = self.journal_dir / session_name
                    ensure_contained(session_path, self.vault_path, reject_symlinks=True)
                    self._recover_pending_locked(session_path, descriptor)
                self._assert_journal_identity(descriptor)
                self.db.commit()
            except BaseException:
                if self.db.in_transaction:
                    self.db.rollback()
                raise
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def write_session(
        self,
        date: datetime,
        suggestions: list[Suggestion],
        mode: str = "default",
        overwrite: bool = False,
    ) -> Path:
        """Atomically write a session and make database history an exact mirror.

        Raises:
            RuntimeError: If the supplied connection already has a transaction.
        """
        if self.db.in_transaction:
            raise RuntimeError("JournalWriter requires an idle SQLite connection")
        validate_session_suggestions(suggestions)

        session_path = self._safe_session_path(date, create_dir=True)
        journal_descriptor = self._open_journal_descriptor()
        try:
            self._assert_journal_identity(journal_descriptor)
            content = self._format_session_note(date, suggestions, mode).encode("utf-8")
            expected_database_hash = self._expected_state_hash(date, suggestions)
            expected_file_hash = _hash_bytes(content)
            temporary_path = self._stage_sibling(session_path, content, ".tmp", journal_descriptor)
        except BaseException:
            if journal_descriptor is not None:
                os.close(journal_descriptor)
            raise
        transaction_active = False
        replaced = False
        pending_created = False
        existed = False
        old_file_hash: str | None = None
        pending_path, backup_path = self._pending_paths(session_path)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            transaction_active = True
            self._recover_pending_locked(session_path, journal_descriptor)

            old_content = self._read_sibling(session_path, journal_descriptor)
            existed = old_content is not None
            if existed and not overwrite:
                raise FileExistsError(
                    f"Session note already exists: {session_path}. Use --force to overwrite."
                )
            old_file_hash = _hash_bytes(old_content) if old_content is not None else None
            if old_content is not None:
                self._atomic_write(backup_path, old_content, ".backup", journal_descriptor)
            self._write_pending_record(
                session_path,
                had_old_file=existed,
                expected_database_hash=expected_database_hash,
                expected_file_hash=expected_file_hash,
                old_file_hash=old_file_hash,
                descriptor=journal_descriptor,
            )
            pending_created = True
            self._assert_journal_identity(journal_descriptor)

            self._replace_suggestion_rows(date.strftime("%Y-%m-%d"), suggestions)
            self._assert_journal_identity(journal_descriptor)
            # Do not overwrite a user edit made after the snapshot/backup.
            current_content = self._read_sibling(session_path, journal_descriptor)
            current_hash = _hash_bytes(current_content) if current_content is not None else None
            if current_hash != old_file_hash:
                raise RuntimeError(
                    f"Journal changed during write: {session_path}; preserving the edit"
                )
            self._install_staged_file(
                temporary_path,
                session_path,
                replace_existing=existed,
                descriptor=journal_descriptor,
                expected_destination_hash=old_file_hash,
            )
            replaced = True
            self._assert_journal_identity(journal_descriptor)
            self._fsync_journal(journal_descriptor)
            self._assert_journal_identity(journal_descriptor)
            self.db.commit()
            transaction_active = False
            try:
                self._unlink_sibling(backup_path, journal_descriptor)
                self._unlink_sibling(pending_path, journal_descriptor)
                self._fsync_journal(journal_descriptor)
            except OSError as cleanup_error:
                # Recovery sees matching DB/file hashes and safely removes these later.
                logger.warning("Could not remove journal recovery files: %s", cleanup_error)
            return session_path
        except BaseException as original_error:
            restore_error: OSError | None = None
            rollback_error: sqlite3.Error | None = None
            conflict_error: RuntimeError | None = None
            database_committed = (
                not self.db.in_transaction
                and self._database_state_hash(date.strftime("%Y-%m-%d")) == expected_database_hash
            )
            if replaced and not database_committed:
                try:
                    current_content = self._read_sibling(session_path, journal_descriptor)
                    current_file_hash = (
                        _hash_bytes(current_content) if current_content is not None else None
                    )
                    if current_file_hash == expected_file_hash:
                        backup_content = self._read_sibling(backup_path, journal_descriptor)
                        if existed and backup_content is None:
                            conflict_error = RuntimeError(
                                f"Journal rollback backup is unavailable: {backup_path}; "
                                "preserving the generated journal and recovery record"
                            )
                        elif backup_content is not None:
                            if _hash_bytes(backup_content) != old_file_hash:
                                conflict_error = RuntimeError(
                                    f"Journal rollback backup is corrupt: {backup_path}; "
                                    "preserving the generated journal and recovery record"
                                )
                            else:
                                self._replace_sibling(backup_path, session_path, journal_descriptor)
                                self._fsync_journal(journal_descriptor)
                        else:
                            self._unlink_sibling(session_path, journal_descriptor)
                            self._fsync_journal(journal_descriptor)
                    elif current_file_hash != old_file_hash:
                        conflict_error = RuntimeError(
                            f"Journal rollback conflict: {session_path} was edited after "
                            "replacement; preserving the edit and recovery record"
                        )
                except OSError as exc:
                    restore_error = exc
            if not database_committed and (transaction_active or self.db.in_transaction):
                try:
                    self.db.rollback()
                except sqlite3.Error as exc:
                    rollback_error = exc
            if (
                restore_error is None
                and conflict_error is None
                and pending_created
                and not database_committed
            ):
                self._unlink_sibling(backup_path, journal_descriptor)
                self._unlink_sibling(pending_path, journal_descriptor)
                self._fsync_journal(journal_descriptor)
            if conflict_error is not None:
                raise conflict_error from original_error
            if restore_error is not None or rollback_error is not None:
                raise RuntimeError(
                    "Journal write failed and recovery was incomplete: "
                    f"restore={restore_error!r}, rollback={rollback_error!r}"
                ) from original_error
            raise
        finally:
            self._unlink_sibling(temporary_path, journal_descriptor)
            if journal_descriptor is not None:
                os.close(journal_descriptor)

    def _format_session_note(self, date: datetime, suggestions: list[Suggestion], mode: str) -> str:
        formatted_date = f"{date:%B} {date.day}, {date:%Y}"
        lines = [f"# GeistFabrik Session – {formatted_date}", ""]
        if mode != "default":
            lines.extend([f"_Mode: {mode}_", ""])
        if not suggestions:
            lines.append("_No suggestions generated this session._")
        else:
            for index, suggestion in enumerate(suggestions, start=1):
                block_id = self._generate_block_id(date, index)
                lines.extend([f"## {suggestion.geist_id} {block_id}", suggestion.text, ""])
        lines.extend(["---", "", "_Generated by GeistFabrik_"])
        return "\n".join(lines)

    def _generate_block_id(self, date: datetime, index: int) -> str:
        return f"^g{date:%Y%m%d}-{index:03d}"

    def _replace_suggestion_rows(self, date_str: str, suggestions: list[Suggestion]) -> None:
        now = datetime.now().isoformat()
        self.db.execute("DELETE FROM session_suggestions WHERE session_date = ?", (date_str,))
        rows = [
            (
                date_str,
                suggestion.geist_id,
                suggestion.text,
                self._generate_block_id(datetime.fromisoformat(date_str), index),
                now,
            )
            for index, suggestion in enumerate(suggestions, start=1)
        ]
        if rows:
            self.db.executemany(
                """
                INSERT INTO session_suggestions
                (session_date, geist_id, suggestion_text, block_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def session_exists(self, date: datetime) -> bool:
        return (
            self._safe_session_path(date, create_dir=False).exists()
            if self.journal_dir.exists()
            else False
        )

    def get_recent_suggestions(self, days: int = 60) -> list[str]:
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = self.db.execute(
            """
            SELECT suggestion_text FROM session_suggestions
            WHERE session_date >= ? ORDER BY session_date DESC
            """,
            (cutoff,),
        )
        return [str(row[0]) for row in cursor.fetchall()]
