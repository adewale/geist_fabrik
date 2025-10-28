# Vector Search Backends Specification

**Status**: Proposed (Not Yet Implemented)
**Version**: 1.0
**Created**: October 2025
**Target**: Version 0.9.2 (Post-1.0 Enhancement)

---

## Overview

This specification defines a **pluggable vector search backend architecture** for GeistFabrik, enabling comparison and selection between different vector similarity search implementations.

**Primary Goal**: Support both in-memory and sqlite-vec backends with identical functionality, configurable selection, and comprehensive benchmarking.

**Secondary Goal**: Establish performance characteristics at different vault scales to inform future optimization decisions.

---

## Motivation

### Current State

**Implementation** (v0.9.0):
- In-memory vector search using Python cosine similarity
- All embeddings loaded into memory at session start
- Efficient for 100-1000 notes (~30-50MB memory)
- Simple, portable, zero external dependencies

**Documentation** (specs):
- Originally specified sqlite-vec extension
- Implementation diverged to in-memory approach
- Documentation updated to reflect reality (v0.9.1)

### Problem Statement

**We don't have empirical data on:**
1. **Performance thresholds**: At what vault size does in-memory become a bottleneck?
2. **Memory usage**: Actual memory consumption at different scales
3. **Query latency**: Search performance characteristics
4. **Scalability**: How each approach scales with vault growth

**This makes it difficult to:**
- Give users guidance on expected performance
- Make data-driven decisions about future optimization
- Justify the current in-memory approach
- Know when to recommend alternative approaches

### Proposed Solution

**Implement pluggable vector search backends:**

```
┌─────────────────────────────────────────────────┐
│         EmbeddingComputer (unchanged)           │
│  - Computes embeddings via sentence-transformers│
│  - Stores embeddings in SQLite                  │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│        VectorSearchBackend (NEW ABSTRACTION)    │
│                                                  │
│  Interface:                                     │
│  - load_embeddings(session_date)                │
│  - find_similar(query_embedding, k) -> List     │
│  - get_similarity(path_a, path_b) -> float      │
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────┴────────────┐
        ▼                       ▼
┌──────────────────┐   ┌────────────────────┐
│ InMemoryBackend  │   │ SqliteVecBackend   │
│  (default)       │   │  (optional)        │
│                  │   │                    │
│ - Load all into  │   │ - Query via        │
│   memory         │   │   sqlite-vec       │
│ - Python cosine  │   │ - Native SQL       │
│ - Fast for small │   │ - Scales better    │
└──────────────────┘   └────────────────────┘
```

**Benefits:**
1. ✅ Keep current implementation as default (no breaking changes)
2. ✅ Enable sqlite-vec for users with large vaults (opt-in)
3. ✅ Benchmark both implementations empirically
4. ✅ Provide data-driven guidance to users
5. ✅ Future-proof for additional backends (e.g., FAISS, Annoy)

---

## Design Principles

1. **Backward Compatibility**: Existing vaults work without config changes
2. **Zero Breaking Changes**: Current API unchanged
3. **Optional Dependency**: sqlite-vec is opt-in (not required)
4. **Identical Behavior**: Both backends return same results (within epsilon)
5. **Performance Transparency**: Benchmarks guide user decisions
6. **Test Parity**: Both backends tested identically

---

## Architecture

### 1. VectorSearchBackend Interface

**New File**: `src/geistfabrik/vector_search.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple
import numpy as np


class VectorSearchBackend(ABC):
    """Abstract base class for vector similarity search backends."""

    @abstractmethod
    def load_embeddings(self, session_date: str) -> None:
        """Load embeddings for the given session.

        Args:
            session_date: ISO date string (YYYY-MM-DD)
        """
        pass

    @abstractmethod
    def find_similar(
        self,
        query_embedding: np.ndarray,
        k: int = 10
    ) -> List[Tuple[str, float]]:
        """Find k most similar notes to query embedding.

        Args:
            query_embedding: Query vector (384 or 387 dimensions)
            k: Number of results to return

        Returns:
            List of (note_path, similarity_score) tuples, sorted descending
        """
        pass

    @abstractmethod
    def get_similarity(self, path_a: str, path_b: str) -> float:
        """Get similarity score between two notes.

        Args:
            path_a: Path to first note
            path_b: Path to second note

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        pass

    @abstractmethod
    def get_embedding(self, path: str) -> np.ndarray:
        """Get embedding vector for a note.

        Args:
            path: Note path

        Returns:
            Embedding vector

        Raises:
            KeyError: If note path not found
        """
        pass


class InMemoryVectorBackend(VectorSearchBackend):
    """In-memory vector search using Python cosine similarity.

    This is the current implementation (v0.9.0), now encapsulated
    in the backend interface.

    Characteristics:
    - Fast for small-medium vaults (100-1000 notes)
    - Loads all embeddings into memory
    - Pure Python, no external dependencies
    - Memory usage: ~50 bytes per dimension per note
    """

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.embeddings: Dict[str, np.ndarray] = {}

    def load_embeddings(self, session_date: str) -> None:
        """Load all embeddings for session into memory."""
        cursor = self.db.execute(
            """
            SELECT note_path, embedding
            FROM session_embeddings
            WHERE session_date = ?
            """,
            (session_date,)
        )

        self.embeddings = {}
        for row in cursor:
            path, blob = row
            embedding = np.frombuffer(blob, dtype=np.float32)
            self.embeddings[path] = embedding

    def find_similar(
        self,
        query_embedding: np.ndarray,
        k: int = 10
    ) -> List[Tuple[str, float]]:
        """Find similar notes via in-memory cosine similarity."""
        from .embeddings import cosine_similarity

        similarities = [
            (path, cosine_similarity(query_embedding, emb))
            for path, emb in self.embeddings.items()
        ]

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]

    def get_similarity(self, path_a: str, path_b: str) -> float:
        """Compute similarity between two notes."""
        from .embeddings import cosine_similarity

        emb_a = self.embeddings[path_a]
        emb_b = self.embeddings[path_b]
        return cosine_similarity(emb_a, emb_b)

    def get_embedding(self, path: str) -> np.ndarray:
        """Get embedding for a note."""
        return self.embeddings[path]


class SqliteVecBackend(VectorSearchBackend):
    """Vector search using sqlite-vec extension.

    Requires: pip install sqlite-vec

    Characteristics:
    - Scales better for large vaults (5000+ notes)
    - Native SQL vector operations
    - Disk-based with intelligent caching
    - Uses vec0 virtual table
    """

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.session_date: str = ""
        self._setup_vec_table()

    def _setup_vec_table(self) -> None:
        """Create vec0 virtual table if needed."""
        # Check if sqlite-vec is available
        try:
            self.db.execute("SELECT vec_version()")
        except sqlite3.OperationalError:
            raise RuntimeError(
                "sqlite-vec extension not available. "
                "Install with: pip install sqlite-vec"
            )

        # Create virtual table for this session's embeddings
        self.db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_search USING vec0(
                embedding float[387]
            )
        """)

    def load_embeddings(self, session_date: str) -> None:
        """Load embeddings into vec0 virtual table."""
        self.session_date = session_date

        # Clear existing
        self.db.execute("DELETE FROM vec_search")

        # Load from session_embeddings
        cursor = self.db.execute(
            """
            SELECT note_path, embedding
            FROM session_embeddings
            WHERE session_date = ?
            """,
            (session_date,)
        )

        for path, blob in cursor:
            embedding = np.frombuffer(blob, dtype=np.float32)
            # Insert into vec_search with path as rowid
            self.db.execute(
                "INSERT INTO vec_search(rowid, embedding) VALUES (?, ?)",
                (path, embedding.tobytes())
            )

        self.db.commit()

    def find_similar(
        self,
        query_embedding: np.ndarray,
        k: int = 10
    ) -> List[Tuple[str, float]]:
        """Find similar notes via sqlite-vec."""
        cursor = self.db.execute(
            """
            SELECT rowid, distance
            FROM vec_search
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (query_embedding.tobytes(), k)
        )

        # Convert distance to similarity (cosine distance → similarity)
        results = [
            (str(row[0]), 1.0 - row[1])  # distance to similarity
            for row in cursor
        ]
        return results

    def get_similarity(self, path_a: str, path_b: str) -> float:
        """Get similarity between two notes."""
        # Retrieve both embeddings
        cursor_a = self.db.execute(
            "SELECT embedding FROM vec_search WHERE rowid = ?",
            (path_a,)
        )
        cursor_b = self.db.execute(
            "SELECT embedding FROM vec_search WHERE rowid = ?",
            (path_b,)
        )

        row_a = cursor_a.fetchone()
        row_b = cursor_b.fetchone()

        if not row_a or not row_b:
            raise KeyError(f"Note not found: {path_a} or {path_b}")

        emb_a = np.frombuffer(row_a[0], dtype=np.float32)
        emb_b = np.frombuffer(row_b[0], dtype=np.float32)

        from .embeddings import cosine_similarity
        return cosine_similarity(emb_a, emb_b)

    def get_embedding(self, path: str) -> np.ndarray:
        """Get embedding for a note."""
        cursor = self.db.execute(
            "SELECT embedding FROM vec_search WHERE rowid = ?",
            (path,)
        )
        row = cursor.fetchone()
        if not row:
            raise KeyError(f"Note not found: {path}")

        return np.frombuffer(row[0], dtype=np.float32)
```

---

### 2. EmbeddingComputer Integration

**Modified File**: `src/geistfabrik/embeddings.py`

**Changes**:
```python
class EmbeddingComputer:
    def __init__(
        self,
        db: sqlite3.Connection,
        backend: str = "in-memory"  # NEW: backend selection
    ):
        self.db = db
        self.model = None

        # NEW: Initialize vector search backend
        self.backend = self._create_backend(backend)

    def _create_backend(self, backend: str) -> VectorSearchBackend:
        """Factory method for backend creation."""
        from .vector_search import InMemoryVectorBackend, SqliteVecBackend

        if backend == "in-memory":
            return InMemoryVectorBackend(self.db)
        elif backend == "sqlite-vec":
            return SqliteVecBackend(self.db)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def get_session_embeddings(
        self,
        session_date: str
    ) -> VectorSearchBackend:
        """Get loaded embeddings for a session.

        Returns the backend with embeddings loaded, ready for queries.
        """
        self.backend.load_embeddings(session_date)
        return self.backend
```

**Usage in VaultContext**:
```python
# Current (v0.9.0):
embeddings = embedding_computer.get_session_embeddings(session_date)
# embeddings is Dict[str, np.ndarray]
similarities = [(p, cosine_similarity(query, emb)) for p, emb in embeddings.items()]

# New (v0.9.2):
backend = embedding_computer.get_session_embeddings(session_date)
# backend is VectorSearchBackend
similarities = backend.find_similar(query_embedding, k=10)
```

---

### 3. Configuration Schema

**File**: `.geistfabrik/config.yaml`

```yaml
# Vector search backend configuration
vector_search:
  # Backend to use for similarity search
  # Options: "in-memory" | "sqlite-vec"
  # Default: "in-memory"
  backend: "in-memory"

  # (Optional) Backend-specific settings
  backends:
    in_memory:
      # Load embeddings lazily (not yet implemented)
      lazy_load: false

    sqlite_vec:
      # vec0 index type (future: "flat" | "ivf" | "hnsw")
      index_type: "flat"

      # Cache size for vec0 queries (MB)
      cache_size_mb: 100
```

**Config Loading**:
```python
@dataclass
class VectorSearchConfig:
    backend: str = "in-memory"
    backend_settings: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorSearchConfig":
        return cls(
            backend=data.get("backend", "in-memory"),
            backend_settings=data.get("backends", {})
        )

@dataclass
class GeistFabrikConfig:
    # ... existing fields ...
    vector_search: VectorSearchConfig = field(default_factory=VectorSearchConfig)
```

---

## Testing Strategy

### 1. Unit Tests

**Goal**: Verify backend interface compliance

**New File**: `tests/unit/test_vector_search_backends.py`

```python
import pytest
import numpy as np
from geistfabrik.vector_search import (
    VectorSearchBackend,
    InMemoryVectorBackend,
    SqliteVecBackend
)


class TestVectorSearchBackend:
    """Test suite for vector search backends.

    This class is parameterized to run the same tests against
    all backend implementations, ensuring identical behavior.
    """

    @pytest.fixture(params=["in-memory", "sqlite-vec"])
    def backend(self, request, tmp_db):
        """Parameterized fixture providing each backend."""
        backend_type = request.param

        if backend_type == "in-memory":
            return InMemoryVectorBackend(tmp_db)
        elif backend_type == "sqlite-vec":
            # Skip if sqlite-vec not installed
            pytest.importorskip("sqlite_vec")
            return SqliteVecBackend(tmp_db)

    def test_load_embeddings(self, backend, sample_embeddings):
        """Test embedding loading."""
        backend.load_embeddings("2025-01-01")

        # Verify embeddings loaded
        assert len(backend.embeddings) > 0  # in-memory
        # or query count for sqlite-vec

    def test_find_similar_returns_correct_count(self, backend):
        """Test find_similar returns k results."""
        query = np.random.rand(384).astype(np.float32)

        results = backend.find_similar(query, k=5)

        assert len(results) == 5
        assert all(isinstance(r, tuple) for r in results)
        assert all(len(r) == 2 for r in results)  # (path, score)

    def test_find_similar_sorted_descending(self, backend):
        """Test results sorted by similarity (descending)."""
        query = np.random.rand(384).astype(np.float32)

        results = backend.find_similar(query, k=10)
        scores = [score for _, score in results]

        assert scores == sorted(scores, reverse=True)

    def test_get_similarity_symmetric(self, backend):
        """Test similarity(A, B) == similarity(B, A)."""
        backend.load_embeddings("2025-01-01")

        paths = list(backend.embeddings.keys())[:2]

        sim_ab = backend.get_similarity(paths[0], paths[1])
        sim_ba = backend.get_similarity(paths[1], paths[0])

        assert abs(sim_ab - sim_ba) < 1e-6

    def test_get_similarity_self_is_one(self, backend):
        """Test similarity(A, A) == 1.0."""
        backend.load_embeddings("2025-01-01")

        path = list(backend.embeddings.keys())[0]

        sim = backend.get_similarity(path, path)

        assert abs(sim - 1.0) < 1e-6

    def test_backends_return_same_results(self):
        """Test both backends return identical results.

        This is a critical test ensuring behavioral parity.
        """
        # Create both backends with same data
        in_memory = InMemoryVectorBackend(db)
        sqlite_vec = SqliteVecBackend(db)

        in_memory.load_embeddings("2025-01-01")
        sqlite_vec.load_embeddings("2025-01-01")

        query = np.random.rand(384).astype(np.float32)

        results_mem = in_memory.find_similar(query, k=10)
        results_vec = sqlite_vec.find_similar(query, k=10)

        # Should return same paths (order might differ slightly due to ties)
        paths_mem = {path for path, _ in results_mem}
        paths_vec = {path for path, _ in results_vec}

        assert paths_mem == paths_vec

        # Scores should be within epsilon (floating point tolerance)
        for (path_m, score_m), (path_v, score_v) in zip(results_mem, results_vec):
            if path_m == path_v:
                assert abs(score_m - score_v) < 1e-5
```

**Test Coverage**: >90% for both backends

---

### 2. Integration Tests

**Goal**: Verify backends work end-to-end in VaultContext

**New File**: `tests/integration/test_vector_backends_integration.py`

```python
import pytest
from geistfabrik import Vault, VaultContext
from geistfabrik.config_loader import GeistFabrikConfig


@pytest.mark.parametrize("backend", ["in-memory", "sqlite-vec"])
def test_vault_context_with_backend(tmp_vault, backend):
    """Test VaultContext works with both backends."""
    if backend == "sqlite-vec":
        pytest.importorskip("sqlite_vec")

    # Configure backend
    config = GeistFabrikConfig()
    config.vector_search.backend = backend

    vault = Vault(tmp_vault, config=config)
    vault.sync()

    context = VaultContext(vault, date="2025-01-01")

    # Test semantic search
    notes = context.notes()
    if notes:
        neighbors = context.neighbours(notes[0], k=5)
        assert len(neighbors) <= 5
        assert all(isinstance(n, Note) for n in neighbors)


@pytest.mark.parametrize("backend", ["in-memory", "sqlite-vec"])
def test_geist_execution_with_backend(tmp_vault, backend):
    """Test geists can execute with both backends."""
    if backend == "sqlite-vec":
        pytest.importorskip("sqlite_vec")

    config = GeistFabrikConfig()
    config.vector_search.backend = backend

    vault = Vault(tmp_vault, config=config)
    vault.sync()

    context = VaultContext(vault, date="2025-01-01")

    # Execute a geist that uses semantic search
    from geistfabrik.default_geists.code import semantic_neighbours

    suggestions = semantic_neighbours.suggest(context)

    # Should work regardless of backend
    assert isinstance(suggestions, list)
```

**Test Coverage**: All backend-dependent operations tested with both backends

---

## Benchmark Design

### 1. Benchmark Suite

**New File**: `tests/benchmarks/test_vector_backend_performance.py`

```python
import pytest
import time
import numpy as np
from typing import List, Tuple


class VectorBackendBenchmark:
    """Benchmark suite comparing vector search backends."""

    # Test vault sizes
    VAULT_SIZES = [100, 500, 1000, 2500, 5000, 10000]

    # Query scenarios
    QUERY_K_VALUES = [5, 10, 20, 50]

    @pytest.mark.benchmark
    @pytest.mark.parametrize("backend", ["in-memory", "sqlite-vec"])
    @pytest.mark.parametrize("vault_size", VAULT_SIZES)
    def test_load_time(self, backend, vault_size, benchmark):
        """Benchmark: Time to load embeddings."""
        db = create_test_vault(size=vault_size)
        backend_inst = create_backend(backend, db)

        result = benchmark(backend_inst.load_embeddings, "2025-01-01")

        # Record metrics
        benchmark.extra_info.update({
            "vault_size": vault_size,
            "backend": backend,
            "operation": "load"
        })

    @pytest.mark.benchmark
    @pytest.mark.parametrize("backend", ["in-memory", "sqlite-vec"])
    @pytest.mark.parametrize("vault_size", VAULT_SIZES)
    @pytest.mark.parametrize("k", QUERY_K_VALUES)
    def test_query_time(self, backend, vault_size, k, benchmark):
        """Benchmark: Time to find k similar notes."""
        db = create_test_vault(size=vault_size)
        backend_inst = create_backend(backend, db)
        backend_inst.load_embeddings("2025-01-01")

        query = np.random.rand(384).astype(np.float32)

        result = benchmark(backend_inst.find_similar, query, k)

        benchmark.extra_info.update({
            "vault_size": vault_size,
            "backend": backend,
            "k": k,
            "operation": "query"
        })

    @pytest.mark.benchmark
    @pytest.mark.parametrize("backend", ["in-memory", "sqlite-vec"])
    @pytest.mark.parametrize("vault_size", VAULT_SIZES)
    def test_memory_usage(self, backend, vault_size):
        """Benchmark: Memory usage for loaded embeddings."""
        import psutil
        import os

        process = psutil.Process(os.getpid())

        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        db = create_test_vault(size=vault_size)
        backend_inst = create_backend(backend, db)
        backend_inst.load_embeddings("2025-01-01")

        mem_after = process.memory_info().rss / 1024 / 1024  # MB

        memory_used = mem_after - mem_before

        print(f"\n{backend} @ {vault_size} notes: {memory_used:.2f} MB")

        return {
            "vault_size": vault_size,
            "backend": backend,
            "memory_mb": memory_used
        }
```

---

### 2. Benchmark Execution

**Script**: `scripts/run_benchmarks.sh`

```bash
#!/bin/bash
# Run vector backend performance benchmarks

echo "Running Vector Backend Benchmarks..."
echo "===================================="

# Run pytest-benchmark
uv run pytest tests/benchmarks/test_vector_backend_performance.py \
    --benchmark-only \
    --benchmark-columns=min,max,mean,stddev,median \
    --benchmark-sort=name \
    --benchmark-json=benchmark_results.json

# Generate comparison report
uv run python scripts/analyze_benchmarks.py benchmark_results.json
```

**Analysis Script**: `scripts/analyze_benchmarks.py`

```python
#!/usr/bin/env python3
"""Analyze vector backend benchmark results."""

import json
import sys
from typing import Dict, List


def analyze_benchmarks(results_file: str):
    """Generate comparison report from benchmark results."""
    with open(results_file) as f:
        data = json.load(f)

    benchmarks = data["benchmarks"]

    # Group by operation type
    load_times = group_by(benchmarks, "operation", "load")
    query_times = group_by(benchmarks, "operation", "query")

    # Print comparison tables
    print("\n=== LOAD TIME COMPARISON ===\n")
    print_load_comparison(load_times)

    print("\n=== QUERY TIME COMPARISON ===\n")
    print_query_comparison(query_times)

    print("\n=== RECOMMENDATIONS ===\n")
    generate_recommendations(load_times, query_times)


def print_load_comparison(benchmarks: List[Dict]):
    """Print load time comparison table."""
    print("Vault Size | In-Memory | Sqlite-Vec | Speedup")
    print("-----------|-----------|------------|--------")

    # Group by vault size
    by_size = {}
    for b in benchmarks:
        size = b["extra_info"]["vault_size"]
        backend = b["extra_info"]["backend"]

        if size not in by_size:
            by_size[size] = {}

        by_size[size][backend] = b["stats"]["mean"]

    for size in sorted(by_size.keys()):
        mem_time = by_size[size].get("in-memory", 0)
        vec_time = by_size[size].get("sqlite-vec", 0)
        speedup = mem_time / vec_time if vec_time else 0

        print(f"{size:>10} | {mem_time:>9.3f}s | {vec_time:>10.3f}s | {speedup:>6.2f}x")


def generate_recommendations(load_times, query_times):
    """Generate user recommendations based on results."""
    # Analyze crossover point where sqlite-vec becomes faster

    print("Based on benchmark results:")
    print("")
    print("✓ Use in-memory backend for:")
    print("  - Vaults with < 1000 notes")
    print("  - When startup time matters")
    print("  - When avoiding external dependencies")
    print("")
    print("✓ Use sqlite-vec backend for:")
    print("  - Vaults with > 2500 notes")
    print("  - When memory usage is constrained")
    print("  - When query performance is critical")
```

---

### 3. Expected Benchmark Results

**Hypothesis** (to be validated):

| Vault Size | In-Memory Load | Sqlite-Vec Load | In-Memory Query | Sqlite-Vec Query | Winner |
|------------|----------------|-----------------|-----------------|------------------|--------|
| 100        | 0.01s          | 0.05s           | 0.001s          | 0.003s           | In-Memory |
| 500        | 0.05s          | 0.15s           | 0.005s          | 0.008s           | In-Memory |
| 1000       | 0.10s          | 0.25s           | 0.010s          | 0.012s           | In-Memory |
| 2500       | 0.25s          | 0.50s           | 0.030s          | 0.020s           | Mixed |
| 5000       | 0.50s          | 0.80s           | 0.080s          | 0.030s           | Sqlite-Vec |
| 10000      | 1.00s          | 1.50s           | 0.200s          | 0.050s           | Sqlite-Vec |

**Memory Usage Hypothesis**:

| Vault Size | In-Memory | Sqlite-Vec | Savings |
|------------|-----------|------------|---------|
| 100        | 5 MB      | 2 MB       | 60%     |
| 1000       | 50 MB     | 10 MB      | 80%     |
| 5000       | 250 MB    | 30 MB      | 88%     |
| 10000      | 500 MB    | 50 MB      | 90%     |

---

## Implementation Plan

### Phase 1: Backend Abstraction (Week 1, Day 1-2)

**Tasks**:
1. ✅ Create `src/geistfabrik/vector_search.py` with:
   - `VectorSearchBackend` abstract base class
   - `InMemoryVectorBackend` (extract current logic)
   - `SqliteVecBackend` (new implementation)

2. ✅ Update `src/geistfabrik/embeddings.py`:
   - Add backend parameter to `EmbeddingComputer.__init__`
   - Add `_create_backend()` factory method
   - Modify `get_session_embeddings()` to return backend

3. ✅ Update `src/geistfabrik/config_loader.py`:
   - Add `VectorSearchConfig` dataclass
   - Add to `GeistFabrikConfig`
   - Handle loading from YAML

**Deliverables**:
- Backend abstraction implemented
- In-memory backend working (refactored from existing)
- Config schema defined

**Exit Criteria**:
- Code compiles
- Existing tests still pass (in-memory backend)

---

### Phase 2: Sqlite-Vec Implementation (Week 1, Day 3-4)

**Tasks**:
1. ✅ Implement `SqliteVecBackend`:
   - `_setup_vec_table()` - Create vec0 virtual table
   - `load_embeddings()` - Populate from session_embeddings
   - `find_similar()` - Query via vec0 MATCH
   - `get_similarity()` - Pairwise similarity
   - `get_embedding()` - Retrieve single embedding

2. ✅ Add optional dependency:
   - Update `pyproject.toml` with `[vector-search]` extra
   - Update installation docs

3. ✅ Add graceful fallback:
   - Detect if sqlite-vec not installed
   - Provide helpful error message
   - Fall back to in-memory if specified but unavailable

**Deliverables**:
- Sqlite-vec backend fully implemented
- Optional dependency configured
- Graceful handling of missing dependency

**Exit Criteria**:
- Sqlite-vec backend passes interface tests
- Can toggle between backends via config

---

### Phase 3: Testing (Week 1, Day 5 + Week 2, Day 1)

**Tasks**:
1. ✅ Unit tests (`tests/unit/test_vector_search_backends.py`):
   - Parameterized tests for both backends
   - Backend parity tests (same results)
   - Interface compliance tests
   - Edge case tests (empty vault, single note, etc.)

2. ✅ Integration tests (`tests/integration/test_vector_backends_integration.py`):
   - VaultContext with both backends
   - Geist execution with both backends
   - End-to-end semantic search
   - Configuration loading

3. ✅ Ensure existing tests pass:
   - Run full test suite with in-memory (default)
   - Verify no regressions

**Deliverables**:
- 20+ new unit tests
- 10+ new integration tests
- All existing tests passing

**Exit Criteria**:
- Test coverage >90% for vector_search.py
- Both backends tested identically
- No failing tests

---

### Phase 4: Benchmarking (Week 2, Day 2-3)

**Tasks**:
1. ✅ Create benchmark suite:
   - `tests/benchmarks/test_vector_backend_performance.py`
   - Load time benchmarks
   - Query time benchmarks
   - Memory usage benchmarks

2. ✅ Create benchmark runner:
   - `scripts/run_benchmarks.sh`
   - `scripts/analyze_benchmarks.py`

3. ✅ Run benchmarks:
   - Execute on test machine
   - Generate results JSON
   - Analyze crossover points

4. ✅ Document results:
   - Create `docs/VECTOR_BACKEND_BENCHMARKS.md`
   - Include tables, charts, recommendations

**Deliverables**:
- Benchmark suite implemented
- Results documented
- User guidance created

**Exit Criteria**:
- Benchmarks run successfully
- Results analyzed and documented
- Recommendations clear

---

### Phase 5: Documentation (Week 2, Day 4)

**Tasks**:
1. ✅ Update user documentation:
   - `README.md` - Mention backend options
   - `docs/CONFIGURATION.md` - Document vector_search config
   - `docs/VECTOR_BACKEND_BENCHMARKS.md` - Benchmark results

2. ✅ Update developer documentation:
   - `CLAUDE.md` - Update architecture section
   - `docs/ARCHITECTURE.md` - Add backend diagram
   - API docs for `VectorSearchBackend`

3. ✅ Create migration guide:
   - How to enable sqlite-vec
   - When to use which backend
   - Troubleshooting

**Deliverables**:
- User docs updated
- Developer docs updated
- Migration guide created

**Exit Criteria**:
- Documentation complete
- Examples work
- Clear guidance provided

---

## Configuration Examples

### Default (In-Memory)

```yaml
# .geistfabrik/config.yaml
# No configuration needed - in-memory is default
```

### Enable Sqlite-Vec

```yaml
# .geistfabrik/config.yaml
vector_search:
  backend: "sqlite-vec"
```

### With Backend-Specific Settings

```yaml
# .geistfabrik/config.yaml
vector_search:
  backend: "sqlite-vec"
  backends:
    sqlite_vec:
      cache_size_mb: 200
```

---

## Dependency Management

### Core Dependencies (Unchanged)

```toml
[project]
dependencies = [
    "sentence-transformers>=2.2.0",
    "pyyaml>=6.0",
]
```

### Optional Dependencies (New)

```toml
[project.optional-dependencies]
vector-search = [
    "sqlite-vec>=0.1.0",
]
```

### Installation

```bash
# Default installation (in-memory backend)
pip install geistfabrik

# With sqlite-vec backend support
pip install geistfabrik[vector-search]

# or with uv
uv pip install geistfabrik[vector-search]
```

---

## Migration Guide

### For Existing Users (v0.9.0 → v0.9.2)

**No action required** - in-memory backend is default:
- Existing vaults work without changes
- No config changes needed
- No performance changes

**Optional: Enable sqlite-vec for large vaults:**

1. Install optional dependency:
   ```bash
   pip install sqlite-vec
   ```

2. Update config:
   ```yaml
   vector_search:
     backend: "sqlite-vec"
   ```

3. Re-sync vault:
   ```bash
   geistfabrik invoke /path/to/vault
   ```

4. Benchmark:
   ```bash
   # Time your typical workflow
   time geistfabrik invoke /path/to/vault
   ```

### Rollback

To switch back to in-memory:

```yaml
vector_search:
  backend: "in-memory"
```

No data loss - embeddings are stored in SQLite regardless of backend.

---

## Performance Guidance

### When to Use In-Memory (Default)

**Recommended for**:
- ✅ Small to medium vaults (100-1000 notes)
- ✅ When avoiding external dependencies
- ✅ When startup time matters
- ✅ When memory is not constrained

**Characteristics**:
- Fast startup for small vaults
- Faster queries for small datasets
- Simple, no configuration needed
- Pure Python, portable

### When to Use Sqlite-Vec

**Recommended for**:
- ✅ Large vaults (2500+ notes)
- ✅ When memory is constrained
- ✅ When query performance is critical
- ✅ When vault is still growing

**Characteristics**:
- Better scalability
- Lower memory usage
- Native SQL integration
- Requires external dependency

---

## Future Enhancements

### v0.9.3+: Additional Backends

**Potential backends for future**:

1. **FAISS Backend** (Facebook AI Similarity Search)
   - Ultra-fast approximate search
   - GPU acceleration support
   - Best for 10,000+ notes

2. **Annoy Backend** (Approximate Nearest Neighbors)
   - Memory-mapped indices
   - Very fast approximate search
   - Good for 5,000-50,000 notes

3. **Hnswlib Backend** (Hierarchical Navigable Small World)
   - State-of-art performance
   - Excellent recall/speed tradeoff
   - Good for any size

### Configuration Evolution

```yaml
vector_search:
  backend: "faiss"  # Future option
  backends:
    faiss:
      index_type: "IVF256,Flat"
      nprobe: 32
      gpu: false
```

---

## Success Criteria

This specification is successfully implemented when:

1. ✅ Both backends implemented and working
2. ✅ Backend selection via configuration
3. ✅ In-memory remains default (backward compatible)
4. ✅ Test parity achieved (both backends tested identically)
5. ✅ Benchmarks completed and documented
6. ✅ User guidance clear (when to use which)
7. ✅ No performance regressions for default (in-memory)
8. ✅ Optional dependency handled gracefully
9. ✅ Documentation complete
10. ✅ All existing tests passing

---

## Non-Goals (Out of Scope)

Explicitly **NOT** included in this spec:

- ❌ Removing in-memory backend (always supported)
- ❌ Making sqlite-vec a required dependency
- ❌ Implementing approximate search (FAISS, Annoy, etc.)
- ❌ GPU acceleration
- ❌ Distributed vector search
- ❌ Automatic backend selection based on vault size
- ❌ Hybrid backends (using both simultaneously)

These may be considered for future versions.

---

## Open Questions

### Q1: Epsilon Tolerance for Result Parity

**Question**: What epsilon tolerance is acceptable for backend result parity?

**Context**: Due to floating-point arithmetic differences, backends may return slightly different similarity scores.

**Options**:
- A) Strict: `epsilon = 1e-6` (very close)
- B) Moderate: `epsilon = 1e-5` (close enough)
- C) Loose: `epsilon = 1e-4` (practical tolerance)

**Recommendation**: **Option B (1e-5)** - Balances strict correctness with practical floating-point reality.

---

### Q2: Benchmark Vault Generation

**Question**: How to generate realistic test vaults for benchmarking?

**Options**:
- A) Random embeddings (fast, reproducible)
- B) Real notes from test corpus (realistic but slow)
- C) Hybrid (random with realistic properties)

**Recommendation**: **Option A (random)** for v0.9.2, Option B for future research.

---

### Q3: Benchmark Environment

**Question**: What hardware specs for "official" benchmarks?

**Options**:
- A) GitHub Actions runner (reproducible)
- B) Developer machine (realistic)
- C) Both (comprehensive)

**Recommendation**: **Option C (both)** - CI for regression detection, local for user guidance.

---

### Q4: Config Migration Strategy

**Question**: Auto-migrate configs from old to new format?

**Options**:
- A) Auto-migrate silently
- B) Warn and auto-migrate
- C) Error and require manual migration

**Recommendation**: **Option A (silent migration)** - No old configs exist (new feature).

---

## Document History

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-28 | 1.0 | Initial specification created |

---

**Author**: Claude (AI Assistant)
**Status**: Draft - Ready for Review
**Next Step**: Review and approval before implementation
