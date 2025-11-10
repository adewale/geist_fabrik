# GeistFabrik Benchmark Scripts

This directory contains benchmarking tools for GeistFabrik performance testing.

**For comprehensive benchmarking guide, see [`../docs/BENCHMARKING_GUIDE.md`](../docs/BENCHMARKING_GUIDE.md)**

---

## 1. sklearn Optimisation Benchmarks

Test different sklearn configuration optimisations for large vaults (10k+ notes).

### Running Benchmarks

```bash
# Run comprehensive benchmark (8 configs × 9 geists = 72 runs)
python scripts/benchmark_optimizations.py \
  --vault "/path/to/large/vault" \
  --output /tmp/sklearn_results.json \
  --timeout 120

# Analyze results
python scripts/analyze_benchmarks.py --input /tmp/sklearn_results.json
```

### What It Tests

- **8 configurations**: baseline + 7 optimisation combinations
- **9 geists**: 6 problem geists (slow/timeout) + 3 control geists (fast)
- **Correctness validation**: MD5 hash verification
- **Performance analysis**: Speedup calculations, winner recommendation

### Results

See [`../docs/SKLEARN_OPTIMIZATION_BENCHMARK.md`](../docs/SKLEARN_OPTIMIZATION_BENCHMARK.md) for detailed results.

**Key findings**:
- 21% speedup with `assume_finite=True`
- All optimisations preserve correctness
- No timeouts with any configuration

---

## 2. Vector Search Backend Benchmarks

Compare performance of different vector search backends (in-memory vs sqlite-vec).

## Running Benchmarks

```bash
# Default benchmark (100, 500, 1000, 2000 notes with 100 queries each)
python scripts/benchmark_backends.py

# Custom vault sizes
python scripts/benchmark_backends.py --sizes 100,500,1000

# Custom query count
python scripts/benchmark_backends.py --queries 50

# Skip sqlite-vec backend (if not installed)
python scripts/benchmark_backends.py --skip-sqlite-vec
```

## Benchmark Results

Based on synthetic embeddings (387 dimensions) across different vault sizes:

### Vault: 100 notes
- **InMemoryVectorBackend**: 0.18ms load, 0.30ms avg query
- **SqliteVecBackend**: 1.78ms load, 0.17ms avg query
- **Speedup**: SqliteVec is **1.8x faster** for queries

### Vault: 500 notes
- **InMemoryVectorBackend**: 0.51ms load, 1.04ms avg query
- **SqliteVecBackend**: 7.00ms load, 0.13ms avg query
- **Speedup**: SqliteVec is **8.0x faster** for queries

### Vault: 1000 notes
- **InMemoryVectorBackend**: 0.72ms load, 2.00ms avg query
- **SqliteVecBackend**: 18.30ms load, 0.15ms avg query
- **Speedup**: SqliteVec is **13.5x faster** for queries

## Interpretation

**Load Time**: InMemoryVectorBackend loads embeddings faster (simple memcpy from database).
SqliteVecBackend has overhead from creating vec0 virtual table and path mappings.

**Query Time**: SqliteVecBackend scales much better for large vaults due to native SQL
vector operations. Query time stays nearly constant (~0.15ms) regardless of vault size,
while InMemoryVectorBackend shows linear scaling (O(n) cosine similarity).

## Recommendations

- **Small vaults (< 500 notes)**: Use `in-memory` backend (default)
  - Fast load time
  - Query performance acceptable (< 1ms)
  - No additional dependencies

- **Large vaults (> 1000 notes)**: Use `sqlite-vec` backend
  - Significantly faster queries (10-20x)
  - Load overhead amortized across many queries
  - Requires: `uv pip install -e ".[vector-search]"`

- **Medium vaults (500-1000 notes)**: Either backend works
  - InMemory: Simpler, no dependencies
  - SqliteVec: Better query performance

## Configuration

Choose backend in `_geistfabrik/config.yaml`:

```yaml
vector_search:
  backend: in-memory  # or "sqlite-vec"
```

Both backends provide **identical functionality** and are tested for parity.
The only difference is performance characteristics.
