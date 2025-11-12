"""Unit tests for scale_shifter geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import scale_shifter
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
def vault_with_scale_variety(tmp_path):
    """Create a vault with notes at different abstraction scales."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create abstract/theoretical notes
    for i in range(10):
        (vault_path / f"abstract_{i}.md").write_text(
            f"# Abstract Theory {i}\n\n"
            f"This note explores theoretical frameworks and general principles. "
            f"The concept provides a paradigm for understanding universal patterns "
            f"and abstract models that apply across categories and systems."
        )

    # Create concrete/specific notes
    for i in range(10):
        (vault_path / f"concrete_{i}.md").write_text(
            f"# Concrete Example {i}\n\n"
            f"This note describes a specific case study with practical details. "
            f"The actual implementation shows real individual instances and "
            f"tangible examples of particular situations."
        )

    # Create mixed notes (to reach 30+ for sampling)
    for i in range(15):
        (vault_path / f"mixed_{i}.md").write_text(
            f"# Mixed Note {i}\n\nSome general content and some specific details."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with too few notes for scale analysis."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 10 notes (need at least 20)
    for i in range(10):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_scale_shifter_returns_suggestions(vault_with_scale_variety):
    """Test that scale_shifter returns suggestions with varied notes."""
    vault, session = vault_with_scale_variety

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = scale_shifter.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_scale_shifter_suggestion_structure(vault_with_scale_variety):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_scale_variety

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = scale_shifter.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "scale_shifter"

        # Should mention scale/zoom
        assert any(
            keyword in suggestion.text.lower()
            for keyword in ["zoom", "abstract", "concrete", "specific", "scale"]
        )

        # Should reference at least 1 note
        assert len(suggestion.notes) >= 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_scale_shifter_uses_obsidian_link(vault_with_scale_variety):
    """Test that scale_shifter uses obsidian_link for note references."""
    vault, session = vault_with_scale_variety

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = scale_shifter.suggest(context)

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


def test_scale_shifter_empty_vault(tmp_path):
    """Test that scale_shifter handles empty vault gracefully."""
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

    suggestions = scale_shifter.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_scale_shifter_insufficient_notes(vault_insufficient_notes):
    """Test that scale_shifter handles insufficient notes gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = scale_shifter.suggest(context)

    # Should return empty list when < 20 notes
    assert len(suggestions) == 0


def test_scale_shifter_max_suggestions(vault_with_scale_variety):
    """Test that scale_shifter never returns more than 2 suggestions."""
    vault, session = vault_with_scale_variety

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = scale_shifter.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_scale_shifter_deterministic_with_seed(vault_with_scale_variety):
    """Test that scale_shifter returns same results with same seed."""
    vault, session = vault_with_scale_variety

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

    suggestions1 = scale_shifter.suggest(context1)
    suggestions2 = scale_shifter.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2
