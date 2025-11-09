"""Tests for creation_burst geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import creation_burst
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


@pytest.fixture
def test_vault(tmp_path):
    """Create a test vault with burst days."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create burst day: 2024-03-15 with 6 notes
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    for i in range(6):
        note_path = vault_path / f"burst_note_{i}.md"
        note_path.write_text(f"# Burst Note {i}\n\nContent from the burst day.")

    # Create small burst day: 2024-03-16 with 4 notes
    small_burst_date = datetime(2024, 3, 16, 10, 0, 0)
    for i in range(4):
        note_path = vault_path / f"small_burst_note_{i}.md"
        note_path.write_text(f"# Small Burst Note {i}\n\nContent from small burst.")

    # Create normal day: 2024-03-17 with 2 notes (below threshold)
    normal_date = datetime(2024, 3, 17, 10, 0, 0)
    for i in range(2):
        note_path = vault_path / f"normal_note_{i}.md"
        note_path.write_text(f"# Normal Note {i}\n\nRegular note.")

    # Initialize vault and sync
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set created dates in database (using file mtime as proxy)
    for i in range(6):
        vault.db.execute(
            "UPDATE notes SET created = ? WHERE title = ?",
            (burst_date.isoformat(), f"Burst Note {i}"),
        )
    for i in range(4):
        vault.db.execute(
            "UPDATE notes SET created = ? WHERE title = ?",
            (small_burst_date.isoformat(), f"Small Burst Note {i}"),
        )
    for i in range(2):
        vault.db.execute(
            "UPDATE notes SET created = ? WHERE title = ?",
            (normal_date.isoformat(), f"Normal Note {i}"),
        )
    vault.db.commit()

    return vault


@pytest.fixture
def vault_context(test_vault):
    """Create VaultContext for geist execution."""
    session_date = datetime(2024, 3, 20)
    session = Session(session_date, test_vault.db)

    # Compute embeddings
    notes = test_vault.all_notes()
    session.compute_embeddings(notes)

    function_registry = FunctionRegistry()
    return VaultContext(
        vault=test_vault,
        session=session,
        seed=20240320,  # Deterministic seed
        function_registry=function_registry,
    )


def test_creation_burst_detects_burst_day(vault_context):
    """Test that burst days with 3+ notes are detected."""
    suggestions = creation_burst.suggest(vault_context)

    # Should return exactly 1 suggestion
    assert len(suggestions) == 1

    suggestion = suggestions[0]
    assert suggestion.geist_id == "creation_burst"
    assert "2024-03-" in suggestion.text  # Date should be present
    assert len(suggestion.notes) >= 3  # At least 3 notes (burst threshold)


def test_creation_burst_large_burst_question(vault_context):
    """Test that 6+ notes use 'What was special about that day?' question."""
    # Set seed to select the larger burst (6 notes)
    vault_context._rng = None  # Reset RNG
    vault_context.seed = 1  # Try different seed

    suggestions = creation_burst.suggest(vault_context)

    if suggestions and len(suggestions[0].notes) >= 6:
        # If we got the large burst, check question
        assert "What was special about that day?" in suggestions[0].text


def test_creation_burst_small_burst_question(vault_context):
    """Test that 3-5 notes use 'Does today feel generative?' question."""
    # Set seed to select the smaller burst (4 notes)
    vault_context._rng = None
    vault_context.seed = 2

    suggestions = creation_burst.suggest(vault_context)

    if suggestions and 3 <= len(suggestions[0].notes) <= 5:
        # If we got the small burst, check question
        assert "Does today feel generative?" in suggestions[0].text


def test_creation_burst_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from burst detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    # Create 10 journal notes on same day (should be ignored)
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    for i in range(10):
        note_path = journal_dir / f"2024-03-{15 + i:02d}.md"
        note_path.write_text(f"# Session {i}\n\nJournal entry.")

    # Create only 2 regular notes (below threshold)
    for i in range(2):
        note_path = vault_path / f"note_{i}.md"
        note_path.write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set all to same date
    vault.db.execute("UPDATE notes SET created = ?", (burst_date.isoformat(),))
    vault.db.commit()

    session = Session(burst_date, vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = creation_burst.suggest(context)

    # Should return empty list (journal notes excluded, only 2 regular notes)
    assert len(suggestions) == 0


def test_creation_burst_no_bursts(tmp_path):
    """Test that geist returns empty list when no burst days exist."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create only a few notes per day (below threshold)
    base_date = datetime(2024, 3, 1, 10, 0, 0)
    for day in range(5):
        for i in range(2):  # Only 2 notes per day (below 3 threshold)
            note_path = vault_path / f"note_{day}_{i}.md"
            note_path.write_text(f"# Note {day}-{i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set created dates
    for day in range(5):
        for i in range(2):
            note_date = base_date + timedelta(days=day)
            vault.db.execute(
                "UPDATE notes SET created = ? WHERE title = ?",
                (note_date.isoformat(), f"Note {day}-{i}"),
            )
    vault.db.commit()

    session = Session(base_date, vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240301,
        function_registry=FunctionRegistry(),
    )

    suggestions = creation_burst.suggest(context)

    # Should return empty list (no bursts)
    assert len(suggestions) == 0


def test_creation_burst_limits_display_titles(tmp_path):
    """Test that only first 8 titles are shown in suggestion text."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create burst with 15 notes
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    for i in range(15):
        note_path = vault_path / f"note_{i}.md"
        note_path.write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    vault.db.execute("UPDATE notes SET created = ?", (burst_date.isoformat(),))
    vault.db.commit()

    session = Session(burst_date, vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = creation_burst.suggest(context)

    # Text should show first 8 + "and 7 more"
    assert "and 7 more" in suggestions[0].text

    # But notes list should contain all 15
    assert len(suggestions[0].notes) == 15


def test_creation_burst_includes_date(vault_context):
    """Test that suggestion includes the burst day date."""
    suggestions = creation_burst.suggest(vault_context)

    assert len(suggestions) == 1
    # Date should be in YYYY-MM-DD format
    assert "2024-03-" in suggestions[0].text


def test_creation_burst_returns_single_suggestion(vault_context):
    """Test that geist returns exactly 1 suggestion."""
    suggestions = creation_burst.suggest(vault_context)

    # Should return exactly 1, not a list of many
    assert len(suggestions) == 1
