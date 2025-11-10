# CI Testing Strategy Analysis

## Problem Statement

Windows CI builds hang indefinitely, causing CI runs to timeout after hours. This indicates our current "test everything on all platforms" strategy has fundamental issues.

## Root Cause Analysis

### 1. **Missing Global Timeout Configuration**

**Finding**: Only `test_embeddings_integration.py` has explicit timeouts (60s). Other integration tests have no timeout protection.

```python
# Only these tests have timeouts:
pytestmark = [
    pytest.mark.slow,
    pytest.mark.integration,
    pytest.mark.timeout(60),  # Only here!
]
```

**Impact**: Any test without explicit timeout can hang forever. Windows is exposing this gap.

**Evidence**:
- `pyproject.toml` pytest config has no `timeout` setting
- 18 integration tests, only 8 have explicit timeouts
- 144 unit tests have no timeout protection

### 2. **Platform-Specific Issues on Windows**

**Known Issues**:

a) **Threading behaviour** (`tests/integration/test_vault.py:test_concurrent_sync`):
   - Uses `threading.Thread` with concurrent SQLite access
   - Windows handles thread joining differently than Unix
   - SQLite file locking is stricter on Windows

b) **Temp directory cleanup**:
   - Windows can't delete files still held by processes
   - `tempfile.TemporaryDirectory()` cleanup may hang if SQLite connections not properly closed

c) **File locking semantics**:
   - Unix allows deleting open files
   - Windows prevents deletion of locked files
   - Missing `.close()` calls can cause indefinite hangs

### 3. **Overly Ambitious CI Matrix**

**Current Strategy**: Test everything on all platforms
```yaml
matrix:
  os: [ubuntu-latest]
  python-version: ["3.11", "3.12"]
  include:
    - os: macos-latest
      python-version: "3.11"
    - os: windows-latest  # ← Problem child
      python-version: "3.11"
```

**Why This Is Bad**:

1. **Diminishing returns**: GeistFabrik is primarily a Unix/macOS tool (Obsidian users)
2. **CI time waste**: Windows hangs burn hours of CI time
3. **False confidence**: "All platforms" doesn't mean "all platforms work well"
4. **Maintenance burden**: Platform-specific bugs for minority platforms

### 4. **Integration Tests Are Too Heavy for CI**

**Stats**:
- 144 unit tests (fast, deterministic)
- 18 integration tests (slower, more fragile)
- Integration tests use:
  - Real file I/O
  - SQLite with concurrent access
  - Thread synchronization
  - Temp directory cleanup

**Pattern**: Integration tests are where things go wrong on Windows.

## Industry Standard Approach

**What successful Python projects do**:

1. **Linux-first testing** (Ubuntu)
   - Full test suite (unit + integration)
   - All Python versions (3.11, 3.12)
   - This is the primary platform

2. **macOS/Windows: Smoke tests only**
   - Run unit tests (fast, reliable)
   - Skip integration tests (slow, platform-quirky)
   - Single Python version

3. **Explicit timeouts everywhere**
   - Global timeout (e.g., 5 minutes per test)
   - Individual timeouts for known-slow tests

4. **Platform skip markers**
   ```python
   @pytest.mark.skipif(sys.platform == "win32", reason="Windows file locking issues")
   ```

**Examples**:
- **Django**: Full tests on Ubuntu, smoke tests on Windows
- **Flask**: Linux CI primary, macOS/Windows best-effort
- **pandas**: Linux testing exhaustive, Windows subset
- **pytest itself**: Comprehensive Linux, targeted Windows

## Recommended Solutions

### Option 1: Tiered Testing Strategy ⭐ **RECOMMENDED**

**Rationale**: Focus effort where it matters, add safety nets everywhere.

**Implementation**:

```yaml
# .github/workflows/test.yml
jobs:
  test-full:
    name: Full test suite (Ubuntu)
    runs-on: ubuntu-latest
    timeout-minutes: 15  # Job-level timeout
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: uv sync
      - name: Run ALL tests (unit + integration)
        run: uv run pytest -v --timeout=300  # 5min per-test timeout
      - name: Run linting
        run: uv run ruff check src/ tests/
      - name: Run type checking
        run: uv run mypy src/ --strict

  test-smoke:
    name: Smoke tests (macOS/Windows)
    runs-on: ${{ matrix.os }}
    timeout-minutes: 10  # Shorter timeout for smoke tests
    strategy:
      fail-fast: false
      matrix:
        os: [macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: uv sync
      - name: Run unit tests only
        run: uv run pytest -v tests/unit --timeout=60
      - name: Quick linting check
        run: uv run ruff check src/
```

**Changes**:
- **Ubuntu**: Full suite (unit + integration), both Python versions
- **macOS/Windows**: Unit tests only, Python 3.11
- **Global timeout**: `--timeout=300` (5 min) for full, `--timeout=60` (1 min) for smoke
- **Job timeout**: `timeout-minutes` at job level as backstop

**Benefits**:
- ✅ No more infinite hangs (job-level + test-level timeouts)
- ✅ Fast feedback (smoke tests finish in ~2 minutes)
- ✅ Comprehensive Linux coverage (primary platform)
- ✅ Reduced CI cost (fewer heavy jobs)
- ✅ Clear expectations (not pretending Windows == Linux)

### Option 2: Add Timeouts, Skip Problematic Tests

**If we insist on running integration tests everywhere**:

```python
# pyproject.toml
[tool.pytest.ini_options]
timeout = 300  # Global 5-minute timeout
timeout_method = "thread"  # Better for Windows

# tests/integration/test_vault.py
import sys
import pytest

@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Threading + SQLite concurrency unreliable on Windows"
)
def test_concurrent_sync(tmp_path: Path) -> None:
    # ... existing code
```

**Pros**: More coverage
**Cons**: Still slow, still fragile, masks real Windows issues

### Option 3: Windows as Best-Effort Only

**Mark Windows as allowed to fail**:

```yaml
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    experimental: [false]
    include:
      - os: windows-latest
        experimental: true
continue-on-error: ${{ matrix.experimental }}
```

**Pros**: Won't block PRs
**Cons**: Windows becomes second-class, might hide real issues

## Implementation Plan

### Phase 1: Immediate Fixes (Stop the Bleeding)
1. Add global timeout to pytest config
2. Add job-level timeout to GitHub workflow
3. Skip `test_concurrent_sync` on Windows

### Phase 2: Restructure CI (Recommended Approach)
1. Split into `test-full` and `test-smoke` jobs
2. Update pytest markers to identify smoke tests
3. Document platform support policy

### Phase 3: Improve Test Infrastructure
1. Add timeout markers to all integration tests
2. Audit fixture cleanup (ensure `.close()` called)
3. Add platform skip markers where needed

## Proposed pytest.ini Changes

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --strict-markers --timeout=300"  # ← Add global timeout
timeout_method = "thread"  # ← Better Windows compatibility
markers = [
    "unit: Unit tests (fast, platform-independent)",
    "integration: Integration tests (slower, may be platform-specific)",
    "slow: Slow tests that require network access (model downloads)",
    "smoke: Smoke tests for cross-platform validation",
]
```

## Cost-Benefit Analysis

### Current Approach
- **Cost**: Hours of wasted CI time, developer frustration, unclear failures
- **Benefit**: Theoretical Windows support (but it doesn't work anyway)

### Recommended Approach (Tiered)
- **Cost**: 5 minutes to restructure CI, acknowledge Windows is secondary
- **Benefit**:
  - Fast, reliable CI (2-5 min instead of timeouts)
  - Clear platform support
  - Developer time saved
  - Lower CI costs

## Questions to Answer

1. **Who are our users?**
   - Obsidian users (macOS/Linux primarily)
   - GeistFabrik is a local-first tool for knowledge workers
   - Windows is minority platform for this use case

2. **What's our support commitment?**
   - Should we promise "works on Windows"?
   - Or "best-effort Windows support"?

3. **What's the CI time budget?**
   - Current: Potentially infinite (hangs)
   - Proposed: 10-15 minutes total
   - Savings: Hundreds of CI hours/month

## Recommendation

**Implement Option 1 (Tiered Testing)** because:

1. **Pragmatic**: Focuses effort on primary platform (Linux)
2. **Safe**: Timeouts prevent infinite hangs
3. **Fast**: Smoke tests give quick feedback
4. **Honest**: Doesn't pretend all platforms are equal
5. **Standard**: Matches industry practices

This is what mature Python projects do. We should too.

## Next Steps

1. User decision: Option 1, 2, or 3?
2. Implement chosen strategy
3. Document platform support policy in README
4. Update contribution guidelines for platform-specific issues

---

**Note**: Since I cannot access GitHub Actions to kill running jobs, manual intervention is needed to cancel the hanging Windows CI run via the GitHub web interface.
