# Virtual Notes Regression Tests

## Purpose

The `test_virtual_notes_regression.py` file contains regression tests that prevent a specific class of bugs: **abstraction layer bypass when handling virtual notes**.

## The Bug This Prevents

### Background: Virtual Notes

GeistFabrik supports "virtual notes" - individual journal entries split from date-collection files. For example, a file `Work Journal.md` with multiple date headings becomes multiple virtual notes in the database:

```
Work Journal.md/2024-03-15  (title: "2024-03-15")
Work Journal.md/2024-03-20  (title: "2024-03-20")
```

**Key issue**: Multiple journal files with entries for the same date result in notes with **identical title values** in the database:

```sql
-- All these have title = "2024-03-15":
Work Journal.md/2024-03-15       → title: "2024-03-15"
Personal Journal.md/2024-03-15   → title: "2024-03-15"
Research Journal.md/2024-03-15   → title: "2024-03-15"
```

### The Correct Abstraction

The `Note.obsidian_link` property handles this complexity:

```python
@property
def obsidian_link(self) -> str:
    if self.is_virtual and self.source_file:
        # Returns deeplink: "Work Journal#2024-03-15"
        filename = self.source_file.replace(".md", "")
        return f"{filename}#{self.title}"
    else:
        # Returns regular title: "Project Ideas"
        return self.title
```

### The Bug Pattern: Abstraction Layer Bypass

Geists that query raw database fields instead of using `Note.obsidian_link` will show duplicate titles:

```python
# ❌ WRONG: Bypasses abstraction, shows duplicates
cursor = vault.db.execute("""
    SELECT title FROM notes
    WHERE created = ?
""")
# Results in: ["2024-03-15", "2024-03-15", "2024-03-15"]

# ✅ CORRECT: Uses Note.obsidian_link
notes = [vault.get_note(path) for path in paths]
links = [note.obsidian_link for note in notes]
# Results in: ["Work Journal#2024-03-15", "Personal Journal#2024-03-15", "Research Journal#2024-03-15"]
```

## What The Tests Check

### 1. `test_geist_uses_obsidian_link_for_virtual_notes` (Parametrized)

Runs **all current and future code geists** against a vault with virtual notes and verifies:

- ✅ **No duplicate note references**: If a geist shows `["2024-03-15", "2024-03-15"]`, it's querying raw titles
- ✅ **Virtual notes use deeplinks**: References to virtual notes must contain `#` (e.g., `Work Journal#2024-03-15`)
- ✅ **Suggestion text uses deeplinks**: `[[2024-03-15]]` alone is wrong, must be `[[Work Journal#2024-03-15]]`

This test is **parametrized** - it discovers all code geists dynamically and tests each one. When you add a new geist, this test automatically covers it.

### 2. `test_regression_creation_burst_specific`

Explicit regression test for the `creation_burst` geist where this bug was originally discovered.

Verifies:
- At least 3 virtual notes in burst day
- All use deeplink format (contain `#`)
- No duplicates in the notes list
- Suggestion text uses deeplinks, not plain titles

## How It Catches The Bug

The test vault contains:
- 3 journal files (Work Journal, Personal Journal, Research Journal)
- Each with entries for the same dates (2024-03-15, 2024-03-20)
- This creates 6 virtual notes with duplicate titles

If a geist bypasses `obsidian_link`:
1. **Duplicate detection**: Same title appears multiple times in `suggestion.notes`
2. **Missing deeplink detection**: Note reference matches virtual title exactly without `#`
3. **Text analysis**: Suggestion text contains `[[2024-03-15]]` without deeplink format

## Running The Tests

```bash
# Run all virtual note regression tests
uv run pytest tests/integration/test_virtual_notes_regression.py -v

# Run for specific geist
uv run pytest tests/integration/test_virtual_notes_regression.py::test_geist_uses_obsidian_link_for_virtual_notes[creation_burst] -v

# Run just the creation_burst regression test
uv run pytest tests/integration/test_virtual_notes_regression.py::test_regression_creation_burst_specific -v
```

## When To Update This Test

### Add Geists To Skip List

If you create a geist that intentionally doesn't reference specific notes (e.g., a geist that only generates abstract prompts), add it to the skip list:

```python
skip_geists = {"abstract_prompt", "random_quote"}
```

### Modify For New Virtual Note Types

If GeistFabrik adds new types of virtual entities beyond journal entries, update the test vault creation to include them.

## Historical Context

This test was created in response to a bug in `creation_burst` (November 2025) where multiple journal entries for the same date were displaying as:

```
On 2023-05-21, you created 5 notes: [[2023 May 21]], [[2023 May 21]], [[2023 May 21]]...
```

Instead of:

```
On 2023-05-21, you created 5 notes: [[Work Journal#2023 May 21]], [[Personal Journal#2023 May 21]]...
```

The root cause was querying `GROUP_CONCAT(title, '|')` from the database instead of loading Note objects and using `obsidian_link`.

## Related Files

- **Fixed geist**: `src/geistfabrik/default_geists/code/creation_burst.py`
- **Note model**: `src/geistfabrik/models.py` (defines `Note.obsidian_link`)
- **Original bug test**: `tests/unit/test_creation_burst.py::test_creation_burst_virtual_notes_use_deeplinks`
