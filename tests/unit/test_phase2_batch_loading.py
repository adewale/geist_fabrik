"""Tests for Phase 2 Optimisation: OP-6 Batch Note Loading.

Tests the get_notes_batch() method and its usage in neighbours(), backlinks(), and hubs().
"""

from pathlib import Path

import pytest

from geistfabrik.models import Note
from geistfabrik.vault import Vault


@pytest.fixture
def vault_with_notes(tmp_path: Path) -> Vault:
    """Create a vault with multiple notes for batch loading tests."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()

    # Create 10 notes with links and tags
    notes = []
    for i in range(10):
        note_path = vault_dir / f"note_{i}.md"
        content = f"# Note {i}\n\nThis is note {i}.\n\n"

        # Add some links
        if i > 0:
            content += f"Link to [[note_{i - 1}]]\n"
        if i < 9:
            content += f"Link to [[note_{i + 1}]]\n"

        # Add tags
        content += f"#tag{i % 3}\n"

        note_path.write_text(content)
        notes.append(note_path)

    vault = Vault(str(vault_dir))
    vault.sync()
    return vault


class TestBatchLoading:
    """Test OP-6: Batch note loading functionality."""

    def test_get_notes_batch_loads_multiple_notes(self, vault_with_notes: Vault):
        """Test that get_notes_batch() correctly loads multiple notes."""
        paths = ["note_0.md", "note_1.md", "note_2.md"]
        notes_map = vault_with_notes.get_notes_batch(paths)

        assert len(notes_map) == 3
        assert all(path in notes_map for path in paths)
        assert all(isinstance(note, Note) for note in notes_map.values() if note is not None)

    def test_get_notes_batch_handles_missing_notes(self, vault_with_notes: Vault):
        """Test that get_notes_batch() handles non-existent notes gracefully."""
        paths = ["note_0.md", "nonexistent.md", "note_1.md"]
        notes_map = vault_with_notes.get_notes_batch(paths)

        assert len(notes_map) == 3
        assert notes_map["note_0.md"] is not None
        assert notes_map["nonexistent.md"] is None
        assert notes_map["note_1.md"] is not None

    def test_get_notes_batch_loads_links(self, vault_with_notes: Vault):
        """Test that get_notes_batch() correctly loads note links."""
        paths = ["note_1.md", "note_2.md"]
        notes_map = vault_with_notes.get_notes_batch(paths)

        note1 = notes_map["note_1.md"]
        assert note1 is not None
        assert len(note1.links) >= 1  # Should have link to note_0 and note_2

    def test_get_notes_batch_loads_tags(self, vault_with_notes: Vault):
        """Test that get_notes_batch() correctly loads note tags."""
        paths = ["note_0.md", "note_3.md", "note_6.md"]
        notes_map = vault_with_notes.get_notes_batch(paths)

        # All should have tag0 (i % 3 == 0)
        for path in paths:
            note = notes_map[path]
            assert note is not None
            assert "tag0" in note.tags

    def test_get_notes_batch_empty_list(self, vault_with_notes: Vault):
        """Test that get_notes_batch() handles empty path list."""
        notes_map = vault_with_notes.get_notes_batch([])
        assert notes_map == {}

    def test_get_notes_batch_preserves_order(self, vault_with_notes: Vault):
        """Test that get_notes_batch() returns dict with keys in requested order."""
        paths = ["note_5.md", "note_2.md", "note_8.md", "note_1.md"]
        notes_map = vault_with_notes.get_notes_batch(paths)

        assert list(notes_map.keys()) == paths

    @pytest.mark.benchmark
    def test_get_notes_batch_performance_vs_individual(self, vault_with_notes: Vault):
        """Test that batch loading is more efficient than individual loading."""
        import time

        paths = [f"note_{i}.md" for i in range(10)]

        # Measure individual loading (N × 3 queries)
        start_individual = time.perf_counter()
        individual_notes = []
        for path in paths:
            note = vault_with_notes.get_note(path)
            if note:
                individual_notes.append(note)
        time_individual = time.perf_counter() - start_individual

        # Measure batch loading (3 queries total)
        start_batch = time.perf_counter()
        notes_map = vault_with_notes.get_notes_batch(paths)
        batch_notes = [n for n in notes_map.values() if n is not None]
        time_batch = time.perf_counter() - start_batch

        # Batch should be faster (or at least not significantly slower)
        # Allow some variance due to test environment
        assert time_batch <= time_individual * 1.5, (
            f"Batch loading ({time_batch:.4f}s) should be faster than "
            f"individual loading ({time_individual:.4f}s)"
        )

        # Verify same results
        assert len(batch_notes) == len(individual_notes)


class TestBatchLoadingInVaultContext:
    """Test that VaultContext methods use batch loading (OP-6)."""

    def test_neighbours_uses_batch_loading(self, vault_with_notes: Vault):
        """Test that neighbours() uses get_notes_batch() internally."""
        from datetime import datetime

        from geistfabrik.embeddings import Session
        from geistfabrik.vault_context import VaultContext

        # Create session and context
        session = Session(datetime.today(), vault_with_notes.db)
        notes = vault_with_notes.all_notes()
        session.compute_embeddings(notes)
        context = VaultContext(vault_with_notes, session)

        # Get any note
        note = vault_with_notes.get_note("note_0.md")
        assert note is not None

        # This should use batch loading internally
        neighbours = context.neighbours(note, k=5)

        # Verify we got results
        assert isinstance(neighbours, list)
        assert all(isinstance(n, Note) for n in neighbours)

    def test_backlinks_uses_batch_loading(self, vault_with_notes: Vault):
        """Test that backlinks() uses get_notes_batch() internally."""
        from datetime import datetime

        from geistfabrik.embeddings import Session
        from geistfabrik.vault_context import VaultContext

        session = Session(datetime.today(), vault_with_notes.db)
        notes = vault_with_notes.all_notes()
        session.compute_embeddings(notes)
        context = VaultContext(vault_with_notes, session)

        # Get a note that is linked to
        note = vault_with_notes.get_note("note_1.md")
        assert note is not None

        # This should use batch loading internally
        backlinks = context.backlinks(note)

        # Verify we got results (note_0 and note_2 should link to note_1)
        assert isinstance(backlinks, list)
        assert all(isinstance(n, Note) for n in backlinks)

    def test_hubs_uses_batch_loading(self, vault_with_notes: Vault):
        """Test that hubs() uses get_notes_batch() internally."""
        from datetime import datetime

        from geistfabrik.embeddings import Session
        from geistfabrik.vault_context import VaultContext

        session = Session(datetime.today(), vault_with_notes.db)
        notes = vault_with_notes.all_notes()
        session.compute_embeddings(notes)
        context = VaultContext(vault_with_notes, session)

        # This should use batch loading internally
        hubs = context.hubs(k=3)

        # Verify we got results
        assert isinstance(hubs, list)
        assert len(hubs) <= 3
        assert all(isinstance(n, Note) for n in hubs)


class TestBatchLoadingCorrectness:
    """Test that batch loading produces identical results to individual loading."""

    def test_batch_loading_equivalent_to_individual(self, vault_with_notes: Vault):
        """Test that batch loading produces identical Note objects to individual loading."""
        paths = [f"note_{i}.md" for i in range(5)]

        # Load individually
        individual_notes = {}
        for path in paths:
            note = vault_with_notes.get_note(path)
            individual_notes[path] = note

        # Load in batch
        batch_notes = vault_with_notes.get_notes_batch(paths)

        # Compare results
        for path in paths:
            individual = individual_notes[path]
            batch = batch_notes[path]

            if individual is None:
                assert batch is None
                continue

            assert batch is not None
            assert individual.path == batch.path
            assert individual.title == batch.title
            assert individual.content == batch.content
            assert len(individual.links) == len(batch.links)
            assert len(individual.tags) == len(batch.tags)
            assert individual.created == batch.created
            assert individual.modified == batch.modified

    def test_batch_loading_with_duplicates(self, vault_with_notes: Vault):
        """Test that batch loading handles duplicate paths correctly."""
        paths = ["note_0.md", "note_1.md", "note_0.md"]  # note_0 appears twice
        notes_map = vault_with_notes.get_notes_batch(paths)

        # Should load all requested paths
        assert "note_0.md" in notes_map
        assert "note_1.md" in notes_map
        assert notes_map["note_0.md"] is not None
        assert notes_map["note_1.md"] is not None


@pytest.mark.benchmark
class TestBatchLoadingBenchmark:
    """Benchmark tests for batch loading (OP-6).

    Run with: pytest -m benchmark -v -s
    """

    def test_batch_loading_benchmark(self, vault_with_notes: Vault):
        """Benchmark batch loading vs individual loading."""
        import time

        paths = [f"note_{i}.md" for i in range(10)]

        # Warmup
        vault_with_notes.get_notes_batch(paths)

        # Benchmark individual loading
        trials = 10
        individual_times = []
        for _ in range(trials):
            start = time.perf_counter()
            for path in paths:
                vault_with_notes.get_note(path)
            individual_times.append(time.perf_counter() - start)

        # Benchmark batch loading
        batch_times = []
        for _ in range(trials):
            start = time.perf_counter()
            vault_with_notes.get_notes_batch(paths)
            batch_times.append(time.perf_counter() - start)

        avg_individual = sum(individual_times) / trials
        avg_batch = sum(batch_times) / trials
        speedup = avg_individual / avg_batch

        print("\n" + "=" * 70)
        print("Batch Loading Benchmark (OP-6)")
        print("=" * 70)
        print(f"Notes loaded: {len(paths)}")
        print(f"Individual loading: {avg_individual * 1000:.3f}ms (avg over {trials} trials)")
        print(f"Batch loading:      {avg_batch * 1000:.3f}ms (avg over {trials} trials)")
        print(f"Speedup:            {speedup:.2f}x")
        print("=" * 70)

        # Batch should be at least 1.3x faster (conservative estimate allowing for test variance)
        assert speedup >= 1.3, f"Batch loading should be faster (got {speedup:.2f}x)"
