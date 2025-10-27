"""Unit tests for date-collection note detection and splitting."""

from datetime import date, datetime

from geistfabrik.date_collection import (
    extract_h2_headings,
    is_date_collection_note,
    parse_date_heading,
    split_by_date_headings,
    split_date_collection_note,
)

# Detection Tests


def test_detect_iso_date_headings():
    """Test detection of ## YYYY-MM-DD headings."""
    content = """
## 2025-01-15
Content here

## 2025-01-16
More content
"""
    assert is_date_collection_note(content)


def test_detect_long_date_headings():
    """Test detection of long format dates."""
    content = """
## January 15, 2025
Content here

## January 16, 2025
More content
"""
    assert is_date_collection_note(content)


def test_detect_year_month_day_headings():
    """Test detection of YYYY Month DD format dates."""
    content = """
## 2022 August 8
Content here

## 2022 August 9
More content
"""
    assert is_date_collection_note(content)


def test_detect_mixed_headings_above_threshold():
    """Test 3 dates + 1 topic = detected (75% dates)."""
    content = """
## 2025-01-15
Content

## 2025-01-16
Content

## 2025-01-17
Content

## Random Topic
Not a date
"""
    assert is_date_collection_note(content)


def test_detect_mixed_headings_below_threshold():
    """Test 1 date + 3 topics = not detected (25% dates)."""
    content = """
## 2025-01-15
Content

## Topic One
Content

## Topic Two
Content

## Topic Three
Content
"""
    assert not is_date_collection_note(content)


def test_detect_single_date_heading_rejected():
    """Test single date heading not sufficient."""
    content = """
## 2025-01-15
Only one date section
"""
    assert not is_date_collection_note(content)


def test_detect_no_headings():
    """Test file with no H2 headings not detected."""
    content = """
# Title
Just regular content with no H2 headings.
"""
    assert not is_date_collection_note(content)


def test_detect_only_h1_headings():
    """Test file with only H1 headings not detected."""
    content = """
# 2025-01-15
Content

# 2025-01-16
More content
"""
    assert not is_date_collection_note(content)


def test_detect_regular_note():
    """Test regular note not detected as journal."""
    content = """
# Regular Note

## Introduction
This is not a date.

## Methods
Also not a date.

## Conclusion
Still not a date.
"""
    assert not is_date_collection_note(content)


# Date Parsing Tests


def test_parse_iso_date():
    """Test parsing ISO format YYYY-MM-DD."""
    assert parse_date_heading("## 2025-01-15") == date(2025, 1, 15)


def test_parse_us_date():
    """Test parsing US format MM/DD/YYYY."""
    assert parse_date_heading("## 01/15/2025") == date(2025, 1, 15)


def test_parse_eu_date():
    """Test parsing EU format DD.MM.YYYY."""
    assert parse_date_heading("## 15.01.2025") == date(2025, 1, 15)


def test_parse_long_date():
    """Test parsing long format 'Month DD, YYYY'."""
    assert parse_date_heading("## January 15, 2025") == date(2025, 1, 15)


def test_parse_date_with_weekday():
    """Test parsing 'Weekday, Month DD, YYYY'."""
    assert parse_date_heading("## Monday, January 15, 2025") == date(2025, 1, 15)


def test_parse_year_month_day():
    """Test parsing 'YYYY Month DD' format."""
    assert parse_date_heading("## 2022 August 8") == date(2022, 8, 8)
    assert parse_date_heading("## 2025 January 15") == date(2025, 1, 15)
    assert parse_date_heading("## 2023 December 31") == date(2023, 12, 31)


def test_parse_iso_datetime():
    """Test parsing ISO datetime format."""
    assert parse_date_heading("## 2025-01-15T09:00:00") == date(2025, 1, 15)


def test_parse_invalid_date():
    """Test invalid date returns None."""
    assert parse_date_heading("## 2025-13-45") is None


def test_parse_ambiguous_text():
    """Test ambiguous text returns None."""
    assert parse_date_heading("## Future Plans") is None


# Splitting Tests


def test_split_simple_journal():
    """Test splitting 3 date sections into 3 entries."""
    content = """
## 2025-01-15
First entry content.

## 2025-01-16
Second entry content.

## 2025-01-17
Third entry content.
"""
    sections = split_by_date_headings(content)
    assert len(sections) == 3
    assert sections[0].entry_date == date(2025, 1, 15)
    assert "First entry content" in sections[0].content
    assert sections[1].entry_date == date(2025, 1, 16)
    assert sections[2].entry_date == date(2025, 1, 17)


def test_split_with_frontmatter():
    """Test frontmatter applies to all entries."""
    content = """---
tags: [journal, work]
---

## 2025-01-15
First entry.

## 2025-01-16
Second entry.
"""
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 16, 10, 0),
    )

    assert len(notes) == 2
    # Frontmatter tags should be in all entries
    assert "journal" in notes[0].tags
    assert "work" in notes[0].tags
    assert "journal" in notes[1].tags
    assert "work" in notes[1].tags


def test_split_with_subheadings():
    """Test H3/H4 under H2 included in entry."""
    content = """
## 2025-01-15

### Morning
Morning content.

### Evening
Evening content.

## 2025-01-16
Next day content.
"""
    sections = split_by_date_headings(content)
    assert len(sections) == 2
    assert "### Morning" in sections[0].content
    assert "### Evening" in sections[0].content
    assert "Next day content" in sections[1].content


def test_split_with_code_blocks():
    """Test code blocks stay with correct entry."""
    content = """
## 2025-01-15
Some text.

```python
def example():
    pass
```

## 2025-01-16
Next entry.
"""
    sections = split_by_date_headings(content)
    assert len(sections) == 2
    assert "```python" in sections[0].content
    assert "def example" in sections[0].content


def test_split_preserves_links():
    """Test links extracted per-entry correctly."""
    content = """
## 2025-01-15
Link to [[Note A]].

## 2025-01-16
Link to [[Note B]].
"""
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 16),
    )

    assert len(notes) == 2
    assert any(link.target == "Note A" for link in notes[0].links)
    assert any(link.target == "Note B" for link in notes[1].links)


def test_split_preserves_tags():
    """Test tags extracted per-entry correctly."""
    content = """
## 2025-01-15
Content with #tag1

## 2025-01-16
Content with #tag2
"""
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 16),
    )

    assert len(notes) == 2
    assert "tag1" in notes[0].tags
    assert "tag2" in notes[1].tags


def test_split_empty_sections():
    """Test empty sections skipped."""
    content = """
## 2025-01-15
Content here.

## 2025-01-16

## 2025-01-17
More content.
"""
    sections = split_by_date_headings(content)
    # Empty section should be skipped
    assert len(sections) == 2
    assert sections[0].entry_date == date(2025, 1, 15)
    assert sections[1].entry_date == date(2025, 1, 17)


def test_split_duplicate_dates():
    """Test duplicate dates merged."""
    content = """
## 2025-01-15
Morning entry.

## 2025-01-15
Evening entry.

## 2025-01-16
Next day.
"""
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 16),
    )

    # Duplicate dates should be merged into one note
    assert len(notes) == 2
    assert notes[0].entry_date == date(2025, 1, 15)
    assert "Morning entry" in notes[0].content
    assert "Evening entry" in notes[0].content
    assert notes[1].entry_date == date(2025, 1, 16)


def test_split_preamble_content():
    """Test content before first date handled."""
    content = """
This is preamble content before any dates.

## 2025-01-15
First entry.

## 2025-01-16
Second entry.
"""
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 16),
    )

    # Preamble is discarded, only date sections remain
    assert len(notes) == 2
    assert "preamble" not in notes[0].content.lower()


def test_split_generates_virtual_paths():
    """Test virtual paths formatted correctly."""
    content = """
## 2025-01-15
Content.

## 2025-01-16
More content.
"""
    notes = split_date_collection_note(
        "Daily Journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 16),
    )

    assert notes[0].path == "Daily Journal.md/2025-01-15"
    assert notes[1].path == "Daily Journal.md/2025-01-16"


def test_split_sets_entry_dates():
    """Test entry_date field set from heading."""
    content = """
## 2025-01-15
Content.
"""
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 16),
    )

    assert len(notes) == 1
    assert notes[0].entry_date == date(2025, 1, 15)
    assert notes[0].is_virtual is True
    assert notes[0].source_file == "journal.md"


def test_split_preserves_file_mtime():
    """Test all entries share file modified time."""
    content = """
## 2025-01-15
First.

## 2025-01-16
Second.
"""
    file_modified = datetime(2025, 1, 16, 14, 30)
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        file_modified,
    )

    assert len(notes) == 2
    assert notes[0].modified == file_modified
    assert notes[1].modified == file_modified


# Path Tests


def test_virtual_path_format():
    """Test path is 'filename.md/YYYY-MM-DD'."""
    content = """
## 2025-01-15
Content.
"""
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 15),
    )

    assert notes[0].path == "journal.md/2025-01-15"


def test_virtual_path_is_unique():
    """Test different dates = different paths."""
    content = """
## 2025-01-15
First.

## 2025-01-16
Second.
"""
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 16),
    )

    paths = {note.path for note in notes}
    assert len(paths) == 2


def test_detect_virtual_path():
    """Test can identify virtual vs regular paths."""
    virtual_path = "journal.md/2025-01-15"
    regular_path = "journal.md"

    assert "/" in virtual_path
    assert "/" not in regular_path


def test_extract_source_file():
    """Test extract source file from virtual path."""
    virtual_path = "Daily Journal.md/2025-01-15"
    source_file = virtual_path.split("/")[0]

    assert source_file == "Daily Journal.md"


def test_extract_entry_date():
    """Test extract entry date from virtual path."""
    virtual_path = "journal.md/2025-01-15"
    date_str = virtual_path.split("/")[1]

    assert date_str == "2025-01-15"
    assert date.fromisoformat(date_str) == date(2025, 1, 15)


# Helper Function Tests


def test_extract_h2_headings():
    """Test extracting H2 headings."""
    content = """
# H1 Heading

## H2 Heading One
Content

## H2 Heading Two
More content

### H3 Not Extracted
"""
    headings = extract_h2_headings(content)

    assert len(headings) == 2
    assert "## H2 Heading One" in headings[0][0]
    assert "## H2 Heading Two" in headings[1][0]


def test_split_complex_structure():
    """Test complex markdown structure preserved."""
    content = """
## 2025-01-15

### Morning Session
- Fixed [[Bug 123]]
- Reviewed [[PR 456]]

### Afternoon Session
```python
def example():
    return "code"
```

Implemented [[Feature X]].

> Quote from documentation
> Multiple lines

#important #bug
"""
    notes = split_date_collection_note(
        "work_log.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 15),
    )

    assert len(notes) == 1
    note = notes[0]

    # Check structure preservation
    assert "### Morning Session" in note.content
    assert "### Afternoon Session" in note.content
    assert "```python" in note.content
    assert "> Quote from documentation" in note.content

    # Check links extracted
    link_targets = {link.target for link in note.links}
    assert "Bug 123" in link_targets
    assert "PR 456" in link_targets
    assert "Feature X" in link_targets

    # Check tags extracted
    assert "important" in note.tags
    assert "bug" in note.tags


def test_split_with_inline_and_frontmatter_tags():
    """Test inline and frontmatter tags combined."""
    content = """---
tags: [journal]
---

## 2025-01-15
Content with #inline-tag
"""
    notes = split_date_collection_note(
        "journal.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 15),
    )

    assert len(notes) == 1
    assert "journal" in notes[0].tags  # From frontmatter
    assert "inline-tag" in notes[0].tags  # From content


def test_split_no_valid_sections():
    """Test file with H2 headings but no valid dates."""
    content = """
## Introduction
Not a date.

## Methods
Also not a date.
"""
    notes = split_date_collection_note(
        "regular.md",
        content,
        datetime(2025, 1, 1),
        datetime(2025, 1, 15),
    )

    assert len(notes) == 0


def test_custom_date_threshold():
    """Test configurable date threshold."""
    content = """
## 2025-01-15
Date section.

## Topic One
Not a date.

## Topic Two
Not a date.
"""
    # With default 50% threshold, not detected (1/3 = 33%)
    assert not is_date_collection_note(content)

    # With 25% threshold, detected (1/3 = 33% > 25%)
    assert is_date_collection_note(content, date_threshold=0.25)


def test_custom_min_sections():
    """Test configurable minimum sections."""
    content = """
## 2025-01-15
Single date section.
"""
    # With default min_sections=2, not detected
    assert not is_date_collection_note(content)

    # With min_sections=1, detected
    assert is_date_collection_note(content, min_sections=1)
