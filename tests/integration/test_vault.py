"""Integration tests for Vault with concurrent access."""

import os
import sqlite3
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest

import geistfabrik.vault as vault_module
from geistfabrik import Vault
from geistfabrik.embeddings import Session
from geistfabrik.schema import init_db
from geistfabrik.sqlite_transaction import owned_transaction as real_owned_transaction


def test_concurrent_sync(tmp_path: Path) -> None:
    """Test that concurrent sync operations don't corrupt the database (AC-1.18)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create some notes
    for i in range(5):
        note_file = vault_path / f"note_{i}.md"
        note_file.write_text(f"# Note {i}\n\nContent for note {i}")

    db_path = tmp_path / "vault.db"

    barrier = threading.Barrier(3)

    def sync_vault() -> int:
        vault = Vault(vault_path, db_path)
        try:
            barrier.wait(timeout=5)
            return vault.sync()
        finally:
            vault.close()

    # Every future is observed: a worker-side lock or transaction failure must
    # fail this test instead of being swallowed by Thread.run().
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(sync_vault) for _ in range(3)]
        processed_counts = [future.result() for future in futures]

    assert sorted(processed_counts) == [0, 0, 5]

    # Verify database is not corrupted
    vault = Vault(vault_path, db_path)
    notes = vault.all_notes()

    # Should have all 5 notes
    assert len(notes) == 5

    # Verify all notes are accessible
    for note in notes:
        assert note.title.startswith("Note")
        assert "Content for note" in note.content

    vault.close()


def test_sync_discovers_files_only_after_acquiring_writer_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A synchronizer waiting for SQLite cannot delete from a stale pre-lock scan."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    note_path = vault_path / "note.md"
    content = "# Note\n\nHistorical content"
    note_path.write_text(content)
    db_path = tmp_path / "vault.db"

    seed = Vault(vault_path, db_path)
    assert seed.sync() == 1
    seed.db.execute(
        "INSERT INTO sessions (date, created_at) VALUES (?, ?)",
        ("2024-01-01", "2024-01-01T00:00:00"),
    )
    session_id = seed.db.execute(
        "SELECT session_id FROM sessions WHERE date = ?", ("2024-01-01",)
    ).fetchone()
    assert session_id is not None
    seed.db.execute(
        "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
        (session_id[0], "note.md", b"historical"),
    )
    seed.db.commit()
    seed.close()

    blocker = init_db(db_path)
    worker_ready = threading.Event()
    start_sync = threading.Event()
    lock_attempted = threading.Event()

    @contextmanager
    def signalling_transaction(db: sqlite3.Connection, operation: str) -> Iterator[None]:
        if operation == "Vault.sync":
            lock_attempted.set()
        with real_owned_transaction(db, operation):
            yield

    monkeypatch.setattr(vault_module, "owned_transaction", signalling_transaction)

    def sync_waiting_on_lock() -> int:
        vault = Vault(vault_path, db_path)
        try:
            worker_ready.set()
            assert start_sync.wait(timeout=5)
            return vault.sync()
        finally:
            vault.close()

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(sync_waiting_on_lock)
            assert worker_ready.wait(timeout=5)
            blocker.execute("BEGIN IMMEDIATE")
            note_path.unlink()
            start_sync.set()
            assert lock_attempted.wait(timeout=5)
            note_path.write_text(content)
            blocker.commit()
            future.result(timeout=5)
    finally:
        if blocker.in_transaction:
            blocker.rollback()
        blocker.close()

    observer = init_db(db_path)
    try:
        assert observer.execute(
            "SELECT title FROM notes WHERE path = ?", ("note.md",)
        ).fetchone() == ("Note",)
        assert observer.execute(
            "SELECT embedding FROM session_embeddings WHERE session_id = ? AND note_path = ?",
            (session_id[0], "note.md"),
        ).fetchone() == (b"historical",)
    finally:
        observer.close()


def test_sync_retries_when_filesystem_changes_during_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A changing source rolls back the first attempt and publishes the stable retry."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    note_path = vault_path / "note.md"
    note_path.write_text("# Original\n\nOld content")
    vault = Vault(vault_path)
    original_discover = vault._discover_markdown_files
    original_validate = vault._snapshot_is_current
    discovery_count = 0
    validation_count = 0

    def counted_discovery() -> list[tuple[Path, Path, os.stat_result]]:
        nonlocal discovery_count
        discovery_count += 1
        return original_discover()

    def validate_with_one_change(
        md_files: list[tuple[Path, Path, os.stat_result]],
    ) -> bool:
        nonlocal validation_count
        validation_count += 1
        if validation_count == 1:
            old_mtime = note_path.stat().st_mtime
            note_path.write_text("# Updated\n\nNew content")
            # Preserve mtime: inode/size/ctime identity must still invalidate.
            os.utime(note_path, (old_mtime, old_mtime))
        return original_validate(md_files)

    monkeypatch.setattr(vault, "_discover_markdown_files", counted_discovery)
    monkeypatch.setattr(vault, "_snapshot_is_current", validate_with_one_change)
    try:
        assert vault.sync() == 1
        note = vault.get_note("note.md")
        assert note is not None
        assert note.title == "Updated"
        assert note.content == "# Updated\n\nNew content"
        assert discovery_count == 2
        assert validation_count == 2
    finally:
        vault.close()


def test_sync_repeated_filesystem_changes_fail_without_partial_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exhausted snapshot retries leave the previous committed mirror intact."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    note_path = vault_path / "note.md"
    note_path.write_text("# Original\n\nCommitted content")
    vault = Vault(vault_path)
    assert vault.sync() == 1
    previous_mtime = note_path.stat().st_mtime
    note_path.write_text("# Candidate\n\nUnstable content")
    os.utime(note_path, (previous_mtime + 2, previous_mtime + 2))

    original_discover = vault._discover_markdown_files
    original_validate = vault._snapshot_is_current
    discovery_count = 0
    validation_count = 0

    def counted_discovery() -> list[tuple[Path, Path, os.stat_result]]:
        nonlocal discovery_count
        discovery_count += 1
        return original_discover()

    def validate_while_changing(
        md_files: list[tuple[Path, Path, os.stat_result]],
    ) -> bool:
        nonlocal validation_count
        validation_count += 1
        current_mtime = note_path.stat().st_mtime
        note_path.write_text(f"# Candidate {validation_count}\n\nStill changing")
        os.utime(note_path, (current_mtime + 2, current_mtime + 2))
        return original_validate(md_files)

    monkeypatch.setattr(vault, "_discover_markdown_files", counted_discovery)
    monkeypatch.setattr(vault, "_snapshot_is_current", validate_while_changing)
    try:
        with pytest.raises(vault_module.VaultSyncConflictError, match="changed repeatedly"):
            vault.sync()
        assert discovery_count == 3
        assert validation_count == 3
        assert vault.db.in_transaction is False
        assert vault.db.execute(
            "SELECT title, content FROM notes WHERE path = ?", ("note.md",)
        ).fetchone() == ("Original", "# Original\n\nCommitted content")
    finally:
        vault.close()


def test_concurrent_same_date_session_creation_is_idempotent(tmp_path: Path) -> None:
    """Concurrent creators reuse the date's one canonical session row."""
    db_path = tmp_path / "sessions.db"
    init_db(db_path).close()
    barrier = threading.Barrier(3)

    def create_session() -> int:
        db = init_db(db_path)
        try:
            barrier.wait(timeout=5)
            return Session(datetime(2024, 1, 1), db).session_id
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(create_session) for _ in range(3)]
        session_ids = [future.result() for future in futures]

    assert len(set(session_ids)) == 1
    observer = init_db(db_path)
    try:
        assert observer.execute(
            "SELECT date FROM sessions ORDER BY session_id"
        ).fetchall() == [("2024-01-01",)]
    finally:
        observer.close()
