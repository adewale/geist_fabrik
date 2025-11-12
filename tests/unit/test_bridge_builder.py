"""Unit tests for bridge_builder geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import bridge_builder
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
def vault_with_hubs(tmp_path):
    """Create a vault with hub notes and potential bridge connections."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create hub A (index note) with several links
    (vault_path / "ai_hub.md").write_text(
        """# AI Hub

This is a hub for AI topics.

[[neural_networks]]
[[machine_learning]]
[[algorithms]]
"""
    )

    # Create notes linked to hub A
    (vault_path / "neural_networks.md").write_text(
        "# Neural Networks\n\nDeep learning with neural networks."
    )
    (vault_path / "machine_learning.md").write_text("# Machine Learning\n\nLearning from data.")
    (vault_path / "algorithms.md").write_text("# Algorithms\n\nComputational algorithms.")

    # Create hub B with different links
    (vault_path / "cognitive_hub.md").write_text(
        """# Cognitive Hub

This is a hub for cognition topics.

[[thinking]]
[[reasoning]]
[[mental_models]]
"""
    )

    (vault_path / "thinking.md").write_text("# Thinking\n\nCognitive processes.")
    (vault_path / "reasoning.md").write_text("# Reasoning\n\nLogical reasoning.")
    (vault_path / "mental_models.md").write_text("# Mental Models\n\nFrameworks for thought.")

    # Create a semantically related note to hub A but not linked
    (vault_path / "deep_learning.md").write_text(
        "# Deep Learning\n\nNeural networks, machine learning, and artificial intelligence."
    )

    # Create a semantically related note to hub B but not linked
    (vault_path / "cognition.md").write_text(
        "# Cognition\n\nThinking, reasoning, and mental models."
    )

    # Add some unrelated notes
    for i in range(10):
        (vault_path / f"random_{i}.md").write_text(f"# Random Note {i}\n\nUnrelated content {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_hubs(tmp_path):
    """Create a vault with no clear hub structure."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a few isolated notes without hub structure
    for i in range(5):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_bridge_builder_returns_suggestions(vault_with_hubs):
    """Test that bridge_builder returns suggestions with hub structure."""
    vault, session = vault_with_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_bridge_builder_suggestion_structure(vault_with_hubs):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "bridge_builder"

        # Should reference 2 notes (hub and potential bridge)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_bridge_builder_uses_obsidian_link(vault_with_hubs):
    """Test that bridge_builder uses obsidian_link for note references."""
    vault, session = vault_with_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

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


def test_bridge_builder_empty_vault(tmp_path):
    """Test that bridge_builder handles empty vault gracefully."""
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

    suggestions = bridge_builder.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_bridge_builder_insufficient_hubs(vault_insufficient_hubs):
    """Test that bridge_builder handles vaults without clear hub structure."""
    vault, session = vault_insufficient_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    # May return empty list or few suggestions without hub structure
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_bridge_builder_max_suggestions(vault_with_hubs):
    """Test that bridge_builder never returns more than 3 suggestions."""
    vault, session = vault_with_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_bridge_builder_deterministic_with_seed(vault_with_hubs):
    """Test that bridge_builder returns same results with same seed."""
    vault, session = vault_with_hubs

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

    suggestions1 = bridge_builder.suggest(context1)
    suggestions2 = bridge_builder.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2
