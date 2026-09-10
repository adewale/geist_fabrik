"""Unit tests for Vault class."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from geistfabrik import Vault


def test_vault_path_not_exists() -> None:
    """Test Vault raises error if path doesn't exist."""
    with pytest.raises(FileNotFoundError):
        Vault("/nonexistent/path")


def test_vault_path_is_file(tmp_path: Path) -> None:
    """Test Vault raises error if path is a file."""
    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    with pytest.raises(NotADirectoryError):
        Vault(test_file)


def test_permission_denied(tmp_path: Path) -> None:
    """Test Vault handles permission denied errors gracefully (AC-1.15)."""
    # Skip if running as root (chmod won't prevent root from reading)
    if os.geteuid() == 0:
        pytest.skip("Permission test not applicable when running as root")

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a note with no read permissions
    note_file = vault_path / "test.md"
    note_file.write_text("# Test\n\nContent")
    note_file.chmod(0o000)

    # Create vault
    vault = Vault(vault_path, ":memory:")

    try:
        # Sync should handle permission error gracefully (skip the file)
        # It should not crash, just skip unreadable files
        count = vault.sync()
        # Should process 0 files (the file is unreadable)
        assert count == 0
    finally:
        # Restore permissions for cleanup
        note_file.chmod(0o644)
        vault.close()


def test_vault_init(tmp_path: Path) -> None:
    """Test Vault initializes correctly."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault = Vault(vault_path)
    assert vault.vault_path == vault_path
    assert vault.db is not None
    vault.close()


def test_sync_no_changes(tmp_path: Path) -> None:
    """Test sync with no changes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a note
    note_file = vault_path / "test.md"
    note_file.write_text("# Test\n\nContent")

    vault = Vault(vault_path)

    # First sync should process the file
    count = vault.sync()
    assert count == 1

    # Second sync should skip unchanged file
    count = vault.sync()
    assert count == 0

    vault.close()


def test_sync_modified_file(tmp_path: Path) -> None:
    """Test sync processes modified files."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    note_file = vault_path / "test.md"
    note_file.write_text("# Test v1")

    vault = Vault(vault_path)

    # First sync
    vault.sync()
    note1 = vault.get_note("test.md")
    assert note1 is not None
    assert "v1" in note1.content

    # Modify file and advance mtime deterministically.
    previous_mtime = note_file.stat().st_mtime
    note_file.write_text("# Test v2")
    os.utime(note_file, (previous_mtime + 2, previous_mtime + 2))

    # Second sync should reprocess
    count = vault.sync()
    assert count == 1

    note2 = vault.get_note("test.md")
    assert note2 is not None
    assert "v2" in note2.content

    vault.close()


def test_sync_update_preserves_temporal_history_and_invalidates_semantic_cache(
    tmp_path: Path,
) -> None:
    """A same-path edit preserves history while invalidating derived semantic cache."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    note_file = vault_path / "test.md"
    note_file.write_text("# Original\n\nFirst version")
    db_path = tmp_path / "vault.db"
    vault = Vault(vault_path, db_path)

    assert vault.sync() == 1
    vault.db.execute(
        "INSERT INTO sessions (date, created_at) VALUES (?, ?)",
        ("2024-01-01", "2024-01-01T00:00:00"),
    )
    session_id = vault.db.execute(
        "SELECT session_id FROM sessions WHERE date = ?", ("2024-01-01",)
    ).fetchone()
    assert session_id is not None
    vault.db.execute(
        "INSERT INTO embeddings (note_path, embedding, model_version, computed_at) "
        "VALUES (?, ?, ?, ?)",
        ("test.md", b"semantic", "test", "2024-01-01T00:00:00"),
    )
    vault.db.execute(
        "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
        (session_id[0], "test.md", b"historical"),
    )
    vault.db.commit()

    previous_mtime = note_file.stat().st_mtime
    note_file.write_text("# Updated\n\nSecond version")
    os.utime(note_file, (previous_mtime + 2, previous_mtime + 2))

    assert vault.sync() == 1
    assert vault.db.execute(
        "SELECT 1 FROM embeddings WHERE note_path = ?", ("test.md",)
    ).fetchone() is None
    historical = vault.db.execute(
        "SELECT embedding FROM session_embeddings WHERE session_id = ? AND note_path = ?",
        (session_id[0], "test.md"),
    ).fetchone()
    assert historical == (b"historical",)

    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as observer:
        assert observer.execute(
            "SELECT title FROM notes WHERE path = ?", ("test.md",)
        ).fetchone() == ("Updated",)
        assert observer.execute(
            "SELECT embedding FROM session_embeddings WHERE session_id = ? AND note_path = ?",
            (session_id[0], "test.md"),
        ).fetchone() == (b"historical",)
    vault.close()


def test_sync_failure_rolls_back_and_retry_succeeds(tmp_path: Path) -> None:
    """A mid-sync SQL failure cannot leak partial state into a later commit."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    note_file = vault_path / "test.md"
    note_file.write_text("# Original\n\nFirst version")
    db_path = tmp_path / "vault.db"
    vault = Vault(vault_path, db_path)
    assert vault.sync() == 1

    vault.db.execute(
        """
        CREATE TRIGGER fail_test_link_insert
        BEFORE INSERT ON links
        WHEN NEW.source_path = 'test.md'
        BEGIN
            SELECT RAISE(ABORT, 'injected sync failure');
        END
        """
    )
    vault.db.commit()
    previous_mtime = note_file.stat().st_mtime
    note_file.write_text("# Updated\n\nSecond version links to [[Target]]")
    os.utime(note_file, (previous_mtime + 2, previous_mtime + 2))

    with pytest.raises(sqlite3.IntegrityError, match="injected sync failure"):
        vault.sync()

    assert vault.db.in_transaction is False
    assert vault.db.execute(
        "SELECT title, content FROM notes WHERE path = ?", ("test.md",)
    ).fetchone() == ("Original", "# Original\n\nFirst version")
    assert vault.db.execute("SELECT * FROM links").fetchall() == []

    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as observer:
        assert observer.execute(
            "SELECT title FROM notes WHERE path = ?", ("test.md",)
        ).fetchone() == ("Original",)
        assert observer.execute("SELECT * FROM links").fetchall() == []

    vault.db.execute("DROP TRIGGER fail_test_link_insert")
    vault.db.commit()
    assert vault.sync() == 1
    retried_note = vault.get_note("test.md")
    assert retried_note is not None
    assert retried_note.title == "Updated"
    assert vault.db.execute(
        "SELECT target FROM links WHERE source_path = ?", ("test.md",)
    ).fetchall() == [("Target",)]
    vault.close()


def test_date_collection_update_preserves_only_stable_path_history(tmp_path: Path) -> None:
    """Refreshing a journal preserves history for retained virtual-note paths."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    journal_path = vault_path / "journal.md"
    journal_path.write_text(
        "# Journal\n\n## 2024-01-01\n\nOriginal\n\n## 2024-01-02\n\nRemoved"
    )
    vault = Vault(vault_path)
    assert vault.sync() == 2

    vault.db.execute(
        "INSERT INTO sessions (date, created_at) VALUES (?, ?)",
        ("2024-02-01", "2024-02-01T00:00:00"),
    )
    session_id = vault.db.execute(
        "SELECT session_id FROM sessions WHERE date = ?", ("2024-02-01",)
    ).fetchone()
    assert session_id is not None
    for path in ("journal.md/2024-01-01", "journal.md/2024-01-02"):
        vault.db.execute(
            "INSERT INTO embeddings (note_path, embedding, model_version, computed_at) "
            "VALUES (?, ?, ?, ?)",
            (path, b"semantic", "test", "2024-02-01T00:00:00"),
        )
        vault.db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) "
            "VALUES (?, ?, ?)",
            (session_id[0], path, path.encode()),
        )
    vault.db.commit()

    previous_mtime = journal_path.stat().st_mtime
    journal_path.write_text(
        "# Journal\n\n## 2024-01-01\n\nUpdated\n\n## 2024-01-03\n\nAdded"
    )
    os.utime(journal_path, (previous_mtime + 2, previous_mtime + 2))

    assert vault.sync() == 2
    assert vault.db.execute(
        "SELECT note_path FROM embeddings ORDER BY note_path"
    ).fetchall() == []
    assert vault.db.execute(
        "SELECT note_path FROM session_embeddings ORDER BY note_path"
    ).fetchall() == [("journal.md/2024-01-01",)]
    vault.close()


def test_all_notes(tmp_path: Path) -> None:
    """Test retrieving all notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create multiple notes
    (vault_path / "note1.md").write_text("# Note 1")
    (vault_path / "note2.md").write_text("# Note 2")
    (vault_path / "note3.md").write_text("# Note 3")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    assert len(notes) == 3
    assert all(note.path.endswith(".md") for note in notes)

    vault.close()


def test_get_note(tmp_path: Path) -> None:
    """Test retrieving specific note."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "test.md").write_text("# Test Note\n\nContent")

    vault = Vault(vault_path)
    vault.sync()

    note = vault.get_note("test.md")
    assert note is not None
    assert note.path == "test.md"
    assert note.title == "Test Note"
    assert "Content" in note.content

    vault.close()


def test_get_note_not_found(tmp_path: Path) -> None:
    """Test get_note returns None for non-existent note."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault = Vault(vault_path)
    vault.sync()

    note = vault.get_note("nonexistent.md")
    assert note is None

    vault.close()


def test_parse_links(tmp_path: Path) -> None:
    """Test parsing links from notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    content = "# Note\n\nLink to [[Other Note]] and ![[Embed]]"
    (vault_path / "test.md").write_text(content)

    vault = Vault(vault_path)
    vault.sync()

    note = vault.get_note("test.md")
    assert note is not None
    assert len(note.links) == 2
    assert note.links[0].target == "Other Note"
    assert not note.links[0].is_embed
    assert note.links[1].target == "Embed"
    assert note.links[1].is_embed

    vault.close()


def test_parse_tags(tmp_path: Path) -> None:
    """Test parsing tags from notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    content = """---
tags: [frontmatter-tag]
---

# Note

Content with #inline-tag
"""
    (vault_path / "test.md").write_text(content)

    vault = Vault(vault_path)
    vault.sync()

    note = vault.get_note("test.md")
    assert note is not None
    assert len(note.tags) >= 2
    assert "frontmatter-tag" in note.tags
    assert "inline-tag" in note.tags

    vault.close()


def test_invalid_utf8(tmp_path: Path) -> None:
    """Test handling invalid UTF-8 encoding."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create file with invalid UTF-8
    note_file = vault_path / "test.md"
    note_file.write_bytes(b"# Test\n\nInvalid: \xff\xfe")

    vault = Vault(vault_path)
    # Should not crash, just skip the file
    count = vault.sync()
    assert count == 0  # File skipped due to encoding error

    vault.close()


def test_circular_links(tmp_path: Path) -> None:
    """Test handling circular links (A→B→C→A)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "a.md").write_text("[[b]]")
    (vault_path / "b.md").write_text("[[c]]")
    (vault_path / "c.md").write_text("[[a]]")

    vault = Vault(vault_path)
    vault.sync()

    # Should handle circular links without issues
    note_a = vault.get_note("a.md")
    note_b = vault.get_note("b.md")
    note_c = vault.get_note("c.md")

    assert note_a is not None
    assert note_b is not None
    assert note_c is not None

    vault.close()


def test_broken_links(tmp_path: Path) -> None:
    """Test tracking broken links (links to non-existent notes)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    content = "Link to [[NonExistent Note]]"
    (vault_path / "test.md").write_text(content)

    vault = Vault(vault_path)
    vault.sync()

    note = vault.get_note("test.md")
    assert note is not None
    # Link should still be recorded, even if target doesn't exist
    assert len(note.links) == 1
    assert note.links[0].target == "NonExistent Note"

    vault.close()


def test_self_referencing_notes(tmp_path: Path) -> None:
    """Test handling notes that link to themselves."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    content = "# Self\n\nLink to [[self]]"
    (vault_path / "self.md").write_text(content)

    vault = Vault(vault_path)
    vault.sync()

    note = vault.get_note("self.md")
    assert note is not None
    assert len(note.links) == 1
    assert note.links[0].target == "self"

    vault.close()


def test_case_insensitive_links(tmp_path: Path) -> None:
    """Test case sensitivity in link handling."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Note.md").write_text("# Note")
    content = "Link to [[note]] and [[Note]] and [[NOTE]]"
    (vault_path / "test.md").write_text(content)

    vault = Vault(vault_path)
    vault.sync()

    note = vault.get_note("test.md")
    assert note is not None
    # All three links should be recorded (case preserved)
    assert len(note.links) == 3

    vault.close()


def test_duplicate_titles_different_folders(tmp_path: Path) -> None:
    """Test handling notes with same title in different folders."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / "folder1").mkdir()
    (vault_path / "folder2").mkdir()

    (vault_path / "folder1" / "note.md").write_text("# Note\n\nFolder 1")
    (vault_path / "folder2" / "note.md").write_text("# Note\n\nFolder 2")

    vault = Vault(vault_path)
    vault.sync()

    note1 = vault.get_note("folder1/note.md")
    note2 = vault.get_note("folder2/note.md")

    assert note1 is not None
    assert note2 is not None
    assert note1.title == note2.title  # Same title
    assert note1.path != note2.path  # Different paths
    assert "Folder 1" in note1.content
    assert "Folder 2" in note2.content

    vault.close()


def test_large_note(tmp_path: Path) -> None:
    """Test handling notes larger than 1MB."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a large note (>1MB)
    large_content = "# Large Note\n\n" + ("x" * (1024 * 1024 + 1000))
    (vault_path / "large.md").write_text(large_content)

    vault = Vault(vault_path)
    count = vault.sync()
    assert count == 1

    note = vault.get_note("large.md")
    assert note is not None
    assert len(note.content) > 1024 * 1024

    vault.close()
