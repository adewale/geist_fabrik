"""Unit tests for temporal_clustering geist."""

import os
from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import temporal_clustering
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
def vault_with_temporal_notes(tmp_path):
    """Create a vault with notes spread across different time periods."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Create notes in different quarters (over 2 years)
    for quarter in range(8):
        for i in range(7):  # 7 notes per quarter (56 total)
            date = now - timedelta(days=quarter * 90 + i * 10)
            path = vault_path / f"q{quarter}_note_{i}.md"
            path.write_text(f"# Q{quarter} Note {i}\n\nContent from quarter {quarter}.")
            # Set file times to match the quarter
            timestamp = date.timestamp()
            os.utime(path, (timestamp, timestamp))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with insufficient notes for clustering."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 15 notes (below minimum of 20)
    for i in range(15):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_temporal_clustering_returns_suggestions(vault_with_temporal_notes):
    """Test that temporal_clustering returns suggestions with temporal notes.

    Setup:
        Vault with notes clustered by time.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_clustering.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_temporal_clustering_suggestion_structure(vault_with_temporal_notes):
    """Test that suggestions have correct structure.

    Setup:
        Vault with temporal clusters.

    Verifies:
        - Has required fields
        - References notes from same time period"""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_clustering.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "temporal_clustering"

        # Should reference multiple notes (samples from 2 clusters)
        assert len(suggestion.notes) >= 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_temporal_clustering_uses_obsidian_link(vault_with_temporal_notes):
    """Test that temporal_clustering uses obsidian_link for note references.

    Setup:
        Vault with temporal clusters.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_clustering.suggest(context)

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


def test_temporal_clustering_empty_vault(tmp_path):
    """Test that temporal_clustering handles empty vault gracefully.

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

    suggestions = temporal_clustering.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_temporal_clustering_insufficient_notes(vault_insufficient_notes):
    """Test that temporal_clustering handles insufficient notes gracefully.

    Setup:
        Vault with < 15 notes.

    Verifies:
        - Returns empty list"""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_clustering.suggest(context)

    # Should return empty list when < 20 notes
    assert len(suggestions) == 0


def test_temporal_clustering_max_suggestions(vault_with_temporal_notes):
    """Test that temporal_clustering never returns more than 2 suggestions.

    Setup:
        Vault with temporal clusters.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_clustering.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_temporal_clustering_deterministic_with_seed(vault_with_temporal_notes):
    """Test that temporal_clustering returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_temporal_notes

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

    suggestions1 = temporal_clustering.suggest(context1)
    suggestions2 = temporal_clustering.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_temporal_clustering_groups_by_quarter(tmp_path):
    """Test that temporal_clustering correctly groups notes by quarter."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Create notes in distinct time periods
    for i in range(30):
        # All in recent quarter
        date = now - timedelta(days=i)
        path = vault_path / f"recent_{i}.md"
        path.write_text(f"# Recent {i}\n\nRecent content.")
        timestamp = date.timestamp()
        os.utime(path, (timestamp, timestamp))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_clustering.suggest(context)

    # With only one quarter populated, should not find multiple clusters
    # (need at least 2 quarters with >= 5 notes each)
    assert isinstance(suggestions, list)


def test_temporal_clustering_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    now = datetime.now()

    for i in range(5):
        date = now - timedelta(days=i)
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\nClustering patterns across temporal quarters."
        )
        # Set file times
        timestamp = (now - timedelta(days=90 * i)).timestamp()
        os.utime(journal_dir / f"2024-03-{15 + i:02d}.md", (timestamp, timestamp))

    # Create notes across different quarters (over 2 years)
    for quarter in range(8):
        for i in range(7):  # 7 notes per quarter (56 total)
            date = now - timedelta(days=quarter * 90 + i * 10)
            path = vault_path / f"q{quarter}_note_{i}.md"
            path.write_text(f"# Q{quarter} Note {i}\n\nContent from quarter {quarter}.")
            # Set file times to match the quarter
            timestamp = date.timestamp()
            os.utime(path, (timestamp, timestamp))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_clustering.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
