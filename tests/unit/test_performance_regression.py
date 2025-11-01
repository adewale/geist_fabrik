"""Performance regression tests.

These tests ensure that performance optimizations don't regress in future
changes. They don't measure absolute performance, but rather verify that
optimizations are in place and working correctly.
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


def test_similarity_computation_uses_vectorized_backend():
    """Test that similarity operations delegate to vectorized backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        (vault_path / "note_a.md").write_text("# Note A\n\nSome content here")
        (vault_path / "note_b.md").write_text("# Note B\n\nSimilar content here")

        vault = Vault(vault_path)
        vault.sync()

        session = Session(date=datetime(2025, 1, 15), db=vault.db)
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(vault, session)

        note_a = context.get_note("note_a.md")
        note_b = context.get_note("note_b.md")

        assert note_a is not None
        assert note_b is not None

        # Mock the backend's get_similarity method
        context._backend.get_similarity = MagicMock(return_value=0.85)

        # Call similarity
        sim = context.similarity(note_a, note_b)

        # Should have delegated to backend
        context._backend.get_similarity.assert_called_once_with(note_a.path, note_b.path)
        assert sim == 0.85


def test_has_link_uses_links_between_not_multiple_calls():
    """Test that has_link() calls links_between() once, not multiple times."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        (vault_path / "note_a.md").write_text("# Note A\n\n[[note_b]]")
        (vault_path / "note_b.md").write_text("# Note B")

        vault = Vault(vault_path)
        vault.sync()

        session = Session(date=datetime(2025, 1, 15), db=vault.db)
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(vault, session)

        note_a = context.get_note("note_a.md")
        note_b = context.get_note("note_b.md")

        assert note_a is not None
        assert note_b is not None

        # Mock links_between to track calls
        original_links_between = context.links_between
        context.links_between = MagicMock(wraps=original_links_between)

        # Call has_link
        result = context.has_link(note_a, note_b)

        # Should call links_between exactly once
        assert context.links_between.call_count == 1
        assert result is True


def test_graph_neighbors_uses_set_for_deduplication():
    """Test that graph_neighbors() returns deduplicated results."""
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

        neighbors_a = context.graph_neighbors(note_a)

        # B should appear exactly once, not twice (even though A→B and B→A)
        assert neighbors_a.count(note_b) == 1
        assert len(neighbors_a) == 1


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

        # Mock resolve_link_target to track calls
        original_resolve = context.resolve_link_target
        context.resolve_link_target = MagicMock(wraps=original_resolve)

        # Call outgoing_links
        outgoing = context.outgoing_links(note_a)

        # Should resolve each link exactly once (2 links = 2 resolutions)
        assert context.resolve_link_target.call_count == 2
        assert len(outgoing) == 2


@pytest.mark.skipif(
    True, reason="Benchmark test - run manually with pytest -k test_stats_vectorized_performance"
)
def test_stats_vectorized_performance():
    """Benchmark test: Verify vectorized stats are faster than naive implementation.

    This test is skipped by default but can be run manually to validate
    the performance improvement from vectorized similarity computations.
    """
    import time

    import numpy as np

    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create 100 test notes
        for i in range(100):
            (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent for note {i}")

        vault = Vault(vault_path)
        vault.sync()

        session = Session(date=datetime(2025, 1, 15), db=vault.db)
        session.compute_embeddings(vault.all_notes())

        embeddings_dict = session.get_all_embeddings()
        embeddings_array = np.array(list(embeddings_dict.values()))

        # Naive implementation (O(n²) nested loops)
        start_naive = time.perf_counter()
        naive_sims = []
        for i in range(len(embeddings_array)):
            for j in range(i + 1, len(embeddings_array)):
                sim = float(np.dot(embeddings_array[i], embeddings_array[j]))
                naive_sims.append(sim)
        naive_time = time.perf_counter() - start_naive

        # Vectorized implementation
        try:
            from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
                cosine_similarity,
            )

            start_vectorized = time.perf_counter()
            similarity_matrix = cosine_similarity(embeddings_array)
            _ = similarity_matrix[np.triu_indices_from(similarity_matrix, k=1)]
            vectorized_time = time.perf_counter() - start_vectorized

            # Vectorized should be significantly faster
            speedup = naive_time / vectorized_time
            print(f"\nNaive time: {naive_time:.4f}s")
            print(f"Vectorized time: {vectorized_time:.4f}s")
            print(f"Speedup: {speedup:.1f}x")

            # Conservative assertion: vectorized should be at least 2x faster
            assert speedup > 2.0, f"Expected >2x speedup, got {speedup:.1f}x"

        except ImportError:
            pytest.skip("sklearn not available")


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

    # Mock resolve_link_target to track resolution calls
    original_resolve = context.resolve_link_target
    context.resolve_link_target = MagicMock(wraps=original_resolve)

    # First call - should resolve links
    result1 = context.outgoing_links(note_a)
    assert context.resolve_link_target.call_count == 1

    # Second call - should use cache (no new resolutions)
    result2 = context.outgoing_links(note_a)
    assert context.resolve_link_target.call_count == 1  # Still 1

    # Verify results are identical
    assert result1 is result2
    assert len(result1) == 1


def test_graph_neighbors_caching(temp_vault):
    """Test that graph_neighbors() uses cache on repeated calls."""
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
    result1 = context.graph_neighbors(note_a)

    # Second call - should use cache
    result2 = context.graph_neighbors(note_a)

    # Verify results are identical (same object from cache)
    assert result1 is result2
    assert len(result1) > 0
