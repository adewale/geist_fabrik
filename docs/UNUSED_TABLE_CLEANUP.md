# Unused Table Cleanup and Prevention

## Summary

Removed 2 unused database tables from schema and implemented automated detection to prevent future schema-code disconnect issues.

## Tables Removed

### 1. `suggestions`
```sql
CREATE TABLE suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    geist_id TEXT NOT NULL,
    title TEXT,
    created TEXT NOT NULL
);
```

### 2. `suggestion_notes`
```sql
CREATE TABLE suggestion_notes (
    suggestion_id INTEGER NOT NULL,
    note_path TEXT NOT NULL,
    FOREIGN KEY (suggestion_id) REFERENCES suggestions(id) ON DELETE CASCADE,
    FOREIGN KEY (note_path) REFERENCES notes(path) ON DELETE CASCADE
);
```

**Why they were removed:**
- 0 SQL references in entire codebase (never queried, never inserted)
- Superseded by `session_suggestions` table (denormalized design)
- The normalized design was likely an early architectural decision that was abandoned

## Replacement

These tables were replaced by `session_suggestions`:

```sql
CREATE TABLE session_suggestions (
    session_date TEXT NOT NULL,
    geist_id TEXT NOT NULL,
    suggestion_text TEXT NOT NULL,
    block_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_date, block_id)
);
```

**Why this design is better:**
- Denormalized: all data in one table (simpler queries)
- Used for novelty filtering (see `filtering.py`)
- Used for history tracking (see `journal_writer.py`)
- Actually has code that writes to and reads from it

## Schema Version Update

Updated `SCHEMA_VERSION` from 2 to 3 in `schema.py`.

## Automated Detection

Created `scripts/detect_unused_tables.py` to prevent this issue in the future.

### How It Works

1. Parses `schema.py` to extract table names (regex: `CREATE TABLE IF NOT EXISTS (\w+)`)
2. Searches all Python files in `src/` for SQL operations:
   - `FROM table_name`
   - `INTO table_name`
   - `UPDATE table_name`
   - `DELETE FROM table_name`
   - `JOIN table_name`
3. Reports tables with 0 references
4. Exits with code 1 if unused tables found (useful for CI)

### Usage

```bash
# Check for unused tables
python scripts/detect_unused_tables.py

# Verbose mode (shows which files use each table)
python scripts/detect_unused_tables.py --verbose
```

### Example Output

```
📊 Found 7 tables in schema

✅ embeddings: 1 file(s)
✅ links: 2 file(s)
✅ notes: 3 file(s)
✅ session_embeddings: 1 file(s)
✅ session_suggestions: 2 file(s)
✅ sessions: 1 file(s)
✅ tags: 1 file(s)

============================================================
Summary: 7 used, 0 unused
============================================================

✨ All tables are in use!
```

## Integration

### Pre-commit Hook

Added to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: detect-unused-tables
      name: Detect unused database tables
      entry: python3 scripts/detect_unused_tables.py
      language: system
      files: ^src/geistfabrik/(schema\.py|.*\.py)$
      pass_filenames: false
```

**When it runs:**
- On every commit that touches `schema.py` or any `.py` file in `src/geistfabrik/`
- Blocks commit if unused tables are detected
- Forces developer to either remove unused table or add code that uses it

**How to bypass (if needed):**
```bash
git commit --no-verify  # Skip pre-commit hooks (use sparingly!)
```

### CI Integration

Added to `.github/workflows/test.yml`:

```yaml
- name: Check for unused database tables
  run: python scripts/detect_unused_tables.py
```

**When it runs:**
- On every push to main
- On every pull request
- Fails CI build if unused tables detected

## Benefits

1. **Prevents schema bloat**: Catch unused tables immediately
2. **Forces intentionality**: Can't add a table without using it
3. **Documentation**: The script serves as executable documentation of table usage
4. **Fast feedback**: Runs in <1 second, no dependencies needed
5. **Zero maintenance**: Automatically adapts to schema changes

## Edge Cases

### False Negatives (Missed Unused Tables)

The script searches for specific SQL keywords. It might miss:
- Dynamic table names: `f"FROM {table_name}"` (rare in practice)
- Table names in comments only
- Tables accessed via ORM that abstracts SQL

**Mitigation**: Our codebase uses raw SQL exclusively, so this isn't a concern.

### False Positives (Incorrectly Flagged as Unused)

Could happen if:
- Table is only accessed in migration scripts (not in src/)
- Table is accessed via external tools

**Mitigation**:
- Keep migration logic in `src/`
- Add comment explaining why table appears unused
- Document external access in schema comments

### Tables Used Only in Tests

If a table is ONLY used in tests (not in src/), it will be flagged as unused.

**Decision**: This is intentional. Tables should be used in application code, not just tests. If a table is only for testing, it should be created in test fixtures, not in the main schema.

## Related Work

This addresses one of the gaps identified in `docs/EMBEDDING_CACHE_AUDIT.md`:

> **What Could Have Caught This: SQL Static Analysis Tool**
>
> Hypothetical tool that analyzes SQL usage:
> ```bash
> $ sql-analyse --schema schema.py --code src/
>
> ❌ UNUSED TABLE: embeddings
>    Defined: src/geistfabrik/schema.py:48
>    Never queried in: src/**/*.py
> ```

We've now implemented exactly this tool!

## Future Enhancements

### 1. Coverage Metrics
Track what percentage of schema is actively used:
```
Schema coverage: 7/7 tables used (100%)
Index coverage: 10/11 indexes used (90.9%)
```

### 2. Usage Frequency
Count how many times each table is accessed:
```
notes: 11 references (heavily used)
tags: 2 references (lightly used)
```

Could warn if tables are defined but rarely used.

### 3. Index Usage Analysis
Check if indexes are actually used in queries:
```
CREATE INDEX idx_notes_title ON notes(title);
⚠️  No queries use this index (consider removing)
```

### 4. Foreign Key Validation
Verify foreign key relationships are actually queried:
```
FOREIGN KEY (note_path) REFERENCES notes(path)
✅ Used in JOIN query: vault.py:245
```

### 5. Migration Helper
Generate migration script when tables are removed:
```sql
-- Migration: v2 → v3
-- Remove unused tables

DROP TABLE IF EXISTS suggestions;
DROP TABLE IF EXISTS suggestion_notes;
```

## Performance Impact

**Script runtime**: <100ms for our codebase
**CI overhead**: Negligible (~1 second added to build)
**Pre-commit overhead**: <1 second per commit

## Testing

The script itself is tested by:
1. Running it against current schema (should pass)
2. Type checking: `mypy --strict` passes
3. Pre-commit integration: Runs successfully

To test the detection logic:
```bash
# 1. Add a dummy unused table to schema.py
CREATE TABLE IF NOT EXISTS dummy_unused_table (id INTEGER PRIMARY KEY);

# 2. Run detection script
python scripts/detect_unused_tables.py

# Should output:
# ❌ dummy_unused_table: UNUSED (0 references)

# 3. Try to commit (should fail)
git add src/geistfabrik/schema.py
git commit -m "Test"
# Hook will block the commit!
```

## Lessons Learned

1. **Automated enforcement > documentation**: Docs can be ignored, pre-commit hooks can't
2. **Simple tools are sufficient**: Regex + grep solves 90% of the problem
3. **Early detection is key**: Catch unused tables before they're deployed
4. **Fail fast**: Make it impossible to commit bad schema rather than relying on code review

## Migration Notes

For existing databases with `suggestions` and `suggestion_notes` tables:

```sql
-- These tables were never used, so dropping them is safe
-- No data loss because no data was ever inserted

DROP TABLE IF EXISTS suggestion_notes;
DROP TABLE IF EXISTS suggestions;

-- Update schema version
PRAGMA user_version = 3;
```

This migration is safe because:
- Tables never had any data (never inserted to)
- No code references them (never queried)
- No foreign keys from other tables point to them
