"""Unit tests for island_hopper geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import island_hopper
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
    """Create a vault with disconnected clusters that could be bridged."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create cluster A: AI hub with backlinks
    (vault_path / "ai_hub.md").write_text(
        "# AI Hub\n\nCentral hub for artificial intelligence topics."
    )
    (vault_path / "neural_networks.md").write_text(
        "# Neural Networks\n\nDeep learning networks. See [[ai_hub]]."
    )
    (vault_path / "machine_learning.md").write_text(
        "# Machine Learning\n\nLearning algorithms. See [[ai_hub]]."
    )
    (vault_path / "deep_learning.md").write_text(
        "# Deep Learning\n\nMulti-layer networks. See [[ai_hub]]."
    )

    # Create cluster B: Cognition hub with backlinks
    (vault_path / "cognition_hub.md").write_text(
        "# Cognition Hub\n\nCentral hub for cognitive science topics."
    )
    (vault_path / "thinking.md").write_text(
        "# Thinking\n\nCognitive processes. See [[cognition_hub]]."
    )
    (vault_path / "reasoning.md").write_text(
        "# Reasoning\n\nLogical reasoning. See [[cognition_hub]]."
    )
    (vault_path / "mental_models.md").write_text(
        "# Mental Models\n\nThought frameworks. See [[cognition_hub]]."
    )

    # Create potential bridge notes (semantically related to clusters but not linked)
    (vault_path / "artificial_intelligence.md").write_text(
        "# Artificial Intelligence\n\n"
        "Intelligent systems using neural networks and machine learning."
    )
    (vault_path / "cognitive_computing.md").write_text(
        "# Cognitive Computing\n\nComputing inspired by thinking and reasoning."
    )

    # Add unrelated notes to increase vault size
    for i in range(5):
        (vault_path / f"random_{i}.md").write_text(f"# Random Note {i}\n\nUnrelated content {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with insufficient notes for cluster detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 8 notes (below minimum of 10)
    for i in range(8):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_island_hopper_returns_suggestions(vault_with_clusters):
    """Test that island_hopper returns suggestions with disconnected clusters."""
    vault, session = vault_with_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = island_hopper.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_island_hopper_suggestion_structure(vault_with_clusters):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = island_hopper.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "island_hopper"

        # Should reference multiple notes (bridge + hub + cluster sample)
        assert len(suggestion.notes) >= 3

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_island_hopper_uses_obsidian_link(vault_with_clusters):
    """Test that island_hopper uses obsidian_link for note references."""
    vault, session = vault_with_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = island_hopper.suggest(context)

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


def test_island_hopper_empty_vault(tmp_path):
    """Test that island_hopper handles empty vault gracefully."""
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

    suggestions = island_hopper.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_island_hopper_insufficient_notes(vault_insufficient_notes):
    """Test that island_hopper handles insufficient notes gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = island_hopper.suggest(context)

    # Should return empty list when < 10 notes
    assert len(suggestions) == 0


def test_island_hopper_max_suggestions(vault_with_clusters):
    """Test that island_hopper never returns more than 3 suggestions."""
    vault, session = vault_with_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = island_hopper.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_island_hopper_deterministic_with_seed(vault_with_clusters):
    """Test that island_hopper returns same results with same seed."""
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

    suggestions1 = island_hopper.suggest(context1)
    suggestions2 = island_hopper.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_island_hopper_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\nJournal content with potential clusters and connections."
        )

    # Create cluster A: AI hub with backlinks
    (vault_path / "ai_hub.md").write_text(
        "# AI Hub\n\nCentral hub for artificial intelligence topics."
    )
    (vault_path / "neural_networks.md").write_text(
        "# Neural Networks\n\nDeep learning networks. See [[ai_hub]]."
    )
    (vault_path / "machine_learning.md").write_text(
        "# Machine Learning\n\nLearning algorithms. See [[ai_hub]]."
    )

    # Create cluster B: Cognition hub with backlinks
    (vault_path / "cognition_hub.md").write_text(
        "# Cognition Hub\n\nCentral hub for cognitive science topics."
    )
    (vault_path / "thinking.md").write_text(
        "# Thinking\n\nCognitive processes. See [[cognition_hub]]."
    )
    (vault_path / "reasoning.md").write_text(
        "# Reasoning\n\nLogical reasoning. See [[cognition_hub]]."
    )

    # Create bridge notes
    (vault_path / "artificial_intelligence.md").write_text(
        "# Artificial Intelligence\n\n"
        "Intelligent systems using neural networks and machine learning."
    )

    # Add additional notes
    for i in range(5):
        (vault_path / f"random_{i}.md").write_text(f"# Random Note {i}\n\nUnrelated content.")

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

    suggestions = island_hopper.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
