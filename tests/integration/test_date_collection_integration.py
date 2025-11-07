"""Integration tests for date-collection notes."""

from pathlib import Path

from geistfabrik.vault import Vault


def test_sync_journal_file(tmp_path: Path) -> None:
    """Test that journal file is split on sync."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a journal file
    journal = vault_path / "Daily Journal.md"
    journal.write_text("""
## 2025-01-15
First entry content.

## 2025-01-16
Second entry content.

## 2025-01-17
Third entry content.
""")

    # Sync vault
    vault = Vault(vault_path)
    count = vault.sync()
    assert count == 3, "Should process 3 virtual entries"

    # Check virtual entries created
    notes = vault.all_notes()
    assert len(notes) == 3

    # Check paths
    paths = {n.path for n in notes}
    assert "Daily Journal.md/2025-01-15" in paths
    assert "Daily Journal.md/2025-01-16" in paths
    assert "Daily Journal.md/2025-01-17" in paths

    # Check all are virtual
    assert all(n.is_virtual for n in notes)
    assert all(n.source_file == "Daily Journal.md" for n in notes)

    vault.close()


def test_sync_mixed_vault(tmp_path: Path) -> None:
    """Test vault with both journals and regular notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create regular note
    (vault_path / "Regular Note.md").write_text("# Regular Note\nContent here.")

    # Create journal
    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Entry one.

## 2025-01-16
Entry two.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    assert len(notes) == 3  # 1 regular + 2 virtual

    regular = [n for n in notes if not n.is_virtual]
    virtual = [n for n in notes if n.is_virtual]

    assert len(regular) == 1
    assert len(virtual) == 2
    assert regular[0].path == "Regular Note.md"

    vault.close()


def test_sync_journal_modification(tmp_path: Path) -> None:
    """Test re-sync when journal modified."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    journal = vault_path / "Journal.md"
    journal.write_text("""
## 2025-01-15
Original content.

## 2025-01-16
Second entry.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    assert len(notes) == 2
    # Find the first entry
    entry1 = [n for n in notes if n.path == "Journal.md/2025-01-15"][0]
    assert entry1.content.strip() == "Original content."

    # Modify journal - change first entry
    import time

    time.sleep(0.1)  # Ensure mtime changes
    journal.write_text("""
## 2025-01-15
Modified content.

## 2025-01-16
Second entry.

## 2025-01-17
New entry.
""")

    # Re-sync
    vault.sync()
    notes = vault.all_notes()

    assert len(notes) == 3
    entry1 = vault.get_note("Journal.md/2025-01-15")
    assert entry1 is not None
    assert "Modified content" in entry1.content

    vault.close()


def test_sync_journal_deletion(tmp_path: Path) -> None:
    """Test virtual entries removed when file deleted."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    journal = vault_path / "Journal.md"
    journal.write_text("""
## 2025-01-15
Entry.
""")

    vault = Vault(vault_path)
    vault.sync()

    assert len(vault.all_notes()) == 1

    # Delete journal
    journal.unlink()

    # Re-sync
    vault.sync()

    assert len(vault.all_notes()) == 0

    vault.close()


def test_query_get_note_virtual_path(tmp_path: Path) -> None:
    """Test can retrieve by virtual path."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Test content.

## 2025-01-16
Second entry.
""")

    vault = Vault(vault_path)
    vault.sync()

    # Get by virtual path
    note = vault.get_note("Journal.md/2025-01-15")

    assert note is not None
    assert note.is_virtual
    assert note.source_file == "Journal.md"
    assert "Test content" in note.content

    vault.close()


def test_query_filter_by_source_file(tmp_path: Path) -> None:
    """Test filter entries by source file."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal A.md").write_text("""
## 2025-01-15
Entry A1.

## 2025-01-16
Entry A2.
""")

    (vault_path / "Journal B.md").write_text("""
## 2025-01-15
Entry B1.

## 2025-01-17
Entry B2.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    assert len(notes) == 4

    # Filter by source file
    journal_a_entries = [n for n in notes if n.source_file == "Journal A.md"]
    journal_b_entries = [n for n in notes if n.source_file == "Journal B.md"]

    assert len(journal_a_entries) == 2
    assert len(journal_b_entries) == 2

    vault.close()


def test_query_filter_by_is_virtual(tmp_path: Path) -> None:
    """Test filter virtual vs regular."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Regular.md").write_text("# Regular\nContent.")
    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Entry.

## 2025-01-16
Second entry.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()

    regular = [n for n in notes if not n.is_virtual]
    virtual = [n for n in notes if n.is_virtual]

    assert len(regular) == 1
    assert len(virtual) == 2
    assert regular[0].path == "Regular.md"
    assert any(n.path == "Journal.md/2025-01-15" for n in virtual)

    vault.close()


def test_resolve_link_to_virtual_entry(tmp_path: Path) -> None:
    """Test resolve link to journal entry."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Entry content.

## 2025-01-16
Second entry.
""")

    vault = Vault(vault_path)
    vault.sync()

    # Resolve by virtual path
    note = vault.resolve_link_target("Journal.md/2025-01-15")
    assert note is not None
    assert note.is_virtual

    # Resolve by title (which is now in deeplink format)
    note2 = vault.resolve_link_target("Journal#2025-01-15")
    assert note2 is not None
    assert note2.path == "Journal.md/2025-01-15"

    vault.close()


def test_resolve_cross_entry_link(tmp_path: Path) -> None:
    """Test link between entries in same journal."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
First entry.

## 2025-01-16
Continued from [[2025-01-15]].
""")

    vault = Vault(vault_path)
    vault.sync()

    # Resolve from context of second entry
    note = vault.resolve_link_target("2025-01-15", source_path="Journal.md/2025-01-16")

    assert note is not None
    assert note.path == "Journal.md/2025-01-15"
    assert "First entry" in note.content

    vault.close()


def test_resolve_date_reference_link(tmp_path: Path) -> None:
    """Test [[YYYY-MM-DD]] resolves to entry."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Work Log.md").write_text("""
## 2025-01-15
Started project.

## 2025-01-16
Continued [[2025-01-15]] work.
""")

    vault = Vault(vault_path)
    vault.sync()

    # From context of virtual entry
    target = vault.resolve_link_target("2025-01-15", source_path="Work Log.md/2025-01-16")

    assert target is not None
    assert target.path == "Work Log.md/2025-01-15"

    vault.close()


def test_link_from_regular_to_virtual(tmp_path: Path) -> None:
    """Test regular note links to journal entry."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Important insight here.

## 2025-01-16
Second entry.
""")

    (vault_path / "Note.md").write_text("""
# My Note
See [[Journal#2025-01-15]] for details.
""")

    vault = Vault(vault_path)
    vault.sync()

    # Resolve link by title (which is now in deeplink format)
    target = vault.resolve_link_target("Journal#2025-01-15")

    assert target is not None
    assert target.is_virtual
    assert "Important insight" in target.content

    vault.close()


def test_split_preserves_frontmatter_tags(tmp_path: Path) -> None:
    """Test frontmatter applies to all entries."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""---
tags: [journal, work]
---

## 2025-01-15
First entry #important.

## 2025-01-16
Second entry.
""")

    vault = Vault(vault_path)
    vault.sync()

    entry1 = vault.get_note("Journal.md/2025-01-15")
    entry2 = vault.get_note("Journal.md/2025-01-16")

    # Both should have frontmatter tags
    assert "journal" in entry1.tags
    assert "work" in entry1.tags

    assert "journal" in entry2.tags
    assert "work" in entry2.tags

    # First entry should also have inline tag
    assert "important" in entry1.tags
    assert "important" not in entry2.tags

    vault.close()


def test_split_preserves_links(tmp_path: Path) -> None:
    """Test links extracted per-entry correctly."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Link to [[Note A]].

## 2025-01-16
Link to [[Note B]].
""")

    vault = Vault(vault_path)
    vault.sync()

    entry1 = vault.get_note("Journal.md/2025-01-15")
    entry2 = vault.get_note("Journal.md/2025-01-16")

    # Check links are per-entry
    entry1_targets = {link.target for link in entry1.links}
    entry2_targets = {link.target for link in entry2.links}

    assert "Note A" in entry1_targets
    assert "Note B" not in entry1_targets

    assert "Note B" in entry2_targets
    assert "Note A" not in entry2_targets

    vault.close()


def test_split_with_subheadings(tmp_path: Path) -> None:
    """Test H3/H4 under H2 included in entry."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15

### Morning
Morning content.

### Evening
Evening content.

## 2025-01-16
Next day content.
""")

    vault = Vault(vault_path)
    vault.sync()

    entry1 = vault.get_note("Journal.md/2025-01-15")

    assert "### Morning" in entry1.content
    assert "Morning content" in entry1.content
    assert "### Evening" in entry1.content
    assert "Evening content" in entry1.content
    assert "Next day content" not in entry1.content

    vault.close()


def test_split_complex_structure(tmp_path: Path) -> None:
    """Test complex markdown structure preserved."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Work Log.md").write_text("""
## 2025-01-15

### Tasks
- Fixed [[Bug 123]]
- Reviewed [[PR 456]]

### Code
```python
def example():
    return "test"
```

### Notes
> Important quote
> Multiple lines

#important #bug

## 2025-01-16

Second entry placeholder.
""")

    vault = Vault(vault_path)
    vault.sync()

    entry = vault.get_note("Work Log.md/2025-01-15")

    # Check structure preserved
    assert "### Tasks" in entry.content
    assert "### Code" in entry.content
    assert "```python" in entry.content
    assert "def example" in entry.content
    assert "> Important quote" in entry.content

    # Check links
    link_targets = {link.target for link in entry.links}
    assert "Bug 123" in link_targets
    assert "PR 456" in link_targets

    # Check tags
    assert "important" in entry.tags
    assert "bug" in entry.tags

    vault.close()


def test_sync_incremental(tmp_path: Path) -> None:
    """Test only changed journals re-split."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    journal_a = vault_path / "Journal A.md"
    journal_b = vault_path / "Journal B.md"

    journal_a.write_text("""
## 2025-01-15
Entry A.

## 2025-01-16
Entry A2.
""")

    journal_b.write_text("""
## 2025-01-15
Entry B.

## 2025-01-16
Entry B2.
""")

    vault = Vault(vault_path)
    count = vault.sync()
    assert count == 4  # Both journals processed (2 entries each)

    # Modify only Journal A
    import time

    time.sleep(1.0)  # Ensure mtime difference is detectable
    journal_a.write_text("""
## 2025-01-15
Modified entry A.

## 2025-01-16
Entry A2.
""")

    # Re-sync
    count = vault.sync()
    assert count == 2  # Only Journal A reprocessed (2 entries)

    entry_a = vault.get_note("Journal A.md/2025-01-15")
    assert "Modified entry A" in entry_a.content

    vault.close()


def test_journal_becomes_regular(tmp_path: Path) -> None:
    """Test file changes to no longer match pattern."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    journal = vault_path / "Note.md"
    journal.write_text("""
## 2025-01-15
Entry one.

## 2025-01-16
Entry two.
""")

    vault = Vault(vault_path)
    vault.sync()

    assert len(vault.all_notes()) == 2
    assert all(n.is_virtual for n in vault.all_notes())

    # Change to regular note
    import time

    time.sleep(0.1)
    journal.write_text("""
# Regular Note

## Introduction
Not a date.

## Conclusion
Also not a date.
""")

    vault.sync()

    notes = vault.all_notes()
    assert len(notes) == 1
    assert not notes[0].is_virtual
    assert notes[0].path == "Note.md"

    vault.close()


def test_regular_becomes_journal(tmp_path: Path) -> None:
    """Test file changes to match pattern."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    note = vault_path / "Note.md"
    note.write_text("""
# Regular Note
Regular content.
""")

    vault = Vault(vault_path)
    vault.sync()

    assert len(vault.all_notes()) == 1
    assert not vault.all_notes()[0].is_virtual

    # Change to journal
    import time

    time.sleep(0.1)
    note.write_text("""
## 2025-01-15
Now a journal entry.

## 2025-01-16
Another entry.
""")

    vault.sync()

    notes = vault.all_notes()
    assert len(notes) == 2
    assert all(n.is_virtual for n in notes)

    vault.close()


def test_empty_journal_file(tmp_path: Path) -> None:
    """Test empty file handled gracefully."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Empty.md").write_text("")

    vault = Vault(vault_path)
    vault.sync()

    # Empty file should be treated as regular note (no content)
    # or not create any note at all
    # Current implementation creates a note with empty content
    notes = vault.all_notes()
    assert len(notes) <= 1  # Accept either behavior

    vault.close()


def test_journal_unicode_content(tmp_path: Path) -> None:
    """Test unicode in entries preserved."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Unicode: 你好世界 🎉 Ñoño

## 2025-01-16
Second entry.
""")

    vault = Vault(vault_path)
    vault.sync()

    entry = vault.get_note("Journal.md/2025-01-15")

    assert "你好世界" in entry.content
    assert "🎉" in entry.content
    assert "Ñoño" in entry.content

    vault.close()


def test_journal_mixed_date_formats(tmp_path: Path) -> None:
    """Test mixed formats in same file."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
ISO format.

## January 16, 2025
Long format.

## 2025 January 17
Year-month-day format.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    assert len(notes) == 3

    # All should be detected and split correctly
    paths = {n.path for n in notes}
    assert "Journal.md/2025-01-15" in paths
    assert "Journal.md/2025-01-16" in paths
    assert "Journal.md/2025-01-17" in paths

    vault.close()


def test_entry_dates_set_correctly(tmp_path: Path) -> None:
    """Test entry_date field populated from heading."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Entry one.

## 2025-01-20
Entry two.
""")

    vault = Vault(vault_path)
    vault.sync()

    entry1 = vault.get_note("Journal.md/2025-01-15")
    entry2 = vault.get_note("Journal.md/2025-01-20")

    from datetime import date

    assert entry1.entry_date == date(2025, 1, 15)
    assert entry2.entry_date == date(2025, 1, 20)

    # Created time should match entry_date
    assert entry1.created.date() == date(2025, 1, 15)
    assert entry2.created.date() == date(2025, 1, 20)

    vault.close()


def test_all_date_formats_detected(tmp_path: Path) -> None:
    """Test all 7 supported date formats work."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Formats.md").write_text("""
## 2025-01-15
ISO date.

## 01/16/2025
US format.

## 17.01.2025
EU format.

## January 18, 2025
Long format.

## 2025 January 19
Year-month-day.

## Monday, January 20, 2025
With weekday.

## 2025-01-21T09:00:00
ISO datetime.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    assert len(notes) == 7

    # Check all dates parsed correctly
    from datetime import date

    dates = {n.entry_date for n in notes}
    assert date(2025, 1, 15) in dates
    assert date(2025, 1, 16) in dates
    assert date(2025, 1, 17) in dates
    assert date(2025, 1, 18) in dates
    assert date(2025, 1, 19) in dates
    assert date(2025, 1, 20) in dates
    assert date(2025, 1, 21) in dates

    vault.close()


def test_obsidian_deeplink_for_virtual_notes(tmp_path: Path) -> None:
    """Test that virtual note titles use Obsidian deeplink format.

    Virtual notes represent sections in journal files. Their titles are formatted
    as Obsidian deeplinks (e.g., "Journal#2025-01-15") so that geists can use
    [[{note.title}]] for both regular and virtual notes without special handling.

    This ensures:
    - Geists don't need to know about virtual vs regular notes
    - Links in suggestions work correctly in Obsidian
    - Clicking a link navigates to the correct heading in the source file

    Per Obsidian documentation:
    - Deeplink format: [[PAGE-NAME#Heading]]
    - Spaces in headings are preserved
    - Can omit .md extension
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a journal with multiple date entries
    (vault_path / "Work Log.md").write_text("""
## 2025-01-15
Completed initial project setup.

### Morning
- Created repository
- Set up CI/CD

### Afternoon
- First deployment

## 2025-01-16
Code review day.

## 2025-01-20
Sprint planning session.
""")

    # Create a second journal with different format
    (vault_path / "Daily Journal.md").write_text("""
## January 15, 2025
Reflections on the day.

## January 16, 2025
More thoughts.
""")

    vault = Vault(vault_path)
    vault.sync()

    # Test 1: Virtual notes are created correctly
    notes = vault.all_notes()
    assert len(notes) == 5  # 3 from Work Log + 2 from Daily Journal

    # Test 2: Get specific virtual notes
    work_jan15 = vault.get_note("Work Log.md/2025-01-15")
    work_jan16 = vault.get_note("Work Log.md/2025-01-16")
    journal_jan15 = vault.get_note("Daily Journal.md/2025-01-15")

    assert work_jan15 is not None
    assert work_jan16 is not None
    assert journal_jan15 is not None

    # Test 3: Virtual notes have titles in Obsidian deeplink format
    # This allows geists to use [[{note.title}]] and it just works
    assert work_jan15.is_virtual is True
    assert work_jan15.source_file == "Work Log.md"
    assert work_jan15.title == "Work Log#2025-01-15", (
        "Virtual note titles should use Obsidian deeplink format (filename#date) "
        "so they can be used directly in [[]] links without conversion"
    )

    # Test 4: Virtual note titles work as Obsidian deeplinks
    # Geists can now simply use [[{note.title}]] for both regular and virtual notes
    # For virtual notes, this creates a clickable link to the heading in the source file
    assert work_jan16.title == "Work Log#2025-01-16"

    # Test 5: Different date formats still use ISO format in title
    # Even though the heading in Daily Journal.md is "## January 15, 2025",
    # the title uses ISO format for consistency
    assert journal_jan15.title == "Daily Journal#2025-01-15", (
        "Virtual note titles should use ISO date format for consistency, "
        "regardless of the original heading format"
    )

    # Test 6: Regular notes have normal titles (no deeplink format)
    (vault_path / "Regular Note.md").write_text("# Regular Note\nContent here.")
    vault.sync()

    regular = vault.get_note("Regular Note.md")
    assert regular is not None
    assert not regular.is_virtual
    assert regular.title == "Regular Note", (
        "Regular notes should have normal titles without deeplink format"
    )

    # Test 7: Verify the deeplink format would resolve correctly
    # Using the existing resolve_link_target method
    resolved = vault.resolve_link_target("Work Log#2025-01-15")
    assert resolved is not None, "Deeplink should resolve to the virtual note"
    assert resolved.path == "Work Log.md/2025-01-15", "Should resolve to correct virtual note"

    # Test 8: Deeplink with .md extension should also work
    resolved_with_ext = vault.resolve_link_target("Work Log.md#2025-01-15")
    assert resolved_with_ext is not None, "Deeplink with .md extension should resolve"
    assert resolved_with_ext.path == "Work Log.md/2025-01-15"

    vault.close()


def test_date_collection_disabled_in_config(tmp_path: Path) -> None:
    """Test date-collection can be disabled via config."""
    from geistfabrik.config_loader import DateCollectionConfig, GeistFabrikConfig

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Entry one.

## 2025-01-16
Entry two.
""")

    # Create config with date_collection disabled
    config = GeistFabrikConfig(date_collection=DateCollectionConfig(enabled=False))

    vault = Vault(vault_path, config=config)
    vault.sync()

    # Should be treated as regular note, not split
    notes = vault.all_notes()
    assert len(notes) == 1
    assert not notes[0].is_virtual
    assert notes[0].path == "Journal.md"

    vault.close()


def test_date_collection_exclude_files(tmp_path: Path) -> None:
    """Test files can be excluded from date-collection."""
    from geistfabrik.config_loader import DateCollectionConfig, GeistFabrikConfig

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create template that should be excluded
    templates_dir = vault_path / "Templates"
    templates_dir.mkdir()

    (templates_dir / "Daily Template.md").write_text("""
## 2025-01-15
Template entry.

## 2025-01-16
Another template entry.
""")

    # Create regular journal that should be split
    (vault_path / "My Journal.md").write_text("""
## 2025-01-15
Real entry.

## 2025-01-16
Another real entry.
""")

    # Create config that excludes Templates/*
    config = GeistFabrikConfig(date_collection=DateCollectionConfig(exclude_files=["Templates/*"]))

    vault = Vault(vault_path, config=config)
    vault.sync()

    notes = vault.all_notes()

    # Should have 1 regular note (template) + 2 virtual notes (journal)
    assert len(notes) == 3

    template_notes = [n for n in notes if "Template" in n.path]
    journal_notes = [n for n in notes if "My Journal" in n.path]

    assert len(template_notes) == 1
    assert not template_notes[0].is_virtual  # Template is regular note

    assert len(journal_notes) == 2
    assert all(n.is_virtual for n in journal_notes)  # Journal is split

    vault.close()
