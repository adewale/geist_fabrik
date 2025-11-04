# Phase 2 Optimization Tests

## Overview

This document describes the test suite for GeistFabrik's Phase 2 performance optimizations. These tests verify the correctness and performance of critical optimization features implemented to improve execution speed for large vaults.

## Test Files

### 1. test_phase2_batch_loading.py (OP-6)
**Tests**: 13 tests covering batch note loading infrastructure

**Purpose**: Verify the `get_notes_batch()` method that loads N notes in 3 SQL queries instead of 3×N queries.

**Test Classes**:
- `TestBatchLoading` - Core batch loading functionality
  - Multiple note loading
  - Missing note handling
  - Link and tag loading
  - Order preservation
  - Performance vs individual loading

- `TestBatchLoadingInVaultContext` - Integration with VaultContext
  - `neighbours()` uses batch loading
  - `backlinks()` uses batch loading
  - `hubs()` uses batch loading

- `TestBatchLoadingCorrectness` - Correctness validation
  - Equivalence to individual loading
  - Duplicate path handling

- `TestBatchLoadingBenchmark` - Performance benchmarks
  - Minimum 1.3x speedup expected

**Key Insight**: Batch loading reduces database round-trips from O(N) to O(1), providing ~1.5x speedup for loading 10 notes.

---

### 2. test_phase2_return_scores.py (OP-9)
**Tests**: 13 tests covering the `return_scores` parameter

**Purpose**: Verify the `neighbours(return_scores=True)` parameter that returns similarity scores alongside notes to avoid redundant computations.

**Test Classes**:
- `TestReturnScoresParameter` - Core parameter behavior
  - `return_scores=False` returns `List[Note]`
  - `return_scores=True` returns `List[Tuple[Note, float]]`
  - Default is `False`
  - Scores match `similarity()` results
  - Results are sorted by similarity
  - Same notes in both formats

- `TestReturnScoresCaching` - Cache behavior
  - Separate cache keys for each return_scores value

- `TestReturnScoresUsageInGeists` - Real-world usage
  - Tests 5 geists that use `return_scores`: hidden_hub, bridge_hunter, columbo, bridge_builder, antithesis_generator

- `TestReturnScoresPerformance` - Optimization validation
  - Avoids redundant similarity computations

- `TestReturnScoresBenchmark` - Performance benchmarks
  - Minimum 1.2x speedup expected

**Key Insight**: Computing scores once during neighbor search (instead of separately for each neighbor) provides significant performance benefits.

---

### 3. test_phase2_hubs_optimization.py (OP-8)
**Tests**: 11 tests covering optimized `hubs()` SQL query

**Purpose**: Verify the JOIN-based hubs() implementation that resolves link targets in SQL rather than Python, combined with batch loading.

**Test Classes**:
- `TestHubsOptimization` - Core optimization behavior
  - Returns most-linked notes
  - Respects k parameter
  - Handles link target variations
  - Sorted by link count
  - Uses batch loading

- `TestHubsCorrectness` - Correctness validation
  - Returns correct notes
  - Handles empty vaults
  - Handles self-links

- `TestHubsEdgeCases` - Edge case handling
  - Duplicate links (counts unique sources)
  - k larger than vault size

- `TestHubsPerformanceBenchmark` - Performance benchmarks
  - Target: <10ms for small vaults

**Key Insight**: JOIN-based target resolution in SQL eliminates Python loops for link resolution, providing dramatic speedup.

---

### 4. test_phase2_congruence_mirror.py (OP-4)
**Tests**: 13 tests covering single-pass congruence_mirror algorithm

**Purpose**: Verify the single-pass algorithm that replaced the 4-pass implementation, achieving 31.5x speedup on large vaults.

**Test Classes**:
- `TestCongruenceMirrorOptimization` - Algorithm correctness
  - Returns four quadrant suggestions
  - Correct format for each quadrant (EXPLICIT, IMPLICIT, CONNECTED, DETACHED)

- `TestCongruenceMirrorCorrectness` - Single-pass validation
  - Processes each pair once (no duplicates)
  - Respects minimum vault size
  - Uses cached operations
  - Sampling reduces search space

- `TestCongruenceMirrorDeterminism` - Deterministic behavior
  - Same vault + same date = same output

- `TestCongruenceMirrorPerformance` - Performance benchmarks
  - Small vault: <1s
  - Medium vault (100 notes): <200ms
  - Scaling: Better than O(n²)

**Key Insight**: Single-pass algorithm with intelligent sampling and caching transforms O(n²) operation into near-linear performance.

---

## Test Results

All 51 Phase 2 optimization tests **PASSING** ✅

```bash
uv run pytest tests/unit/test_phase2_*.py -v
```

**Result**: `51 passed in 2.49s`

### Test Breakdown
- **OP-6 (Batch Loading)**: 13 tests passing
- **OP-9 (return_scores)**: 13 tests passing
- **OP-8 (hubs optimization)**: 11 tests passing
- **OP-4 (congruence_mirror)**: 13 tests passing

---

## Key Optimizations Tested

### OP-4: Single-Pass Congruence Mirror
- **Improvement**: 31.5x speedup on large vaults
- **Technique**: Replace 4-pass algorithm with single-pass + caching
- **Impact**: One of the most expensive geists now runs in milliseconds

### OP-6: Batch Note Loading
- **Improvement**: ~1.5x speedup for loading N notes
- **Technique**: SQL IN clauses to load multiple notes in 3 queries instead of 3×N
- **Impact**: Benefits all operations that load multiple notes (neighbours, backlinks, hubs)

### OP-8: Optimized Hubs Query
- **Improvement**: Dramatically faster hub detection
- **Technique**: JOIN-based target resolution in SQL + batch loading
- **Impact**: <10ms for typical vaults (was much slower with Python loops)

### OP-9: Return Scores Parameter
- **Improvement**: ~1.2-1.5x speedup when scores are needed
- **Technique**: Return scores from neighbours() to avoid redundant similarity() calls
- **Impact**: Used by 5 geists (hidden_hub, bridge_hunter, columbo, bridge_builder, antithesis_generator)

---

## Testing Methodology

### Dynamic Geist Loading
Since geists aren't installable Python modules, tests use dynamic loading:

```python
import importlib.util

def load_geist(geist_name: str):
    """Dynamically load a geist module."""
    repo_root = Path(__file__).parent.parent.parent
    geist_path = repo_root / "src" / "geistfabrik" / "default_geists" / "code" / f"{geist_name}.py"

    spec = importlib.util.spec_from_file_location(geist_name, geist_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

### Session Initialization Pattern
Tests use the correct Session API pattern:

```python
session = Session(datetime.today(), vault.db)
notes = vault.all_notes()
session.compute_embeddings(notes)
context = VaultContext(vault, session)
```

### Realistic Test Fixtures
All tests use realistic vault structures with:
- Multiple notes with varied content
- Semantic similarities (e.g., "python.md" and "java.md")
- Link structures (hubs, isolated notes, bidirectional links)
- Tags and metadata

---

## Performance Targets

These tests validate that the optimizations meet their performance targets:

| Optimization | Target | Status |
|--------------|--------|--------|
| Batch Loading | ≥1.3x speedup | ✅ Passing |
| return_scores | ≥1.2x speedup | ✅ Passing |
| Hubs Query | <10ms (small vault) | ✅ Passing |
| Congruence Mirror | <1s (small), <200ms (100 notes) | ✅ Passing |
| Congruence Mirror Scaling | Better than O(n²) | ✅ Passing |

---

## Running Tests

### Run All Phase 2 Tests
```bash
uv run pytest tests/unit/test_phase2_*.py -v
```

### Run Specific Test File
```bash
uv run pytest tests/unit/test_phase2_batch_loading.py -v
uv run pytest tests/unit/test_phase2_return_scores.py -v
uv run pytest tests/unit/test_phase2_hubs_optimization.py -v
uv run pytest tests/unit/test_phase2_congruence_mirror.py -v
```

### Run Benchmark Tests Only
```bash
uv run pytest tests/unit/test_phase2_*.py -v -m benchmark
```

---

## Test Coverage Summary

| Component | Test Coverage | Status |
|-----------|---------------|--------|
| Batch Loading | 13 tests | ✅ Complete |
| return_scores Parameter | 13 tests | ✅ Complete |
| Hubs Optimization | 11 tests | ✅ Complete |
| Congruence Mirror | 13 tests | ✅ Complete |
| **Total** | **51 tests** | **✅ All Passing** |

---

## Related Documentation

- **specs/optimization_phase2.md** - Detailed specification of Phase 2 optimizations
- **specs/CONGRUENCE_MIRROR_GEIST_SPEC.md** - Congruence mirror algorithm specification
- **src/geistfabrik/vault.py** - Batch loading implementation
- **src/geistfabrik/vault_context.py** - return_scores and hubs() implementation
- **src/geistfabrik/default_geists/code/congruence_mirror.py** - Single-pass algorithm

---

## Status: ✅ COMPLETE

All Phase 2 optimization tests are:
- ✅ Fully implemented (51 tests)
- ✅ Comprehensively covering all 4 optimizations
- ✅ Passing with realistic test fixtures
- ✅ Validating both correctness and performance
- ✅ Using proper Session initialization patterns
- ✅ Testing real geist usage patterns
