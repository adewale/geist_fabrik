# Test Suite Improvements & Recommendations

**Purpose**: Make tests simpler, faster, more resilient, and more comprehensive
**Current State**: 153/153 unit tests passing, ~3.5s runtime
**Goal**: Expand coverage without sacrificing speed

---

## Table of Contents

1. [Acceptance Criteria Tool Improvements](#acceptance-criteria-tool-improvements)
2. [Test Architecture Improvements](#test-architecture-improvements)
3. [Shared Stub Library](#shared-stub-library)
4. [Performance Optimizations](#performance-optimizations)
5. [Resilience Improvements](#resilience-improvements)
6. [Implementation Plan](#implementation-plan)

---

## Acceptance Criteria Tool Improvements

### Current Issues

**Problem**: `check_phase_completion.py` runs 100+ shell commands, takes 6+ minutes, hangs CI

**Root Causes**:
1. Runs **every** command in acceptance_criteria.md (some are expensive)
2. No caching of results
3. Sequential execution (not parallel)
4. Includes steps that trigger external downloads

### Recommendations

#### Option 1: Simplify to Python Function (RECOMMENDED)

Replace shell command execution with direct Python function calls:

```python
# ❌ CURRENT: Shell commands
"uv run pytest tests/unit/test_vault.py -v"  # Slow, brittle

# ✅ BETTER: Direct function calls
def check_vault_tests():
    """Check vault tests pass."""
    return pytest.main([
        "tests/unit/test_vault.py",
        "--collect-only"  # Just verify they exist
    ]) == 0
```

**Benefits**:
- 10x faster (no subprocess overhead)
- Easier to debug
- More reliable
- Can cache results

#### Option 2: Metadata-Based Verification

Instead of running tests, check that required artifacts exist:

```python
def check_phase_1():
    """Verify Phase 1 artifacts exist."""
    required_files = [
        "src/geistfabrik/vault.py",
        "src/geistfabrik/markdown_parser.py",
        "tests/unit/test_vault.py",
    ]

    required_tests = [
        "test_vault_init",
        "test_sync_no_changes",
        "test_parse_links",
    ]

    # Check files exist
    for f in required_files:
        if not Path(f).exists():
            return False

    # Check tests exist (not run them)
    test_names = collect_test_names("tests/unit/test_vault.py")
    for t in required_tests:
        if t not in test_names:
            return False

    return True
```

**Benefits**:
- Near-instant (<100ms)
- No test execution overhead
- Simple verification

#### Option 3: Use pytest Markers

Tag tests with phase markers, query pytest for completion:

```python
# In test files
@pytest.mark.phase_1
def test_vault_init():
    ...

# In checker
def check_phase_1():
    # Collect all phase_1 tests
    items = pytest.main([
        "-m", "phase_1",
        "--collect-only",
        "-q"
    ])
    # If >20 tests, phase is complete
    return len(items) >= 20
```

**Benefits**:
- Self-documenting (tests carry their own metadata)
- Easy to query
- Fast (collect-only mode)

### Recommended Approach: Hybrid

1. **Quick check**: Verify artifacts exist (metadata-based)
2. **Periodic deep check**: Run full test suite (manual/scheduled)
3. **CI check**: Just run `pytest -m "not slow"` (existing)

**New Tool**: `scripts/verify_phase.py`

```python
#!/usr/bin/env python3
"""Quick phase verification (metadata-based)."""

def verify_phase_0():
    return (
        Path("src/geistfabrik").is_dir() and
        Path("pyproject.toml").exists() and
        Path("pytest.ini").exists()
    )

def verify_phase_1():
    test_count = count_tests("tests/unit/test_vault.py")
    return test_count >= 20  # Expected minimum

def main():
    phases = [
        (0, "Scaffolding", verify_phase_0()),
        (1, "Vault Parsing", verify_phase_1()),
        # ...
    ]

    for num, name, passed in phases:
        status = "✅" if passed else "❌"
        print(f"{status} Phase {num}: {name}")
```

**Runtime**: <1 second (compared to 6+ minutes)

---

## Test Architecture Improvements

### Current State

- 153 unit tests (~2,300 lines)
- 4 integration tests (~582 lines)
- Good separation (unit vs integration)
- SentenceTransformerStub works well

### Issues

1. **Duplicate Fixtures**: `sample_notes` defined in multiple places
2. **No Shared Test Data**: Each test creates its own data
3. **Limited Parametrization**: Could test more scenarios with same code
4. **No Property-Based Testing**: Edge cases might be missed

### Recommendations

#### 1. Create Shared Test Fixtures Library

**New File**: `tests/fixtures.py`

```python
"""Shared test fixtures for all tests."""

# Standard sample notes (reused everywhere)
SAMPLE_NOTES = [
    Note(
        path="ai.md",
        title="AI Note",
        content="Machine learning and artificial intelligence.",
        links=[],
        tags=["ai"],
        created=datetime(2023, 1, 1),
        modified=datetime(2023, 1, 1),
    ),
    Note(
        path="cooking.md",
        title="Cooking Note",
        content="Recipes and food preparation techniques.",
        links=[],
        tags=["cooking"],
        created=datetime(2023, 2, 1),
        modified=datetime(2023, 2, 1),
    ),
    # ... more standard fixtures
]

# Specialized fixtures
LONG_NOTE = Note(...)        # For testing large content
EMPTY_NOTE = Note(...)       # For testing edge cases
LINKED_NOTES = [...]         # Notes with complex link graph
```

**Usage**:
```python
# In any test file
from tests.fixtures import SAMPLE_NOTES, LONG_NOTE

def test_embedding(mock_computer):
    note = SAMPLE_NOTES[0]  # Consistent across all tests
    embedding = mock_computer.compute_semantic(note.content)
    assert embedding.shape == (384,)
```

**Benefits**:
- No duplication
- Consistent test data
- Easy to add new standard fixtures
- Tests are more readable

#### 2. Parameterized Tests

Use `@pytest.mark.parametrize` to test multiple scenarios:

```python
# ❌ CURRENT: Multiple similar tests
def test_parse_link_basic():
    assert parse_links("[[note]]") == ["note"]

def test_parse_link_with_heading():
    assert parse_links("[[note#heading]]") == ["note"]

def test_parse_link_with_alias():
    assert parse_links("[[note|alias]]") == ["note"]

# ✅ BETTER: Single parameterized test
@pytest.mark.parametrize("text,expected", [
    ("[[note]]", ["note"]),
    ("[[note#heading]]", ["note"]),
    ("[[note|alias]]", ["note"]),
    ("[[note1]] and [[note2]]", ["note1", "note2"]),
    ("No links here", []),
])
def test_parse_links(text, expected):
    assert parse_links(text) == expected
```

**Benefits**:
- Tests more scenarios with less code
- Easy to add new cases
- Clear what's being tested

#### 3. Property-Based Testing

Use `hypothesis` library for generative testing:

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=1000))
def test_embedding_always_normalized(text):
    """Any text should produce normalized embedding."""
    embedding = compute_semantic(text)
    norm = np.linalg.norm(embedding)
    assert norm == pytest.approx(1.0, abs=1e-6)

@given(st.lists(st.text(), min_size=1, max_size=100))
def test_batch_equals_individual(texts):
    """Batch encoding should match individual encoding."""
    batch_embeddings = model.encode(texts)
    for i, text in enumerate(texts):
        individual = model.encode(text)
        assert np.allclose(batch_embeddings[i], individual)
```

**Benefits**:
- Finds edge cases you wouldn't think of
- Tests properties, not specific examples
- Reveals assumptions in code

---

## Shared Stub Library

### Current State

- `SentenceTransformerStub` in `tests/conftest.py`
- Good, but could be more reusable

### Recommendations

#### 1. Extract Stubs to Dedicated Module

**New File**: `tests/stubs.py`

```python
"""Shared stubs for testing."""

class SentenceTransformerStub:
    """Deterministic stub for SentenceTransformer."""
    # Current implementation (keep as-is)
    ...

class VaultStub:
    """Stub Vault with pre-populated notes."""
    def __init__(self, notes: List[Note] = None):
        self.notes = notes or SAMPLE_NOTES
        self._db = None

    def all_notes(self):
        return self.notes

    def get_note(self, path):
        return next((n for n in self.notes if n.path == path), None)

    def sync(self):
        pass  # No-op for stub

class SessionStub:
    """Stub Session with pre-computed embeddings."""
    def __init__(self, embeddings: Dict[str, np.ndarray]):
        self._embeddings = embeddings

    def get_embedding(self, path):
        return self._embeddings.get(path)

    def get_all_embeddings(self):
        return self._embeddings

class DatabaseStub:
    """In-memory database stub with preset data."""
    def __init__(self):
        self.data = {}  # Simple dict instead of SQLite

    def execute(self, query, params=()):
        # Simplified query handling for common patterns
        ...

    def commit(self):
        pass
```

**Benefits**:
- Reusable across test files
- Easier to maintain (one place to update)
- Can create different "flavors" of stubs

#### 2. Stub Factories

Create factory functions for common stub configurations:

```python
def create_stub_vault(note_count=3, with_links=True, with_tags=True):
    """Create a stub vault with configurable complexity."""
    notes = []
    for i in range(note_count):
        note = Note(
            path=f"note{i}.md",
            title=f"Note {i}",
            content=f"Content {i}",
            links=[f"note{(i+1) % note_count}.md"] if with_links else [],
            tags=[f"tag{i}"] if with_tags else [],
            created=datetime(2023, 1, i+1),
            modified=datetime(2023, 1, i+1),
        )
        notes.append(note)
    return VaultStub(notes)

def create_stub_session(vault, date="2025-01-15"):
    """Create stub session with pre-computed embeddings."""
    embeddings = {}
    for note in vault.all_notes():
        # Use deterministic stub embedding
        embeddings[note.path] = hash_to_embedding(note.content)
    return SessionStub(embeddings)
```

**Usage**:
```python
def test_neighbors():
    vault = create_stub_vault(note_count=10, with_links=True)
    session = create_stub_session(vault)

    neighbours = session.get_neighbors("note0.md", k=3)
    assert len(neighbours) == 3
```

**Benefits**:
- Declarative test setup
- Easy to vary scenarios
- Reduces boilerplate

#### 3. Stub Presets

Common configurations as named presets:

```python
# Preset: Small vault for quick tests
SMALL_VAULT = create_stub_vault(note_count=3)

# Preset: Large vault for performance tests
LARGE_VAULT = create_stub_vault(note_count=1000)

# Preset: Complex link graph
GRAPH_VAULT = create_stub_vault_with_graph({
    "a": ["b", "c"],
    "b": ["c", "d"],
    "c": ["d"],
    "d": [],
})

# Preset: Temporal test data (notes spanning multiple years)
TEMPORAL_VAULT = create_temporal_vault(
    start_date="2020-01-01",
    end_date="2025-01-01",
    note_count=100
)
```

**Usage**:
```python
def test_graph_operations():
    vault = GRAPH_VAULT
    orphans = vault.get_orphans()
    assert len(orphans) == 0  # No orphans in our graph

def test_temporal_clustering():
    vault = TEMPORAL_VAULT
    clusters = vault.get_temporal_clusters()
    assert len(clusters) >= 5  # At least 5 years of data
```

---

## Performance Optimizations

### 1. Parallel Test Execution

**Current**: Tests run sequentially
**Improvement**: Run in parallel with `pytest-xdist`

```bash
# Run tests on 4 cores
pytest -n 4

# Runtime: 3.5s → ~1s (with 4 cores)
```

**Configuration**:
```ini
# pytest.ini
[pytest]
addopts = -n auto  # Automatically detect CPU count
```

### 2. Fixture Scope Optimization

**Analysis**: Which fixtures can be session-scoped vs function-scoped?

```python
# ✅ Session-scoped (created once, reused)
@pytest.fixture(scope="session")
def sample_notes():
    """Immutable sample data, safe to share."""
    return SAMPLE_NOTES

# ✅ Function-scoped (fresh each test)
@pytest.fixture
def test_db():
    """Mutable database, need fresh copy."""
    db = init_db()
    yield db
    db.close()
```

**Guideline**:
- Session scope: Immutable, read-only data
- Function scope: Mutable, stateful resources

### 3. Lazy Imports

**Optimization**: Import heavy modules only when needed

```python
# ❌ CURRENT: Import at module level
from sentence_transformers import SentenceTransformer

def rarely_used_function():
    model = SentenceTransformer(...)

# ✅ BETTER: Import when used
def rarely_used_function():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(...)
```

**Benefit**: Faster test collection (~0.5s saved)

### 4. Test Markers for Selective Running

**Add More Markers**:
```python
@pytest.mark.fast     # <1s
@pytest.mark.medium   # 1-5s
@pytest.mark.slow     # >5s

@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.e2e

@pytest.mark.embeddings
@pytest.mark.vault
@pytest.mark.geist
```

**Usage**:
```bash
# Only fast tests
pytest -m fast

# Only embedding tests
pytest -m embeddings

# Fast OR medium (but not slow)
pytest -m "fast or medium"
```

---

## Resilience Improvements

### 1. Retry Flaky Tests

**Use**: `pytest-rerunfailures`

```python
# Retry up to 3 times if fails
@pytest.mark.flaky(reruns=3)
def test_concurrent_access():
    # Test that might fail due to timing
    ...
```

### 2. Explicit Timeouts

**Already good**, but be more granular:

```python
@pytest.mark.timeout(1)  # Fast tests: 1s
def test_parse_links():
    ...

@pytest.mark.timeout(5)  # Medium tests: 5s
def test_vault_sync():
    ...

@pytest.mark.timeout(60)  # Slow tests: 60s
def test_embedding_computation():
    ...
```

### 3. Resource Cleanup Verification

**Add**: Verify fixtures clean up properly

```python
@pytest.fixture
def test_db():
    db = init_db()
    yield db
    db.close()

    # Verify cleanup
    assert not db.execute  # Can't execute on closed DB

# Or use finalizer
@pytest.fixture
def test_db(request):
    db = init_db()

    def cleanup():
        db.close()
        assert not hasattr(db, '_connection')  # Verify closed

    request.addfinalizer(cleanup)
    return db
```

### 4. Snapshot Testing

**Add**: `pytest-snapshot` for regression testing

```python
def test_geist_output(snapshot):
    """Verify geist output doesn't change unexpectedly."""
    vault = create_stub_vault()
    suggestions = generate_suggestions(vault)

    # Compare to saved snapshot
    snapshot.assert_match(suggestions)

    # If output changes, snapshot test fails
    # Review change, update snapshot if intentional
```

**Benefits**:
- Catches unintended changes
- Easy to review diffs
- Good for complex outputs (JSON, text)

---

## Implementation Plan

### Phase 1: Quick Wins (1-2 hours)

1. ✅ Create `tests/fixtures.py` with shared data
2. ✅ Extract stubs to `tests/stubs.py`
3. ✅ Remove duplicate `sample_notes` fixtures
4. ✅ Add more test markers (fast/medium/slow)

### Phase 2: Tool Improvements (2-3 hours)

1. ✅ Create `scripts/verify_phase.py` (metadata-based)
2. ✅ Add pytest markers for phases
3. ✅ Update CI to use new tool
4. ✅ Remove `check_phase_completion.py` from CI

### Phase 3: Test Enhancements (3-4 hours)

1. ✅ Add parameterized tests for parsers
2. ✅ Add property-based tests (hypothesis)
3. ✅ Create stub factories
4. ✅ Add more test presets

### Phase 4: Performance (1 hour)

1. ✅ Enable `pytest-xdist` for parallel execution
2. ✅ Optimize fixture scopes
3. ✅ Add lazy imports where appropriate

### Phase 5: Resilience (1-2 hours)

1. ✅ Add snapshot testing for geist outputs
2. ✅ Add resource cleanup verification
3. ✅ Review and add missing edge cases

---

## Expected Outcomes

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Unit test runtime | 3.5s | ~1s | 3.5x faster (with parallelization) |
| Test LOC (lines of code) | ~2,300 | ~1,800 | 22% reduction (less duplication) |
| Test scenarios covered | ~150 | ~300 | 2x coverage (parametrization) |
| Phase verification time | 6+ min | <1s | 360x faster |
| Edge cases found | Manual | Automated | Property-based testing |
| Maintenance burden | Medium | Low | Shared fixtures/stubs |

---

## Checklist

### Core Infrastructure
- [ ] Create `tests/fixtures.py` with shared test data
- [ ] Create `tests/stubs.py` with reusable stubs
- [ ] Create stub factory functions
- [ ] Create test data presets
- [ ] Remove duplicate fixtures from conftest files

### Tool Improvements
- [ ] Create `scripts/verify_phase.py` (metadata-based checker)
- [ ] Add pytest phase markers to tests
- [ ] Update CI to use new verification tool
- [ ] Remove `check_phase_completion.py` from CI workflow
- [ ] Add --fast, --medium, --slow flags for selective running

### Test Enhancements
- [ ] Convert similar tests to parameterized tests
- [ ] Add hypothesis for property-based testing
- [ ] Add snapshot testing for geist outputs
- [ ] Add more edge case tests (using hypothesis)

### Performance
- [ ] Enable pytest-xdist (parallel execution)
- [ ] Optimize fixture scopes (session vs function)
- [ ] Add lazy imports for heavy modules
- [ ] Profile test suite to identify slow tests

### Resilience
- [ ] Add explicit timeouts to all test categories
- [ ] Add resource cleanup verification
- [ ] Add retry for flaky tests (if any)
- [ ] Verify all fixtures have proper cleanup

---

## Next Steps

1. **Immediate**: Remove `check_phase_completion.py` from CI (prevents hangs)
2. **Short-term**: Create shared fixtures and stubs
3. **Medium-term**: Add parametrization and property-based tests
4. **Long-term**: Enable parallel execution, add snapshot testing

---

**Document Version**: 1.0
**Last Updated**: 2025-10-21
**Status**: Recommendations (Not Yet Implemented)
