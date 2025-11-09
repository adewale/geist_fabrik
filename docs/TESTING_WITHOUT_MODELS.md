# Testing Without Models

Guide for running GeistFabrik tests without downloading sentence-transformers models.

## Quick Start

### Option 1: Use the Script (Recommended)

```bash
# Basic run
./scripts/test_without_models.sh

# With verbose output
./scripts/test_without_models.sh -v

# With coverage report
./scripts/test_without_models.sh -c

# Quick mode (stop on first failure)
./scripts/test_without_models.sh -q
```

### Option 2: Direct Command

```bash
# Simple command (no model downloads)
uv run pytest -m "not slow"

# With verbose output
uv run pytest -m "not slow" -v

# With coverage
uv run pytest -m "not slow" --cov=geistfabrik --cov-report=term-missing
```

## What Gets Tested

### Test Coverage: **43.40% overall**

**655 out of 664 tests** run without model downloads (9 tests skipped):
- ✅ 626 tests pass
- ⏭️ 28 tests skipped (conditional features)
- 🚫 9 tests deselected (marked as `@pytest.mark.slow`)

### Coverage by Component

| Component | Coverage | Notes |
|-----------|----------|-------|
| **Core Models** | 100% | All data structures tested |
| **Config System** | 100% | All configuration loading tested |
| **Date Collection** | 96.38% | Virtual notes fully tested |
| **Config Loader** | 94.78% | All config scenarios tested |
| **Metadata System** | 94.49% | All metadata inference tested |
| **Markdown Parser** | 93.94% | All parsing logic tested |
| **Function Registry** | 91.20% | Function loading/execution tested |
| **Vault Context** | 88.51% | Most helper methods tested |
| **Vault** | 85% | Core sync/query operations tested |
| **Embeddings** | 79% | Logic tested with stub model |
| **Tracery** | 73.87% | Grammar expansion tested |
| **Stats** | 71.88% | Statistical functions tested |
| **Filtering** | 31.16% | Some filters need real embeddings |
| **CLI** | 6.95% | Most commands need real models |
| **Default Geists** | 0% | Need real embeddings to test properly |

## What's Tested ✅

The test suite with stubbed models covers:

### Core Infrastructure (85-100% coverage)
- ✅ **Vault operations**: File sync, incremental updates, note queries
- ✅ **Link resolution**: [[wikilinks]], backlinks, orphan detection
- ✅ **Tag extraction**: #tags in content and frontmatter
- ✅ **Virtual notes**: Date-collection notes (journal splitting)
- ✅ **Markdown parsing**: Frontmatter, headings, lists, code blocks
- ✅ **SQLite persistence**: Schema, indexes, transactions
- ✅ **Config system**: YAML loading, validation, defaults

### Embedding Layer (79% coverage)
- ✅ **Embedding computation**: Batch processing, caching logic
- ✅ **Session management**: Session creation, embedding storage
- ✅ **Similarity calculations**: Cosine similarity math
- ✅ **Vector backends**: Both in-memory and sqlite-vec backends
- ✅ **Temporal embeddings**: Season/age feature computation

### Extensibility Layer (88-94% coverage)
- ✅ **Metadata system**: Module loading, inference, conflict detection
- ✅ **Function registry**: Vault function registration, Tracery integration
- ✅ **Geist loading**: Code and Tracery geist discovery
- ✅ **Tracery grammars**: Symbol expansion, modifiers, function calls

### Graph Operations
- ✅ **Backlinks**: Finding notes that link to a note
- ✅ **Orphans**: Detecting unlinked notes
- ✅ **Hubs**: Finding highly-linked notes
- ✅ **Neighbors**: Graph traversal operations

## What's NOT Tested ❌

These require real embeddings from sentence-transformers:

### Semantic Quality (0-30% coverage)
- ❌ **Real semantic similarity**: Actual meaningful similarities
- ❌ **Individual geists**: Most default geists need real embeddings
- ❌ **Suggestion quality**: Filtering needs semantic context
- ❌ **CLI commands**: Most invoke commands need real model

### Integration Tests Skipped
- ❌ `test_embeddings_integration.py` (all tests)
- ❌ `test_phase3b_regression.py::TestPatternFinderPerformance`

## How It Works

### Stub Model Architecture

When you run `pytest -m "not slow"`, the test framework:

1. **Injects a stub model** via `pytest_configure()` hook in `tests/conftest.py`
2. **Replaces** `SentenceTransformer` with `SentenceTransformerStub`
3. **Generates deterministic embeddings** based on text hash (SHA256)
4. **Returns 384-dim vectors** (same shape as real model)
5. **Normalizes to unit vectors** (same as real model)

### Why This Works

The stub model provides:
- ✅ **Deterministic results**: Same text → same embedding
- ✅ **Correct dimensions**: 384-dim vectors like real model
- ✅ **Unit normalized**: Matches real model's output format
- ✅ **Fast execution**: No network access or model loading
- ✅ **Full API compatibility**: Drop-in replacement for real model

### What's Missing from Stub

The stub model does NOT provide:
- ❌ **Semantic meaning**: Embeddings aren't semantically meaningful
- ❌ **Actual similarity**: Similar texts don't have similar embeddings
- ❌ **Real clustering**: Can't test cluster quality

## Performance

### Execution Time

```
Total runtime: ~3-4 minutes (197 seconds typical)
  • Test collection: ~1 second
  • Test execution: ~190 seconds
  • Coverage computation: ~6 seconds
```

### Comparison to Full Test Suite

| Test Mode | Tests Run | Time | Model Download |
|-----------|-----------|------|----------------|
| **Without models** | 655/664 (98.6%) | ~3 min | ❌ None |
| **With models (first run)** | 664/664 (100%) | ~15 min | ✅ ~90MB |
| **With models (cached)** | 664/664 (100%) | ~5 min | ✅ Cached |

## Perfect for Claude Code for Web

This test mode is **ideal for Claude Code for Web** because:

1. ✅ **No model downloads** - Works in restricted environments
2. ✅ **Fast feedback** - Results in ~3 minutes
3. ✅ **High coverage** - Tests 98.6% of test suite
4. ✅ **Core infrastructure** - All critical components tested
5. ✅ **Deterministic** - No network dependencies

## When to Use Each Test Mode

### Use `pytest -m "not slow"` when:
- ✅ Working in Claude Code for Web
- ✅ Testing core infrastructure changes
- ✅ Rapid TDD iteration
- ✅ Limited network access
- ✅ CI/CD environments (optional)

### Use full test suite (`pytest`) when:
- ✅ Testing semantic similarity logic
- ✅ Developing/testing new geists
- ✅ Testing CLI commands
- ✅ Final validation before release
- ✅ Investigating semantic quality issues

## CI/CD Integration

The project's CI pipeline uses the same approach:

```bash
# From .github/workflows/ci.yml
pytest -m "not slow"
```

This ensures:
- ✅ Fast CI runs (~3 minutes)
- ✅ No model download delays
- ✅ Comprehensive infrastructure testing
- ✅ Consistent with local development

## Troubleshooting

### "Tests are downloading models"

If tests start downloading models, check:
1. You're using `-m "not slow"` flag
2. No `@pytest.mark.slow` tests are being collected
3. Pytest version is compatible (>=7.4.0)

```bash
# Verify slow tests are skipped
pytest --collect-only -m "not slow" -q | grep "deselected"
# Should show: "9 deselected"
```

### "Coverage seems low"

Coverage is ~43% because:
- Default geists (40 files) need real embeddings → 0% coverage
- CLI commands need real models → 6.95% coverage
- But **core infrastructure has 85-100% coverage**

This is expected and acceptable for model-free testing.

### "Tests are slow"

Full suite takes ~3-4 minutes. To speed up:

```bash
# Run unit tests only (~30 seconds)
pytest tests/unit/ -v

# Run single test file
pytest tests/unit/test_vault.py -v

# Stop on first failure
pytest -m "not slow" -x
```

## Summary

**Bottom line**: You can test **98.6% of GeistFabrik's test suite** without downloading models, achieving **43.40% code coverage** with **85-100% coverage of core infrastructure**.

Perfect for rapid development in Claude Code for Web! 🚀
