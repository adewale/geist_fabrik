"""Unit tests for anachronism_detector geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import anachronism_detector
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
    """Create a vault with notes across different time periods."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()
    old_date = now - timedelta(days=400)
    recent_date = now - timedelta(days=30)

    # Create old notes (>1 year ago)
    for i in range(10):
        path = vault_path / f"old_{i}.md"
        path.write_text(f"# Old Note {i}\n\nContent about vintage topic {i}.")
        path.touch()
        # Set mtime to simulate old creation
        old_time = (old_date - timedelta(days=i * 10)).timestamp()
        import os

        os.utime(path, (old_time, old_time))

    # Create recent notes (last 90 days)
    for i in range(10):
        path = vault_path / f"recent_{i}.md"
        path.write_text(f"# Recent Note {i}\n\nContent about modern topic {i}.")
        path.touch()
        recent_time = (recent_date + timedelta(days=i)).timestamp()
        import os

        os.utime(path, (recent_time, recent_time))

    # Create middle-aged notes (6 months ago) to get >30 total
    mid_date = now - timedelta(days=180)
    for i in range(12):
        path = vault_path / f"middle_{i}.md"
        path.write_text(f"# Middle Note {i}\n\nContent about intermediate topic {i}.")
        path.touch()
        mid_time = (mid_date + timedelta(days=i * 5)).timestamp()
        import os

        os.utime(path, (mid_time, mid_time))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with insufficient notes for anachronism detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 10 notes (below minimum of 30)
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


def test_anachronism_detector_returns_suggestions(vault_with_temporal_notes):
    """Test that anachronism_detector returns suggestions with temporal notes."""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = anachronism_detector.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_anachronism_detector_suggestion_structure(vault_with_temporal_notes):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = anachronism_detector.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "anachronism_detector"

        # Should reference 2 notes (old and recent pair)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_anachronism_detector_uses_obsidian_link(vault_with_temporal_notes):
    """Test that anachronism_detector uses obsidian_link for note references."""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = anachronism_detector.suggest(context)

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


def test_anachronism_detector_empty_vault(tmp_path):
    """Test that anachronism_detector handles empty vault gracefully."""
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

    suggestions = anachronism_detector.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_anachronism_detector_insufficient_notes(vault_insufficient_notes):
    """Test that anachronism_detector handles insufficient notes gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = anachronism_detector.suggest(context)

    # Should return empty list when < 30 notes
    assert len(suggestions) == 0


def test_anachronism_detector_no_old_notes(tmp_path):
    """Test that anachronism_detector handles vault with only recent notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create 35 recent notes (all within last month)
    now = datetime.now()
    for i in range(35):
        path = vault_path / f"recent_{i}.md"
        path.write_text(f"# Recent Note {i}\n\nContent.")
        path.touch()

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

    suggestions = anachronism_detector.suggest(context)

    # Should return empty when no old notes exist
    assert len(suggestions) == 0


def test_anachronism_detector_max_suggestions(vault_with_temporal_notes):
    """Test that anachronism_detector never returns more than 2 suggestions."""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = anachronism_detector.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_anachronism_detector_deterministic_with_seed(vault_with_temporal_notes):
    """Test that anachronism_detector returns same results with same seed."""
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

    suggestions1 = anachronism_detector.suggest(context1)
    suggestions2 = anachronism_detector.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2
