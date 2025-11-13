"""Unit tests for bridge_hunter geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import bridge_hunter
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
def vault_with_unlinked_pairs(tmp_path):
    """Create a vault with unlinked notes that have semantic connections."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create cluster A (artificial intelligence)
    (vault_path / "neural_networks.md").write_text(
        "# Neural Networks\n\nDeep learning and artificial neural networks."
    )
    (vault_path / "machine_learning.md").write_text(
        "# Machine Learning\n\nAlgorithms that learn from data."
    )
    (vault_path / "deep_learning.md").write_text(
        "# Deep Learning\n\nMulti-layer neural networks for complex patterns."
    )

    # Create cluster B (cognitive science)
    (vault_path / "cognitive_architecture.md").write_text(
        "# Cognitive Architecture\n\nMental models and cognitive processes."
    )
    (vault_path / "human_cognition.md").write_text(
        "# Human Cognition\n\nHow the human brain processes information."
    )
    (vault_path / "mental_models.md").write_text(
        "# Mental Models\n\nFrameworks for understanding thinking patterns."
    )

    # Create potential bridges (AI-related but not linked to cluster A)
    (vault_path / "artificial_intelligence.md").write_text(
        "# Artificial Intelligence\n\nIntelligent systems, neural networks, and machine learning."
    )
    (vault_path / "brain_cognition.md").write_text(
        "# Brain and Cognition\n\nHuman cognition, mental models, and cognitive architecture."
    )

    # Add some unrelated notes to increase vault size
    for i in range(10):
        (vault_path / f"random_{i}.md").write_text(
            f"# Random Note {i}\n\nUnrelated content about topic {i}."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_pairs(tmp_path):
    """Create a vault with insufficient unlinked pairs for bridge hunting."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 3 notes (not enough for unlinked_pairs to find 2 pairs)
    (vault_path / "note_a.md").write_text("# Note A\n\nContent A.")
    (vault_path / "note_b.md").write_text("# Note B\n\nContent B.")
    (vault_path / "note_c.md").write_text("# Note C\n\nContent C.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_bridge_hunter_returns_suggestions(vault_with_unlinked_pairs):
    """Test that bridge_hunter returns suggestions with unlinked pairs.

    Setup:
        Vault with connected note clusters.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_unlinked_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_hunter.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_bridge_hunter_suggestion_structure(vault_with_unlinked_pairs):
    """Test that suggestions have correct structure.

    Setup:
        Vault with note clusters.

    Verifies:
        - Has required fields
        - References 3+ notes (bridge path)"""
    vault, session = vault_with_unlinked_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_hunter.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "bridge_hunter"

        # Should reference multiple notes in the path (at least 3: start, intermediate(s), end)
        assert len(suggestion.notes) >= 3

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_bridge_hunter_uses_obsidian_link(vault_with_unlinked_pairs):
    """Test that bridge_hunter uses obsidian_link for note references.

    Setup:
        Vault with note clusters.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_unlinked_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_hunter.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_bridge_hunter_empty_vault(tmp_path):
    """Test that bridge_hunter handles empty vault gracefully.

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

    suggestions = bridge_hunter.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_bridge_hunter_insufficient_pairs(vault_insufficient_pairs):
    """Test that bridge_hunter handles insufficient unlinked pairs gracefully."""
    vault, session = vault_insufficient_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_hunter.suggest(context)

    # Should return empty list when < 2 unlinked pairs
    assert len(suggestions) == 0


def test_bridge_hunter_max_suggestions(vault_with_unlinked_pairs):
    """Test that bridge_hunter never returns more than 2 suggestions.

    Setup:
        Vault with multiple clusters.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_unlinked_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_hunter.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_bridge_hunter_deterministic_with_seed(vault_with_unlinked_pairs):
    """Test that bridge_hunter returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_unlinked_pairs

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

    suggestions1 = bridge_hunter.suggest(context1)
    suggestions2 = bridge_hunter.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_bridge_hunter_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with unlinked notes
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\n"
            "Neural networks and machine learning topics. "
            "Cognitive architecture and mental models."
        )

    # Create cluster A (artificial intelligence)
    (vault_path / "neural_networks.md").write_text(
        "# Neural Networks\n\nDeep learning and artificial neural networks."
    )
    (vault_path / "machine_learning.md").write_text(
        "# Machine Learning\n\nAlgorithms that learn from data."
    )
    (vault_path / "deep_learning.md").write_text(
        "# Deep Learning\n\nMulti-layer neural networks for complex patterns."
    )

    # Create cluster B (cognitive science)
    (vault_path / "cognitive_architecture.md").write_text(
        "# Cognitive Architecture\n\nMental models and cognitive processes."
    )
    (vault_path / "human_cognition.md").write_text(
        "# Human Cognition\n\nHow the human brain processes information."
    )
    (vault_path / "mental_models.md").write_text(
        "# Mental Models\n\nFrameworks for understanding thinking patterns."
    )

    # Create potential bridges (AI-related but not linked to cluster A)
    (vault_path / "artificial_intelligence.md").write_text(
        "# Artificial Intelligence\n\nIntelligent systems, neural networks, and machine learning."
    )
    (vault_path / "brain_cognition.md").write_text(
        "# Brain and Cognition\n\nHuman cognition, mental models, and cognitive architecture."
    )

    # Add some unrelated notes to increase vault size
    for i in range(10):
        (vault_path / f"random_{i}.md").write_text(
            f"# Random Note {i}\n\nUnrelated content about topic {i}."
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

    suggestions = bridge_hunter.suggest(context)

    # Verify no suggestions reference geist journal notes
    # Build title-to-path mapping to check note paths
    cursor = vault.db.execute("SELECT title, path FROM notes")
    title_to_path = {row[0]: row[1] for row in cursor.fetchall()}

    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            # Look up path by title or use note_ref as path
            note_path = title_to_path.get(note_ref, note_ref)
            assert "geist journal" not in note_path.lower(), (
                f"Geist journal note '{note_path}' was included in suggestions"
            )
