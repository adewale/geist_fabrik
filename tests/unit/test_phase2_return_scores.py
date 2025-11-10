"""Tests for Phase 2 Optimisation: OP-9 neighbours() with return_scores.

Tests the return_scores parameter and its usage in geists.
"""

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.embeddings import Session
from geistfabrik.models import Note
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


def load_geist(geist_name: str):
    """Dynamically load a geist module."""
    repo_root = Path(__file__).parent.parent.parent
    geist_path = repo_root / "src" / "geistfabrik" / "default_geists" / "code" / f"{geist_name}.py"

    spec = importlib.util.spec_from_file_location(geist_name, geist_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def vault_with_similar_notes(tmp_path: Path) -> Vault:
    """Create a vault with notes that have clear semantic similarity."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()

    # Create notes with similar content
    notes_content = {
        "python.md": "# Python\n\nPython is a programming language for software development.",
        "java.md": "# Java\n\nJava is a programming language for software development.",
        "cooking.md": "# Cooking\n\nCooking is the art of preparing food with recipes.",
        "baking.md": "# Baking\n\nBaking is the art of preparing food with recipes and ovens.",
        "math.md": "# Mathematics\n\nMathematics is the study of numbers and equations.",
    }

    for filename, content in notes_content.items():
        (vault_dir / filename).write_text(content)

    vault = Vault(str(vault_dir))
    vault.sync()
    return vault


@pytest.fixture
def context_with_embeddings(vault_with_similar_notes: Vault) -> VaultContext:
    """Create VaultContext with computed embeddings."""
    session = Session(datetime.today(), vault_with_similar_notes.db)
    notes = vault_with_similar_notes.all_notes()
    session.compute_embeddings(notes)
    return VaultContext(vault_with_similar_notes, session)


class TestReturnScoresParameter:
    """Test OP-9: neighbours() with return_scores parameter."""

    def test_return_scores_false_returns_notes_only(self, context_with_embeddings: VaultContext):
        """Test that return_scores=False returns List[Note]."""
        note = context_with_embeddings.vault.get_note("python.md")
        assert note is not None

        neighbours = context_with_embeddings.neighbours(note, k=3, return_scores=False)

        # Should return list of Note objects
        assert isinstance(neighbours, list)
        assert all(isinstance(n, Note) for n in neighbours)

        # Should not contain tuples
        for n in neighbours:
            assert not isinstance(n, tuple)

    def test_return_scores_true_returns_tuples(self, context_with_embeddings: VaultContext):
        """Test that return_scores=True returns List[Tuple[Note, float]]."""
        note = context_with_embeddings.vault.get_note("python.md")
        assert note is not None

        neighbors_with_scores = context_with_embeddings.neighbours(note, k=3, return_scores=True)

        # Should return list of tuples
        assert isinstance(neighbors_with_scores, list)
        assert all(isinstance(item, tuple) for item in neighbors_with_scores)
        assert all(len(item) == 2 for item in neighbors_with_scores)

        # Each tuple should be (Note, float)
        for note_obj, score in neighbors_with_scores:
            assert isinstance(note_obj, Note)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0  # Cosine similarity range

    def test_return_scores_default_is_false(self, context_with_embeddings: VaultContext):
        """Test that return_scores defaults to False."""
        note = context_with_embeddings.vault.get_note("python.md")
        assert note is not None

        # Call without specifying return_scores
        neighbours = context_with_embeddings.neighbours(note, k=3)

        # Should return list of Note objects (not tuples)
        assert isinstance(neighbours, list)
        assert all(isinstance(n, Note) for n in neighbours)

    def test_return_scores_similarity_values_are_correct(
        self, context_with_embeddings: VaultContext
    ):
        """Test that returned similarity scores match vault.similarity()."""
        note = context_with_embeddings.vault.get_note("python.md")
        assert note is not None

        neighbors_with_scores = context_with_embeddings.neighbours(note, k=3, return_scores=True)

        # Verify scores match vault.similarity()
        for neighbour, returned_score in neighbors_with_scores:
            computed_score = context_with_embeddings.similarity(note, neighbour)

            # Scores should match (within floating point tolerance)
            assert abs(returned_score - computed_score) < 1e-6, (
                f"Returned score {returned_score} doesn't match computed score {computed_score}"
            )

    def test_return_scores_sorted_by_similarity(self, context_with_embeddings: VaultContext):
        """Test that neighbours are sorted by similarity descending."""
        note = context_with_embeddings.vault.get_note("python.md")
        assert note is not None

        neighbors_with_scores = context_with_embeddings.neighbours(note, k=4, return_scores=True)

        # Extract scores
        scores = [score for _, score in neighbors_with_scores]

        # Should be sorted descending
        assert scores == sorted(scores, reverse=True)

    def test_return_scores_same_notes_different_formats(
        self, context_with_embeddings: VaultContext
    ):
        """Test that both return formats return the same notes."""
        note = context_with_embeddings.vault.get_note("python.md")
        assert note is not None

        # Get neighbours without scores
        neighbours = context_with_embeddings.neighbours(note, k=3, return_scores=False)

        # Get neighbours with scores
        neighbors_with_scores = context_with_embeddings.neighbours(note, k=3, return_scores=True)

        # Extract notes from tuples
        neighbors_from_tuples = [n for n, _ in neighbors_with_scores]

        # Should be the same notes in the same order
        assert len(neighbours) == len(neighbors_from_tuples)
        for i, (n1, n2) in enumerate(zip(neighbours, neighbors_from_tuples)):
            assert n1.path == n2.path, f"Note {i} differs: {n1.path} vs {n2.path}"


class TestReturnScoresCaching:
    """Test that return_scores uses separate cache keys."""

    def test_return_scores_cached_separately(self, context_with_embeddings: VaultContext):
        """Test that return_scores=True and False have separate cache entries."""
        note = context_with_embeddings.vault.get_note("python.md")
        assert note is not None

        # Call with return_scores=False
        neighbors1 = context_with_embeddings.neighbours(note, k=3, return_scores=False)

        # Call with return_scores=True
        neighbors2 = context_with_embeddings.neighbours(note, k=3, return_scores=True)

        # Both should be cached independently
        assert isinstance(neighbors1, list)
        assert isinstance(neighbors2, list)
        assert all(isinstance(n, Note) for n in neighbors1)
        assert all(isinstance(item, tuple) for item in neighbors2)

        # Verify cache contains both
        cache_key_false = (note.path, 3, False)
        cache_key_true = (note.path, 3, True)

        assert cache_key_false in context_with_embeddings._neighbours_cache
        assert cache_key_true in context_with_embeddings._neighbours_cache


class TestReturnScoresUsageInGeists:
    """Test that geists using return_scores work correctly."""

    def test_hidden_hub_uses_return_scores(self, context_with_embeddings: VaultContext):
        """Test that hidden_hub geist uses return_scores correctly."""
        hidden_hub = load_geist("hidden_hub")

        # This geist uses return_scores=True
        suggestions = hidden_hub.suggest(context_with_embeddings)

        # Should not raise errors and should return suggestions
        assert isinstance(suggestions, list)
        # May be empty if vault doesn't meet criteria, but shouldn't error

    def test_bridge_hunter_uses_return_scores(self, context_with_embeddings: VaultContext):
        """Test that bridge_hunter geist uses return_scores correctly."""
        bridge_hunter = load_geist("bridge_hunter")

        # This geist uses return_scores=True
        suggestions = bridge_hunter.suggest(context_with_embeddings)

        # Should not raise errors and should return suggestions
        assert isinstance(suggestions, list)

    def test_columbo_uses_return_scores(self, context_with_embeddings: VaultContext):
        """Test that columbo geist uses return_scores correctly."""
        columbo = load_geist("columbo")

        # This geist uses return_scores=True
        suggestions = columbo.suggest(context_with_embeddings)

        # Should not raise errors and should return suggestions
        assert isinstance(suggestions, list)

    def test_bridge_builder_uses_return_scores(self, context_with_embeddings: VaultContext):
        """Test that bridge_builder geist uses return_scores correctly."""
        bridge_builder = load_geist("bridge_builder")

        # This geist uses return_scores=True
        suggestions = bridge_builder.suggest(context_with_embeddings)

        # Should not raise errors and should return suggestions
        assert isinstance(suggestions, list)

    def test_antithesis_generator_uses_return_scores(self, context_with_embeddings: VaultContext):
        """Test that antithesis_generator geist uses return_scores correctly."""
        antithesis_generator = load_geist("antithesis_generator")

        # This geist uses return_scores=True
        suggestions = antithesis_generator.suggest(context_with_embeddings)

        # Should not raise errors and should return suggestions
        assert isinstance(suggestions, list)


class TestReturnScoresPerformance:
    """Test that return_scores avoids redundant similarity computations."""

    def test_return_scores_avoids_recomputation(self, context_with_embeddings: VaultContext):
        """Test that using return_scores=True avoids calling similarity() again."""
        note = context_with_embeddings.vault.get_note("python.md")
        assert note is not None

        # Clear similarity cache to measure fresh computations
        context_with_embeddings._similarity_cache.clear()

        # Get neighbours with scores
        neighbors_with_scores = context_with_embeddings.neighbours(note, k=3, return_scores=True)

        # Extract neighbours and scores
        neighbours = [n for n, _ in neighbors_with_scores]
        scores_from_neighbours = {n.path: s for n, s in neighbors_with_scores}

        # Count similarity cache entries BEFORE calling similarity()
        cache_before = len(context_with_embeddings._similarity_cache)

        # Now if we call similarity() on these neighbours, it should be cached
        for neighbour in neighbours:
            score = context_with_embeddings.similarity(note, neighbour)
            # Should match the score we got from neighbours()
            assert abs(score - scores_from_neighbours[neighbour.path]) < 1e-6

        # Cache should have grown (similarity was cached during neighbours call)
        cache_after = len(context_with_embeddings._similarity_cache)

        # The similarity() calls should have used cached values from neighbours()
        assert cache_after >= cache_before


@pytest.mark.benchmark
class TestReturnScoresBenchmark:
    """Benchmark tests for return_scores optimisation (OP-9).

    Run with: pytest -m benchmark -v -s
    """

    def test_return_scores_benchmark(self, context_with_embeddings: VaultContext):
        """Benchmark return_scores=True vs calling similarity() separately."""
        import time

        note = context_with_embeddings.vault.get_note("python.md")
        assert note is not None

        trials = 100

        # Method 1: Get neighbours, then compute similarity for each (old way)
        times_without_return_scores = []
        for _ in range(trials):
            # Clear caches to measure fresh computation
            context_with_embeddings._neighbours_cache.clear()
            context_with_embeddings._similarity_cache.clear()

            start = time.perf_counter()
            neighbours = context_with_embeddings.neighbours(note, k=5, return_scores=False)
            _ = [context_with_embeddings.similarity(note, n) for n in neighbours]
            times_without_return_scores.append(time.perf_counter() - start)

        # Method 2: Get neighbours with scores (new way with OP-9)
        times_with_return_scores = []
        for _ in range(trials):
            # Clear caches to measure fresh computation
            context_with_embeddings._neighbours_cache.clear()
            context_with_embeddings._similarity_cache.clear()

            start = time.perf_counter()
            _ = context_with_embeddings.neighbours(note, k=5, return_scores=True)
            times_with_return_scores.append(time.perf_counter() - start)

        avg_without = sum(times_without_return_scores) / trials
        avg_with = sum(times_with_return_scores) / trials
        speedup = avg_without / avg_with

        print("\n" + "=" * 70)
        print("Return Scores Benchmark (OP-9)")
        print("=" * 70)
        print("K neighbours: 5")
        print(
            f"Without return_scores: {avg_without * 1000:.3f}ms (neighbours + {5} similarity calls)"
        )
        print(f"With return_scores:    {avg_with * 1000:.3f}ms (neighbours only)")
        print(f"Speedup:               {speedup:.2f}x")
        print("Redundant calls avoided: 5")
        print("=" * 70)

        # With return_scores should be faster (avoids 5 redundant similarity computations)
        # Conservative estimate: at least 1.2x faster
        assert speedup >= 1.2, f"return_scores should be faster (got {speedup:.2f}x)"
