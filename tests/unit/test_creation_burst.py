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
def vault_with_bursts(tmp_path):
    """Create a vault with 2 burst days (6 notes + 4 notes) and 1 normal day (2 notes).

    Structure:
    - Burst day 2024-03-15: 6 notes (large burst)
    - Burst day 2024-03-16: 4 notes (small burst)
    - Normal day 2024-03-17: 2 notes (below threshold)

    Returns:
        tuple[Vault, Session]: Initialized vault with embeddings for session 2024-03-20
    """
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

    # Initialise vault and sync
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

    # Compute embeddings for session
    session_date = datetime(2024, 3, 20)
    session = Session(session_date, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


def test_creation_burst_detects_burst_day(vault_with_bursts):
    """Test that burst days with 3+ notes are detected."""
    vault, session = vault_with_bursts

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240320,
        function_registry=FunctionRegistry(),
    )

    suggestions = creation_burst.suggest(context)

    # Should return exactly 1 suggestion
    assert len(suggestions) == 1

    suggestion = suggestions[0]
    assert suggestion.geist_id == "creation_burst"
    assert "2024-03-" in suggestion.text  # Date should be present
    assert len(suggestion.notes) >= 3  # At least 3 notes (burst threshold)


def test_creation_burst_large_burst_question(vault_with_bursts):
    """Test that 6+ notes use 'What was special about that day?' question."""
    vault, session = vault_with_bursts

    # Set seed to select the larger burst (6 notes)
    context = VaultContext(
        vault=vault,
        session=session,
        seed=1,  # Try different seed
        function_registry=FunctionRegistry(),
    )

    suggestions = creation_burst.suggest(context)

    if suggestions and len(suggestions[0].notes) >= 6:
        # If we got the large burst, check question
        assert "What was special about that day?" in suggestions[0].text


def test_creation_burst_small_burst_question(vault_with_bursts):
    """Test that 3-5 notes use 'Does today feel generative?' question."""
    vault, session = vault_with_bursts

    # Set seed to select the smaller burst (4 notes)
    context = VaultContext(
        vault=vault,
        session=session,
        seed=2,
        function_registry=FunctionRegistry(),
    )

    suggestions = creation_burst.suggest(context)

    if suggestions and 3 <= len(suggestions[0].notes) <= 5:
        # If we got the small burst, check question
        assert "Does today feel generative?" in suggestions[0].text


def test_creation_burst_large_burst_guaranteed_question(tmp_path):
    """Test that large bursts (6+ notes) always use 'What was special about that day?' question.

    Creates vault with ONLY one large burst day (6 notes), ensuring it gets selected.
    Verifies question text matches expected template for large bursts.
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create burst day with exactly 6 notes (large burst threshold)
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    for i in range(6):
        note_path = vault_path / f"burst_note_{i}.md"
        note_path.write_text(f"# Burst Note {i}\n\nContent from the burst day.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set created dates
    for i in range(6):
        vault.db.execute(
            "UPDATE notes SET created = ? WHERE title = ?",
            (burst_date.isoformat(), f"Burst Note {i}"),
        )
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

    assert len(suggestions) == 1
    assert len(suggestions[0].notes) == 6
    # Large burst (6+ notes) should use this specific question
    assert "What was special about that day?" in suggestions[0].text


def test_creation_burst_small_burst_guaranteed_question(tmp_path):
    """Test that small bursts (3-5 notes) always use 'Does today feel generative?' question.

    Creates vault with ONLY one small burst day (4 notes), ensuring it gets selected.
    Verifies question text matches expected template for small bursts.
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create burst day with exactly 4 notes (small burst: 3-5 notes)
    burst_date = datetime(2024, 3, 16, 10, 0, 0)
    for i in range(4):
        note_path = vault_path / f"burst_note_{i}.md"
        note_path.write_text(f"# Burst Note {i}\n\nContent from the burst day.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set created dates
    for i in range(4):
        vault.db.execute(
            "UPDATE notes SET created = ? WHERE title = ?",
            (burst_date.isoformat(), f"Burst Note {i}"),
        )
    vault.db.commit()

    session = Session(burst_date, vault.db)
    session.compute_embeddings(vault.all_notes())
    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240316,
        function_registry=FunctionRegistry(),
    )

    suggestions = creation_burst.suggest(context)

    assert len(suggestions) == 1
    assert len(suggestions[0].notes) == 4
    # Small burst (3-5 notes) should use this specific question
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


def test_creation_burst_includes_date(vault_with_bursts):
    """Test that suggestion includes the burst day date."""
    vault, session = vault_with_bursts

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240320,
        function_registry=FunctionRegistry(),
    )

    suggestions = creation_burst.suggest(context)

    assert len(suggestions) == 1
    # Date should be in YYYY-MM-DD format
    assert "2024-03-" in suggestions[0].text


def test_creation_burst_returns_single_suggestion(vault_with_bursts):
    """Test that geist returns exactly 1 suggestion."""
    vault, session = vault_with_bursts

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240320,
        function_registry=FunctionRegistry(),
    )

    suggestions = creation_burst.suggest(context)

    # Should return exactly 1, not a list of many
    assert len(suggestions) == 1


def test_creation_burst_virtual_notes_use_deeplinks(tmp_path):
    """Test that virtual notes from journal files use deeplink format.

    When multiple journal entries exist for the same date (e.g., from different
    journal files), the suggestion should show distinct deeplinks like
    "Journal#2024-03-15" instead of duplicate titles.
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create multiple journal files with entries for the same date
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    date_heading = "2024-03-15"

    # Journal 1 - Use H2 headings (##) for date-collection detection
    journal1 = vault_path / "Work Journal.md"
    journal1.write_text(f"""## {date_heading}

Work meeting about project planning.

## 2024-03-16

Another day of work.
""")

    # Journal 2 - Use H2 headings (##) for date-collection detection
    journal2 = vault_path / "Personal Journal.md"
    journal2.write_text(f"""## {date_heading}

Had a great idea about productivity.

## 2024-03-16

Continued thinking about it.
""")

    # Journal 3 - Use H2 headings (##) for date-collection detection
    journal3 = vault_path / "Research Journal.md"
    journal3.write_text(f"""## {date_heading}

Found interesting paper on embeddings.

## 2024-03-16

More research notes.
""")

    # Add regular note on same day to reach 4 total notes (above threshold)
    note = vault_path / "regular_note.md"
    note.write_text("# Regular Note\n\nSome content.")

    # Initialize vault
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set created dates
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE path LIKE '%Journal%'",
        (burst_date.isoformat(),),
    )
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (burst_date.isoformat(), "Regular Note"),
    )
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

    assert len(suggestions) == 1
    suggestion = suggestions[0]

    # Check that suggestion text contains deeplinks (filename#heading format)
    # Virtual notes should show as "Work Journal#2024-03-15" etc., not just "2024-03-15"
    assert any(
        journal in suggestion.text
        for journal in ["Work Journal#", "Personal Journal#", "Research Journal#"]
    )

    # Check that notes list contains deeplinks for virtual entries
    # Virtual notes should use deeplink format in the notes list
    virtual_note_refs = [n for n in suggestion.notes if "#" in n]
    assert len(virtual_note_refs) >= 3, (
        f"Expected at least 3 virtual note refs with deeplinks, got {len(virtual_note_refs)}: "
        f"{suggestion.notes}"
    )

    # Verify all notes are distinct (no duplicates like "2024-03-15" repeated)
    assert len(suggestion.notes) == len(set(suggestion.notes)), (
        f"Found duplicate note references: {suggestion.notes}"
    )
