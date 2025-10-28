"""Edge case tests for date-collection notes."""

from datetime import date
from pathlib import Path

from geistfabrik.vault import Vault


def test_very_large_journal(tmp_path: Path) -> None:
    """Test journal with 100+ entries."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Generate 100 date entries
    entries = []
    for i in range(100):
        day = i + 1
        if day > 31:
            continue  # Stay within January
        entries.append(f"## 2025-01-{day:02d}\nEntry {day} content.\n")

    content = "\n".join(entries)
    (vault_path / "Large Journal.md").write_text(content)

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    # Should create 31 virtual entries (days in January)
    assert len(notes) == 31
    assert all(n.is_virtual for n in notes)

    vault.close()


def test_invalid_date_formats_ignored(tmp_path: Path) -> None:
    """Test that invalid dates are ignored, not treated as dates."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Mixed.md").write_text("""
## 2025-01-15
Valid date.

## 2025-13-45
Invalid date (month 13, day 45).

## 2025-01-16
Another valid date.

## Not a date at all
Regular heading.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()

    # Should only detect the 2 valid dates (50% of 4 H2s = 2, meets threshold)
    assert len(notes) == 2
    virtual = [n for n in notes if n.is_virtual]
    assert len(virtual) == 2

    dates = {n.entry_date for n in virtual}
    assert date(2025, 1, 15) in dates
    assert date(2025, 1, 16) in dates

    vault.close()


def test_h1_and_h3_dates_not_detected(tmp_path: Path) -> None:
    """Test that only H2 headings are considered for dates."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Wrong Levels.md").write_text("""
# 2025-01-15
H1 date (should not be detected).

## 2025-01-16
H2 date (should be detected).

### 2025-01-17
H3 date (should not be detected).

## 2025-01-18
Another H2 date.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    # Only H2 dates detected
    assert len(virtual) == 2
    dates = {n.entry_date for n in virtual}
    assert date(2025, 1, 16) in dates
    assert date(2025, 1, 18) in dates

    vault.close()


def test_very_long_entry_content(tmp_path: Path) -> None:
    """Test entry with very long content (10KB+)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Generate 10KB+ of content
    long_content = "Lorem ipsum dolor sit amet. " * 400  # ~11KB

    (vault_path / "Long Entry.md").write_text(f"""
## 2025-01-15
{long_content}

## 2025-01-16
Short entry.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    assert len(virtual) == 2

    # Find the long entry
    long_entry = [n for n in virtual if n.entry_date == date(2025, 1, 15)][0]
    assert len(long_entry.content) > 10000

    vault.close()


def test_unicode_in_various_positions(tmp_path: Path) -> None:
    """Test unicode in file names, headings, and content."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Unicode in filename
    (vault_path / "日記.md").write_text("""
## 2025-01-15
Content with émojis 🎉 and Ñoño.

## 2025-01-16
More unicode: 你好世界 🌍
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    assert len(virtual) == 2
    assert "émojis" in virtual[0].content or "émojis" in virtual[1].content
    assert "你好世界" in virtual[0].content or "你好世界" in virtual[1].content

    vault.close()


def test_empty_journal_sections_skipped(tmp_path: Path) -> None:
    """Test that empty sections are skipped."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Sparse.md").write_text("""
## 2025-01-15
Content here.

## 2025-01-16


## 2025-01-17
More content.

## 2025-01-18
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    # Empty sections (01-16, 01-18) should be skipped
    assert len(virtual) == 2
    dates = {n.entry_date for n in virtual}
    assert date(2025, 1, 15) in dates
    assert date(2025, 1, 17) in dates

    vault.close()


def test_code_blocks_with_hash_symbols(tmp_path: Path) -> None:
    """Test that ## inside code blocks don't confuse parser."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Code.md").write_text("""
## 2025-01-15
Example code:

```python
# This is a comment
## This looks like a heading but isn't
def foo():
    pass
```

## 2025-01-16
More content.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    # Should still detect the real H2 dates
    assert len(virtual) == 2
    assert virtual[0].entry_date == date(2025, 1, 15)
    assert "```python" in virtual[0].content

    vault.close()


def test_frontmatter_with_date_fields(tmp_path: Path) -> None:
    """Test that date fields in frontmatter don't interfere."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""---
created: 2025-01-01
modified: 2025-01-15
tags: [journal]
---

## 2025-01-15
Entry content.

## 2025-01-16
More content.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    assert len(virtual) == 2
    # Frontmatter tags should be inherited
    assert all("journal" in n.tags for n in virtual)

    vault.close()


def test_nested_directories(tmp_path: Path) -> None:
    """Test journal files in nested directories."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    journals_dir = vault_path / "Journals" / "2025" / "January"
    journals_dir.mkdir(parents=True)

    (journals_dir / "Daily.md").write_text("""
## 2025-01-15
Entry 1.

## 2025-01-16
Entry 2.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    assert len(virtual) == 2
    # Virtual paths should preserve directory structure
    assert virtual[0].path.startswith("Journals/2025/January/")

    vault.close()


def test_special_characters_in_filename(tmp_path: Path) -> None:
    """Test filenames with spaces and special chars."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "My Daily Journal - 2025.md").write_text("""
## 2025-01-15
Entry 1.

## 2025-01-16
Entry 2.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    assert len(virtual) == 2
    assert virtual[0].source_file == "My Daily Journal - 2025.md"

    vault.close()


def test_links_with_headings_and_blocks(tmp_path: Path) -> None:
    """Test links with heading and block references."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
See [[Note#Section]] and [[Note^block123]].

## 2025-01-16
More links [[2025-01-15#Details]].
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    assert len(virtual) == 2

    # Links should be extracted with their parts
    entry1 = [n for n in virtual if n.entry_date == date(2025, 1, 15)][0]
    link_targets = {link.target for link in entry1.links}
    assert "Note" in link_targets

    vault.close()


def test_duplicate_consecutive_dates(tmp_path: Path) -> None:
    """Test consecutive duplicate date headings are merged."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Journal.md").write_text("""
## 2025-01-15
Morning entry.

## 2025-01-15
Afternoon entry.

## 2025-01-15
Evening entry.

## 2025-01-16
Next day.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    # Duplicates should be merged
    assert len(virtual) == 2

    entry1 = [n for n in virtual if n.entry_date == date(2025, 1, 15)][0]
    # All three sub-entries should be in the merged content
    assert "Morning entry" in entry1.content
    assert "Afternoon entry" in entry1.content
    assert "Evening entry" in entry1.content

    vault.close()


def test_mixed_date_and_datetime_formats(tmp_path: Path) -> None:
    """Test mixing date and datetime formats."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Mixed.md").write_text("""
## 2025-01-15
Just a date.

## 2025-01-16T09:00:00
With timestamp.

## January 17, 2025
Long format.

## 01/18/2025
US format.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    assert len(virtual) == 4

    dates = {n.entry_date for n in virtual}
    assert date(2025, 1, 15) in dates
    assert date(2025, 1, 16) in dates
    assert date(2025, 1, 17) in dates
    assert date(2025, 1, 18) in dates

    vault.close()


def test_file_with_only_whitespace_entries(tmp_path: Path) -> None:
    """Test file where all entries are whitespace only."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Empty Entries.md").write_text("""
## 2025-01-15


## 2025-01-16


## 2025-01-17

""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()

    # All entries empty, should create no virtual entries
    assert len(notes) == 0

    vault.close()


def test_tags_in_different_positions(tmp_path: Path) -> None:
    """Test tags at beginning, middle, and end of entries."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Tags.md").write_text("""
## 2025-01-15
#start-tag

Middle content.

#middle-tag

End content. #end-tag

## 2025-01-16
Another entry.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    entry1 = [n for n in virtual if n.entry_date == date(2025, 1, 15)][0]

    # All tags should be extracted
    assert "start-tag" in entry1.tags
    assert "middle-tag" in entry1.tags
    assert "end-tag" in entry1.tags

    vault.close()


def test_cross_year_boundary_dates(tmp_path: Path) -> None:
    """Test dates that cross year boundaries."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "Year End.md").write_text("""
## 2024-12-31
Last day of 2024.

## 2025-01-01
First day of 2025.

## 2025-01-02
Second day.
""")

    vault = Vault(vault_path)
    vault.sync()

    notes = vault.all_notes()
    virtual = [n for n in notes if n.is_virtual]

    assert len(virtual) == 3

    dates = {n.entry_date for n in virtual}
    assert date(2024, 12, 31) in dates
    assert date(2025, 1, 1) in dates
    assert date(2025, 1, 2) in dates

    vault.close()
