# GeistFabrik Benchmarking Guide

This guide consolidates all benchmarking documentation and provides a roadmap for understanding GeistFabrik's performance characteristics across different vault sizes and optimisation strategies.

## Table of Contents

1. [Overview](#overview)
2. [Quick Reference](#quick-reference)
3. [Benchmark Types](#benchmark-types)
4. [Running Benchmarks](#running-benchmarks)
5. [Understanding Results](#understanding-results)
6. [Optimisation Strategies](#optimisation-strategies)
7. [Detailed Results](#detailed-results)

---

## Overview

GeistFabrik includes comprehensive benchmarking infrastructure to:

- **Validate performance** across different vault sizes (10-10,000+ notes)
- **Test optimisation strategies** (algorithmic improvements, sklearn tuning)
- **Ensure correctness** (optimisations must preserve output)
- **Guide configuration** (help users optimise for their vault size)

Key performance targets:
- **Small vaults** (10-100 notes): <5s session time
- **Medium vaults** (100-1,000 notes): <30s session time
- **Large vaults** (1,000-10,000+ notes): <2min session time with optimisations

---

## Quick Reference

### Basic Performance Testing

```bash
# Time a full session on your vault
time uv run geistfabrik invoke ~/my-vault --full

# Test a specific slow geist
uv run geistfabrik test pattern_finder ~/my-vault --timeout 60 --debug

# Get performance stats
uv run geistfabrik stats ~/my-vault
```

### Optimisation Benchmarking

```bash
# Run sklearn optimisation benchmark (72 runs = 8 configs × 9 geists)
python scripts/benchmark_optimizations.py \
  --vault "/path/to/large/vault" \
  --output benchmark_results.json \
  --timeout 120

# Analyze results
python scripts/analyze_benchmarks.py --input benchmark_results.json
```

### Quick Scripts

```bash
# scripts/ directory contains helper scripts
ls scripts/*.py

# See scripts/BENCHMARKS.md for quick reference
cat scripts/BENCHMARKS.md
```

---

## Benchmark Types

### 1. Baseline Performance Benchmarks

**Purpose**: Establish performance baselines on different vault sizes

**Documents**:
- [`10K_VAULT_BENCHMARK.md`](10K_VAULT_BENCHMARK.md) - 10,000 note stress test

**Note**: Historical benchmark files (PERFORMANCE_BENCHMARK.md, LYT_KIT_BENCHMARK.md) have been archived. Performance characteristics are documented in CHANGELOG.md.

**What they measure**:
- Session execution time (sync + embed + geists + filter + output)
- Per-geist execution time and timeout rates
- Memory usage and database size
- Scalability characteristics (O(n) vs O(n²) operations)

**When to use**: Testing on a new vault size or validating baseline performance

### 2. Optimisation Benchmarks

**Purpose**: Validate that optimisations improve performance while preserving correctness

**Documents**:
- [`SKLEARN_OPTIMIZATION_BENCHMARK.md`](SKLEARN_OPTIMIZATION_BENCHMARK.md) - sklearn tuning results

**Note**: Historical optimisation benchmark files have been archived. Optimisation results are documented in CHANGELOG.md.

**What they measure**:
- Speedup percentage (before vs after optimisation)
- Correctness preservation (MD5 hash validation)
- Cache hit rates and memory overhead
- Individual optimisation contributions

**When to use**: After implementing performance improvements, before committing optimisations

### 3. Profiling and Debugging

**Purpose**: Identify performance bottlenecks in specific geists

**Tools**:
- `--debug` flag: Enables cProfile instrumentation
- `scripts/profile_*.py`: Targeted profiling scripts

**Documents**:
- [`docs/GEIST_INSTRUMENTATION_DESIGN.md`](GEIST_INSTRUMENTATION_DESIGN.md) - Profiling system design

**What they measure**:
- Function-level time breakdown
- Hot paths and bottlenecks
- Suggestions for optimisation

**When to use**: Investigating slow geists, debugging timeouts

---

## Running Benchmarks

### Full Session Benchmarks

Test complete session performance including all phases:

```bash
# Basic timing
time uv run geistfabrik invoke ~/my-vault --full

# With profiling
uv run geistfabrik invoke ~/my-vault --full --debug 2>&1 | tee benchmark.log

# Specific date for reproducibility
uv run geistfabrik invoke ~/my-vault --full --date 2025-01-15
```

**Phases measured**:
1. Vault sync (parse changed files)
2. Embedding computation (sentence-transformers)
3. Geist execution (all enabled geists)
4. Filtering (boundary, novelty, diversity, quality)
5. Output generation (session note writing)

### Individual Geist Benchmarks

Test specific geists that are slow or timing out:

```bash
# Test with timeout and profiling
uv run geistfabrik test geist_name ~/my-vault --timeout 60 --debug

# Example: Test pattern_finder on large vault
uv run geistfabrik test pattern_finder /tmp/10k-vault --timeout 120 --debug
```

### Optimisation Benchmarks

Test different optimisation configurations:

```bash
# Run comprehensive sklearn optimisation benchmark
python scripts/benchmark_optimizations.py \
  --vault "/tmp/10000-markdown-files/10000 markdown files/" \
  --output /tmp/sklearn_results.json \
  --timeout 120

# This tests:
# - 8 configurations (baseline + 7 optimisation combinations)
# - 9 geists (6 problem geists + 3 control geists)
# - 72 total runs with correctness validation
```

**Analyze results**:

```bash
python scripts/analyze_benchmarks.py --input /tmp/sklearn_results.json
```

**Output includes**:
- Correctness validation (all configs produce same results)
- Performance comparison (speedup vs baseline)
- Configuration recommendation
- Implementation instructions

### Memory Profiling

```bash
# Check memory usage during session
time uv run python -c "
from geistfabrik.vault import Vault
from geistfabrik.embeddings import Session
from datetime import datetime
import psutil
import os

vault = Vault('~/my-vault')
vault.sync()

process = psutil.Process(os.getpid())
before = process.memory_info().rss / 1024 / 1024

session = Session(datetime.today(), vault.db)
session.compute_embeddings(vault.all_notes())

after = process.memory_info().rss / 1024 / 1024
print(f'Memory increase: {after - before:.1f} MB')
"
```

---

## Understanding Results

### Key Metrics

#### Session Time
Total time from invocation to session note written. Target: <2 minutes for 10k vault.

```
Session completed in 87.3s
  ├─ Sync: 2.1s (2.4%)
  ├─ Embeddings: 45.2s (51.8%)
  ├─ Geists: 38.7s (44.3%)
  ├─ Filtering: 0.9s (1.0%)
  └─ Output: 0.4s (0.5%)
```

#### Geist Execution Time
Individual geist performance. Problem geists are marked with ⚠️.

```
Executing geist: pattern_finder
  ├─ Execution: 12.3s
  └─ Suggestions: 5
```

Timeouts indicate algorithmic inefficiencies or overly complex operations.

#### Speedup Calculation

```
Speedup = baseline_time / optimized_time

Example:
  Baseline: 23.2s avg
  Optimised: 19.4s avg
  Speedup: 1.20x (20% faster)
```

#### Correctness Validation

All optimisation benchmarks validate correctness using MD5 hashes:

```
✅ pattern_finder: consistent across all configs (hash: 56580ef8)
```

If hashes differ, the optimisation has changed behaviour (bug).

### Reading Benchmark Reports

Benchmark documents follow this structure:

1. **Executive Summary**: Key findings and recommendations
2. **Test Environment**: Vault details, system specs, test date
3. **Methodology**: How the test was conducted
4. **Results**: Tables and graphs of measurements
5. **Analysis**: Interpretation of results
6. **Recommendations**: Configuration suggestions

---

## Optimisation Strategies

### 1. Algorithmic Optimisations (BIG OPTIMISATION #1)

**Target**: O(n²) or worse algorithmic inefficiencies

**Examples**:
- Replace `list.remove()` in nested loops with `set.remove()`
- Use dict lookups instead of `list.index()`
- Use set membership instead of list membership

**Impact**: Fixes timeouts, 2-5% overall improvement

**See**: CHANGELOG.md "BIG OPTIMISATION #1"

### 2. Vectorization (BIG OPTIMISATION #2)

**Target**: Manual loop-based similarity calculations

**Examples**:
- Use `sklearn.metrics.pairwise.cosine_similarity` instead of loops
- Use `scipy.spatial.distance.euclidean` instead of `np.linalg.norm`
- Cache redundant norm calculations

**Impact**: 10-15% speedup on geist execution phase

**See**: CHANGELOG.md "BIG OPTIMISATION #2"

### 3. sklearn Configuration Tuning (BIG OPTIMISATION #3)

**Target**: sklearn validation overhead in large vaults

**Optimisations**:
- `assume_finite=True`: Skip NaN/inf checks (21% speedup)
- `force_all_finite=False`: Relax validation
- NumPy array optimisations

**Impact**: 21% speedup on 10k vault, preserves correctness

**See**: [`SKLEARN_OPTIMIZATION_BENCHMARK.md`](SKLEARN_OPTIMIZATION_BENCHMARK.md)

### 4. Caching and Indexing

**Targets**:
- Redundant `vault.notes()` calls
- Repeated similarity computations
- Database queries without indexes

**Examples**:
- Session-scoped cluster caching (75% speedup for cluster_mirror)
- Composite database indexes (85.6% faster orphan queries)
- Batch note loading (66% reduction in query overhead)

**Impact**: 38-46% session speedup, 86.3% cache hit rate

**See**: [`PERFORMANCE_OPTIMIZATION_RESULTS.md`](PERFORMANCE_OPTIMIZATION_RESULTS.md)

---

## Detailed Results

### By Vault Size

- **10,000 notes**: [`10K_VAULT_BENCHMARK.md`](10K_VAULT_BENCHMARK.md)

**Note**: Historical benchmarks for smaller vaults have been archived. See CHANGELOG.md for performance characteristics.

### By Optimisation Phase

**Note**: Historical optimisation phase benchmarks have been archived. See CHANGELOG.md for optimisation results and performance improvements across all phases.

### By Optimisation Type

- **sklearn Tuning**: [`SKLEARN_OPTIMIZATION_BENCHMARK.md`](SKLEARN_OPTIMIZATION_BENCHMARK.md)
- **Profiling System**: [`GEIST_INSTRUMENTATION_DESIGN.md`](GEIST_INSTRUMENTATION_DESIGN.md)

### Scripts Reference

- **Quick command reference**: [`scripts/BENCHMARKS.md`](../scripts/BENCHMARKS.md)
- **Optimisation benchmark**: `scripts/benchmark_optimizations.py`
- **Results analysis**: `scripts/analyze_benchmarks.py`
- **Configuration**: `scripts/benchmark_config.py`

---

## Contributing Performance Improvements

When optimising GeistFabrik:

1. **Establish baseline**: Run benchmarks before changes
2. **Implement optimisation**: Make targeted improvements
3. **Validate correctness**: Ensure outputs haven't changed
4. **Measure impact**: Run benchmarks after changes
5. **Document results**: Update CHANGELOG.md and add benchmark doc
6. **Test edge cases**: Different vault sizes, unusual structures
7. **Add tests**: Unit tests for optimisation logic

**Example workflow**:

```bash
# 1. Baseline
python scripts/benchmark_optimizations.py --vault /tmp/10k-vault \
  --output baseline.json --timeout 120

# 2. Make changes...

# 3. Test optimised version
python scripts/benchmark_optimizations.py --vault /tmp/10k-vault \
  --output optimised.json --timeout 120

# 4. Compare
python scripts/analyze_benchmarks.py --input baseline.json > baseline_report.txt
python scripts/analyze_benchmarks.py --input optimised.json > optimized_report.txt

# 5. Validate
diff baseline_report.txt optimized_report.txt
# Check that suggestion hashes match (correctness)
# Compare timings (performance)

# 6. Document
# Update CHANGELOG.md
# Create docs/MY_OPTIMIZATION_BENCHMARK.md with detailed results
```

---

## Troubleshooting

### Timeouts

**Symptom**: Geist times out (hits timeout limit)

**Diagnosis**:
```bash
uv run geistfabrik test geist_name ~/vault --timeout 120 --debug
```

Look for:
- Nested loops (O(n²) or worse)
- Large list operations (remove, index)
- Redundant computations

**Fix**: Apply algorithmic optimisations or caching

### Memory Issues

**Symptom**: Process killed or swap usage high

**Diagnosis**:
```bash
# Monitor memory during execution
uv run geistfabrik invoke ~/vault --full &
PID=$!
while kill -0 $PID 2>/dev/null; do
  ps -p $PID -o rss=,vsz=
  sleep 5
done
```

**Fix**:
- Use iterators instead of lists where possible
- Clear large temporary data structures
- Consider chunking operations

### Inconsistent Results

**Symptom**: Benchmark results vary significantly between runs

**Causes**:
- Non-deterministic randomness
- Background processes
- Thermal throttling
- Different vault states

**Fix**:
- Use `--date` flag for deterministic randomness
- Close other applications
- Run multiple times and average
- Sync vault before benchmarking

---

## Summary

GeistFabrik's benchmarking suite provides comprehensive performance testing across:

- **Multiple vault sizes** (10 to 10,000+ notes)
- **Different optimisation strategies** (algorithmic, vectorization, configuration tuning)
- **Correctness validation** (MD5 hash verification)
- **Detailed profiling** (function-level breakdown with `--debug`)

**Start here**:
1. Run basic timing: `time uv run geistfabrik invoke ~/vault --full`
2. If too slow, profile: Add `--debug` flag
3. For large vaults (10k+), test optimisations: `scripts/benchmark_optimizations.py`
4. Compare before/after: `scripts/analyze_benchmarks.py`

**Key documents**:
- Quick reference: [`scripts/BENCHMARKS.md`](../scripts/BENCHMARKS.md)
- Comprehensive results: [`PERFORMANCE_OPTIMIZATION_RESULTS.md`](PERFORMANCE_OPTIMIZATION_RESULTS.md)
- sklearn tuning: [`SKLEARN_OPTIMIZATION_BENCHMARK.md`](SKLEARN_OPTIMIZATION_BENCHMARK.md)
- Troubleshooting: [`GEIST_INSTRUMENTATION_DESIGN.md`](GEIST_INSTRUMENTATION_DESIGN.md)
