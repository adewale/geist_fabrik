"""Unit tests for seasonal_revisit geist."""

import os
from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import seasonal_revisit
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
def vault_with_past_seasonal_notes(tmp_path):
    """Create a vault with notes from same season in previous years."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()
    current_month = now.month

    # Create notes from same season in previous years
    # If current month is March (Spring), create March notes from past years
    for year_offset in range(1, 4):  # 1, 2, 3 years ago
        for i in range(5):
            path = vault_path / f"seasonal_{year_offset}y_ago_{i}.md"
            content = f"""# Seasonal Note {year_offset} Years Ago {i}

Content from the same season {year_offset} year(s) ago."""
            path.write_text(content)
            # Set creation time to same month, previous years
            past_date = datetime(now.year - year_offset, current_month, min(15 + i, 28))
            os.utime(path, (past_date.timestamp(), past_date.timestamp()))

    # Add current year notes (should be excluded)
    for i in range(5):
        path = vault_path / f"current_season_{i}.md"
        content = f"""# Current Season Note {i}

Content from current year."""
        path.write_text(content)

    # Add notes from different seasons
    for i in range(10):
        path = vault_path / f"other_season_{i}.md"
        # Use a different month (6 months offset)
        other_month = (current_month + 6) % 12 or 12
        content = f"""# Other Season Note {i}

Content from different season."""
        path.write_text(content)
        other_date = datetime(now.year - 1, other_month, 15)
        os.utime(path, (other_date.timestamp(), other_date.timestamp()))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_no_past_seasonal_notes(tmp_path):
    """Create a vault with no notes from same season in previous years."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()
    current_month = now.month

    # Only create notes from different seasons
    for i in range(15):
        path = vault_path / f"note_{i}.md"
        # Use a different month (6 months offset)
        other_month = (current_month + 6) % 12 or 12
        content = f"""# Note {i}

Content from different season."""
        path.write_text(content)
        other_date = datetime(now.year - 1, other_month, 15)
        os.utime(path, (other_date.timestamp(), other_date.timestamp()))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_seasonal_revisit_returns_suggestions(vault_with_past_seasonal_notes):
    """Test that seasonal_revisit returns suggestions with past seasonal notes."""
    vault, session = vault_with_past_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_revisit.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_seasonal_revisit_suggestion_structure(vault_with_past_seasonal_notes):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_past_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_revisit.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "seasonal_revisit"

        # Should reference 1 note
        assert len(suggestion.notes) == 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_seasonal_revisit_uses_obsidian_link(vault_with_past_seasonal_notes):
    """Test that seasonal_revisit uses obsidian_link for note references."""
    vault, session = vault_with_past_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_revisit.suggest(context)

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


def test_seasonal_revisit_empty_vault(tmp_path):
    """Test that seasonal_revisit handles empty vault gracefully."""
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

    suggestions = seasonal_revisit.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_seasonal_revisit_no_past_seasonal(vault_no_past_seasonal_notes):
    """Test that seasonal_revisit handles vault with no past seasonal notes."""
    vault, session = vault_no_past_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_revisit.suggest(context)

    # Should return empty list when no past seasonal notes
    assert len(suggestions) == 0


def test_seasonal_revisit_only_current_year(tmp_path):
    """Test that seasonal_revisit ignores notes from current year."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Only create notes from current year (should be excluded)
    for i in range(15):
        path = vault_path / f"current_{i}.md"
        content = f"# Current {i}\n\nContent."
        path.write_text(content)

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

    suggestions = seasonal_revisit.suggest(context)

    # Should return empty when only current year notes exist
    assert len(suggestions) == 0


def test_seasonal_revisit_max_suggestions(vault_with_past_seasonal_notes):
    """Test that seasonal_revisit never returns more than 2 suggestions."""
    vault, session = vault_with_past_seasonal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = seasonal_revisit.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_seasonal_revisit_deterministic_with_seed(vault_with_past_seasonal_notes):
    """Test that seasonal_revisit returns same results with same seed."""
    vault, session = vault_with_past_seasonal_notes

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

    suggestions1 = seasonal_revisit.suggest(context1)
    suggestions2 = seasonal_revisit.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_seasonal_revisit_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with seasonal content
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    now = datetime.now()
    current_month = now.month

    for i in range(5):
        path = journal_dir / f"2024-03-{15 + i:02d}.md"
        content = f"""# Session {i}

Content from the same season years ago. Seasonal patterns.

^g20240315-{i}"""
        path.write_text(content)
        # Set creation time to same season, previous year
        past_date = datetime(now.year - 1, current_month, min(15 + i, 28))
        os.utime(path, (past_date.timestamp(), past_date.timestamp()))

    # Create notes from same season in previous years
    for year_offset in range(1, 4):  # 1, 2, 3 years ago
        for i in range(5):
            path = vault_path / f"seasonal_{year_offset}y_ago_{i}.md"
            content = f"""# Seasonal Note {year_offset} Years Ago {i}

Content from the same season {year_offset} year(s) ago."""
            path.write_text(content)
            past_date = datetime(now.year - year_offset, current_month, min(15 + i, 28))
            os.utime(path, (past_date.timestamp(), past_date.timestamp()))

    # Add current year notes
    for i in range(5):
        path = vault_path / f"current_season_{i}.md"
        content = f"""# Current Season Note {i}

Content from current year."""
        path.write_text(content)

    # Add notes from different seasons
    for i in range(10):
        path = vault_path / f"other_season_{i}.md"
        other_month = (current_month + 6) % 12 or 12
        content = f"""# Other Season Note {i}

Content from different season."""
        path.write_text(content)
        other_date = datetime(now.year - 1, other_month, 15)
        os.utime(path, (other_date.timestamp(), other_date.timestamp()))

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

    suggestions = seasonal_revisit.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
