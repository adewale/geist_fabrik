# Embedding Cache Audit: How We Missed Dead Schema

## The Issue

The `embeddings` table existed in the database schema since the beginning but was **never used**:
- Schema defined in `src/geistfabrik/schema.py` (line 48-54)
- Never queried with `SELECT`
- Never populated with `INSERT`
- Every session recomputed ALL semantic embeddings from scratch
- **Performance impact**: ~2-5 seconds of wasted computation per session for unchanged notes

## How We Missed It

### 1. **Schema-Code Disconnect**
The schema was defined separately from the code that uses it:
- `schema.py` defined the table structure
- `embeddings.py` implemented the logic
- No enforcement that schema tables must be used

### 2. **No Dead Code Detection for SQL**
Standard tools don't detect unused database tables:
- Ruff/mypy only check Python code
- No SQL static analysis in our toolchain
- Database tables can exist forever without queries

### 3. **Spec-Implementation Gap**
The specification mentioned persistent embeddings, but:
- Implementation took a shortcut (session-only embeddings)
- No verification that spec requirements were met
- No performance benchmarks to catch inefficiency

### 4. **Missing Performance Tests**
We had functional tests but not performance tests:
- Tests verified correctness (embeddings work)
- No tests for efficiency (are we recomputing unnecessarily?)
- No multi-session tests to catch repeated computation

### 5. **No Usage Metrics**
We didn't instrument the code to track:
- How many embeddings computed vs cached
- Time spent in embedding computation
- Database table access patterns

## What Could Have Caught This

### Immediate (Automated Tools)

#### 1. **SQL Static Analysis Tool**
```bash
# Hypothetical tool that analyzes SQL usage
$ sql-analyze --schema schema.py --code src/

❌ UNUSED TABLE: embeddings
   Defined: src/geistfabrik/schema.py:48
   Never queried in: src/**/*.py

   Suggestion: Remove table or add queries
```

**Implementation:**
- Parse schema to extract table definitions
- Grep codebase for `SELECT/INSERT/UPDATE/DELETE FROM <table>`
- Report tables with no references
- Similar to "unused import" detection

#### 2. **Database Query Coverage Tool**
Similar to code coverage but for SQL:
```python
# Instrument database connection
from db_coverage import CoverageConnection

db = CoverageConnection("vault.db")
# Run all tests
db.report()
# Output: "Table 'embeddings' has 0% query coverage (0 reads, 0 writes)"
```

**Implementation:**
- Wrapper around sqlite3.Connection
- Tracks which tables are accessed
- Reports unused tables after test suite

#### 3. **Performance Regression Tests**
```python
def test_embedding_cache_performance():
    """Verify embeddings are cached across sessions."""
    session1 = Session(date1, db)
    session1.compute_embeddings(notes)

    # Second session with unchanged notes should be fast
    session2 = Session(date2, db)

    start = time.time()
    session2.compute_embeddings(notes)
    duration = time.time() - start

    # Should be < 1s if cached (not 5s to recompute)
    assert duration < 1.0, f"Embeddings not cached! Took {duration}s"
```

**Catches:**
- Repeated expensive computations
- Missing cache implementations
- Performance degradation

### Intermediate (Code Review Practices)

#### 4. **Schema-Code Mapping Document**
Maintain a mapping between schema tables and their usage:

```markdown
# Schema Usage Map

| Table | Purpose | Primary Writer | Primary Reader |
|-------|---------|---------------|---------------|
| notes | Store vault notes | vault.py:sync() | vault.py:get_note() |
| embeddings | Cache semantic embeddings | ❌ **NONE** | ❌ **NONE** |
| session_embeddings | Temporal embeddings | embeddings.py:compute_embeddings() | embeddings.py:get_embedding() |

⚠️  WARNING: `embeddings` table has no users!
```

**Process:**
- Update document when adding schema changes
- Require code references for each table
- Review in PR to catch disconnects

#### 5. **Specification Checklist**
For each spec requirement, track implementation status:

```markdown
# Phase Implementation Checklist

## Temporal Embeddings (Phase X)

- [x] Create sessions table
- [x] Create session_embeddings table
- [x] Compute temporal embeddings per session
- [ ] **Cache semantic embeddings for unchanged notes** ❌ MISSING
- [x] Support multiple sessions
```

**Process:**
- Extract requirements from specs
- Create checklist during implementation
- Verify each item has corresponding code
- Catches spec-implementation gaps

### Advanced (Profiling & Instrumentation)

#### 6. **Performance Profiling in Tests**
```python
@pytest.mark.benchmark
def test_multi_session_performance(benchmark_profile):
    """Profile embedding computation across sessions."""
    with benchmark_profile("embedding_computation"):
        # Run multiple sessions
        for i in range(5):
            session = Session(dates[i], db)
            session.compute_embeddings(notes)

    # Analyze profile
    stats = benchmark_profile.stats
    if stats["sentence_transformer.encode"] > expected_calls:
        raise AssertionError(
            f"Expected {expected_calls} encoding calls, got {stats['sentence_transformer.encode']}"
        )
```

**Catches:**
- Redundant computations through call counts
- Performance bottlenecks
- Missing caching through repeated expensive calls

#### 7. **Database Access Instrumentation**
```python
class InstrumentedConnection:
    def __init__(self, conn):
        self.conn = conn
        self.table_access = defaultdict(lambda: {"reads": 0, "writes": 0})

    def execute(self, query, *args):
        # Parse query to extract table name
        table = self._extract_table(query)
        if "SELECT" in query:
            self.table_access[table]["reads"] += 1
        elif "INSERT" in query or "UPDATE" in query:
            self.table_access[table]["writes"] += 1
        return self.conn.execute(query, *args)
```

**Usage:**
- Run in development/CI
- Log warnings for zero-access tables
- Suggest schema cleanup

### Long-term (Architecture Improvements)

#### 8. **Schema-as-Code with ORM**
Use SQLAlchemy or similar to enforce schema-code connection:
```python
class Embedding(Base):
    __tablename__ = "embeddings"
    note_path = Column(Text, primary_key=True)
    embedding = Column(LargeBinary)

# If table is defined but never queried:
# → Linter warns "Model Embedding defined but never queried"
```

**Benefits:**
- Tables must be referenced in Python code
- Easier to detect unused tables
- Type safety for queries

#### 9. **Specification-Driven Development**
Generate tests from specifications:
```yaml
# spec.yaml
performance_requirements:
  - requirement: "Semantic embeddings cached for unchanged notes"
    test: "test_semantic_embedding_cache"
    metric: "cache_hit_rate > 0.8 for unchanged notes"
```

**Process:**
- Automatically generate test stubs from specs
- CI fails if requirements lack tests
- Ensures spec-implementation alignment

## Implementation of Fixes

### The Actual Fix (Implemented)
Modified `embeddings.py` to:
1. Check `embeddings` table for cached semantic embeddings (by content hash)
2. Only compute embeddings for notes with changed content
3. Cache newly computed embeddings
4. Log cache statistics (`X/Y cached, Z computed`)

**Expected Impact:**
- First session: 0% cache hit (cold start)
- Subsequent sessions with 90% unchanged notes: 90% cache hit
- Time savings: ~2-4 seconds per session
- Over 100 sessions: ~3-7 minutes saved

### Recommended Immediate Actions

1. **Add SQL Usage Lint Rule** (2 hours)
   - Script to grep for table names in schema
   - Check if table appears in SELECT/INSERT statements
   - Add to pre-commit hooks

2. **Add Performance Regression Test** (1 hour)
   - Test that measures multi-session embedding time
   - Fails if second session takes >50% of first session time
   - Catches future cache regressions

3. **Create Schema Usage Map** (30 minutes)
   - Document in README or docs/ARCHITECTURE.md
   - Table showing each schema table and its purpose
   - Update with every schema change

### Recommended Long-term Actions

1. **Integrate py-sqlanalyze** or similar (4 hours)
   - Automated detection of unused tables
   - Part of CI pipeline
   - Warns on PRs that add unused schema

2. **Add Database Query Coverage** (8 hours)
   - Wrapper around sqlite3.Connection
   - Tracks table access during tests
   - Reports coverage like pytest-cov

3. **Performance Benchmark Suite** (16 hours)
   - Dedicated performance tests
   - Track metrics over time (cache hit rates, computation time)
   - Alert on regressions

## Lessons Learned

### What Worked
- ✅ Functional tests caught bugs
- ✅ Type checking prevented type errors
- ✅ Linting enforced code style

### What Didn't Work
- ❌ No detection of unused schema elements
- ❌ No performance testing beyond "it works"
- ❌ No instrumentation to reveal inefficiency
- ❌ Spec requirements not verified in tests

### Key Insight
**Standard software engineering tools focus on Python code correctness, not SQL schema usage or performance efficiency.**

We need:
- SQL-aware static analysis
- Performance-aware testing
- Specification-to-test mapping
- Runtime instrumentation

## Conclusion

This wasn't a bug in the traditional sense - the code worked correctly. It was an **efficiency gap** between the intended design (caching) and actual implementation (no caching).

Such gaps require:
1. **Schema-code awareness**: Tools that understand SQL table usage
2. **Performance testing**: Tests that verify efficiency, not just correctness
3. **Specification tracking**: Ensure design intentions are implemented
4. **Runtime instrumentation**: Visibility into what the code actually does

The fix is straightforward (50 lines), but catching it earlier would have required tooling we don't typically have for database-backed applications.

## Appendix: Quick-Win Audit Scripts

### Unused Table Detector
```bash
#!/bin/bash
# detect_unused_tables.sh

# Extract table names from schema
TABLES=$(grep "CREATE TABLE" src/geistfabrik/schema.py | sed 's/.*TABLE.*\s\+\(\w\+\).*/\1/')

for table in $TABLES; do
    # Check if table appears in SELECT/INSERT/UPDATE/DELETE
    count=$(grep -r "FROM $table\|INTO $table\|UPDATE $table" src/ --include="*.py" | wc -l)

    if [ $count -eq 0 ]; then
        echo "⚠️  UNUSED TABLE: $table"
    fi
done
```

### Embedding Performance Test
```python
# tests/performance/test_embedding_cache.py
def test_embedding_cache_effectiveness(sample_notes, test_db):
    """Verify semantic embeddings are cached across sessions."""
    from datetime import datetime, timedelta
    import time

    date1 = datetime(2025, 1, 1)
    date2 = datetime(2025, 1, 2)

    # First session - cold cache
    session1 = Session(date1, test_db)
    start = time.time()
    session1.compute_embeddings(sample_notes)
    first_duration = time.time() - start

    # Second session - should use cache (notes unchanged)
    session2 = Session(date2, test_db)
    start = time.time()
    session2.compute_embeddings(sample_notes)
    second_duration = time.time() - start

    # Second session should be much faster (semantic embeddings cached)
    # Only temporal features recomputed
    speedup = first_duration / second_duration

    assert speedup > 2.0, (
        f"Expected >2x speedup with cache, got {speedup:.2f}x "
        f"(first: {first_duration:.2f}s, second: {second_duration:.2f}s)"
    )
```

Run with: `pytest tests/performance/ -v`
