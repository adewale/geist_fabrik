"""Integration tests for Vault with concurrent access."""

import threading
from pathlib import Path

from geistfabrik import Vault


def test_concurrent_sync(tmp_path: Path) -> None:
    """Test that concurrent sync operations don't corrupt the database (AC-1.18)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create some notes
    for i in range(5):
        note_file = vault_path / f"note_{i}.md"
        note_file.write_text(f"# Note {i}\n\nContent for note {i}")

    db_path = tmp_path / "vault.db"

    # Function to sync in a thread
    def sync_vault() -> None:
        vault = Vault(vault_path, db_path)
        vault.sync()
        vault.close()

    # Run multiple threads concurrently
    threads = []
    for _ in range(3):
        thread = threading.Thread(target=sync_vault)
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

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
