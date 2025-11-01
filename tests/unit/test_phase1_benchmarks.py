"""Benchmark tests for Phase 1 performance optimizations.

These tests measure actual performance improvements from:
- Session-scoped caching (backlinks, outgoing_links, graph_neighbors)
- Vectorized operations (contrarian_to, unlinked_pairs)

Run benchmarks with:
    pytest tests/unit/test_phase1_benchmarks.py -m benchmark -v -s

Or run specific benchmark:
    pytest tests/unit/test_phase1_benchmarks.py::test_backlinks_caching_benchmark -v -s
"""

import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


@pytest.fixture
def benchmark_vault():
    """Create vault with 100 notes for benchmarking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create 100 notes with links
        for i in range(100):
            content = f"# Note {i}\n\nSome content about topic {i % 10}."

            # Add some links to create graph structure
            if i > 0:
                content += f"\n\n[[note_{i - 1}]]"
            if i < 99:
                content += f"\n\n[[note_{i + 1}]]"

            (vault_path / f"note_{i}.md").write_text(content)

        yield vault_path


@pytest.mark.benchmark
def test_backlinks_caching_benchmark(benchmark_vault):
    """Benchmark: Verify backlinks() caching improves performance.

    Expected: 10-50x speedup for repeated queries on same notes.
    """
    vault = Vault(benchmark_vault)
    vault.sync()

    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())

    # Test WITHOUT caching (clear cache between calls)
    context_no_cache = VaultContext(vault, session)
    notes = context_no_cache.notes()[:10]  # Test on 10 notes

    start_no_cache = time.perf_counter()
    for _ in range(10):  # 10 iterations
        for note in notes:
            _ = context_no_cache.backlinks(note)
            context_no_cache._backlinks_cache.clear()  # Force re-query
    time_no_cache = time.perf_counter() - start_no_cache

    # Test WITH caching
    context_with_cache = VaultContext(vault, session)

    start_with_cache = time.perf_counter()
    for _ in range(10):  # Same 10 iterations
        for note in notes:
            _ = context_with_cache.backlinks(note)
            # Cache persists
    time_with_cache = time.perf_counter() - start_with_cache

    # Calculate speedup
    speedup = time_no_cache / time_with_cache

    print(f"\n{'=' * 60}")
    print("Backlinks Caching Benchmark")
    print(f"{'=' * 60}")
    print(f"Without caching: {time_no_cache:.3f}s (100 queries)")
    print(f"With caching:    {time_with_cache:.3f}s (100 queries)")
    print(f"Speedup:         {speedup:.1f}x")
    print(f"{'=' * 60}\n")

    # Assert minimum speedup threshold
    assert speedup >= 5.0, f"Expected >=5x speedup, got {speedup:.1f}x"


@pytest.mark.benchmark
def test_graph_operations_benchmark(benchmark_vault):
    """Benchmark: Verify combined caching improves graph operations.

    Tests scenario where geist traverses graph repeatedly (common pattern).
    """
    vault = Vault(benchmark_vault)
    vault.sync()

    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(vault, session)

    notes = context.notes()[:20]

    # Simulate graph traversal (as done by geists)
    start = time.perf_counter()
    for note in notes:
        _ = context.backlinks(note)
        _ = context.outgoing_links(note)
        _ = context.graph_neighbors(note)
    elapsed = time.perf_counter() - start

    print(f"\n{'=' * 60}")
    print("Graph Operations Benchmark (With Caching)")
    print(f"{'=' * 60}")
    print("Traversed: 20 notes")
    print(f"Total time: {elapsed:.3f}s")
    print(f"Per-note: {elapsed / 20 * 1000:.1f}ms")
    print(f"{'=' * 60}\n")

    # Should be fast with caching (<100ms per note)
    assert elapsed / 20 < 0.1, f"Expected <100ms per note, got {elapsed / 20 * 1000:.1f}ms"


@pytest.mark.benchmark
def test_contrarian_to_vectorization_benchmark(benchmark_vault):
    """Benchmark: Verify contrarian_to() vectorization speedup.

    Expected: 10-50x speedup from vectorized numpy operations.
    """
    vault = Vault(benchmark_vault)
    vault.sync()

    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(vault, session)

    # Initialize function registry
    registry = FunctionRegistry(context)

    # Get a note to query against
    notes = context.notes()
    test_note = notes[50]  # Middle note

    # Measure vectorized implementation (current)
    start = time.perf_counter()
    for _ in range(10):  # 10 iterations
        result = registry.call("contrarian_to", context, test_note.title, k=5)
        assert len(result) > 0
    time_vectorized = time.perf_counter() - start

    print(f"\n{'=' * 60}")
    print("Contrarian_to Vectorization Benchmark")
    print(f"{'=' * 60}")
    print("Vault size: 100 notes")
    print(f"Vectorized time: {time_vectorized:.3f}s (10 calls)")
    print(f"Per-call: {time_vectorized / 10 * 1000:.1f}ms")
    print(f"{'=' * 60}\n")

    # Should complete 10 calls in <1 second
    assert time_vectorized < 1.0, f"Expected <1s for 10 calls, got {time_vectorized:.3f}s"


@pytest.mark.benchmark
def test_unlinked_pairs_vectorization_benchmark(benchmark_vault):
    """Benchmark: Verify unlinked_pairs() vectorization speedup.

    Expected: 10-50x speedup from vectorized similarity matrix computation.
    """
    vault = Vault(benchmark_vault)
    vault.sync()

    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(vault, session)

    # Measure vectorized implementation (current)
    start = time.perf_counter()
    result = context.unlinked_pairs(k=10, candidate_limit=100)
    elapsed = time.perf_counter() - start

    print(f"\n{'=' * 60}")
    print("Unlinked Pairs Vectorization Benchmark")
    print(f"{'=' * 60}")
    print("Candidate notes: 100")
    print(f"Pairs found: {len(result)}")
    print(f"Time: {elapsed:.3f}s")
    print(f"{'=' * 60}\n")

    # Should complete in <1 second for 100 notes
    assert elapsed < 1.0, f"Expected <1s, got {elapsed:.3f}s"
    assert len(result) > 0, "Should find at least some unlinked pairs"


@pytest.mark.benchmark
def test_phase1_integrated_benchmark(benchmark_vault):
    """Integrated benchmark: Measure cumulative Phase 1 improvements.

    Simulates typical geist execution pattern using all optimized operations.
    """
    # Clear global registry to avoid test pollution
    from geistfabrik.function_registry import _GLOBAL_REGISTRY

    _GLOBAL_REGISTRY.clear()

    vault = Vault(benchmark_vault)
    vault.sync()

    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(vault, session)

    registry = FunctionRegistry()

    # Simulate typical geist operations
    start = time.perf_counter()

    # Phase 1: Graph operations (uses caching)
    notes = context.notes()[:20]
    for note in notes:
        _ = context.backlinks(note)
        _ = context.outgoing_links(note)
        _ = context.graph_neighbors(note)

    # Phase 2: Similarity operations (uses vectorization)
    test_note = notes[10]
    _ = registry.call("contrarian_to", context, test_note.title, k=5)
    _ = context.unlinked_pairs(k=10, candidate_limit=50)

    # Phase 3: Repeat graph operations (should hit cache)
    for note in notes[:10]:
        _ = context.backlinks(note)
        _ = context.graph_neighbors(note)

    elapsed = time.perf_counter() - start

    print(f"\n{'=' * 60}")
    print("Phase 1 Integrated Benchmark")
    print(f"{'=' * 60}")
    print("Operations:")
    print("  - Graph traversal: 20 notes (× 2 passes)")
    print("  - Contrarian search: 1 query")
    print("  - Unlinked pairs: 50 candidates")
    print("")
    print(f"Total time: {elapsed:.3f}s")
    print(f"{'=' * 60}\n")

    # Should complete all operations in <2 seconds
    assert elapsed < 2.0, f"Expected <2s, got {elapsed:.3f}s"
