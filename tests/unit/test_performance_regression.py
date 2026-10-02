"""Performance regression tests.

These tests ensure that performance optimisations don't regress in future
changes. They don't measure absolute performance, but rather verify that
optimisations are in place and working correctly.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from geistfabrik.embeddings import Session
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


@pytest.fixture
def temp_vault():
    """Create a temporary vault with test notes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create 10 test notes
        for i in range(10):
            (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent {i}")

        yield vault_path


@pytest.fixture
def vault_context(temp_vault):
    """Create VaultContext with test vault."""
    vault = Vault(temp_vault)
    vault.sync()

    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())

    return VaultContext(vault, session)


def test_vault_notes_caching(vault_context):
    """Test that vault.notes() is cached and doesn't call vault.all_notes() multiple times."""
    # Mock the underlying vault.all_notes() method
    original_all_notes = vault_context.vault.all_notes
    vault_context.vault.all_notes = MagicMock(wraps=original_all_notes)

    # First call - should invoke vault.all_notes()
    notes1 = vault_context.notes()
    assert len(notes1) == 10
    assert vault_context.vault.all_notes.call_count == 1

    # Second call - should use cache, not invoke vault.all_notes()
    notes2 = vault_context.notes()
    assert len(notes2) == 10
    assert vault_context.vault.all_notes.call_count == 1  # Still 1, not 2

    # Third call - still cached
    notes3 = vault_context.notes()
    assert len(notes3) == 10
    assert vault_context.vault.all_notes.call_count == 1

    # Verify same list is returned (identity check)
    assert notes1 is notes2
    assert notes2 is notes3


def test_vault_notes_cache_is_session_scoped(temp_vault):
    """Test that vault.notes() cache is per-session, not shared across sessions."""
    vault = Vault(temp_vault)
    vault.sync()

    # Session 1
    session1 = Session(date=datetime(2025, 1, 15), db=vault.db)
    session1.compute_embeddings(vault.all_notes())
    context1 = VaultContext(vault, session1)

    notes1 = context1.notes()
    assert len(notes1) == 10

    # Session 2 (new VaultContext)
    session2 = Session(date=datetime(2025, 1, 16), db=vault.db)
    session2.compute_embeddings(vault.all_notes())
    context2 = VaultContext(vault, session2)

    notes2 = context2.notes()
    assert len(notes2) == 10

    # Each session has its own cache
    assert notes1 is not notes2  # Different objects


def test_orphans_query_correctness():
    """Test that orphans() query correctly identifies orphan notes.

    Note: The orphans() method uses LEFT JOIN pattern (see vault_context.py:222-236)
    instead of NOT IN subquery for better performance. This test verifies the
    query produces correct results.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        (vault_path / "note_a.md").write_text("# Note A")
        (vault_path / "note_b.md").write_text("# Note B\n\n[[note_a]]")

        vault = Vault(vault_path)
        vault.sync()

        session = Session(date=datetime(2025, 1, 15), db=vault.db)
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(vault, session)

        # Call orphans()
        orphans = context.orphans()
        orphan_paths = {n.path for n in orphans}

        # note_a: has incoming link from note_b → NOT orphan
        # note_b: has outgoing link to note_a → NOT orphan
        # Both notes are connected, so no orphans
        assert len(orphan_paths) == 0

        # Add a truly orphaned note
        (vault_path / "note_c.md").write_text("# Note C\n\nNo links")
        vault.sync()

        # Recreate session and context
        session = Session(date=datetime(2025, 1, 15), db=vault.db)
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(vault, session)

        orphans = context.orphans()
        orphan_paths = {n.path for n in orphans}

        # Now note_c should be the only orphan
        assert "note_c.md" in orphan_paths
        assert len(orphan_paths) == 1


def test_composite_index_exists_for_links_table():
    """Test that idx_links_target_source composite index exists in database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        (vault_path / "note.md").write_text("# Note")

        vault = Vault(vault_path)
        vault.sync()

        # Check that composite index exists
        cursor = vault.db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_links_target_source'"
        )
        result = cursor.fetchone()

        assert result is not None, "Composite index idx_links_target_source should exist"
        assert result[0] == "idx_links_target_source"


def test_graph_neighbours_uses_set_for_deduplication():
    """Test that graph_neighbours() returns deduplicated results."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        # Bidirectional link between A and B
        (vault_path / "note_a.md").write_text("# Note A\n\n[[note_b]]")
        (vault_path / "note_b.md").write_text("# Note B\n\n[[note_a]]")

        vault = Vault(vault_path)
        vault.sync()

        session = Session(date=datetime(2025, 1, 15), db=vault.db)
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(vault, session)

        note_a = context.get_note("note_a.md")
        note_b = context.get_note("note_b.md")

        assert note_a is not None
        assert note_b is not None

        neighbours_a = context.graph_neighbours(note_a)

        # B should appear exactly once, not twice (even though A→B and B→A)
        assert neighbours_a.count(note_b) == 1
        assert len(neighbours_a) == 1


def test_outgoing_links_resolves_targets_efficiently():
    """Test that outgoing_links() resolves link targets without redundant lookups."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        (vault_path / "note_a.md").write_text("# Note A\n\n[[note_b]]\n[[note_c]]")
        (vault_path / "note_b.md").write_text("# Note B")
        (vault_path / "note_c.md").write_text("# Note C")

        vault = Vault(vault_path)
        vault.sync()

        session = Session(date=datetime(2025, 1, 15), db=vault.db)
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(vault, session)

        note_a = context.get_note("note_a.md")
        assert note_a is not None

        statements = []
        vault.db.set_trace_callback(statements.append)
        outgoing = context.outgoing_links(note_a)
        vault.db.set_trace_callback(None)

        # A bounded snapshot load replaces per-edge note/alias SQL lookups.
        assert len(statements) <= 3
        assert {note.path for note in outgoing} == {"note_b.md", "note_c.md"}


def test_backlinks_caching(temp_vault):
    """Test that backlinks() uses cache on repeated calls."""
    # Create notes with backlinks
    (temp_vault / "note_a.md").write_text("# Note A\n\n[[note_b]]")
    (temp_vault / "note_b.md").write_text("# Note B")

    vault = Vault(temp_vault)
    vault.sync()

    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(vault, session)

    note_b = context.get_note("note_b.md")
    assert note_b is not None

    # First call - populates cache
    result1 = context.backlinks(note_b)

    # Second call - should use cache
    result2 = context.backlinks(note_b)

    # Verify results are identical (same object from cache)
    assert result1 is result2
    assert len(result1) == 1  # note_a links to note_b


def test_outgoing_links_caching(temp_vault):
    """Test that outgoing_links() uses cache on repeated calls."""
    # Create linked notes
    (temp_vault / "note_a.md").write_text("# Note A\n\n[[note_b]]")
    (temp_vault / "note_b.md").write_text("# Note B")

    vault = Vault(temp_vault)
    vault.sync()

    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(vault, session)

    note_a = context.get_note("note_a.md")
    assert note_a is not None

    result1 = context.outgoing_links(note_a)
    statements = []
    vault.db.set_trace_callback(statements.append)
    result2 = context.outgoing_links(note_a)
    incoming = context.backlinks(result1[0])
    vault.db.set_trace_callback(None)
    assert statements == []
    assert incoming == [note_a]

    # Verify results are identical
    assert result1 is result2
    assert len(result1) == 1


def test_graph_neighbours_caching(temp_vault):
    """Test that graph_neighbours() uses cache on repeated calls."""
    # Create bidirectional links
    (temp_vault / "note_a.md").write_text("# Note A\n\n[[note_b]]")
    (temp_vault / "note_b.md").write_text("# Note B\n\n[[note_a]]")

    vault = Vault(temp_vault)
    vault.sync()

    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(vault, session)

    note_a = context.get_note("note_a.md")
    assert note_a is not None

    # First call
    result1 = context.graph_neighbours(note_a)

    # Second call - should use cache
    result2 = context.graph_neighbours(note_a)

    # Verify results are identical (same object from cache)
    assert result1 is result2
    assert len(result1) > 0
