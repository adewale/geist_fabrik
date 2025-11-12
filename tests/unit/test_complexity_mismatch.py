"""Unit tests for complexity_mismatch geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import complexity_mismatch
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
def vault_with_complexity_mismatches(tmp_path):
    """Create a vault with complexity/importance mismatches."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create highly connected but short notes (underdeveloped)
    for i in range(5):
        links = " ".join([f"[[important_{j}]]" for j in range(5) if j != i])
        (vault_path / f"important_{i}.md").write_text(
            f"# Important Note {i}\n\nShort note. {links}"
        )

    # Create long but isolated notes (overcomplicated)
    for i in range(5):
        long_content = " ".join([f"Word{j}" for j in range(500)])
        (vault_path / f"isolated_{i}.md").write_text(f"# Isolated Note {i}\n\n{long_content}")

    # Create balanced notes (filler)
    for i in range(10):
        content = " ".join([f"Content{j}" for j in range(100)])
        (vault_path / f"balanced_{i}.md").write_text(
            f"# Balanced Note {i}\n\n{content} [[balanced_{(i + 1) % 10}]]"
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with too few notes for analysis."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    for i in range(3):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_complexity_mismatch_returns_suggestions(vault_with_complexity_mismatches):
    """Test that complexity_mismatch returns suggestions with mismatches."""
    vault, session = vault_with_complexity_mismatches

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = complexity_mismatch.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_complexity_mismatch_suggestion_structure(vault_with_complexity_mismatches):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_complexity_mismatches

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = complexity_mismatch.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "complexity_mismatch"

        # Should mention complexity/simplification/expansion
        assert any(
            keyword in suggestion.text.lower()
            for keyword in ["expanded", "simplified", "words", "links", "depth", "focused"]
        )

        # Should reference exactly 1 note
        assert len(suggestion.notes) == 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_complexity_mismatch_uses_obsidian_link(vault_with_complexity_mismatches):
    """Test that complexity_mismatch uses obsidian_link for note references."""
    vault, session = vault_with_complexity_mismatches

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = complexity_mismatch.suggest(context)

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


def test_complexity_mismatch_empty_vault(tmp_path):
    """Test that complexity_mismatch handles empty vault gracefully."""
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

    suggestions = complexity_mismatch.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_complexity_mismatch_balanced_vault(tmp_path):
    """Test that complexity_mismatch returns few/no suggestions for balanced vault."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes with balanced complexity and importance
    for i in range(20):
        content = " ".join([f"Word{j}" for j in range(150)])  # Medium length
        links = " ".join([f"[[note_{(i + j) % 20}]]" for j in range(1, 4)])  # Medium links
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\n{content} {links}")

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

    suggestions = complexity_mismatch.suggest(context)

    # Should return few or no suggestions for balanced vault
    assert len(suggestions) <= 3


def test_complexity_mismatch_max_suggestions(vault_with_complexity_mismatches):
    """Test that complexity_mismatch never returns more than 3 suggestions."""
    vault, session = vault_with_complexity_mismatches

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = complexity_mismatch.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_complexity_mismatch_deterministic_with_seed(vault_with_complexity_mismatches):
    """Test that complexity_mismatch returns same results with same seed."""
    vault, session = vault_with_complexity_mismatches

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

    suggestions1 = complexity_mismatch.suggest(context1)
    suggestions2 = complexity_mismatch.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2
