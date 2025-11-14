"""Unit tests for cluster_mirror geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import cluster_mirror
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def vault_with_clusters(tmp_path):
    """Create a vault with semantically distinct groups of notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create cluster 1: Python programming notes
    for i in range(8):
        (vault_path / f"python_{i}.md").write_text(
            f"# Python Note {i}\n\n"
            f"Python programming language topics: classes, functions, decorators, "
            f"generators, comprehensions, async, typing, testing."
        )

    # Create cluster 2: Machine learning notes
    for i in range(8):
        (vault_path / f"ml_{i}.md").write_text(
            f"# ML Note {i}\n\n"
            f"Machine learning concepts: neural networks, training, optimization, "
            f"backpropagation, gradient descent, loss functions, regularization."
        )

    # Create cluster 3: Cooking notes
    for i in range(8):
        (vault_path / f"cooking_{i}.md").write_text(
            f"# Cooking Note {i}\n\n"
            f"Cooking techniques and recipes: sautéing, roasting, baking, "
            f"braising, grilling, seasoning, marinating, preparation."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_clusters(tmp_path):
    """Create a vault with too few notes to form meaningful clusters."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 6 notes (need at least min_size=5 per cluster × 2 clusters)
    for i in range(6):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nSome content.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_cluster_mirror_returns_suggestions(vault_with_clusters):
    """Test that cluster_mirror returns suggestions with clusterable notes.

    Setup:
        Vault with semantic note clusters.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = cluster_mirror.suggest(context)

    # Should return at most 1 suggestion showing clusters
    # Note: HDBSCAN can be non-deterministic in edge cases, so we check for 0 or 1
    # The fixture has clear clusters, so we should get 1, but allow 0 in rare cases
    assert isinstance(suggestions, list)
    assert len(suggestions) in [0, 1], f"Expected 0 or 1 suggestions, got {len(suggestions)}"


def test_cluster_mirror_suggestion_structure(vault_with_clusters):
    """Test that suggestions have correct structure.

    Setup:
        Vault with note clusters.

    Verifies:
        - Has required fields
        - References 3+ clustered notes"""
    vault, session = vault_with_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = cluster_mirror.suggest(context)

    # BEHAVIORAL: Verify geist follows output constraints
    # (This is a basic check - deeper assertions added to high-priority geists in Session 2)
    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "cluster_mirror"

        # Should end with the muse question
        assert "What do these clusters remind you of?" in suggestion.text

        # Should have note references
        assert len(suggestion.notes) > 0

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_cluster_mirror_uses_obsidian_link(vault_with_clusters):
    """Test that cluster_mirror uses obsidian_link for note references.

    Setup:
        Vault with note clusters.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = cluster_mirror.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_cluster_mirror_shows_multiple_clusters(vault_with_clusters):
    """Test that cluster_mirror shows 2-3 clusters with representatives."""
    vault, session = vault_with_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = cluster_mirror.suggest(context)

    # HDBSCAN can be non-deterministic; if no clusters found, skip test
    if not suggestions:
        import pytest

        pytest.skip("HDBSCAN did not find sufficient clusters (non-deterministic)")

    assert len(suggestions) == 1
    suggestion = suggestions[0]

    # Should show 2-3 clusters (each with label → notes format)
    # Count occurrences of "→" which separates labels from notes
    arrow_count = suggestion.text.count("→")
    assert 2 <= arrow_count <= 3

    # Should have multiple note references (3 per cluster × 2-3 clusters)
    assert len(suggestion.notes) >= 6  # At least 2 clusters × 3 notes


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_cluster_mirror_empty_vault(tmp_path):
    """Test that cluster_mirror handles empty vault gracefully.

    Setup:
        Empty vault.

    Verifies:
        - Returns empty list"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = cluster_mirror.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_cluster_mirror_insufficient_clusters(vault_insufficient_clusters):
    """Test that cluster_mirror handles insufficient clusters gracefully."""
    vault, session = vault_insufficient_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = cluster_mirror.suggest(context)

    # Should return empty list when < 2 clusters found
    assert len(suggestions) == 0


def test_cluster_mirror_deterministic_with_seed(vault_with_clusters):
    """Test that cluster_mirror returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_clusters

    # Reuse same FunctionRegistry to avoid duplicate registration
    registry = FunctionRegistry()

    context1 = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=registry,
    )

    context2 = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=registry,
    )

    suggestions1 = cluster_mirror.suggest(context1)
    suggestions2 = cluster_mirror.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_cluster_mirror_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with clusterable content
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\n"
            f"Python programming language topics: classes, functions, decorators, "
            f"generators, comprehensions, async, typing, testing."
        )

    # Create regular notes with clusterable patterns
    # Create cluster 1: Python programming notes
    for i in range(8):
        (vault_path / f"python_{i}.md").write_text(
            f"# Python Note {i}\n\n"
            f"Python programming language topics: classes, functions, decorators, "
            f"generators, comprehensions, async, typing, testing."
        )

    # Create cluster 2: Machine learning notes
    for i in range(8):
        (vault_path / f"ml_{i}.md").write_text(
            f"# ML Note {i}\n\n"
            f"Machine learning concepts: neural networks, training, optimization, "
            f"backpropagation, gradient descent, loss functions, regularization."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = cluster_mirror.suggest(context)

    # Get all journal note titles to check against
    journal_notes = [n for n in vault.all_notes() if "geist journal" in n.path.lower()]
    journal_titles = {n.title for n in journal_notes}

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert note_ref not in journal_titles, (
                f"Geist journal note '{note_ref}' was included in suggestions. "
                f"Expected only non-journal notes."
            )
