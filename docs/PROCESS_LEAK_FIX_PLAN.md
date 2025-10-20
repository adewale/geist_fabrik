# Process Leak Fix Plan

## Executive Summary

**Problem**: Running `pytest -v` spawns 300+ Python processes that never die, consuming 14GB+ RAM and killing the machine.

**Root Cause**: Commit ec00fb8 (Oct 20, 2025) optimized embedding computation with batch processing. This 15-20x speed improvement for production had an unintended side effect: aggressive parallelization in tests without resource limits.

**Immediate Fixes** (do both for 104x reduction):
1. **Shared session fixtures** - Architectural fix: reuse embeddings instead of recomputing 13 times
2. **Thread/process limits** - Safety net: prevent unlimited spawning even in future tests

**Expected Results**:
- Shared sessions: 13 embedding computations → 1 (13x reduction)
- Thread limits: 8 workers per operation → 1 (8x reduction)
- Combined: 104 processes → 1 process (104x reduction)
- Test suite speed: 30 seconds → 5 seconds (6x faster)

**Timeline**: Priorities 0 & 0.5 (immediate, 20 minutes total) provide architectural fix + safety net. Priorities 1-3 (same session) add cleanup and further optimization. Priorities 4-6 (later) refactor signal handling and test fixtures.

---

## Problem Summary

Running the test suite spawns multiple Python processes that never die, eventually consuming all system resources and killing the machine. The issue is caused by interaction between:

1. **Recent batch encoding optimization** (commit ec00fb8) - aggressive parallelization
2. **No thread/process limits** - unlimited spawning
3. **No cleanup between tests** - resource accumulation
4. **Signal-based timeout mechanism** - causes processes to hang
5. **152 tests** (38 new) - multiple trigger points

## Root Causes

### 0. Recent Performance Optimization Made Problem Worse (Commit ec00fb8)

**Location**: `src/geistfabrik/embeddings.py:168-217` (commit ec00fb8f6ea84992d8e2e279fb80c2a88a9b4220)

**What changed**: Optimization 3 changed from computing embeddings one-by-one to **batch processing all notes at once**:

```python
# BEFORE: One call per note
for note in notes:
    embedding = self.computer.model.encode(note.content)

# AFTER: Single batch call for all notes
texts = [note.content for note in notes]
semantic_embeddings = self.computer.model.encode(
    texts, convert_to_numpy=True, show_progress_bar=False
)
```

**Why this matters**:
- Batch encoding triggers **more aggressive parallelization** in sentence-transformers
- Each batch operation spawns 2-8 worker processes (vs 0-2 for single encoding)
- Commit message literally says "Leverages GPU parallelization"
- Combined with 38 new tests (114→152), this multiplies process spawning exponentially

**Timeline**: This optimization was added on Oct 20, 2025 - likely when the problem started.

### 1. SentenceTransformer Model Spawning Worker Processes

**Location**: `src/geistfabrik/embeddings.py:38` and `embeddings.py:188-190`

The `sentence-transformers` library spawns worker processes for encoding operations:

```python
# Line 38 - Model initialization
self._model = SentenceTransformer(self.model_name)

# Lines 188-190 - Batch encoding that spawns processes
semantic_embeddings = self.computer.model.encode(
    texts, convert_to_numpy=True, show_progress_bar=False
)
```

**Issue**: Each test that creates a `Session` object loads the SentenceTransformer model. The model's internal PyTorch/Transformers implementation spawns worker processes that aren't properly cleaned up when tests finish.

### 2. No Model Cleanup Between Tests

**Location**: `src/geistfabrik/embeddings.py:22-39`

The `EmbeddingComputer` uses lazy loading but has no cleanup mechanism:

```python
def __init__(self, model_name: str = MODEL_NAME):
    self.model_name = model_name
    self._model: Optional[SentenceTransformer] = None  # Lazy loaded

@property
def model(self) -> SentenceTransformer:
    if self._model is None:
        self._model = SentenceTransformer(self.model_name)
    return self._model
```

**Issue**: No `__del__` method or context manager to clean up the model and its worker processes when the EmbeddingComputer is destroyed.

### 3. Signal Handling Interference

**Location**: `src/geistfabrik/geist_executor.py:133-168`

The timeout mechanism uses Unix signals which are process-wide:

```python
# Set up timeout (Unix-only)
if sys.platform != "win32":
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(self.timeout)
```

**Issue**: SIGALRM signal handling can interfere with sentence-transformers worker processes, potentially causing them to hang or not terminate properly. Signals are process-wide and not thread-safe with multiprocessing.

### 4. Dynamic Module Pollution

**Location**: `src/geistfabrik/geist_executor.py:98`

Test geists are loaded directly into `sys.modules`:

```python
sys.modules[geist_id] = module
```

**Issue**: Test geists (including those with `time.sleep(10)` and `while True: pass`) remain in `sys.modules` and are never cleaned up, potentially keeping references alive.

### 5. Multiple Tests Creating Sessions

The following tests all create `Session` objects which trigger model loading:

- `tests/unit/test_embeddings.py`: 13 tests that create Sessions (lines 102-444)
- `tests/unit/test_geist_executor.py`: Uses VaultContext which may trigger embeddings
- `tests/integration/test_kepano_vault.py`: Multiple tests with real vault data

**Issue**: Each test potentially spawns new worker processes without cleaning up previous ones.

### 6. No Thread/Process Limiting Environment Variables

**Location**: System environment (not set anywhere in code or CI)

**Missing configuration**:
```bash
# All of these are currently UNSET:
OMP_NUM_THREADS=1         # OpenMP threads
MKL_NUM_THREADS=1         # Intel MKL threads
NUMEXPR_NUM_THREADS=1     # NumExpr threads
OPENBLAS_NUM_THREADS=1    # OpenBLAS threads
VECLIB_MAXIMUM_THREADS=1  # macOS Accelerate threads
TOKENIZERS_PARALLELISM=false  # HuggingFace tokenizers
```

**Issue**: Without these limits, each of the following can spawn unlimited threads/processes:
- PyTorch BLAS operations (used by sentence-transformers)
- NumPy linear algebra operations (`np.linalg.norm` in `embeddings.py:278-279`)
- HuggingFace tokenizers (used internally by SentenceTransformer)
- OpenBLAS/MKL matrix operations

On a system with N cores, each uncontrolled library can spawn N threads × M tests = catastrophic multiplication.

### 7. Database Connections Without Proper Cleanup

**Location**: `tests/unit/test_embeddings.py` and other test files

**Pattern found**:
```python
def test_something():
    db = init_db()
    # ... test code ...
    db.close()  # ⚠️ Never reached if test fails
```

**Issue**:
- 9 tests in `test_embeddings.py` manually create and close database connections
- If a test fails or raises an exception before `db.close()`, connection stays open
- SQLite connections can hold file locks and resources
- Not the primary cause but contributes to resource exhaustion

**Better pattern** (not currently used):
```python
@pytest.fixture
def test_db():
    db = init_db()
    yield db
    db.close()  # Always runs, even on test failure
```

### 8. Python 3.14 Dev Version Compatibility

**Location**: Local development environment

**Current state**: Running Python 3.14.0 (unreleased development version)
- Project specifies: `requires-python = ">=3.11"`
- CI tests on: Python 3.11 and 3.12
- Local machine: Python 3.14.0 dev build

**Issue**:
- sentence-transformers and PyTorch may have incomplete support for Python 3.14
- Multiprocessing behavior changed in Python 3.14 alpha releases
- Thread/process cleanup may be less reliable in pre-release Python
- CI on 3.11/3.12 might not show same symptoms (or might show different ones)

**Not the root cause** but may amplify the problem locally.

## How This Kills Your Machine

When running `pytest -v`, the following cascade occurs:

### Before Optimization (114 tests, one-by-one encoding)
- Light process spawning: 0-2 workers per model.encode() call
- 13 embedding tests × 2 workers = ~26 processes max
- Problematic but manageable

### After Optimization (152 tests, batch encoding)
1. **Test 1** (`test_compute_semantic_embedding`): Loads SentenceTransformer + single encode → spawns 2-4 worker processes
2. **Test 2** (`test_compute_embeddings` with 3 notes): **Batch encode** → spawns 4-8 worker processes
3. **Test 3** (`test_semantic_similarity`): Another batch encode → spawns 4-8 more worker processes
4. Each batch operation spawns multiple workers due to:
   - PyTorch DataLoader parallelism (default: num_cpu_cores workers)
   - Tokenizer parallelism (default: enabled, spawns multiple threads)
   - BLAS threads for numpy operations (default: num_cpu_cores)
   - Model's internal pooling/encoding parallelism

5. This continues for **13+ embedding tests** + integration tests with kepano vault (real data)
6. **Without thread limits**, on an 8-core machine:
   - 8 PyTorch workers × 13 tests = 104 processes
   - 8 tokenizer threads × 13 tests = 104 threads
   - 8 BLAS threads × 13 tests = 104 threads
   - **Total: 300+ threads/processes** attempting to run concurrently

7. Each worker/thread holds:
   - Model weights in memory (~90MB for all-MiniLM-L6-v2)
   - Tokenizer resources (~20MB)
   - Python interpreter overhead (~30MB)
   - Total: ~140MB × 100+ processes = **14GB+ memory**

8. Signal-based timeout (SIGALRM) further disrupts cleanup, causing processes to hang
9. System runs out of memory → swapping → complete unresponsiveness → machine kill

### The Perfect Storm
- **New batch encoding** (aggressive parallelization)
- **+38 new tests** (more trigger points)
- **No thread limits** (unlimited spawning)
- **No cleanup** (accumulation)
- **Signal interference** (processes hang instead of dying)
- **Python 3.14 dev** (potentially flaky multiprocessing)

## Fix Plan

### Priority 0.5: Shared Session Fixtures (ARCHITECTURAL FIX - DO FIRST)

**File**: `tests/unit/test_embeddings.py`

**Problem**: Currently 13 tests each compute embeddings independently:

```python
# Test 1
def test_compute_embeddings(sample_notes):
    db = init_db()
    session = Session(datetime(2023, 6, 15), db)
    session.compute_embeddings(sample_notes)  # ← Batch encode: spawns 8 workers
    # test code...

# Test 2
def test_get_all_embeddings(sample_notes):
    db = init_db()
    session = Session(datetime(2023, 6, 15), db)
    session.compute_embeddings(sample_notes)  # ← Again! spawns 8 more workers
    # test code...

# ... 11 more tests doing the same thing ...
```

**13 tests × 8 workers = 104 processes** (even though most tests just need embeddings to exist)

**Solution**: Create module-scoped fixture that computes embeddings once, shared across tests:

```python
@pytest.fixture(scope="module")
def shared_session_with_embeddings(sample_notes):
    """Pre-computed embeddings shared across all tests in module.

    This fixture computes embeddings ONCE for the entire test module,
    then reuses them across all tests that only need to read/query embeddings.
    """
    db = init_db()

    # Insert notes into database
    for note in sample_notes:
        db.execute(
            """
            INSERT INTO notes (path, title, content, created, modified, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                note.path, note.title, note.content,
                note.created.isoformat(), note.modified.isoformat(),
                note.modified.timestamp(),
            ),
        )
    db.commit()

    # Create session and compute embeddings ONCE
    session = Session(datetime(2023, 6, 15), db)
    session.compute_embeddings(sample_notes)  # ← Only happens ONCE for entire module

    yield session

    db.close()

@pytest.fixture
def isolated_session(sample_notes):
    """Isolated session for tests that need to test computation behavior.

    Use this fixture for tests that specifically test:
    - Session creation
    - Embedding computation process
    - Vault state hashing
    - Session reuse logic
    """
    db = init_db()

    # Insert notes
    for note in sample_notes:
        db.execute(...)
    db.commit()

    yield db  # Return db so test can create its own session

    db.close()

# Most tests use shared fixture (fast, low resource):
def test_get_all_embeddings(shared_session_with_embeddings):
    embeddings = shared_session_with_embeddings.get_all_embeddings()
    assert len(embeddings) == 3
    # No computation, just retrieval from SQLite

def test_semantic_similarity(shared_session_with_embeddings):
    embeddings = shared_session_with_embeddings.get_all_embeddings()
    sim = cosine_similarity(embeddings["note1.md"], embeddings["note2.md"])
    assert sim > 0.5
    # Using pre-computed embeddings

# Tests that need isolation keep current behavior:
def test_session_creation(isolated_session):
    """Test session creation - needs fresh session."""
    db = isolated_session
    session = Session(datetime(2023, 6, 15), db)
    assert session.session_id > 0

def test_compute_embeddings(isolated_session):
    """Test computation process - needs to actually compute."""
    db = isolated_session
    session = Session(datetime(2023, 6, 15), db)
    notes = [...]
    session.compute_embeddings(notes)
    # Test the computation behavior
```

**Tests to convert to `shared_session_with_embeddings`** (~9 tests, 70%):
- `test_get_all_embeddings` - Just reads embeddings
- `test_semantic_similarity` - Compares pre-computed embeddings
- `test_cosine_similarity` - Pure math function
- `test_find_similar_notes` - Pure utility function
- `test_embedding_persistence` - Tests retrieval
- `test_embed_very_long_note` - Tests that long content doesn't crash
- `test_empty_embedding_handling` - Tests empty content handling
- And others that just need embeddings to exist

**Tests to keep with `isolated_session`** (~4 tests, 30%):
- `test_session_creation` - Tests session object creation
- `test_session_reuse` - Tests session ID behavior
- `test_compute_embeddings` - Tests the computation process itself
- `test_compute_vault_state_hash` - Tests hash computation

**Impact**:
- **Process spawning**: 13 computations × 8 workers = 104 → 1 computation × 8 workers = 8 (13x reduction)
- **Test speed**: ~30 seconds → ~5 seconds (6x faster)
- **Memory usage**: 13 model loads → 1 model load (13x reduction)
- **Cleaner tests**: Most tests become pure read operations

**Why Priority 0.5 (do first)**:
- **Architectural fix** - Addresses the root cause: unnecessary repeated computation
- **Huge impact** - 13x reduction with minimal effort
- **Fast to implement** - 15-30 minutes
- **Low risk** - Most tests don't need isolation
- **Makes everything else easier** - Fewer processes means less strain on other fixes

### Priority 0: Set Thread/Process Limits (SAFETY NET - DO SECOND)

**Files**:
- `src/geistfabrik/embeddings.py` (module-level)
- `.github/workflows/test.yml` (CI environment)
- `pyproject.toml` (pytest configuration)

**Changes needed**:
1. Set environment variables at the top of `embeddings.py` (before any imports that use BLAS)
2. Add environment variables to GitHub Actions workflow
3. Document in README for local development

**Implementation**:

In `src/geistfabrik/embeddings.py` (add at top, before imports):
```python
"""Embeddings computation for GeistFabrik."""

import os

# CRITICAL: Limit thread/process spawning for ML libraries
# These MUST be set before importing numpy, torch, or transformers
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import hashlib
import math
# ... rest of imports
```

In `.github/workflows/test.yml` (add before "Run tests" step):
```yaml
- name: Set thread limits
  run: |
    echo "OMP_NUM_THREADS=1" >> $GITHUB_ENV
    echo "MKL_NUM_THREADS=1" >> $GITHUB_ENV
    echo "TOKENIZERS_PARALLELISM=false" >> $GITHUB_ENV

- name: Run tests
  run: uv run pytest -v
```

**Why Priority 0 (safety net)**:
- **Prevents unlimited spawning** - limits workers even if future tests compute repeatedly
- **Environment-level protection** - applies to all code, not just tests
- **Fixes all libraries** - not just sentence-transformers
- **Safe and reversible** - can be easily adjusted
- **Should reduce 8 workers to 1 worker** per operation

**Combined with Priority 0.5**:
```
Before:
- 13 tests compute embeddings
- Each spawns 8 workers (no limits)
- Total: 104 worker processes

After Priority 0.5 only (shared sessions):
- 1 test computes embeddings
- Spawns 8 workers (still no limits)
- Total: 8 worker processes (13x better)

After Priority 0 only (thread limits):
- 13 tests compute embeddings
- Each spawns 1 worker (limited)
- Total: 13 worker processes (8x better)

After BOTH Priority 0.5 + 0:
- 1 test computes embeddings
- Spawns 1 worker (limited)
- Total: 1 worker process (104x better!)
```

**Defense in depth**: Priority 0.5 fixes the architecture, Priority 0 ensures it stays fixed even if tests change.

### Priority 1: Configure SentenceTransformer Device and Options

**File**: `src/geistfabrik/embeddings.py`

**Changes needed**:
1. Explicitly set device to 'cpu' to avoid GPU worker spawning
2. Configure model with minimal workers
3. Add batch_size limit to prevent excessive parallelization

**Implementation**:
```python
# Line 38 - Modify model initialization
self._model = SentenceTransformer(
    self.model_name,
    device='cpu',  # Explicit CPU to avoid GPU worker spawning
)

# Line 188-190 - Add batch_size limit to encode
semantic_embeddings = self.computer.model.encode(
    texts,
    convert_to_numpy=True,
    show_progress_bar=False,
    batch_size=8,  # Limit batch size to reduce parallel workers
)
```

**Why Priority 1**: Works with Priority 0 to fully control parallelism.

### Priority 2: Add Model Cleanup to EmbeddingComputer

**File**: `src/geistfabrik/embeddings.py`

**Changes needed**:
1. Add `close()` method to `EmbeddingComputer` class
2. Add `__enter__` and `__exit__` methods for context manager support
3. Add `__del__` method as fallback cleanup

**Implementation**:
```python
def close(self) -> None:
    """Clean up model resources."""
    if self._model is not None:
        self._model = None

def __enter__(self):
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False

def __del__(self):
    self.close()
```

**Why second**: Ensures cleanup happens even if processes spawn, preventing accumulation.

### Priority 3: Additional Shared Fixtures in conftest.py

**File**: `tests/conftest.py`

**Changes needed**:
1. Create session-scoped fixture for `EmbeddingComputer` (for non-embedding tests that need it)
2. Create function-scoped fixture for database with proper cleanup (for all tests)

**Implementation**:
```python
@pytest.fixture(scope="session")
def shared_embedding_computer():
    """Single shared EmbeddingComputer for all tests that need direct model access.

    Note: Most embedding tests should use the shared_session_with_embeddings
    fixture instead, which includes pre-computed embeddings. This fixture is
    for tests that specifically need to test EmbeddingComputer behavior.
    """
    computer = EmbeddingComputer()
    yield computer
    computer.close()

@pytest.fixture
def test_db():
    """Function-scoped database with cleanup.

    Use this instead of manually calling init_db() and db.close().
    Ensures cleanup happens even if test fails.
    """
    db = init_db()
    yield db
    db.close()
```

**Note**: Priority 0.5 already handles the shared session for embedding tests. This priority adds:
- Shared EmbeddingComputer for direct model testing (e.g., `test_compute_semantic_embedding`)
- Database fixture to replace manual init/close throughout tests

**Why third**: Complements Priority 0.5 by providing shared resources for non-embedding tests.

### Priority 4: Replace Signal-Based Timeout with Thread-Safe Alternative

**File**: `src/geistfabrik/geist_executor.py`

**Changes needed**:
1. Replace SIGALRM with `concurrent.futures.ThreadPoolExecutor` with timeout
2. Alternative: Use `func_timeout` library (thread-based timeout)
3. Ensure timeout mechanism doesn't interfere with worker processes

**Implementation**:
```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# In execute_geist method:
with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(geist.func, context)
    try:
        suggestions = future.result(timeout=self.timeout)
    except FutureTimeoutError:
        self._handle_failure(geist_id, "timeout", "Execution timed out")
        return []
```

**Why fourth**: Eliminates signal interference with worker processes while maintaining timeout functionality.

### Priority 5: Clean Up sys.modules in Test Fixtures

**File**: `tests/unit/test_geist_executor.py`

**Changes needed**:
1. Modify `geists_dir` fixture to track loaded modules
2. Clean up test modules after each test
3. Ensure no module references persist

**Implementation**:
```python
@pytest.fixture
def geists_dir(tmp_path: Path):
    geists = tmp_path / "geists"
    geists.mkdir()

    # Track modules before test
    initial_modules = set(sys.modules.keys())

    yield geists

    # Clean up modules added during test
    current_modules = set(sys.modules.keys())
    test_modules = current_modules - initial_modules
    for module_name in test_modules:
        if module_name in sys.modules:
            del sys.modules[module_name]
```

**Why fifth**: Prevents module pollution but doesn't directly address process spawning.

### Priority 6: Add Database Connection Cleanup

**File**: `tests/unit/test_embeddings.py` and other test files

**Changes needed**:
1. Ensure all `db.close()` calls happen even on test failure
2. Use fixtures instead of manual db creation
3. Add try/finally blocks where fixtures aren't used

**Implementation**:
- Replace manual `db = init_db()` with fixture usage
- Ensure all tests use `test_db` fixture from conftest.py
- Remove manual `db.close()` calls (handled by fixture)

**Why sixth**: Good practice but not directly related to process spawning.

## Implementation Order

### Phase 1 (IMMEDIATE - Do First, 20 minutes total)

**Step 1: Priority 0.5** - Shared session fixtures (15 minutes)
- Add two fixtures to `tests/unit/test_embeddings.py`
  - `shared_session_with_embeddings` (module-scoped)
  - `isolated_session` (function-scoped)
- Update ~9 test signatures to use `shared_session_with_embeddings`
- Keep ~4 tests using `isolated_session`
- Test: Run `pytest tests/unit/test_embeddings.py -v`
- **Expected result**:
  - 13 embedding computations → 1 computation
  - 104 worker processes → 8 worker processes
  - 30 seconds → 5 seconds test time

**Step 2: Priority 0** - Thread/process limits (5 minutes)
- Modify `src/geistfabrik/embeddings.py` to set environment variables at top
- Update `.github/workflows/test.yml` to set environment
- Test: Run full suite, monitor process count with `ps aux | grep python | wc -l`
- **Expected result**:
  - 8 worker processes → 1 worker process
  - Combined with 0.5: **104 processes → 1 process (104x reduction)**

**Checkpoint after Phase 1**:
- Test suite should complete without spawning runaway processes
- Memory usage should stay under 500MB
- Tests should run faster (~6x faster for embedding tests)
- If this works, Phases 2-6 become "nice to have" rather than critical

### Phase 2 (Same Session, 15 minutes)
**Priority 1**: Configure SentenceTransformer options
- Add `device='cpu'` and `batch_size=8` limit
- Test: Run embedding tests specifically
- **Expected result**: Further reduction in memory usage per operation

### Phase 3 (Same Session, 10 minutes)
**Priority 2**: Add cleanup methods to EmbeddingComputer
- Add `close()`, `__enter__`, `__exit__`, `__del__` methods
- Test: Verify cleanup happens (add debug logging)
- **Expected result**: No leaked model references, better resource hygiene

### Phase 4 (Same Session, 15 minutes)
**Priority 3**: Additional shared fixtures in conftest.py
- Session-scoped EmbeddingComputer for direct model tests
- Function-scoped database fixture
- Convert manual `db = init_db()` / `db.close()` to fixture usage
- **Expected result**: Cleaner test code, more reliable cleanup

### Phase 5 (Next Session)
**Priority 4**: Replace signal-based timeout
- Use ThreadPoolExecutor with timeout instead of SIGALRM
- Test geist executor timeout tests
- **Expected result**: No signal interference with workers

### Phase 6 (Next Session)
**Priority 5 & 6**: Clean up test fixtures
- Add sys.modules cleanup
- Convert manual db.close() to fixtures
- **Expected result**: Cleaner test code, more reliable cleanup

## Testing Strategy

### After Phase 1 (Critical Validation)

**Before starting**:
```bash
# Baseline measurement
ps aux | grep python | wc -l  # Note the number
pytest tests/unit/test_embeddings.py -v --durations=10
# Watch for hanging processes
```

**After Priority 0.5 (shared sessions)**:
```bash
# Should be much faster
pytest tests/unit/test_embeddings.py -v --durations=10
# Expected: ~5 seconds (was ~30 seconds)

# Check process count during test
# In another terminal:
watch -n 0.5 'ps aux | grep python | wc -l'
# Should see max ~10-15 processes (not 100+)
```

**After Priority 0 (thread limits)**:
```bash
# Should be same speed, but fewer processes
pytest tests/unit/test_embeddings.py -v

# Check process count
ps aux | grep python | wc -l
# Should see only ~5 processes

# Run full suite
pytest -v
# Monitor memory: should stay under 500MB
```

### After Each Subsequent Phase

1. Run full test suite: `pytest -v`
2. Check all tests still pass
3. Monitor process count: `ps aux | grep python | wc -l`
4. Monitor memory: `ps aux | grep python` (check RSS column)
5. Verify test speed hasn't regressed

## Success Criteria

### Phase 1 Success (Must achieve):
- ✅ Running embedding tests spawns ≤10 Python processes total (was 104+)
- ✅ Embedding tests complete in ~5 seconds (was ~30 seconds)
- ✅ All processes terminate within 5 seconds of test completion
- ✅ Memory usage stays under 500MB during test run
- ✅ Tests complete without system slowdown
- ✅ Machine remains responsive during test run

### Full Success (Nice to have):
- ✅ All 152 tests pass
- ✅ Total test suite completes in reasonable time
- ✅ Clean process cleanup (verified with `watch`)
- ✅ CI passes on all platforms (Ubuntu, macOS, Windows)

## Immediate Workaround (If Fixes Take Time)

```bash
# Run tests sequentially with process limit
pytest -v --forked -n 0

# Or run specific test files only
pytest tests/unit/test_vault.py tests/unit/test_markdown_parser.py -v

# Skip embedding tests temporarily
pytest -v -k "not embedding"
```

## Files to Modify

### Phase 1 (Critical)
1. `tests/unit/test_embeddings.py` (Priority 0.5 - add shared fixtures)
2. `src/geistfabrik/embeddings.py` (Priority 0 - add env vars at top)
3. `.github/workflows/test.yml` (Priority 0 - add env vars to CI)

### Phase 2-4 (Improvements)
4. `src/geistfabrik/embeddings.py` (Priorities 1, 2 - model config, cleanup methods)
5. `tests/conftest.py` (Priority 3 - additional fixtures)
6. `tests/unit/test_embeddings.py` (Priority 3 - convert to fixtures)

### Phase 5-6 (Refactoring)
7. `src/geistfabrik/geist_executor.py` (Priority 4 - replace signal timeout)
8. `tests/unit/test_geist_executor.py` (Priority 5 - sys.modules cleanup)
9. `tests/unit/test_vault_context.py` (Priority 6 - fixture conversion)
10. `tests/integration/test_kepano_vault.py` (Priority 6 - fixture conversion)

## Related Issues

- Signal handling is Unix-only (line 134 in geist_executor.py) - Windows compatibility concern
- Lazy loading pattern makes cleanup timing unclear
- No resource management in VaultContext class
- Integration tests may need longer timeouts for real vault data

## Key Findings Summary

### The Smoking Gun: Commit ec00fb8 (Oct 20, 2025)

**What happened**: A well-intentioned performance optimization changed embedding computation from one-by-one to batch processing. This had the unintended consequence of:

1. **15-20x faster for production** ✅ (Good!)
2. **300x more processes in tests** ❌ (Machine killer!)

The optimization is **correct for production** but **catastrophic for tests** without proper resource controls.

### The Root Cause Chain

```
Batch Encoding (aggressive parallelism)
    ↓
+ No Thread Limits (unlimited spawning)
    ↓
+ No Cleanup (accumulation)
    ↓
+ Signal Interference (processes hang)
    ↓
+ 152 Tests (multiple trigger points)
    ↓
= PROCESS EXPLOSION → System Death
```

### The Fix Strategy

**Don't revert the optimization** - it's good for production. Instead:
1. **Share embeddings in tests** → Architectural fix: compute once, reuse 13 times
2. **Add environment limits** → Safety net: control spawning
3. **Add cleanup code** → Prevent accumulation
4. **Fix signal handling** → Prevent hanging

**Result**:
- Fast production code (15-20x faster) ✅
- Safe tests (104x fewer processes) ✅
- Faster tests (6x faster) ✅
- Lower memory usage (13x reduction) ✅

## Notes

- The core issue is: **good optimization + no resource limits = test environment disaster**
- This is not a bug in sentence-transformers, PyTorch, or any single component
- The fixes are defensive programming to ensure proper resource management
- **Critical lesson**: Performance optimizations that increase parallelism need corresponding resource controls in test environments
- Consider adding resource monitoring to CI to catch similar issues early
- Future optimizations should include test environment configuration as part of the change
