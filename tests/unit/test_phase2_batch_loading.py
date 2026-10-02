"""Tests for Phase 2 Optimisation: OP-6 Batch Note Loading.

Tests the get_notes_batch() method and its usage in neighbours(), backlinks(), and hubs().
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.models import Note
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SEED, VaultBuilder


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


def _sql_during(ctx: VaultContext, action: Callable[[], object]) -> list[str]:
    """SQL statements the context's connection executes while ``action`` runs."""
    statements: list[str] = []
    ctx.db.set_trace_callback(statements.append)
    try:
        action()
    finally:
        ctx.db.set_trace_callback(None)
    return statements


@pytest.fixture
def linked_context(tmp_path: Path) -> VaultContext:
    """ "Hub" is linked from 20 notes, "Leaf" from one; Spoke i also links Spoke i+1."""
    builder = VaultBuilder(tmp_path)
    builder.note("Hub", "central garden idea")
    builder.note("Leaf", "quiet corner")
    for i in range(20):
        nxt = f" [[Spoke {i + 1}]]" if i < 19 else " [[Leaf]]"
        builder.note(f"Spoke {i}", f"garden idea number {i} [[Hub]]{nxt}")
    ctx = builder.build()
    ctx.neighbours(ctx.notes()[0], count=1)  # load the vector backend once
    return ctx


def _fresh(ctx: VaultContext) -> VaultContext:
    """A new context on the same session, so no session cache can hide queries."""
    return VaultContext(ctx.vault, ctx.session, seed=SEED, function_registry=FunctionRegistry())


class TestQueryCountDoesNotGrowWithResultSize:
    """OP-6: VaultContext loads result notes in a constant number of queries.

    The regression each test catches is loading notes one path at a time
    (N+1 queries), which only shows up as slowness on large vaults.
    """

    def test_neighbours(self, linked_context: VaultContext) -> None:
        hub = next(n for n in linked_context.notes() if n.title == "Hub")
        small_ctx, large_ctx = _fresh(linked_context), _fresh(linked_context)

        small = _sql_during(small_ctx, lambda: small_ctx.neighbours(hub, count=2))
        large = _sql_during(large_ctx, lambda: large_ctx.neighbours(hub, count=20))

        assert len(large_ctx.neighbours(hub, count=20)) == 20
        assert len(large) == len(small) <= 3, large

    def test_backlinks(self, linked_context: VaultContext) -> None:
        notes = {n.title: n for n in linked_context.notes()}
        few_ctx, many_ctx = _fresh(linked_context), _fresh(linked_context)

        few = _sql_during(few_ctx, lambda: few_ctx.backlinks(notes["Leaf"]))
        many = _sql_during(many_ctx, lambda: many_ctx.backlinks(notes["Hub"]))

        assert [n.title for n in few_ctx.backlinks(notes["Leaf"])] == ["Spoke 19"]
        assert len(many_ctx.backlinks(notes["Hub"])) == 20
        assert len(many) == len(few) <= 3, many

    def test_hubs(self, linked_context: VaultContext) -> None:
        one_ctx, many_ctx = _fresh(linked_context), _fresh(linked_context)

        one = _sql_during(one_ctx, lambda: one_ctx.hubs(count=1))
        many = _sql_during(many_ctx, lambda: many_ctx.hubs(count=21))

        assert [n.title for n in one_ctx.hubs(count=1)] == ["Hub"]
        assert len(many_ctx.hubs(count=21)) == 21  # Hub, Leaf and Spokes 1-19
        assert len(many) == len(one) <= 3, many


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

        # A ten-row microbenchmark is dominated by timer noise. Extend this
        # benchmark fixture so query-count savings are measurable on CI.
        for i in range(10, 100):
            (vault_with_notes.vault_path / f"note_{i}.md").write_text(
                f"# Note {i}\n\nBenchmark content {i}.\n#tag{i % 3}\n"
            )
        vault_with_notes.sync()
        paths = [f"note_{i}.md" for i in range(100)]

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
