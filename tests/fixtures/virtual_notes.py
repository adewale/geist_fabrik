"""Reusable fixtures for testing virtual notes from journal files.

Virtual notes are created from journal files with H2 date headings.

Requirements for date-collection detection:
- Use H2 headings (##), not H1 (#) or H3 (###)
- Minimum 2 date headings (configurable via min_sections)
- At least 50% of H2 headings must parse as dates (date_threshold)

Example usage:
    def test_my_geist(vault_with_virtual_notes):
        suggestions = my_geist.suggest(vault_with_virtual_notes)
        virtual_notes = [n for n in vault_with_virtual_notes.notes() if n.is_virtual]
        assert len(virtual_notes) > 0
"""

from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry, _GLOBAL_REGISTRY


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


def create_journal_file(
    path: Path,
    dates: list[str],
    name: str = "Journal",
    content_template: str = "{date} entry content.",
) -> None:
    """Create a journal file with multiple date entries.

    Args:
        path: Path where journal file should be created
        dates: List of date strings (e.g., ["2024-03-15", "2024-03-16"])
        name: Journal name (default: "Journal")
        content_template: Template for entry content, {date} will be replaced

    Example:
        create_journal_file(
            vault_path / "Work Journal.md",
            dates=["2024-03-15", "2024-03-16"],
            name="Work Journal",
            content_template="Work tasks for {date}."
        )
    """
    entries = []
    for date in dates:
        entry = f"## {date}\n\n{content_template.format(date=date)}\n"
        entries.append(entry)

    path.write_text("\n".join(entries))


@pytest.fixture
def vault_with_virtual_notes(tmp_path) -> Generator[Vault, None, None]:
    """Create a vault with journal files containing virtual notes.

    Creates:
    - 3 journal files (Work Journal, Personal Journal, Research Journal)
    - Each with 2 date entries (2024-03-15, 2024-03-20)
    - 2 regular notes (Project Ideas, Research Notes)

    Total: 6 virtual notes + 2 regular notes = 8 notes

    Usage:
        def test_my_feature(vault_with_virtual_notes):
            vault = vault_with_virtual_notes
            notes = vault.all_notes()
            virtual = [n for n in notes if n.is_virtual]
            assert len(virtual) == 6
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create multiple journal files with overlapping dates
    create_journal_file(
        vault_path / "Work Journal.md",
        dates=["2024-03-15", "2024-03-20"],
        content_template="Project planning meeting. Discussed roadmap for Q2.",
    )

    create_journal_file(
        vault_path / "Personal Journal.md",
        dates=["2024-03-15", "2024-03-20"],
        content_template="Had a great insight about productivity systems.",
    )

    create_journal_file(
        vault_path / "Research Journal.md",
        dates=["2024-03-15", "2024-03-20"],
        content_template="Found interesting paper on embeddings and semantic search.",
    )

    # Add some regular notes
    (vault_path / "Project Ideas.md").write_text("""# Project Ideas

- Build a note-taking system
- Create visualization tools
""")

    (vault_path / "Research Notes.md").write_text("""# Research Notes

Notes on semantic search and embeddings.
""")

    # Initialize vault
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    yield vault

    vault.db.close()


@pytest.fixture
def vault_context_with_virtual_notes(
    vault_with_virtual_notes,
) -> Generator[VaultContext, None, None]:
    """Create VaultContext with virtual notes and computed embeddings.

    Builds on vault_with_virtual_notes to provide a ready-to-use VaultContext
    with embeddings computed for all notes (regular + virtual).

    Usage:
        def test_my_geist(vault_context_with_virtual_notes):
            suggestions = my_geist.suggest(vault_context_with_virtual_notes)
            # Virtual notes are already in the context, embeddings computed
    """
    vault = vault_with_virtual_notes
    session_date = datetime(2024, 3, 25)
    session = Session(session_date, vault.db)

    # Compute embeddings for all notes
    notes = vault.all_notes()
    session.compute_embeddings(notes)

    function_registry = FunctionRegistry()
    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240325,
        function_registry=function_registry,
    )

    yield context


@pytest.fixture
def vault_with_burst_day(tmp_path) -> Generator[tuple[Vault, datetime], None, None]:
    """Create a vault with a burst day (multiple notes created on same date).

    Useful for testing creation_burst geist specifically.

    Creates:
    - 3 journal files with entries for 2024-03-15
    - 1 regular note also created on 2024-03-15
    - Total: 4 notes on burst day (3 virtual + 1 regular)

    Returns:
        Tuple of (vault, burst_date)

    Usage:
        def test_burst_day_detection(vault_with_burst_day):
            vault, burst_date = vault_with_burst_day
            # All notes have created date = burst_date
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    date_heading = "2024-03-15"

    # Create journal files with entries for burst day
    create_journal_file(
        vault_path / "Work Journal.md",
        dates=[date_heading, "2024-03-16"],
        content_template="Work meeting about project planning.",
    )

    create_journal_file(
        vault_path / "Personal Journal.md",
        dates=[date_heading, "2024-03-16"],
        content_template="Had a great idea about productivity.",
    )

    create_journal_file(
        vault_path / "Research Journal.md",
        dates=[date_heading, "2024-03-16"],
        content_template="Found interesting paper on embeddings.",
    )

    # Add regular note
    (vault_path / "regular_note.md").write_text("# Regular Note\n\nSome content.")

    # Initialize vault
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set all virtual entries and regular note to burst date
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE path LIKE '%Journal%'",
        (burst_date.isoformat(),),
    )
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (burst_date.isoformat(), "Regular Note"),
    )
    vault.db.commit()

    yield vault, burst_date

    vault.db.close()


def assert_virtual_notes_created(vault: Vault, expected_count: int = 6) -> None:
    """Helper to verify virtual notes were created correctly.

    Args:
        vault: Vault to check
        expected_count: Expected number of virtual notes (default: 6)

    Raises:
        AssertionError: If virtual notes are not created correctly

    Usage:
        vault = create_test_vault()
        assert_virtual_notes_created(vault, expected_count=6)
    """
    all_notes = vault.all_notes()
    virtual_notes = [n for n in all_notes if n.is_virtual]

    assert (
        len(virtual_notes) == expected_count
    ), f"Expected {expected_count} virtual notes, got {len(virtual_notes)}"

    # Verify all virtual notes have required fields
    for note in virtual_notes:
        assert note.is_virtual is True, f"Note {note.path} should have is_virtual=True"
        assert (
            note.source_file is not None
        ), f"Note {note.path} should have source_file set"
        assert (
            note.entry_date is not None
        ), f"Note {note.path} should have entry_date set"
        assert "#" in note.obsidian_link, (
            f"Note {note.path} obsidian_link should contain '#' for deeplink, "
            f"got: {note.obsidian_link}"
        )


def assert_no_duplicate_titles_in_suggestions(suggestions: list) -> None:
    """Helper to verify suggestions don't contain duplicate note titles.

    This catches the abstraction layer bypass bug where geists query
    raw database titles instead of using Note.obsidian_link.

    Args:
        suggestions: List of Suggestion objects to check

    Raises:
        AssertionError: If any suggestion has duplicate note references

    Usage:
        suggestions = my_geist.suggest(vault_context)
        assert_no_duplicate_titles_in_suggestions(suggestions)
    """
    for suggestion in suggestions:
        if not suggestion.notes:
            continue

        # Check for duplicates
        note_counts = {}
        for note_ref in suggestion.notes:
            note_counts[note_ref] = note_counts.get(note_ref, 0) + 1

        duplicates = [ref for ref, count in note_counts.items() if count > 1]

        assert not duplicates, (
            f"Found duplicate note references in suggestion: {duplicates}\n"
            f"This suggests the geist is querying raw 'title' values instead of "
            f"using Note.obsidian_link.\n"
            f"All notes: {suggestion.notes}\n"
            f"Suggestion text: {suggestion.text[:100]}..."
        )
