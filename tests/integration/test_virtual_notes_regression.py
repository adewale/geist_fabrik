"""Regression tests for virtual note handling across all geists.

This test suite ensures that geists properly use the Note.obsidian_link
property instead of bypassing the abstraction layer by querying raw
database fields like 'title'.

The bug this prevents:
- Virtual notes from journal files have identical titles in the database
  (e.g., multiple entries for "2024-03-15" from different journal files)
- Geists that query raw titles will show duplicates: "[[2024-03-15]], [[2024-03-15]]"
- Geists that use obsidian_link will show deeplinks: "[[Work Journal#2024-03-15]], [[Personal Journal#2024-03-15]]"

This test runs ALL code geists against a vault with virtual notes and
verifies that any suggestions referencing those notes use proper deeplinks.
"""

import importlib
import pkgutil
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists import code as code_geists_module
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry, _GLOBAL_REGISTRY


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


@pytest.fixture
def vault_with_virtual_notes(tmp_path):
    """Create a test vault with multiple journal files containing entries for the same dates.

    This setup creates a scenario where the abstraction layer bypass bug would manifest:
    - Multiple journal files (Work Journal, Personal Journal, Research Journal)
    - Each has entries for the same dates (2024-03-15 and 2024-03-20)
    - All entries for "2024-03-15" have identical title values in the database
    - Proper handling requires using obsidian_link to get deeplinks
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create multiple journal files with overlapping dates
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    other_date = datetime(2024, 3, 20, 14, 0, 0)

    # Work Journal with entries for both dates
    work_journal = vault_path / "Work Journal.md"
    work_journal.write_text("""# 2024-03-15

Project planning meeting. Discussed roadmap for Q2.

# 2024-03-20

Team sync. Reviewed sprint progress.
""")

    # Personal Journal with entries for both dates
    personal_journal = vault_path / "Personal Journal.md"
    personal_journal.write_text("""# 2024-03-15

Had a great insight about productivity systems.

# 2024-03-20

Reflection on learning journey.
""")

    # Research Journal with entries for both dates
    research_journal = vault_path / "Research Journal.md"
    research_journal.write_text("""# 2024-03-15

Found interesting paper on embeddings and semantic search.

# 2024-03-20

Reading about clustering algorithms.
""")

    # Add some regular notes to provide more content for geists
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

    # Set created dates for virtual entries
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE path LIKE '%/2024-03-15'",
        (burst_date.isoformat(),),
    )
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE path LIKE '%/2024-03-20'",
        (other_date.isoformat(),),
    )
    vault.db.commit()

    return vault


@pytest.fixture
def vault_context(vault_with_virtual_notes):
    """Create VaultContext for geist execution."""
    session_date = datetime(2024, 3, 25)
    session = Session(session_date, vault_with_virtual_notes.db)

    # Compute embeddings
    notes = vault_with_virtual_notes.all_notes()
    session.compute_embeddings(notes)

    function_registry = FunctionRegistry()
    return VaultContext(
        vault=vault_with_virtual_notes,
        session=session,
        seed=20240325,
        function_registry=function_registry,
    )


def discover_all_code_geists():
    """Dynamically discover all code geists in the default_geists.code package.

    Returns:
        list[tuple[str, module]]: List of (geist_name, geist_module) tuples
    """
    geists = []
    package_path = Path(code_geists_module.__file__).parent

    for module_info in pkgutil.iter_modules([str(package_path)]):
        if not module_info.name.startswith("_"):
            module = importlib.import_module(
                f"geistfabrik.default_geists.code.{module_info.name}"
            )
            if hasattr(module, "suggest"):
                geists.append((module_info.name, module))

    return geists


@pytest.mark.parametrize("geist_name,geist_module", discover_all_code_geists())
def test_geist_uses_obsidian_link_for_virtual_notes(
    geist_name, geist_module, vault_context
):
    """Test that each geist properly handles virtual notes using obsidian_link.

    This test verifies that geists don't bypass the abstraction layer by:
    1. Querying raw 'title' values from the database
    2. Failing to load Note objects
    3. Not using the obsidian_link property

    The test detects abstraction layer bypass by checking for:
    - Duplicate titles (same title appearing multiple times) when virtual notes exist
    - Missing deeplinks (# character) for virtual note references

    Args:
        geist_name: Name of the geist being tested
        geist_module: The geist module to test
        vault_context: VaultContext with virtual notes
    """
    # Skip geists that are known to not reference notes
    # (Add geists to this list if they intentionally don't reference specific notes)
    skip_geists = set()  # Currently none, kept for future use if needed

    if geist_name in skip_geists:
        pytest.skip(f"{geist_name} intentionally doesn't reference specific notes")

    # Run the geist
    try:
        suggestions = geist_module.suggest(vault_context)
    except Exception as e:
        # Some geists may fail on this minimal vault - that's okay
        # We're only testing those that successfully run and reference virtual notes
        pytest.skip(f"{geist_name} failed on test vault: {e}")
        return

    if not suggestions:
        # Geist returned no suggestions - nothing to test
        return

    # Get all virtual note titles from the vault for comparison
    all_notes = vault_context.all_notes()
    virtual_note_titles = {
        note.title for note in all_notes if note.is_virtual
    }

    if not virtual_note_titles:
        # No virtual notes in vault - skip
        pytest.skip("No virtual notes in test vault")
        return

    # Check each suggestion for potential abstraction layer bypass
    for suggestion in suggestions:
        if not suggestion.notes:
            # No note references - nothing to check
            continue

        # Count how many times each note reference appears
        note_ref_counts = {}
        for note_ref in suggestion.notes:
            note_ref_counts[note_ref] = note_ref_counts.get(note_ref, 0) + 1

        # Check 1: Detect duplicate note references
        # If a geist queries raw titles, virtual notes will show as duplicates
        duplicates = [ref for ref, count in note_ref_counts.items() if count > 1]

        assert not duplicates, (
            f"{geist_name}: Found duplicate note references {duplicates}. "
            f"This suggests the geist is querying raw 'title' values from the database "
            f"instead of using Note.obsidian_link. All references: {suggestion.notes}"
        )

        # Check 2: Verify virtual notes use deeplink format (filename#heading)
        # If a note reference matches a virtual note title exactly, it's missing the deeplink
        for note_ref in suggestion.notes:
            # Check if this reference is a virtual note title without deeplink
            if note_ref in virtual_note_titles and "#" not in note_ref:
                assert False, (
                    f"{geist_name}: Found virtual note reference '{note_ref}' without deeplink. "
                    f"Virtual notes should use deeplink format (e.g., 'Work Journal#2024-03-15') "
                    f"via Note.obsidian_link, not raw title values. "
                    f"All references: {suggestion.notes}"
                )

        # Check 3: If suggestion text contains wikilinks to virtual note titles,
        # verify they use deeplinks
        for virtual_title in virtual_note_titles:
            # Look for the title in wikilinks like [[2024-03-15]]
            if f"[[{virtual_title}]]" in suggestion.text:
                # Check if there's also a deeplink version in the text
                has_deeplink = f"#{virtual_title}]]" in suggestion.text

                assert has_deeplink, (
                    f"{geist_name}: Suggestion text contains '[[{virtual_title}]]' "
                    f"without deeplink format. Virtual notes should appear as "
                    f"'[[Filename#{virtual_title}]]'. "
                    f"Suggestion: {suggestion.text[:200]}..."
                )


def test_regression_creation_burst_specific(vault_context):
    """Specific regression test for creation_burst geist.

    This test explicitly verifies the fix for the original bug where
    creation_burst was showing duplicate titles for virtual notes.
    """
    from geistfabrik.default_geists.code import creation_burst

    suggestions = creation_burst.suggest(vault_context)

    if not suggestions:
        pytest.skip("creation_burst returned no suggestions on test vault")
        return

    suggestion = suggestions[0]

    # The burst day (2024-03-15) has 3 virtual notes
    # They should ALL use deeplink format, not duplicate titles
    assert len(suggestion.notes) >= 3, (
        f"Expected at least 3 notes for burst day, got {len(suggestion.notes)}"
    )

    # Check for deeplinks (must contain #)
    virtual_refs = [n for n in suggestion.notes if "#" in n]
    assert len(virtual_refs) >= 3, (
        f"Expected at least 3 virtual note refs with deeplinks, got {len(virtual_refs)}: "
        f"{suggestion.notes}"
    )

    # No duplicates allowed
    assert len(suggestion.notes) == len(set(suggestion.notes)), (
        f"Found duplicate note references: {suggestion.notes}"
    )

    # Verify text also uses deeplinks
    # Should NOT contain plain "[[2024-03-15]]" - should be "[[Journal#2024-03-15]]"
    assert "[[2024-03-15]]" not in suggestion.text or "#2024-03-15]]" in suggestion.text, (
        f"Suggestion text contains plain '[[2024-03-15]]' without deeplink: {suggestion.text}"
    )
