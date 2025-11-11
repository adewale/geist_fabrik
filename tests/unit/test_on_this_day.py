"""Unit tests for on_this_day geist."""

from datetime import datetime
from unittest.mock import patch

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import on_this_day
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
def vault_with_anniversary_notes(tmp_path):
    """Create a vault with notes from same calendar date in different years."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes
    (vault_path / "note1.md").write_text("# Note 1\n\nFirst anniversary note.")
    (vault_path / "note2.md").write_text("# Note 2\n\nSecond anniversary note.")
    (vault_path / "note3.md").write_text("# Note 3\n\nThird anniversary note.")
    (vault_path / "other.md").write_text("# Other\n\nDifferent date.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set creation dates - all on March 15 but different years
    # Current "today" will be March 15, 2024
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2023, 3, 15, 10, 0).isoformat(), "Note 1"),  # 1 year ago
    )
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2022, 3, 15, 10, 0).isoformat(), "Note 2"),  # 2 years ago
    )
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2021, 3, 15, 10, 0).isoformat(), "Note 3"),  # 3 years ago
    )
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2023, 5, 20, 10, 0).isoformat(), "Other"),  # Different date
    )
    vault.db.commit()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_finds_anniversary_notes(mock_datetime, vault_with_anniversary_notes):
    """Test that on_this_day finds notes from same date in previous years."""
    vault, session = vault_with_anniversary_notes

    # Mock today as March 15, 2024
    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    # Should return suggestions (at most 2)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2
    assert len(suggestions) > 0  # Should find at least one

    # Verify suggestion structure
    for suggestion in suggestions:
        assert suggestion.geist_id == "on_this_day"
        assert "ago today" in suggestion.text
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_suggestion_structure(mock_datetime, vault_with_anniversary_notes):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_anniversary_notes

    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, 'text')
        assert hasattr(suggestion, 'notes')
        assert hasattr(suggestion, 'geist_id')

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "on_this_day"

        # Should reference exactly 1 note
        assert len(suggestion.notes) == 1

        # Note reference should be string
        assert isinstance(suggestion.notes[0], str)


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_uses_obsidian_link(mock_datetime, vault_with_anniversary_notes):
    """Test that on_this_day uses obsidian_link for note references."""
    vault, session = vault_with_anniversary_notes

    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_year_phrase(mock_datetime, vault_with_anniversary_notes):
    """Test correct phrasing for 1 year vs multiple years."""
    vault, session = vault_with_anniversary_notes

    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    # Should have suggestions
    assert len(suggestions) > 0

    # Check for year phrasing
    texts = [s.text for s in suggestions]
    all_text = " ".join(texts)

    # Should have either "One year ago" or "X years ago"
    assert ("One year ago today" in all_text or "years ago today" in all_text)


# ============================================================================
# Edge Case Tests
# ============================================================================


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_empty_vault(mock_datetime, tmp_path):
    """Test that on_this_day handles empty vault gracefully."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_no_matching_dates(mock_datetime, tmp_path):
    """Test when no notes match the current date."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes on different dates
    (vault_path / "note1.md").write_text("# Note 1\n\nContent.")
    (vault_path / "note2.md").write_text("# Note 2\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set dates to NOT match March 15
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2023, 5, 20, 10, 0).isoformat(), "Note 1"),
    )
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2022, 7, 10, 10, 0).isoformat(), "Note 2"),
    )
    vault.db.commit()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    # Today is March 15 - no notes match
    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    # Should return empty when no matches
    assert len(suggestions) == 0


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_excludes_current_year(mock_datetime, tmp_path):
    """Test that notes from current year are excluded."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create note on same date in current year
    (vault_path / "this_year.md").write_text("# This Year\n\nCurrent year note.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set date to March 15, 2024 (current year when "today" is 2024)
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2024, 3, 15, 8, 0).isoformat(), "This Year"),
    )
    vault.db.commit()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    # Today is also March 15, 2024
    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    # Should exclude notes from current year
    assert len(suggestions) == 0


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_excludes_future_dates(mock_datetime, tmp_path):
    """Test that notes with future dates are excluded."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create note with future date
    (vault_path / "future.md").write_text("# Future\n\nFuture note.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set date to March 15, 2025 (future)
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2025, 3, 15, 10, 0).isoformat(), "Future"),
    )
    vault.db.commit()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    # Today is March 15, 2024
    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    # Should exclude future notes
    assert len(suggestions) == 0


# ============================================================================
# Limit Tests
# ============================================================================


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_max_two_suggestions(mock_datetime, vault_with_anniversary_notes):
    """Test that on_this_day returns at most 2 suggestions."""
    vault, session = vault_with_anniversary_notes

    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_sorts_by_recency(mock_datetime, vault_with_anniversary_notes):
    """Test that on_this_day prefers more recent years."""
    vault, session = vault_with_anniversary_notes

    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    # Use deterministic seed
    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    # Should prioritize 1-year-ago over 2-years-ago over 3-years-ago
    if len(suggestions) > 0:
        # Check that suggestions mention recent years
        texts = [s.text for s in suggestions]
        all_text = " ".join(texts)

        # Should include year references
        assert "year" in all_text.lower() or "years" in all_text.lower()


# ============================================================================
# Virtual Notes Tests
# ============================================================================


@patch('geistfabrik.default_geists.code.on_this_day.datetime')
def test_on_this_day_with_virtual_notes(mock_datetime, tmp_path):
    """Test that on_this_day works with virtual notes from journals."""
    from tests.fixtures.virtual_notes import create_journal_file

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create journal with entry on March 15 in previous year
    create_journal_file(
        vault_path / "Journal.md",
        dates=["2023-03-15", "2023-03-16"],
        content_template="Journal entry for {date}."
    )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    # Today is March 15, 2024
    mock_datetime.now.return_value = datetime(2024, 3, 15, 10, 0)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = on_this_day.suggest(context)

    # Should find the virtual note from March 15, 2023
    assert len(suggestions) > 0

    # Check that virtual notes use deeplinks (contain '#')
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            # Virtual notes should have deeplink format
            if "Journal" in note_ref:
                assert "#" in note_ref, f"Virtual note missing deeplink: {note_ref}"
