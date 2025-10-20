"""Unit tests for Vault class."""

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
    import os
    import sys

    # Skip on Windows where permission model is different
    if sys.platform == "win32":
        pytest.skip("Permission test not applicable on Windows")

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

    # Modify file
    import time

    time.sleep(0.1)  # Ensure different mtime
    note_file.write_text("# Test v2")

    # Second sync should reprocess
    count = vault.sync()
    assert count == 1

    note2 = vault.get_note("test.md")
    assert note2 is not None
    assert "v2" in note2.content

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
