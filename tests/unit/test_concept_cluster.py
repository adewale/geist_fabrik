"""Unit tests for concept_cluster geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import concept_cluster
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
def vault_with_concept_clusters(tmp_path):
    """Create a vault with tightly related note groups."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a tight cluster of Python testing notes
    for i in range(8):
        (vault_path / f"testing_{i}.md").write_text(
            f"# Testing Note {i}\n\n"
            f"Python testing frameworks: pytest, unittest, fixtures, mocking, "
            f"assertions, test discovery, parametrization, coverage analysis."
        )

    # Create a tight cluster of React hooks notes
    for i in range(8):
        (vault_path / f"hooks_{i}.md").write_text(
            f"# Hooks Note {i}\n\n"
            f"React hooks patterns: useState, useEffect, useContext, useReducer, "
            f"custom hooks, dependency arrays, hook rules, optimization."
        )

    # Create some unrelated notes
    for i in range(10):
        (vault_path / f"misc_{i}.md").write_text(f"# Misc Note {i}\n\nRandom topic {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with too few notes for clustering."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 3 notes (need at least 5)
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


def test_concept_cluster_returns_suggestions(vault_with_concept_clusters):
    """Test that concept_cluster returns suggestions with clusterable notes."""
    vault, session = vault_with_concept_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = concept_cluster.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_concept_cluster_suggestion_structure(vault_with_concept_clusters):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_concept_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = concept_cluster.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "concept_cluster"

        # Should mention organizing or shared theme
        assert any(
            keyword in suggestion.text.lower()
            for keyword in ["cluster", "organised", "shared theme", "tightly related"]
        )

        # Should reference at least 3 notes (cluster_notes)
        assert len(suggestion.notes) >= 3

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_concept_cluster_uses_obsidian_link(vault_with_concept_clusters):
    """Test that concept_cluster uses obsidian_link for note references."""
    vault, session = vault_with_concept_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = concept_cluster.suggest(context)

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


def test_concept_cluster_empty_vault(tmp_path):
    """Test that concept_cluster handles empty vault gracefully."""
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

    suggestions = concept_cluster.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_concept_cluster_insufficient_notes(vault_insufficient_notes):
    """Test that concept_cluster handles insufficient notes gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = concept_cluster.suggest(context)

    # Should return empty list when < 5 notes
    assert len(suggestions) == 0


def test_concept_cluster_max_suggestions(vault_with_concept_clusters):
    """Test that concept_cluster never returns more than 2 suggestions."""
    vault, session = vault_with_concept_clusters

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = concept_cluster.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_concept_cluster_deterministic_with_seed(vault_with_concept_clusters):
    """Test that concept_cluster returns same results with same seed."""
    vault, session = vault_with_concept_clusters

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

    suggestions1 = concept_cluster.suggest(context1)
    suggestions2 = concept_cluster.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2
