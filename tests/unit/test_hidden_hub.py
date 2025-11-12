"""Unit tests for hidden_hub geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import hidden_hub
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
def vault_with_hidden_hubs(tmp_path):
    """Create a vault with semantically central notes that lack links."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a semantically central note with few links (hidden hub candidate)
    (vault_path / "artificial_intelligence.md").write_text(
        "# Artificial Intelligence\n\nMachine learning, neural networks, deep learning, "
        "algorithms, cognition, reasoning, and intelligent systems."
    )

    # Create many semantically related notes
    topics = [
        "machine_learning",
        "neural_networks",
        "deep_learning",
        "algorithms",
        "cognition",
        "reasoning",
        "intelligent_systems",
        "pattern_recognition",
        "data_science",
        "computational_intelligence",
        "artificial_neural_networks",
        "supervised_learning",
        "unsupervised_learning",
        "reinforcement_learning",
        "computer_vision",
        "natural_language_processing",
        "expert_systems",
        "knowledge_representation",
        "automated_reasoning",
        "cognitive_computing",
    ]

    for topic in topics:
        (vault_path / f"{topic}.md").write_text(
            f"# {topic.replace('_', ' ').title()}\n\n"
            f"Content about {topic.replace('_', ' ')} and artificial intelligence."
        )

    # Add some unrelated notes to reach minimum threshold
    for i in range(10):
        (vault_path / f"random_{i}.md").write_text(f"# Random Note {i}\n\nUnrelated content {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with insufficient notes for hidden hub detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 15 notes (below minimum of 20)
    for i in range(15):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_hidden_hub_returns_suggestions(vault_with_hidden_hubs):
    """Test that hidden_hub returns suggestions with semantically central notes."""
    vault, session = vault_with_hidden_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hidden_hub.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_hidden_hub_suggestion_structure(vault_with_hidden_hubs):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_hidden_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hidden_hub.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "hidden_hub"

        # Should reference at least 4 notes (hidden hub + 3 sampled neighbors)
        assert len(suggestion.notes) >= 4

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_hidden_hub_uses_obsidian_link(vault_with_hidden_hubs):
    """Test that hidden_hub uses obsidian_link for note references."""
    vault, session = vault_with_hidden_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hidden_hub.suggest(context)

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


def test_hidden_hub_empty_vault(tmp_path):
    """Test that hidden_hub handles empty vault gracefully."""
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

    suggestions = hidden_hub.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_hidden_hub_insufficient_notes(vault_insufficient_notes):
    """Test that hidden_hub handles insufficient notes gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hidden_hub.suggest(context)

    # Should return empty list when < 20 notes
    assert len(suggestions) == 0


def test_hidden_hub_max_suggestions(vault_with_hidden_hubs):
    """Test that hidden_hub never returns more than 3 suggestions."""
    vault, session = vault_with_hidden_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hidden_hub.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_hidden_hub_deterministic_with_seed(vault_with_hidden_hubs):
    """Test that hidden_hub returns same results with same seed."""
    vault, session = vault_with_hidden_hubs

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

    suggestions1 = hidden_hub.suggest(context1)
    suggestions2 = hidden_hub.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2
