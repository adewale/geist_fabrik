# Journal Files & Virtual Notes Specification

**Status**: ✅ Implemented (v0.9.0, November 2025)
**Purpose**: Unified specification for date-collection notes (journals) and virtual note architecture

## Quick Start

### For Geist Developers

**The only thing you need to know**:

```python
# ✅ ALWAYS use note.obsidian_link for wiki-links
text = f"What if you revisited [[{note.obsidian_link}]]?"
notes = [note.obsidian_link]  # In Suggestion.notes

# ❌ NEVER use raw title or manually construct links
text = f"[[{note.title}]]"  # WRONG - breaks virtual notes
text = f"[[{note.source_file}#{note.title}]]"  # WRONG - redundant
```

**Why**: `obsidian_link` handles both regular and virtual notes correctly:
- Regular note: Returns `"Project Ideas"`
- Virtual note: Returns `"Work Journal#2024-03-15"` (deeplink format)

### For Test Writers

**Critical requirements for creating journal files in tests**:

```python
# ✅ MUST use H2 headings (##), not H1 (#) or H3 (###)
journal.write_text("""## 2024-03-15

Work meeting about project planning.

## 2024-03-16

Another day of work.
""")

# ✅ MUST have at least 2 date headings (min_sections requirement)
# ✅ MUST have ≥50% of H2 headings as dates (date_threshold)
```

**Common mistake**:
```python
# ❌ This will NOT create virtual notes (uses H1, only 1 heading)
journal.write_text("""# 2024-03-15
Content here...
""")
```

---

## Core Architecture

### The obsidian_link Abstraction

**Problem**: Virtual notes need special handling for Obsidian deeplinks, but we don't want every geist to know about them.

**Solution**: The `Note.obsidian_link` property encapsulates all linking logic:

```python
@dataclass(frozen=True)
class Note:
    path: str                    # Internal identifier
    title: str                   # Human-readable name
    is_virtual: bool = False
    source_file: Optional[str] = None

    @property
    def obsidian_link(self) -> str:
        """Return link text for Obsidian wiki-links (without [[brackets]])."""
        if self.is_virtual and self.source_file:
            # Virtual notes: Use deeplink format
            filename = self.source_file.replace(".md", "")
            return f"{filename}#{self.title}"
        else:
            # Regular notes: Just the title
            return self.title
```

**Examples**:

| Note Type | path | title | obsidian_link |
|-----------|------|-------|---------------|
| Regular | `"Ideas.md"` | `"Project Ideas"` | `"Project Ideas"` |
| Virtual | `"Journal.md/2024-03-15"` | `"2024-03-15"` | `"Journal#2024-03-15"` |

### Virtual Note Fields

```python
# Regular note
Note(
    path="Ideas.md",
    title="Project Ideas",
    is_virtual=False,
    source_file=None,
    entry_date=None
)

# Virtual note (journal entry)
Note(
    path="Work Journal.md/2024-03-15",      # Internal ID (ISO date)
    title="2024-03-15",                     # Original heading text
    is_virtual=True,                        # Marks as virtual
    source_file="Work Journal.md",          # Parent file
    entry_date=date(2024, 3, 15)           # Parsed date
)
```

**Key insight**: Virtual notes preserve the original heading text in `title`, but use ISO dates in `path` for consistency.

### Date-Collection Detection

A file is split into virtual notes if:

1. **Has ≥2 H2 headings** (configurable via `min_sections`)
2. **≥50% of H2 headings parse as dates** (configurable via `date_threshold`)
3. **Not excluded** via `config.yaml`

**Detection code**:
```python
def is_date_collection_note(content: str, min_sections: int = 2, date_threshold: float = 0.5) -> bool:
    headings = extract_h2_headings(content)  # Only H2, not H1 or H3!

    if len(headings) < min_sections:
        return False

    date_count = sum(1 for h, _ in headings if parse_date_heading(h) is not None)
    return date_count >= len(headings) * date_threshold
```

**Why H2 only**: Clear standard, prevents conflicts with H1 file titles and H3 subsections.

---

## Testing Virtual Notes

### Test Setup Requirements

**CRITICAL**: Creating virtual notes in tests requires specific markdown structure:

```python
def create_journal_file_for_testing(path: Path):
    """Create a journal file that will be detected as date-collection."""
    path.write_text("""## 2024-03-15

First entry content.

## 2024-03-16

Second entry content.
""")
    # Result: 2 virtual notes created on vault.sync()
```

**Common failures**:

```python
# ❌ Single heading - doesn't meet min_sections
"""## 2024-03-15
Content..."""

# ❌ H1 headings - not detected (extract_h2_headings ignores H1)
"""# 2024-03-15
Content..."""

# ❌ H3 headings - not detected (extract_h2_headings ignores H3)
"""### 2024-03-15
Content..."""

# ❌ Mixed but below threshold - 1 date + 3 topics = 25% < 50%
"""## 2024-03-15
## Topic A
## Topic B
## Topic C"""
```

### Test Fixture Pattern

**Don't test your test setup** - use verified fixtures:

```python
# ❌ BAD: Complex setup that might fail
def test_my_geist(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create journal... (20 lines of setup)
    # Manually update DB... (10 lines more)
    # Compute embeddings... (might fail)

    # Now test the geist
    suggestions = my_geist.suggest(vault_context)
    assert ...

# ✅ GOOD: Use tested fixture
def test_my_geist(vault_with_virtual_notes):  # Fixture provides ready vault
    suggestions = my_geist.suggest(vault_with_virtual_notes)
    assert ...
```

### Abstraction Layer Bypass Detection

**The bug pattern**: Querying raw database fields instead of using `Note.obsidian_link`

```python
# ❌ ABSTRACTION BYPASS - shows duplicate titles
cursor = vault.db.execute("""
    SELECT title FROM notes WHERE created = ?
""")
# Returns: ["2024-03-15", "2024-03-15", "2024-03-15"]  # Duplicates!

# ✅ CORRECT - use Note objects
cursor = vault.db.execute("""
    SELECT path FROM notes WHERE created = ?
""")
paths = [row[0] for row in cursor.fetchall()]
notes = [vault.get_note(path) for path in paths]
links = [note.obsidian_link for note in notes]
# Returns: ["Work Journal#2024-03-15", "Personal#2024-03-15", ...]  # Distinct!
```

**Regression test**: `tests/integration/test_virtual_notes_regression.py` runs all geists against virtual notes to catch this.

---

## Supported Date Formats

| Format | Example | Notes |
|--------|---------|-------|
| ISO Date | `2025-01-15` | Preferred format |
| US Format | `01/15/2025` | Month/Day/Year |
| EU Format | `15.01.2025` | Day.Month.Year |
| Long Format | `January 15, 2025` | Full month name |
| Year-Month-Day | `2025 January 15` | Alternate ordering |
| With Weekday | `Monday, January 15, 2025` | Day name prefix |
| ISO DateTime | `2025-01-15T09:00:00` | With timestamp |

**All formats are normalized to ISO in the virtual path** (`"Journal.md/2025-01-15"`), but the original heading text is preserved in `title`.

---

## Implementation Details

### Virtual Path Format

```
Original file:       Work Journal.md
Virtual entry paths: Work Journal.md/2024-03-15
                     Work Journal.md/2024-03-16
                     Work Journal.md/2024-03-17
```

**Separator**: Forward slash `/` distinguishes virtual from regular paths
**Date format**: Always ISO (YYYY-MM-DD) for consistency and uniqueness
**No extension**: Path uses `.md` from source, date doesn't have extension

### Link Resolution

The `Vault.resolve_link_target()` method handles multiple link formats:

```python
# 1. Direct virtual path
vault.get_note("Journal.md/2024-03-15")  # Works

# 2. Heading link with ISO date
vault.resolve_link_target("Journal#2024-03-15")  # Parses date, finds virtual path

# 3. Heading link with original format
vault.resolve_link_target("Journal#January 15, 2025")  # Parses date, finds same note

# 4. Context-aware bare date (from within same journal)
vault.resolve_link_target("2024-03-15", source_path="Journal.md/2024-03-16")
# Constructs "Journal.md/2024-03-15"
```

### Database Schema

```sql
-- Extended notes table (schema v4)
ALTER TABLE notes ADD COLUMN is_virtual INTEGER DEFAULT 0;
ALTER TABLE notes ADD COLUMN source_file TEXT;
ALTER TABLE notes ADD COLUMN entry_date DATE;

CREATE INDEX idx_notes_source_file ON notes(source_file);
CREATE INDEX idx_notes_entry_date ON notes(entry_date);
```

**Query patterns**:
```sql
-- Find all entries from a journal
SELECT * FROM notes WHERE source_file = 'Journal.md'

-- Find entries in date range
SELECT * FROM notes WHERE entry_date BETWEEN '2024-01-01' AND '2024-12-31'

-- Exclude virtual notes
SELECT * FROM notes WHERE is_virtual = 0
```

### Configuration

```yaml
# config.yaml
date_collection:
  enabled: true

  # Don't split these files
  exclude_files:
    - "Archive/*.md"
    - "Templates/*.md"

  # Minimum date headings required
  min_sections: 2

  # Minimum percentage of H2s that must be dates
  date_threshold: 0.5
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Using `note.title` for Links

```python
# ❌ WRONG - breaks for virtual notes
text = f"See [[{note.title}]]"
# Virtual note: "[[2024-03-15]]" - doesn't link correctly in Obsidian

# ✅ CORRECT - works for all notes
text = f"See [[{note.obsidian_link}]]"
# Virtual note: "[[Work Journal#2024-03-15]]" - works!
```

### Pitfall 2: Forgetting H2 Requirements in Tests

```python
# ❌ Will NOT create virtual notes
journal.write_text("# 2024-03-15\nContent")  # H1 not H2

# ✅ Will create virtual notes
journal.write_text("## 2024-03-15\nContent\n\n## 2024-03-16\nMore")  # H2, ≥2
```

### Pitfall 3: Testing Setup Instead of Behavior

```python
# ❌ Test has two responsibilities
def test_my_feature(tmp_path):
    # 30 lines creating complex vault setup...
    # Did the setup work? Who knows!

    # Now test the actual feature
    result = do_something(vault)
    assert result == expected

# ✅ Separate setup verification from feature testing
def test_journal_fixture_creates_virtual_notes(vault_with_journals):
    """Test the FIXTURE, not the feature."""
    virtual = [n for n in vault.all_notes() if n.is_virtual]
    assert len(virtual) > 0  # Fixture works

def test_my_feature(vault_with_journals):
    """Test the FEATURE with verified fixture."""
    result = do_something(vault_with_journals)
    assert result == expected
```

### Pitfall 4: Querying Raw Database Fields

```python
# ❌ ABSTRACTION BYPASS
cursor = db.execute("SELECT title FROM notes WHERE ...")
titles = [row[0] for row in cursor]
# Problem: Multiple virtuals with same title → duplicates

# ✅ USE NOTE OBJECTS
cursor = db.execute("SELECT path FROM notes WHERE ...")
paths = [row[0] for row in cursor]
notes = [vault.get_note(p) for p in paths if vault.get_note(p)]
links = [n.obsidian_link for n in notes]
# Solution: obsidian_link gives unique deeplinks
```

---

## Historical Context

### The Creation Burst Bug (November 2025)

**Symptom**: Suggestions showed duplicate titles:
```
On 2024-03-15, you created 5 notes: [[2024-03-15]], [[2024-03-15]], [[2024-03-15]]...
```

**Root cause**: `creation_burst` geist queried `GROUP_CONCAT(title, '|')` from database instead of using `Note.obsidian_link`.

**Fix**: Changed to `GROUP_CONCAT(path, '|')`, load Note objects, use `obsidian_link`:
```python
# Query paths, not titles
cursor = vault.db.execute("""
    SELECT GROUP_CONCAT(path, '|') FROM notes WHERE ...
""")
paths_str = cursor.fetchone()[0]
paths = paths_str.split("|")

# Load Note objects
notes = [vault.get_note(path) for path in paths]
notes = [n for n in notes if n is not None]

# Use obsidian_link
links = [note.obsidian_link for note in notes]
```

**Lesson**: Abstraction exists for a reason - don't bypass it with raw database queries.

### Virtual Note Title Bug (November 2025)

**Symptom**: Double filename prefix in links:
```
[[Exercise journal#Exercise journal#2024 February 18]]
```

**Root cause**: Early implementation stored deeplink format in `title` field:
```python
# ❌ OLD/WRONG
title = f"{file_stem}#{entry_date.isoformat()}"
```

**Fix**: Store only heading text in `title`, let `obsidian_link` construct deeplink:
```python
# ✅ CORRECT
title = original_heading_text.lstrip('#').strip()  # "2024 February 18"
# obsidian_link property combines: "Exercise journal#2024 February 18"
```

**Migration**: Pre-v0.9.1 databases need rebuild (delete `vault.db`, re-sync).

---

## Testing Strategy

### Unit Tests (`tests/unit/test_date_collection.py`)

- Date parsing (7 formats)
- Journal detection (H2 requirements, thresholds)
- Entry splitting logic
- Path generation
- Title preservation

### Integration Tests (`tests/integration/test_date_collection_integration.py`)

- Full vault sync workflow
- Link resolution (multiple formats)
- Embedding computation per-entry
- Temporal queries with virtual notes

### Regression Tests (`tests/integration/test_virtual_notes_regression.py`)

- **Parametrized test**: Runs ALL code geists against vault with virtual notes
- **Duplicate detection**: Catches abstraction layer bypass
- **Deeplink validation**: Ensures virtual notes use `#` format
- **Future-proof**: Automatically tests new geists as they're added

### Edge Case Tests (`tests/integration/test_date_collection_edge_cases.py`)

- Unicode content
- Large journals (>365 entries)
- Empty sections
- Duplicate dates
- Mixed date formats
- Nested directories

---

## For Vault Developers

### Adding Virtual Note Support to a Function

If you're adding a new vault function that returns note references:

```python
def my_vault_function(vault: Vault) -> list[str]:
    """Example function returning note references."""
    notes = vault.all_notes()

    # Filter/process notes...
    selected = notes[:5]

    # ✅ Return obsidian_link for all notes (handles regular + virtual)
    return [note.obsidian_link for note in selected]
```

**Rule**: Always return `obsidian_link`, never raw `title` or manually constructed links.

### Filtering Virtual vs Regular Notes

```python
# Get only regular notes
regular_notes = [n for n in vault.all_notes() if not n.is_virtual]

# Get only virtual notes
virtual_notes = [n for n in vault.all_notes() if n.is_virtual]

# Get entries from specific journal
journal_entries = [n for n in vault.all_notes()
                   if n.source_file == "Work Journal.md"]
```

### VaultContext Behavior

All VaultContext methods treat virtual and regular notes uniformly:

```python
ctx.notes()                 # Returns both types
ctx.get_note(path)          # Works with virtual paths
ctx.neighbours(note, k=5)   # Semantic search across all
ctx.old_notes(k=10)         # Uses entry_date for virtuals
ctx.recent_notes(k=10)      # Uses entry_date for virtuals
```

---

## References

- **Implementation**: `src/geistfabrik/date_collection.py`
- **Data model**: `src/geistfabrik/models.py` (Note.obsidian_link)
- **Link resolution**: `src/geistfabrik/vault.py` (resolve_link_target)
- **Schema**: `src/geistfabrik/schema.py` (migrate_to_v4)
- **Config**: `src/geistfabrik/config_loader.py` (DateCollectionConfig)
- **Tests**: `tests/unit/test_date_collection.py`, `tests/integration/test_date_collection_integration.py`
- **Regression**: `tests/integration/test_virtual_notes_regression.py`
- **User guide**: `JOURNAL_FILES.md`
- **Obsidian docs**: https://help.obsidian.md/Linking+notes+and+files/Internal+links#Link+to+a+heading+in+a+note

---

**Last Updated**: November 2025
**Version**: Implements v0.9.0, includes lessons from creation_burst bug fix
