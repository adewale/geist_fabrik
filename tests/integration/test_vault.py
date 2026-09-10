"""Integration tests for Vault with concurrent access."""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from geistfabrik import Vault
from geistfabrik.embeddings import Session
from geistfabrik.schema import init_db


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
            barrier.wait()
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


def test_concurrent_same_date_session_creation_is_idempotent(tmp_path: Path) -> None:
    """Concurrent creators reuse the date's one canonical session row."""
    db_path = tmp_path / "sessions.db"
    init_db(db_path).close()
    barrier = threading.Barrier(3)

    def create_session() -> int:
        db = init_db(db_path)
        try:
            barrier.wait()
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
