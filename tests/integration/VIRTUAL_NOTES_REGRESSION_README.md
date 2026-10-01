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

The `Note.link_text` property handles this complexity:

```python
@property
def link_text(self) -> str:
    if self.is_virtual and self.source_file:
        # Returns deeplink: "Work Journal#2024-03-15"
        filename = self.source_file.replace(".md", "")
        return f"{filename}#{self.title}"
    else:
        # Returns regular title: "Project Ideas"
        return self.title
```

### The Bug Pattern: Abstraction Layer Bypass

Geists that query raw database fields instead of using `Note.link_text` will show duplicate titles:

```python
# ❌ WRONG: Bypasses abstraction, shows duplicates
cursor = vault.db.execute("""
    SELECT title FROM notes
    WHERE created = ?
""")
# Results in: ["2024-03-15", "2024-03-15", "2024-03-15"]

# ✅ CORRECT: Uses Note.link_text
notes = [vault.get_note(path) for path in paths]
links = [note.link_text for note in notes]
# Results in: ["Work Journal#2024-03-15", "Personal Journal#2024-03-15", "Research Journal#2024-03-15"]
```

## What The Tests Check

### `test_code_geists_reference_virtual_notes_by_link_text`

Runs **every code geist**, each on its own fresh `VaultContext`, against a vault
that is mostly virtual notes: four journals whose dated entries collide on the
same dates, session history, and last session's persisted cluster labels. It
checks two things over the real output:

- every `Suggestion.notes` entry is the `link_text` of exactly one note (a bare
  date such as `"2024-05-22"` matches every journal's entry for that date, so
  the boundary filter cannot tell a public entry from an excluded one);
- no `[[wikilink]]` in the suggestion text is a bare virtual title.

The contract can only be checked where a geist produces output, so the test
also requires every geist in `EXPECTED_VIRTUAL_REFERENCERS` to reference at
least one virtual note on the fixture. An empty run fails. If a geist stops
producing on this fixture, re-trigger it in the fixture or remove it from the
set with a reason.

`test_fixture_titles_collide_across_journals` guards the fixture itself: each
shared date must be the bare title of several virtual notes.

### Where the creation_burst regression lives

The original bug was found in `creation_burst`. Its dedicated regression test is
`tests/unit/test_creation_burst.py::test_creation_burst_virtual_notes_use_deeplinks`,
which asserts that three same-date journal entries appear as distinct
`Journal#date` deeplinks in both the suggestion text and `suggestion.notes`.

The same bug survived in `cluster_evolution_tracker`, `metadata_outlier_detector`
and `seasonal_topic_analysis`, which put `note.title` into `Suggestion.notes`.
The previous version of this test checked each geist only inside a loop over its
output, and none of those three produced output on its fixture, so it passed.

## Running The Tests

```bash
uv run pytest tests/integration/test_virtual_notes_regression.py -v
uv run pytest tests/unit/test_creation_burst.py::test_creation_burst_virtual_notes_use_deeplinks -v
```

## When To Update This Test

If GeistFabrik adds new types of virtual entities beyond journal entries, add
them to the fixture.

## Historical Context

This test was created in response to a bug in `creation_burst` (November 2025) where multiple journal entries for the same date were displaying as:

```
On 2023-05-21, you created 5 notes: [[2023 May 21]], [[2023 May 21]], [[2023 May 21]]...
```

Instead of:

```
On 2023-05-21, you created 5 notes: [[Work Journal#2023 May 21]], [[Personal Journal#2023 May 21]]...
```

The root cause was querying `GROUP_CONCAT(title, '|')` from the database instead of loading Note objects and using `link_text`.

## Related Files

- **Fixed geist**: `src/geistfabrik/default_geists/code/creation_burst.py`
- **Note model**: `src/geistfabrik/models.py` (defines `Note.link_text`)
- **Original bug test**: `tests/unit/test_creation_burst.py::test_creation_burst_virtual_notes_use_deeplinks`
