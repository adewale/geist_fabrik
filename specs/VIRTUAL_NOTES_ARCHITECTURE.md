# Virtual Notes Architecture

## The Missing Abstraction

During development, we discovered a fundamental design issue: **conflating title (what a note is called) with obsidian_link (how to reference it in Obsidian)**.

### The Problem

Virtual notes are journal entries split from date-collection files. They need to be linkable in Obsidian using deeplink syntax (`[[Journal#2025-01-15]]`), but we initially tried to encode this in the title field:

```python
# Original approach - BAD
title = "Journal#2025-01-15"  # Mixed concerns
```

This forced every piece of code that used titles to understand virtual note syntax.

### The Solution

Separate title from link syntax via a property:

```python
@property
def obsidian_link(self) -> str:
    """Return the Obsidian wiki-link string for this note."""
    if self.is_virtual and self.source_file:
        filename = self.source_file.replace(".md", "")
        return f"{filename}#{self.title}"
    else:
        return self.title
```

**Regular notes:**
- path: `"Project Ideas.md"`
- title: `"Project Ideas"`
- obsidian_link: `"Project Ideas"` (same as title)

**Virtual notes:**
- path: `"Journal.md/2025-01-15"` (internal identifier with ISO date)
- title: `"2025-01-15"` (or `"January 15, 2025"` - original heading text)
- obsidian_link: `"Journal#2025-01-15"` (deeplink format)
- source_file: `"Journal.md"`
- entry_date: `date(2025, 1, 15)`

### Geist Usage

Geists use `note.obsidian_link` uniformly:

```python
# Works for both regular and virtual notes
def suggest(vault: VaultContext) -> List[Suggestion]:
    note = vault.sample_notes(1)[0]
    return [Suggestion(
        text=f"Consider linking [[{note.obsidian_link}]] to your current work.",
        notes=[note.obsidian_link],
        geist_id="example"
    )]
```

No conditional logic. No awareness of virtual vs regular notes.

## What Knows About Virtual Notes

### Infrastructure Layer (Should Know)

1. **`Note.obsidian_link` property** (`models.py`)
   - Encapsulates deeplink construction logic
   - Only place that combines source_file + title for virtual notes

2. **`date_collection.py`**
   - Creates virtual notes from journal files
   - Sets `is_virtual=True`, `source_file`, `entry_date`, and title fields
   - Preserves original heading text in title (not normalised to ISO)

3. **`vault.py`**
   - Persists virtual note fields to database
   - Resolves heading links to virtual notes (e.g., `[[Journal#2025-01-15]]`)
   - Handles context-aware date resolution (bare dates from within journals)

4. **`schema.py`**
   - Database schema includes `is_virtual`, `source_file`, `entry_date` columns

### Application Layer (Should NOT Know)

✅ **All 47 default geists** - Use `note.obsidian_link`, don't check `is_virtual`
✅ **VaultContext** - No virtual-note-specific methods or logic
✅ **Filtering pipeline** - Operates on Suggestions, not notes directly
✅ **Session output** - Just writes suggestions with links as-is

## Design Principles

### 1. Title Represents Content, Not Format

The title field is **what the note is called**, not how to link to it:
- Regular note: `"Project Ideas"` (from heading or filename)
- Virtual note: `"2025-01-15"` or `"January 15, 2025"` (from heading text)

### 2. obsidian_link Encapsulates Linking Logic

The `obsidian_link` property knows **how to reference this note in Obsidian**:
- Regular note: Same as title
- Virtual note: Constructs deeplink from source_file + title

### 3. Original Heading Text Preserved

Virtual note titles preserve the exact heading text from the file:
- File has `## January 15, 2025` → title is `"January 15, 2025"`
- File has `## 2025-01-15` → title is `"2025-01-15"`

This ensures:
- Links work in Obsidian (which requires exact heading match)
- Human-readable titles in vault queries
- No surprising normalisation

### 4. ISO Dates Only for Internal Paths

The path uses ISO format for consistency and uniqueness:
- `"Journal.md/2025-01-15"` (always ISO regardless of heading format)

The `entry_date` field stores the parsed date for temporal operations:
- Sorting entries by date
- Filtering by date range
- Date-based link resolution

## Link Resolution

### How Virtual Note Links Resolve

1. **Exact title match** - Try the target as-is against all note titles
2. **Heading link with date** - If target is `"Journal#<date>"`, parse the date and construct virtual path
3. **Context-aware date resolution** - If source is virtual and target is a bare date, find entry in same journal

Examples:

```python
# Direct virtual path
vault.get_note("Journal.md/2025-01-15")  # Works

# Heading link
vault.resolve_link_target("Journal#2025-01-15")  # Parses date, finds virtual path

# Heading link with original format
vault.resolve_link_target("Journal#January 15, 2025")  # Parses date, finds same note

# Bare date from virtual note context
vault.resolve_link_target("2025-01-15", source_path="Journal.md/2025-01-16")
# Constructs "Journal.md/2025-01-15"
```

### Why Vault Needs Virtual Note Knowledge

The `Vault.resolve_link_target()` method needs date-collection knowledge because:

1. **Obsidian allows multiple link formats** for the same note
2. **Date headings can be written many ways** (ISO, long form, etc.)
3. **Context matters** - bare dates mean different things in different contexts

This is **core functionality**, not a leaky abstraction. The complexity is unavoidable and correctly placed at the infrastructure layer.

## Testing Strategy

Virtual notes are tested at multiple levels:

1. **Unit tests** (`test_date_collection.py`)
   - Date parsing
   - Journal file detection
   - Entry splitting logic

2. **Integration tests** (`test_date_collection_integration.py`)
   - Full sync workflow
   - Link resolution
   - Round-trip journal ↔ virtual notes
   - Obsidian deeplink validation

3. **Property tests** (via test cases)
   - Virtual notes have `is_virtual=True`
   - Virtual notes have `obsidian_link != title`
   - Regular notes have `obsidian_link == title`

## Migration Notes

### From Title-Based Links to obsidian_link

If you have existing geists that use `note.title`:

```python
# Old pattern - WRONG for virtual notes
suggestion = f"Link to [[{note.title}]]"

# New pattern - CORRECT for all notes
suggestion = f"Link to [[{note.obsidian_link}]]"
```

### Accessing Note Names

If you need the human-readable name (not for linking):

```python
# For display/logging - use title
print(f"Processing note: {note.title}")

# For Obsidian links - use obsidian_link
text = f"Consider [[{note.obsidian_link}]]"
```

## Future Considerations

### What If We Need More Link Formats?

The property pattern allows adding new formats:

```python
@property
def obsidian_embed(self) -> str:
    """Return the embed syntax for this note."""
    return f"![[{self.obsidian_link}]]"

@property
def markdown_link(self) -> str:
    """Return standard markdown link syntax."""
    if self.is_virtual:
        # Could link to the source file with anchor
        return f"[{self.title}]({self.source_file}#{self.title})"
    return f"[{self.title}]({self.path})"
```

### What If Obsidian Changes Link Syntax?

Only the `obsidian_link` property needs updating. All geists continue to work.

### What About Other Virtual Note Types?

The pattern generalizes. If we add "virtual notes from sections" or "virtual notes from blocks":

1. Add appropriate fields to Note dataclass
2. Update `obsidian_link` property to handle new types
3. Geists remain unchanged

## Summary

The `obsidian_link` property is the key abstraction that:
- Separates concerns (naming vs linking)
- Encapsulates virtual note complexity
- Keeps geists simple and maintainable
- Allows the system to evolve without breaking high-level code

Virtual notes are **infrastructure**, not application logic. The abstraction boundary is clean and correct.
