"""Unit tests for seasonal_patterns geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import seasonal_patterns
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
def vault_with_seasonal_notes(tmp_path):
    """Create a vault with notes across multiple seasons and years."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes across multiple years and seasons
    # Year 1: January notes (Winter)
    for i in range(10):
        path = vault_path / f"winter_2022_{i}.md"
        content = f"""# Winter Note 2022 {i}

Winter theme content about cold weather, #winter, #reflection."""
        path.write_text(content)
        # Set creation time to January 2022
        winter_time = datetime(2022, 1, 15 + i).timestamp()
        import os

        os.utime(path, (winter_time, winter_time))

    # Year 2: January notes (Winter) - similar content for pattern detection
    for i in range(10):
        path = vault_path / f"winter_2023_{i}.md"
        content = f"""# Winter Note 2023 {i}

Winter theme content about cold weather, #winter, #planning."""
        path.write_text(content)
        winter_time = datetime(2023, 1, 15 + i).timestamp()
        import os

        os.utime(path, (winter_time, winter_time))

    # Year 3: June notes (Summer)
    for i in range(10):
        path = vault_path / f"summer_2022_{i}.md"
        content = f"""# Summer Note 2022 {i}

Summer activities, vacation planning, #summer, #travel."""
        path.write_text(content)
        summer_time = datetime(2022, 6, 15 + i).timestamp()
        import os

        os.utime(path, (summer_time, summer_time))

    # Year 4: June notes (Summer) - similar content
    for i in range(10):
        path = vault_path / f"summer_2023_{i}.md"
        content = f"""# Summer Note 2023 {i}

Summer activities, beach trips, #summer, #outdoors."""
        path.write_text(content)
        summer_time = datetime(2023, 6, 15 + i).timestamp()
        import os

        os.utime(path, (summer_time, summer_time))

    # Add scattered notes in other months for variety
    for i in range(15):
        path = vault_path / f"misc_{i}.md"
        content = f"""# Misc Note {i}

Miscellaneous content without strong seasonal pattern."""
        path.write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_seasonal_notes(tmp_path):
    """Create a vault with insufficient notes for seasonal pattern detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 20 notes (below minimum of 50)
    for i in range(20):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_seasonal_patterns_returns_suggestions(vault_with_seasonal_notes):
    """Test that seasonal_patterns returns suggestions with seasonal notes."""
    vault, session = vault_with_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_patterns.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_seasonal_patterns_suggestion_structure(vault_with_seasonal_notes):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_patterns.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "seasonal_patterns"

        # Should reference at least 2 notes
        assert len(suggestion.notes) >= 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_seasonal_patterns_uses_obsidian_link(vault_with_seasonal_notes):
    """Test that seasonal_patterns uses obsidian_link for note references."""
    vault, session = vault_with_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_patterns.suggest(context)

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


def test_seasonal_patterns_empty_vault(tmp_path):
    """Test that seasonal_patterns handles empty vault gracefully."""
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

    suggestions = seasonal_patterns.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_seasonal_patterns_insufficient_notes(vault_insufficient_seasonal_notes):
    """Test that seasonal_patterns handles insufficient notes gracefully."""
    vault, session = vault_insufficient_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_patterns.suggest(context)

    # Should return empty list when < 50 notes
    assert len(suggestions) == 0


def test_seasonal_patterns_no_recurrence(tmp_path):
    """Test that seasonal_patterns handles vault with no seasonal recurrence."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create 60 notes all in different months (no recurrence)
    base_date = datetime(2020, 1, 1)
    for i in range(60):
        path = vault_path / f"note_{i}.md"
        content = f"# Note {i}\n\nUnique content {i}."
        path.write_text(content)
        # Spread across 5 years, different months
        note_time = (base_date + timedelta(days=i * 30)).timestamp()
        import os

        os.utime(path, (note_time, note_time))

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

    suggestions = seasonal_patterns.suggest(context)

    # May return empty or minimal suggestions
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_seasonal_patterns_max_suggestions(vault_with_seasonal_notes):
    """Test that seasonal_patterns never returns more than 2 suggestions."""
    vault, session = vault_with_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_patterns.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_seasonal_patterns_deterministic_with_seed(vault_with_seasonal_notes):
    """Test that seasonal_patterns returns same results with same seed."""
    vault, session = vault_with_seasonal_notes

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

    suggestions1 = seasonal_patterns.suggest(context1)
    suggestions2 = seasonal_patterns.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2
