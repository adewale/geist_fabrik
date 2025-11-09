# Date-Collection Notes (Journal Files)

**Version**: 1.0
**Status**: Implemented in GeistFabrik 0.9.0

## Table of Contents

1. [Overview](#overview)
2. [User Guide](#user-guide)
   - [What are Date-Collection Notes?](#what-are-date-collection-notes)
   - [How to Use Them](#how-to-use-them)
   - [Supported Date Formats](#supported-date-formats)
   - [Best Practices](#best-practices)
3. [Architecture](#architecture)
   - [Virtual Entry System](#virtual-entry-system)
   - [Path Format](#path-format)
   - [Link Resolution](#link-resolution)
   - [Incremental Sync](#incremental-sync)
4. [Technical Reference](#technical-reference)
   - [Database Schema](#database-schema)
   - [Detection Algorithm](#detection-algorithm)
   - [Splitting Algorithm](#splitting-algorithm)
   - [Configuration Options](#configuration-options)
5. [API Reference](#api-reference)

---

## Overview

Date-collection notes allow users to maintain journal files with multiple date-based entries in a single markdown file. GeistFabrik automatically detects these files and splits them into individual **virtual entries** that can be linked, searched, and queried as if they were separate notes.

**Key Features:**

- **Automatic Detection**: No special frontmatter required
- **Multiple Date Formats**: Supports 7 different date heading formats
- **Seamless Integration**: Virtual entries work like regular notes
- **Incremental Updates**: Only re-processes files when they change
- **Flexible Linking**: Link to entries by date, title, or virtual path
- **Frontmatter Inheritance**: YAML frontmatter applies to all entries

**Example:**

```markdown
---
tags: [journal, personal]
---

## 2025-01-15

Had a great insight about [[PKM Systems]] today. The key is...

## 2025-01-16

Followed up on yesterday's thoughts. Created [[New Project Idea]].

## 2025-01-17

Implemented the first prototype...
```

This single file becomes three virtual entries:
- `Daily Journal.md/2025-01-15`
- `Daily Journal.md/2025-01-16`
- `Daily Journal.md/2025-01-17`

Each entry can be referenced independently while keeping your journal organized in one file.

---

## User Guide

### What are Date-Collection Notes?

Date-collection notes are markdown files that contain multiple sections, each headed by a level-2 heading (`## `) with a date. They're commonly used for:

- **Daily journals** tracking thoughts and activities
- **Work logs** recording tasks and decisions
- **Research notes** organizing observations by date
- **Meeting notes** with dated sections
- **Project logs** tracking progress over time

GeistFabrik treats each dated section as an individual "virtual entry" that can be:
- Queried and filtered independently
- Linked to from other notes
- Discovered through semantic search
- Referenced in geist suggestions

### How to Use Them

#### 1. Create a Journal File

Just create a markdown file with date headings:

```markdown
## 2025-01-15
First entry here.

## 2025-01-16
Second entry here.
```

**Requirements for Detection:**
- At least **2 date headings** in the file
- At least **50%** of H2 headings must be valid dates
- Dates must use level-2 headings (`##`)

These thresholds prevent false positives on regular notes that happen to have one date heading.

#### 2. Add Frontmatter (Optional)

YAML frontmatter applies to all virtual entries:

```markdown
---
tags: [work, project-alpha]
author: me
---

## 2025-01-15
First work log entry.

## 2025-01-16
Second work log entry.
```

Both entries will have tags `[work, project-alpha]`.

#### 3. Link to Entries

You can link to journal entries in multiple ways:

**By Virtual Path:**
```markdown
See [[Daily Journal.md/2025-01-15]] for details.
```

**By Title:**
```markdown
See [[Daily Journal - 2025-01-15]] for details.
```

**By Date Reference (from same journal):**
```markdown
## 2025-01-20
Continuing from [[2025-01-15]]...
```

#### 4. Use Subheadings

Each entry can have its own structure:

```markdown
## 2025-01-15

### Morning
Started work on [[Feature X]].

### Afternoon
Met with team about [[Project Y]].

### Evening Reflection
Great progress today! #win
```

All subheadings stay with their date section.

### Supported Date Formats

GeistFabrik recognizes these date heading formats:

| Format | Example | Description |
|--------|---------|-------------|
| ISO Date | `## 2025-01-15` | YYYY-MM-DD format |
| US Format | `## 01/15/2025` | MM/DD/YYYY format |
| EU Format | `## 15.01.2025` | DD.MM.YYYY format |
| Long Format | `## January 15, 2025` | Full month name |
| With Weekday | `## Monday, January 15, 2025` | Includes day of week |
| Year-Month-Day | `## 2025 January 15` | YYYY Month DD format |
| ISO DateTime | `## 2025-01-15T09:00:00` | With timestamp |

**Notes:**
- Dates must be in H2 headings (`##`) only
- H3+ headings are treated as subheadings within entries
- Invalid dates (e.g., `2025-13-45`) are ignored

### Best Practices

#### ✅ Do

- **Use consistent date formats** within a file
- **Add descriptive filenames** like `Work Log.md` or `Research Journal.md`
- **Include frontmatter** for tags that apply to all entries
- **Use subheadings** (H3+) to structure individual entries
- **Link freely** between entries and other notes
- **Mix date formats** if needed (all 7 formats work together)

#### ❌ Don't

- **Don't use H3+ for dates** - only H2 headings are detected
- **Don't have just one date** - need at least 2 for detection
- **Don't mix dates and topics 50/50** - date sections must be majority
- **Don't manually create "virtual paths"** - they're generated automatically

#### Example: Well-Structured Journal

```markdown
---
tags: [journal, personal]
year: 2025
---

# Daily Journal

## 2025-01-15

### Thoughts
Had an insight about [[Zettelkasten Method]].

### Reading
Started [[Book - How to Take Smart Notes]].

#pkm #learning

## 2025-01-16

### Follow-up
Applied yesterday's insight to [[My PKM System]].

### New Ideas
- Link to [[2025-01-15]] for context
- Consider implementing [[Progressive Summarization]]

#implementation
```

**This creates:**
- 2 virtual entries with inherited tags `[journal, personal]`
- Entry-specific tags also preserved
- Clean cross-references between entries
- Structured content within each day

---

## Architecture

### Virtual Entry System

Date-collection notes are split into **virtual entries** during vault synchronization. Virtual entries:

- **Exist only in the database**, not as separate files on disk
- **Share the same file modification time** as their source file
- **Inherit frontmatter** from the source file
- **Have synthetic paths** like `Journal.md/2025-01-15`
- **Behave like regular notes** in queries and geist execution

**Design Rationale:**

Traditional PKM approaches create separate files per day (e.g., `2025-01-15.md`), which leads to:
- File clutter (365+ files per year)
- Difficult navigation and reorganization
- Loss of context across related days
- Backup and sync complexity

Virtual entries solve this by keeping content together in the filesystem while treating entries as separate notes in queries and suggestions.

### Path Format

Virtual entries use a hierarchical path format:

```
<source-file>/<entry-date-iso>
```

**Examples:**
- `Daily Journal.md/2025-01-15`
- `Work Log.md/2025-01-20`
- `Notes/Research.md/2025-02-01`

**Properties:**
- **Source file** preserves full relative path from vault root
- **Entry date** always in ISO format (`YYYY-MM-DD`) regardless of heading format
- **Separator** is forward slash (`/`), which isn't valid in filenames
- **Uniqueness** guaranteed by date within each journal file

**Why This Format?**

- **Clear hierarchy**: Shows parent-child relationship
- **No filesystem conflicts**: `/` separator prevents confusion with real files
- **Sortable**: ISO date format sorts chronologically
- **URL-safe**: Can be used in wiki-links without escaping

### Link Resolution

Links to virtual entries work through enhanced target resolution:

**Resolution Order:**

1. **Exact path match** - Try as virtual path (`Journal.md/2025-01-15`)
2. **With .md extension** - Try adding `.md` to path
3. **Title lookup** - Search for matching title (`Journal - 2025-01-15`)
4. **Date reference** - If source is virtual, resolve date in same journal

**Examples:**

From a regular note:
```markdown
See [[Daily Journal.md/2025-01-15]] for details.
See [[Daily Journal - 2025-01-15]] for details.
```

From within a journal entry:
```markdown
## 2025-01-20
Continued from [[2025-01-15]]...
```

The third example uses **context-aware resolution**: when linking from within a journal entry (`Journal.md/2025-01-20`), a date-only reference like `[[2025-01-15]]` is resolved within the same journal file.

### Incremental Sync

Virtual entries are regenerated only when their source file changes:

**On First Sync:**
1. Detect if file is a date-collection note
2. Parse and split into virtual entries
3. Store each entry with source file reference
4. Record file modification time

**On Subsequent Syncs:**
1. Check file mtime against database
2. Skip if unchanged (within 0.01s tolerance)
3. If changed:
   - Delete all old virtual entries for this file
   - Re-parse and regenerate entries
   - Update database

**Performance:**
- **Large journals** (100+ entries) re-split in ~10-50ms
- **Unchanged files** skipped in <1ms
- **Mixed vaults** (journals + regular notes) sync efficiently
- **Parallel processing** possible (file-level independence)

**Edge Cases Handled:**

- **File becomes journal**: Old regular note deleted, virtuals created
- **Journal becomes regular**: Virtuals deleted, regular note created
- **Journal deleted**: All virtual entries removed
- **Duplicate dates**: Sections merged into single entry

---

## Technical Reference

### Database Schema

Virtual entry support adds three fields to the `notes` table:

```sql
CREATE TABLE notes (
    path TEXT PRIMARY KEY,              -- Regular or virtual path
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created TEXT NOT NULL,              -- ISO datetime
    modified TEXT NOT NULL,             -- ISO datetime
    file_mtime REAL NOT NULL,          -- File modification time
    is_virtual INTEGER DEFAULT 0,       -- 1 for virtual entries
    source_file TEXT,                   -- Source file path (for virtuals)
    entry_date TEXT                     -- ISO date (for virtuals)
);

CREATE INDEX idx_notes_source_file ON notes(source_file);
CREATE INDEX idx_notes_entry_date ON notes(entry_date);
```

**Field Semantics:**

- `path`: Virtual path for entries, regular path for notes
- `is_virtual`: Flag for filtering queries
- `source_file`: Enables grouping entries by journal
- `entry_date`: Parsed date from heading (ISO format)
- `file_mtime`: Shared across all entries from same file

### Detection Algorithm

A file is classified as a date-collection note if:

```python
def is_date_collection_note(
    content: str,
    min_sections: int = 2,
    date_threshold: float = 0.5
) -> bool:
    """
    Returns True if file should be split into virtual entries.

    Parameters:
        min_sections: Minimum H2 headings required (default: 2)
        date_threshold: Min fraction of H2s that are dates (default: 0.5)
    """
    headings = extract_h2_headings(content)

    if len(headings) < min_sections:
        return False

    date_count = sum(1 for h in headings if parse_date_heading(h) is not None)

    return date_count >= len(headings) * date_threshold
```

**Examples:**

| H2 Headings | Date Headings | Detected? | Reason |
|-------------|---------------|-----------|--------|
| 3 dates | 3 | ✅ Yes | 100% dates, ≥2 sections |
| 1 date | 1 | ❌ No | <2 sections |
| 2 dates, 2 topics | 2 | ✅ Yes | 50% dates, ≥2 sections |
| 1 date, 3 topics | 1 | ❌ No | 25% dates (<50%) |

**Configuration:**

Both thresholds are configurable:

```yaml
# .geistfabrik/config.yaml
date_collection:
  min_sections: 2      # Require at least 2 H2 headings
  date_threshold: 0.5  # Require 50% to be dates
```

### Splitting Algorithm

Once detected, the file is split in three phases:

**Phase 1: Parse Frontmatter**

Extract YAML frontmatter and tags to apply to all entries:

```python
frontmatter, clean_content = parse_frontmatter(content)
frontmatter_tags = frontmatter.get('tags', [])
```

**Phase 2: Extract Date Sections**

Split content by date headings, preserving everything between headings:

```python
for each H2 heading:
    if heading is valid date:
        extract content from after this heading to before next heading
        skip the heading line itself
        preserve all subheadings (H3+), code blocks, lists, etc.
```

**Phase 3: Create Virtual Notes**

For each date section:

```python
virtual_path = f"{source_file}/{entry_date.isoformat()}"
title = f"{file_stem} - {entry_date.isoformat()}"
created = datetime.combine(entry_date, datetime.min.time())
modified = file_modified_time

# Parse links and tags from section content
links = extract_links(section_content)
tags = frontmatter_tags + extract_tags(section_content)

# Create Note object with virtual fields
note = Note(
    path=virtual_path,
    title=title,
    content=section_content,  # Heading excluded
    links=links,
    tags=tags,
    created=created,
    modified=file_modified_time,
    is_virtual=True,
    source_file=source_file,
    entry_date=entry_date
)
```

**Duplicate Date Handling:**

If multiple sections have the same date:

```markdown
## 2025-01-15
Morning content.

## 2025-01-15
Evening content.
```

They are **merged** into a single virtual entry:

```
2025-01-15 entry content = "Morning content.\n\nEvening content."
```

### Configuration Options

Date-collection behavior is configured in `.geistfabrik/config.yaml`:

```yaml
date_collection:
  # Enable/disable feature
  enabled: true

  # Files to exclude from detection
  exclude_files:
    - "Templates/*.md"
    - "Archive/Old Journal.md"

  # Detection thresholds
  min_sections: 2         # Minimum H2 headings to trigger detection
  date_threshold: 0.5     # Minimum fraction of H2s that must be dates

  # Supported date formats (all enabled by default)
  formats:
    - iso              # 2025-01-15
    - us               # 01/15/2025
    - eu               # 15.01.2025
    - long             # January 15, 2025
    - weekday          # Monday, January 15, 2025
    - year_month_day   # 2025 January 15
    - iso_datetime     # 2025-01-15T09:00:00
```

**Notes:**
- Changes to `enabled` require vault re-initialization
- `exclude_files` uses glob patterns
- Threshold changes apply immediately on next sync
- Format selection affects detection but not existing entries

---

## API Reference

### Note Model Extensions

The `Note` dataclass has three new fields:

```python
@dataclass
class Note:
    # ... existing fields ...

    # Virtual entry fields
    is_virtual: bool = False
    source_file: Optional[str] = None
    entry_date: Optional[date] = None
```

**Field Descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `is_virtual` | `bool` | `True` for virtual entries, `False` for regular notes |
| `source_file` | `Optional[str]` | Source file path (e.g., `"Journal.md"`) for virtual entries |
| `entry_date` | `Optional[date]` | Parsed date from heading for virtual entries |

**Example Usage:**

```python
# Filter to only journal entries
journal_entries = [n for n in vault.all_notes() if n.is_virtual]

# Get all entries from a specific journal
work_log = [n for n in vault.all_notes()
            if n.source_file == "Work Log.md"]

# Get entries from a specific date
today = [n for n in vault.all_notes()
         if n.entry_date == date(2025, 1, 15)]
```

### Vault Methods

#### `is_date_collection_note()`

```python
def is_date_collection_note(
    content: str,
    min_sections: int = 2,
    date_threshold: float = 0.5
) -> bool:
    """
    Check if content represents a date-collection note.

    Args:
        content: Full markdown content to analyze
        min_sections: Minimum H2 headings required
        date_threshold: Minimum fraction of H2s that must be dates

    Returns:
        True if content should be split into virtual entries
    """
```

#### `split_date_collection_note()`

```python
def split_date_collection_note(
    file_path: str,
    content: str,
    file_created: datetime,
    file_modified: datetime,
) -> List[Note]:
    """
    Split journal file into virtual note entries.

    Args:
        file_path: Original file path (e.g., "Daily Journal.md")
        content: Full file content
        file_created: File creation timestamp
        file_modified: File modification timestamp

    Returns:
        List of Note objects with is_virtual=True
    """
```

#### `resolve_link_target()` Enhancement

```python
def resolve_link_target(
    self,
    target: str,
    source_path: Optional[str] = None
) -> Optional[Note]:
    """
    Resolve wiki-link target to a Note (including virtual entries).

    Args:
        target: Link target string from wiki-link
        source_path: Optional path of note containing the link
                     (enables context-aware date resolution)

    Returns:
        Note object if found, None otherwise

    Resolution order:
        1. Exact path (handles virtual paths like "Journal.md/2025-01-15")
        2. Path with .md extension added
        3. Title match (handles virtual titles like "Journal - 2025-01-15")
        4. Date reference (if source is virtual, same journal)
    """
```

### Helper Functions

#### `parse_date_heading()`

```python
def parse_date_heading(heading: str) -> Optional[date]:
    """
    Parse date from H2 heading.

    Args:
        heading: H2 heading line (including ##)

    Returns:
        Parsed date if heading matches a format, None otherwise

    Examples:
        >>> parse_date_heading("## 2025-01-15")
        date(2025, 1, 15)

        >>> parse_date_heading("## January 15, 2025")
        date(2025, 1, 15)

        >>> parse_date_heading("## Random Topic")
        None
    """
```

#### `extract_h2_headings()`

```python
def extract_h2_headings(content: str) -> List[Tuple[str, int]]:
    """
    Extract H2 headings and their line numbers.

    Args:
        content: Markdown content

    Returns:
        List of (heading_text, line_number) tuples
        Line numbers are 1-indexed
    """
```

---

## Migration Guide

### From Daily Note Files to Date-Collection Notes

If you have existing daily note files:

**Before:**
```
vault/
  2025-01-15.md
  2025-01-16.md
  2025-01-17.md
```

**After:**
```
vault/
  Daily Journal.md
```

**Migration Steps:**

1. Create new journal file:
   ```bash
   touch "Daily Journal.md"
   ```

2. Combine existing files:
   ```bash
   for file in 2025-*.md; do
       date=$(basename "$file" .md)
       echo "## $date" >> "Daily Journal.md"
       cat "$file" >> "Daily Journal.md"
       echo "" >> "Daily Journal.md"
   done
   ```

3. Update links in other notes:
   ```
   [[2025-01-15]] -> [[Daily Journal.md/2025-01-15]]
   ```

4. Remove old files:
   ```bash
   rm 2025-*.md
   ```

5. Sync vault:
   ```bash
   geistfabrik sync ~/vault
   ```

GeistFabrik will automatically detect the new journal and create virtual entries.

### Handling Existing Templates

If you have templates that use date headings:

```yaml
# .geistfabrik/config.yaml
date_collection:
  exclude_files:
    - "Templates/*.md"
    - "*.template.md"
```

This prevents templates from being detected as journals.

---

## Troubleshooting

### File Not Detected as Journal

**Symptoms:** File appears as single regular note instead of split entries.

**Causes:**
1. Only one date heading (need ≥2)
2. Less than 50% of H2 headings are dates
3. Using H3 or lower for dates (must be H2)
4. Date format not recognized

**Solutions:**
- Add a second date heading
- Remove non-date H2 headings or convert to H3
- Verify date format matches supported patterns
- Check `date_threshold` in config

### Links Not Resolving

**Symptoms:** `[[link]]` doesn't resolve to virtual entry.

**Causes:**
1. Incorrect virtual path format
2. Entry doesn't exist
3. Title mismatch

**Solutions:**
- Use exact virtual path: `[[Journal.md/2025-01-15]]`
- Or use generated title: `[[Journal - 2025-01-15]]`
- Check entry exists: `geistfabrik query ~/vault --path "Journal.md/2025-01-15"`

### Entries Not Updating

**Symptoms:** Changes to journal file don't appear in virtual entries.

**Causes:**
1. File modification time not updated
2. Vault not synced

**Solutions:**
- Force re-sync: `touch "Journal.md" && geistfabrik sync ~/vault`
- Check file permissions

### Performance Issues

**Symptoms:** Slow vault sync with large journals.

**Causes:**
1. Very large journal files (1000+ entries)
2. Re-processing unchanged files

**Solutions:**
- Split large journals by year/month
- Verify incremental sync is working
- Check mtime comparison tolerance

---

## Implementation Status

**Completed (v0.9.0):**
- ✅ Date pattern recognition (7 formats)
- ✅ Virtual entry creation and storage
- ✅ Link resolution for virtual paths
- ✅ Incremental sync optimization
- ✅ Frontmatter inheritance
- ✅ Schema migration (v3 → v4)
- ✅ Comprehensive test coverage (64 tests)

**Future Enhancements (post-1.0):**
- Configuration UI
- Journal file templates
- Automatic daily note creation
- Entry-level metadata override
- Custom date format patterns
- Calendar view integration

---

## See Also

- [Specification](../specs/DATE_COLLECTION_NOTES_SPEC.md) - Detailed technical specification
- [Schema Documentation](../docs/SCHEMA.md) - Database schema reference
- [Link Resolution](../docs/LINK_RESOLUTION.md) - Wiki-link handling
- [Configuration Guide](../docs/CONFIGURATION.md) - Config file reference

---

**Document Version**: 1.0
**Last Updated**: 2025-10-27
**GeistFabrik Version**: 0.9.0
