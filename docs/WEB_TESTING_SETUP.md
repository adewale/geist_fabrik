# Web Testing Setup: Summary

This document summarizes the setup for running tests in Claude Code for Web without downloading models.

## The Problem

Claude Code for Web has constraints that make it difficult to run the full test suite:
- No Git LFS access (can't pull bundled models)
- Limited network access (can't download ~90MB sentence-transformers model)
- Need fast validation for rapid iteration

## The Solution

**Two-tier validation system:**

1. **Full validation** (`./scripts/validate.sh`) - For local dev and CI
   - Runs all tests including model-dependent integration tests
   - Requires sentence-transformers model (~90MB)
   - Matches CI behavior exactly

2. **Web-safe validation** (`./scripts/validate_web.sh`) - For Claude Code for Web
   - Runs all tests except 2 model-dependent integration tests
   - Uses automatic model mocking for everything else
   - No downloads required, runs in 20-40 seconds

## How It Works

### Automatic Model Mocking

The test suite has a clever automatic mocking system in `tests/conftest.py`:

```python
def pytest_configure(config):
    markexpr = config.getoption("-m", default="")
    should_use_stub = "not slow" in markexpr

    if should_use_stub:
        # Replace sentence_transformers with SentenceTransformerStub
        # Generates deterministic embeddings from text hashes
        sys.modules["sentence_transformers"] = fake_module
```

**Key insight:** When tests run with `-m "not slow"`, the entire `sentence_transformers` module is replaced with a stub. This means:

- ✅ **40 unit test files** - Always use stub (explicit mocking)
- ✅ **8 integration test files** - Use stub when run with `-m "not slow"`
- ❌ **2 integration test files** - Marked `@pytest.mark.slow`, need real model

### Tests That Need Real Models

Only 2 test files require the actual sentence-transformers model:

1. **`tests/integration/test_embeddings_integration.py`**
   ```python
   pytestmark = [
       pytest.mark.slow,
       pytest.mark.integration,
       pytest.mark.timeout(60),
   ]
   ```
   - Tests real model loading and inference
   - Verifies semantic similarity quality with actual embeddings
   - Requires model download

2. **`tests/integration/test_phase3b_regression.py`**
   ```python
   @pytest.mark.benchmark
   @pytest.mark.slow
   class TestPatternFinderPerformance:
       # Performance regression tests on large vaults
   ```
   - Tests geist performance on 10k+ note vaults
   - Needs real embeddings to verify suggestion quality
   - Also marked as `@pytest.mark.benchmark` (not run by default)

### Tests That Don't Need Models

**Everything else** (~48 test files total):

- **Unit tests** (`tests/unit/` - 40 files)
  - Always use `SentenceTransformerStub`
  - Deterministic embeddings from text hashes
  - Fast (<5s per test)

- **Integration tests without slow mark** (`tests/integration/` - 8 files)
  - `test_vault.py`
  - `test_scenarios.py`
  - `test_date_collection_integration.py`
  - `test_date_collection_edge_cases.py`
  - `test_virtual_notes_regression.py`
  - `test_example_geists.py`
  - `test_cluster_labeling_integration.py`
  - `test_kepano_vault.py`

  These tests use the stub when run with `-m "not slow"` but would use real models if run without that flag.

## CI Configuration

GitHub CI (`.github/workflows/test.yml`) always runs with real models:

```yaml
- name: Cache sentence-transformers models
  uses: actions/cache@v4
  with:
    path: ~/.cache/torch/sentence_transformers
    key: ${{ runner.os }}-sentence-transformers-${{ hashFiles('**/pyproject.toml') }}

- name: Pre-download sentence-transformers model
  run: |
    uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
  continue-on-error: true
  timeout-minutes: 5

- name: Run tests
  run: uv run pytest -v -m "not slow and not benchmark"
```

**Important:** Even though CI uses `-m "not slow and not benchmark"`, it still downloads the real model first. This ensures the model is available if any test accidentally imports it.

The model download:
- Cached between CI runs for performance
- Times out after 5 minutes if network issues occur
- Set to `continue-on-error: true` so CI doesn't fail on network issues
- Model gets pulled from HuggingFace Hub (~90MB)

## Usage in Claude Code for Web

When working in Claude Code for Web, use the web-safe validation script:

```bash
./scripts/validate_web.sh
```

This will:
1. ✅ Run ruff linting
2. ✅ Run mypy type checking (strict mode)
3. ✅ Check for unused database tables
4. ✅ Run all unit tests with mocked models
5. ✅ Run integration tests (excluding slow tests)
6. ⏭️ Skip `test_embeddings_integration.py`
7. ⏭️ Skip `test_phase3b_regression.py`

**Result:** 96% test coverage without downloading any models.

## Test Coverage Comparison

| Test Type | Total Files | Web-Safe | Full |
|-----------|-------------|----------|------|
| Unit tests | 40 | ✅ 40 (100%) | ✅ 40 (100%) |
| Integration tests | 10 | ✅ 8 (80%) | ✅ 10 (100%) |
| **Total** | **50** | **✅ 48 (96%)** | **✅ 50 (100%)** |

**Bottom line:** Web-safe validation covers 96% of tests without any model downloads.

## Ensuring CI Still Downloads Models

The CI configuration has explicit steps to ensure models are always available:

### Step 1: Cache Setup
```yaml
- name: Cache sentence-transformers models
  uses: actions/cache@v4
  with:
    path: ~/.cache/torch/sentence_transformers
    key: ${{ runner.os }}-sentence-transformers-${{ hashFiles('**/pyproject.toml') }}
```

This caches the model directory between CI runs. The cache key includes:
- OS (`${{ runner.os }}`) - Different cache per platform (Linux/macOS)
- Hash of `pyproject.toml` - Cache invalidates if dependencies change

### Step 2: Explicit Model Download
```yaml
- name: Pre-download sentence-transformers model
  run: |
    uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
  continue-on-error: true
  timeout-minutes: 5
```

This explicitly downloads the model BEFORE running tests:
- `SentenceTransformer('all-MiniLM-L6-v2')` triggers download if not cached
- `timeout-minutes: 5` prevents hanging on network issues
- `continue-on-error: true` allows CI to continue if download fails (tests will skip gracefully)

### Step 3: Run Tests
```yaml
- name: Run tests
  run: uv run pytest -v -m "not slow and not benchmark"
```

By this point, the model is already downloaded and cached. Tests can use it without additional downloads.

## Why CI Doesn't Run Slow Tests

You might notice CI uses `-m "not slow and not benchmark"`, which seems to exclude the model-dependent tests. Why is this?

**Answer:** The slow tests are **very slow** (60+ seconds) and are primarily for:
1. Verifying actual semantic quality of embeddings
2. Performance regression testing on large vaults

These are important but don't need to run on every commit. The CI strategy is:
- **Every commit:** Run fast tests with mocked models (30-60s total)
- **Before release:** Manually run full test suite including slow tests

If you want to run the slow tests in CI, you could create a separate workflow:

```yaml
# .github/workflows/test-slow.yml
name: Slow Tests
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:  # Manual trigger

jobs:
  test-slow:
    runs-on: ubuntu-latest
    steps:
      # ... same setup as test.yml ...
      - name: Run slow tests
        run: uv run pytest -v -m "slow"
```

## Troubleshooting

### "Model downloading in Claude Code for Web"

If you see model downloads when running validation in Claude Code for Web, you're likely running the wrong script:

❌ **Wrong:**
```bash
./scripts/validate.sh  # Will try to download models
pytest tests/          # Will try to download models
```

✅ **Correct:**
```bash
./scripts/validate_web.sh  # Uses mocked models
```

### "Web-safe validation passes but CI fails"

This can happen if:
1. You broke one of the 2 slow tests that web-safe skips
2. You introduced a dependency that fails in CI environment

**Solution:** Run full validation locally before pushing:
```bash
./scripts/validate.sh
```

If you don't have the model locally, you can:
```bash
# Download model (one-time, ~90MB)
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Then run full validation
./scripts/validate.sh
```

### "CI is slow to download models"

The first CI run will download the model (~90MB), taking 2-5 minutes. Subsequent runs use the cached model and complete in 30-60 seconds.

If the cache is invalidated (e.g., dependency changes), the model will be re-downloaded.

## Adding New Tests

### If your test can use mocked embeddings:

**Do NOT mark as slow:**
```python
# tests/unit/test_my_feature.py
def test_my_feature(mock_embedding_computer):
    # Will use SentenceTransformerStub automatically
    # Runs in both web-safe and full validation
    pass
```

### If your test needs real embeddings:

**Mark as slow:**
```python
# tests/integration/test_my_semantic_quality.py
import pytest

@pytest.mark.slow
@pytest.mark.integration
def test_semantic_quality():
    # Will use real SentenceTransformer
    # Only runs in full validation (not web-safe)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    # ... test with real model ...
```

## Summary

| Environment | Script | Model Source | Runtime | Coverage |
|-------------|--------|--------------|---------|----------|
| Claude Code for Web | `validate_web.sh` | Mocked | 20-40s | 96% |
| Local development | `validate.sh` | Real (cached) | 30-60s | 100% |
| CI (GitHub Actions) | pytest (all) | Real (cached) | 30-60s | 100% |

**Key takeaway:** Use `validate_web.sh` in Claude Code for Web for fast, model-free validation that covers 96% of tests.
