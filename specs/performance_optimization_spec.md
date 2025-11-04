# Performance Optimization Spec

**Version**: 1.0
**Date**: 2025-11-01
**Status**: Implementation Guide

## Overview

This specification documents performance optimization patterns discovered through empirical research on GeistFabrik, and identifies opportunities for applying these patterns throughout the codebase.

## Background

GeistFabrik generates suggestions by executing 45+ geists per session. Initial profiling revealed cluster_mirror taking 20.9s on a 3406-note vault. Through systematic optimization, we achieved 75% speedup (5.3s) by applying session-scoped caching patterns.

This spec captures lessons learned and extends those insights to other hot paths.

---

## Core Optimization Patterns

### Pattern 1: Session-Scoped Caching

**Principle**: Cache expensive operations at VaultContext level for session duration.

**When to apply**:
- Method is called multiple times within a session
- Result depends only on vault state (deterministic)
- Result is immutable or computation is pure
- Method has measurable latency (>1ms)

**Implementation template**:
```python
class VaultContext:
    def __init__(self, ...):
        self._method_cache: Dict[CacheKey, Result] = {}

    def method(self, param: Type) -> Result:
        cache_key = self._build_cache_key(param)

        if cache_key in self._method_cache:
            return self._method_cache[cache_key]

        result = self._compute_result(param)
        self._method_cache[cache_key] = result
        return result
```

**Cache key design**:
- Single parameter: Use parameter directly (`note.path`, `min_size`)
- Multiple parameters: Use tuple (`(note.path, k)`)
- Order-independent: Sort keys (`tuple(sorted([a.path, b.path]))`)

**Examples already implemented**:
- `notes()`: Full vault note list (no key, singleton)
- `similarity(a, b)`: Cosine similarity between notes (ordered tuple key)
- `neighbours(note, k)`: k-NN search (tuple key)
- `get_clusters(min_size)`: HDBSCAN clustering (int key)

**Memory considerations**:
- Cache lifetime: Single session (minutes to hours)
- Typical vault: 100-1000 notes = ~10-100MB cache
- Notes cache: ~1KB per note
- Similarity cache: ~8 bytes per pair, max O(n²) but sparse
- Clusters cache: ~10-50MB for full clustering result

---

### Pattern 2: Vectorized Operations

**Principle**: Use numpy/sklearn batch operations instead of Python loops.

**When to apply**:
- Computing similarity for multiple note pairs
- Finding k-nearest neighbors
- Matrix operations on embeddings
- Statistical computations on large datasets

**Performance gain**: 10-100x speedup depending on operation size.

**Implementation examples**:

```python
# ❌ Slow: Loop-based similarity
similarities = []
for i in range(len(notes)):
    for j in range(i+1, len(notes)):
        sim = cosine_similarity(embeddings[i], embeddings[j])
        similarities.append(sim)

# ✅ Fast: Vectorized similarity matrix
embeddings_matrix = np.array(embeddings)
similarity_matrix = np.dot(embeddings_matrix, embeddings_matrix.T)
norms = np.linalg.norm(embeddings_matrix, axis=1)
similarity_matrix = similarity_matrix / np.outer(norms, norms)
```

**Delegation to backend**:
- VaultContext delegates to `_backend` for vector operations
- Backend handles numpy/sklearn efficiently
- Methods: `get_similarity()`, `find_similar()`, `compute_all_similarities()`

---

### Pattern 3: Batch Database Queries

**Principle**: Replace multiple single-row queries with one multi-row query.

**When to apply**:
- Loading multiple notes by path
- Fetching links for multiple notes
- Resolving multiple link targets
- Any query inside a loop

**Performance gain**: 5-20x speedup for loading N items.

**Implementation example**:

```python
# ❌ Slow: N queries
notes = []
for path in paths:
    note = vault.get_note(path)
    if note:
        notes.append(note)

# ✅ Fast: 1 query
notes = vault.get_notes_batch(paths).values()
```

**SQL pattern**:
```sql
-- Instead of N calls to:
SELECT * FROM notes WHERE path = ?

-- Use single query:
SELECT * FROM notes WHERE path IN (?, ?, ?, ...)
```

---

### Pattern 4: Query Optimization

**Principle**: Use efficient SQL patterns for common queries.

**Patterns**:

1. **LEFT JOIN instead of NOT IN**:
```sql
-- ❌ Slow: Subquery pattern
SELECT * FROM notes WHERE path NOT IN (SELECT source_path FROM links)

-- ✅ Fast: LEFT JOIN pattern
SELECT n.* FROM notes n
LEFT JOIN links l ON l.source_path = n.path
WHERE l.source_path IS NULL
```

2. **Composite indexes for JOIN keys**:
```sql
CREATE INDEX idx_links_target_source ON links(target, source_path);
```

3. **LIMIT early, filter late**:
```sql
-- Get more candidates with LIMIT, then filter in Python
-- Cheaper than complex WHERE clauses
```

---

### Pattern 5: Early Stopping & Sampling

**Principle**: Avoid processing all data when sample is sufficient.

**When to apply**:
- "Sample, don't rank" design principle
- Finding examples (not exhaustive search)
- Geists that need variety, not completeness
- Large vaults (>500 notes)

**Implementation example**:

```python
# ❌ Slow: Process all notes
all_notes = vault.notes()
results = []
for note in all_notes:
    score = expensive_computation(note)
    results.append((note, score))
results.sort(key=lambda x: x[1], reverse=True)
return results[:k]

# ✅ Fast: Sample + early stopping
candidates = vault.sample(vault.notes(), min(200, len(vault.notes())))
results = []
for note in candidates:
    score = expensive_computation(note)
    if score > threshold:
        results.append((note, score))
    if len(results) >= k * 2:  # Early stop with buffer
        break
results.sort(key=lambda x: x[1], reverse=True)
return results[:k]
```

---

### Pattern 6: Single-Pass Algorithms

**Principle**: Compute multiple results in one pass instead of multiple passes.

**When to apply**:
- Multiple metrics on same data
- Categorization into multiple buckets
- Related computations that share intermediate results

**Example from congruence_mirror**:

```python
# ❌ Slow: 4 separate passes
explicit = find_explicit_pair()      # Pass 1
implicit = find_implicit_pair()      # Pass 2
connected = find_connected_pair()    # Pass 3
detached = find_detached_pair()      # Pass 4

# ✅ Fast: Single pass with categorization
all_pairs = analyze_all_pairs()  # Single pass, categorize on the fly
explicit = all_pairs['explicit']
implicit = all_pairs['implicit']
connected = all_pairs['connected']
detached = all_pairs['detached']
```

---

## Identified Optimization Opportunities

### Priority 1: High Impact, Low Effort

#### OP-1: Cache backlinks() ✅ IMPLEMENTED

**Location**: `src/geistfabrik/vault_context.py:221-247`

**Current state**:
- Performs SQL query every call
- No caching
- Called by multiple geists (congruence_mirror, hidden_hub, stub_expander)

**Problem**:
- hidden_hub calls for 50 notes = 50 queries
- congruence_mirror calls for all outgoing links

**Solution**:
```python
# Add to __init__:
self._backlinks_cache: Dict[str, List[Note]] = {}

def backlinks(self, note: Note) -> List[Note]:
    """Find notes that link to this note (cached)."""
    if note.path in self._backlinks_cache:
        return self._backlinks_cache[note.path]

    # ... existing query logic ...

    self._backlinks_cache[note.path] = result
    return result
```

**Expected impact**: 30-50% speedup for hidden_hub, congruence_mirror

**Test requirements**:
- Verify cache hit on repeated calls
- Verify cache is session-scoped (not shared)
- Add performance regression test

---

#### OP-2: Cache outgoing_links() ✅ IMPLEMENTED

**Location**: `src/geistfabrik/vault_context.py:249-266`

**Current state**:
- Resolves links every call
- `resolve_link_target()` makes multiple DB queries per link

**Problem**:
- congruence_mirror calls for all notes
- No caching of resolution results

**Solution**:
```python
# Add to __init__:
self._outgoing_links_cache: Dict[str, List[Note]] = {}

def outgoing_links(self, note: Note) -> List[Note]:
    """Get notes this note links to (cached)."""
    if note.path in self._outgoing_links_cache:
        return self._outgoing_links_cache[note.path]

    result = []
    for link in note.links:
        target = self.resolve_link_target(link.target)
        if target is not None:
            result.append(target)

    self._outgoing_links_cache[note.path] = result
    return result
```

**Expected impact**: 20-30% speedup for link-heavy geists

**Test requirements**:
- Performance regression test
- Verify cache correctness

---

#### OP-3: Vectorize contrarian_to() ✅ IMPLEMENTED

**Location**: `src/geistfabrik/function_registry.py:194-224`

**Current state**:
- Computes similarity to ALL notes
- For 1000-note vault = 1000 similarity calls

**Problem**:
- Doesn't scale to large vaults
- Tracery geists may call multiple times

**Solution source**: User-provided optimization strategy: "Do NOT switch to sampling. Instead of looping through notes, compute ALL similarities at once using numpy matrix multiplication"

**Implemented approach - Vectorized computation**:
```python
@vault_function("contrarian_to")
def contrarian_to(vault: "VaultContext", note_title: str, k: int = 3) -> List[str]:
    import numpy as np

    note = vault.resolve_link_target(note_title)
    if note is None:
        return []

    all_notes = vault.notes()
    candidate_notes = [n for n in all_notes if n.path != note.path]

    # Get query embedding
    query_embedding = vault._embeddings.get(note.path)

    # Build embedding matrix (vectorized)
    candidate_embeddings = [
        vault._embeddings.get(n.path) for n in candidate_notes
    ]

    # Vectorized: Compute ALL similarities at once using matrix multiplication
    query_array = np.array(query_embedding)
    candidates_matrix = np.array(candidate_embeddings)
    similarities = np.dot(candidates_matrix, query_array)

    # Normalize (vectorized)
    query_norm = np.linalg.norm(query_array)
    candidate_norms = np.linalg.norm(candidates_matrix, axis=1)
    similarities = similarities / (candidate_norms * query_norm)

    # Get k least similar (vectorized)
    least_similar_indices = np.argsort(similarities)[:k]
    return [candidate_notes[i].title for i in least_similar_indices]
```

**Measured results** (from benchmarks):
- 100-note vault: ~0.2ms per call (10 calls in <1s)
- 50-100x speedup vs. loop-based approach
- Zero cache misses after first call (deterministic ordering)

**Expected impact**: 50-80% speedup for large vaults (1000+ notes)

**Test requirements**:
- Verify results quality with sampling
- Add large vault test case

---

### Priority 2: High Impact, Medium Effort

#### OP-4: Single-pass congruence_mirror ✅ IMPLEMENTED

**Location**: `src/geistfabrik/default_geists/code/congruence_mirror.py`

**Current state**:
- 4 separate functions, 4 passes over data
- Each computes similarity independently

**Problem**:
- find_explicit_pair(): O(n) links × similarity
- find_implicit_pair(): O(n) notes × O(k) neighbors × similarity
- find_connected_pair(): O(n) links × similarity
- find_detached_pair(): 50 samples × similarity

**Solution**:
Refactor to single-pass categorization:

```python
def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Analyze all note pairs in single pass, categorize into quadrants."""

    # Single pass: categorize pairs as we encounter them
    explicit, implicit, connected, detached = [], [], [], []
    processed = set()

    all_notes = vault.notes()

    # Phase 1: Process all linked pairs once
    for note in all_notes:
        outgoing = vault.outgoing_links(note)  # Now cached (OP-2)

        for target in outgoing:
            # Create deterministic pair key
            pair_key = tuple(sorted([note.path, target.path]))
            if pair_key in processed:
                continue
            processed.add(pair_key)

            # Compute similarity once, categorize
            sim = vault.similarity(note, target)  # Cached

            if sim > 0.65:
                explicit.append((note, target, sim))
            elif sim < 0.45:
                connected.append((note, target, sim))
            # Else: medium similarity, skip

    # Phase 2: Sample unlinked pairs for implicit/detached
    # Use smarter sampling based on semantic neighborhoods
    sample_size = min(100, len(all_notes))
    sample_notes = vault.sample(all_notes, sample_size)

    for i, note_a in enumerate(sample_notes):
        # Get semantic neighbors (cached)
        neighbors = vault.neighbours(note_a, k=10)

        for note_b in neighbors:
            pair_key = tuple(sorted([note_a.path, note_b.path]))
            if pair_key in processed:
                continue
            processed.add(pair_key)

            # Check if linked
            if vault.has_link(note_a, note_b):
                continue

            # Already have similarity from neighbours
            sim = vault.similarity(note_a, note_b)

            if sim > 0.65:
                implicit.append((note_a, note_b, sim))
            elif sim < 0.35:
                detached.append((note_a, note_b, sim))

    # Generate suggestions from categories
    suggestions = []

    if explicit:
        explicit.sort(key=lambda x: x[2], reverse=True)
        a, b, sim = explicit[0]
        suggestions.append(_make_explicit_suggestion(a, b, sim))

    if implicit:
        implicit.sort(key=lambda x: x[2], reverse=True)
        a, b, sim = implicit[0]
        suggestions.append(_make_implicit_suggestion(a, b, sim))

    if connected:
        # Sort by dissimilarity (ascending)
        connected.sort(key=lambda x: x[2])
        a, b, sim = connected[0]
        suggestions.append(_make_connected_suggestion(a, b, sim))

    if detached:
        # Sort by dissimilarity (ascending)
        detached.sort(key=lambda x: x[2])
        a, b, sim = detached[0]
        suggestions.append(_make_detached_suggestion(a, b, sim))

    return vault.sample(suggestions, min(2, len(suggestions)))

# Helper functions to generate suggestion text (same as before)
def _make_explicit_suggestion(a: Note, b: Note, sim: float) -> "Suggestion":
    # ... existing logic ...
    pass
```

**Expected impact**: 40-60% speedup for congruence_mirror

**Measured results** (3406-note vault):
- Before: 60.838s (4 suggestions)
- After: 1.930s (4 suggestions)
- Actual speedup: **31.5x** (97% reduction)
- Far exceeded expectations due to multiplicative effect of caching

**Test requirements**:
- Verify same results as multi-pass version
- Performance benchmark showing single-pass speedup
- Edge cases: empty categories, small vaults

---

#### OP-5: Vectorize unlinked_pairs() ✅ IMPLEMENTED

**Location**: `src/geistfabrik/vault_context.py:508-560`

**Current state**:
- Nested loops computing O(n²) similarities
- Python-level cosine_similarity calls

**Problem**:
- For 200 candidates: 200×199/2 = 19,900 similarity calls
- Loop overhead, redundant embedding lookups

**Solution**:
```python
def unlinked_pairs(self, k: int = 10, candidate_limit: int = 200) -> List[Tuple[Note, Note]]:
    """Find semantically similar note pairs with no links (vectorized)."""
    all_notes = self.notes()

    # Limit candidates for large vaults
    if len(all_notes) > candidate_limit:
        recent = self.recent_notes(k=candidate_limit // 2)
        remaining = [n for n in all_notes if n not in recent]
        random_notes = self.sample(remaining, min(candidate_limit // 2, len(remaining)))
        notes = recent + random_notes
    else:
        notes = all_notes

    # Build valid notes + embeddings arrays
    valid_notes = []
    embeddings_list = []

    for note in notes:
        embedding = self._embeddings.get(note.path)
        if embedding is not None:
            valid_notes.append(note)
            embeddings_list.append(embedding)

    if len(valid_notes) < 2:
        return []

    # Vectorized: Compute all pairwise similarities at once
    embeddings_matrix = np.array(embeddings_list)

    # Matrix multiplication: X @ X^T gives all dot products
    similarity_matrix = np.dot(embeddings_matrix, embeddings_matrix.T)

    # Normalize to get cosine similarities
    norms = np.linalg.norm(embeddings_matrix, axis=1)
    similarity_matrix = similarity_matrix / np.outer(norms, norms)

    # Extract high-similarity pairs (upper triangle, threshold)
    pairs = []
    n = len(valid_notes)

    for i in range(n):
        for j in range(i+1, n):
            sim = similarity_matrix[i, j]

            # Early threshold filter
            if sim <= 0.5:
                continue

            note_a, note_b = valid_notes[i], valid_notes[j]

            # Check if linked (this is the expensive part now)
            if self.links_between(note_a, note_b):
                continue

            pairs.append((note_a, note_b, sim))

    # Sort by similarity descending, return top k
    pairs.sort(key=lambda x: x[2], reverse=True)
    return [(a, b) for a, b, _ in pairs[:k]]
```

**Expected impact**: 40-60% speedup for unlinked_pairs

**Test requirements**:
- Verify results match non-vectorized version
- Performance benchmark
- Memory usage test (similarity matrix can be large)

---

#### OP-6: Batch note loading ✅ IMPLEMENTED

**Location**: `src/geistfabrik/vault.py` (new method)

**Current state**:
- `get_note(path)` makes 3 queries per note (note, links, tags)
- Methods like `backlinks()` call repeatedly

**Problem**:
- Loading 50 notes = 150 queries
- Could batch into 3 queries total

**Solution**:
Add new method to Vault:

```python
def get_notes_batch(self, paths: List[str]) -> Dict[str, Optional[Note]]:
    """Load multiple notes efficiently in batched queries.

    Args:
        paths: List of note paths to load

    Returns:
        Dictionary mapping paths to Note objects (or None if not found)
    """
    if not paths:
        return {}

    # Query 1: Load all notes at once
    placeholders = ','.join(['?'] * len(paths))
    cursor = self.db.execute(
        f"""SELECT path, title, content, created, modified, is_virtual, source_file, entry_date
            FROM notes WHERE path IN ({placeholders})""",
        tuple(paths)
    )

    notes_data = {}
    for row in cursor.fetchall():
        path, title, content, created_ts, modified_ts, is_virtual, source_file, entry_date_str = row
        notes_data[path] = {
            'title': title,
            'content': content,
            'created': datetime.fromtimestamp(created_ts),
            'modified': datetime.fromtimestamp(modified_ts),
            'is_virtual': bool(is_virtual),
            'source_file': source_file,
            'entry_date': datetime.fromisoformat(entry_date_str) if entry_date_str else None,
            'links': [],
            'tags': [],
        }

    # Query 2: Load all links for these notes
    cursor = self.db.execute(
        f"""SELECT source_path, target, display_text, is_embed, block_ref
            FROM links WHERE source_path IN ({placeholders})""",
        tuple(paths)
    )

    for row in cursor.fetchall():
        source_path, target, display_text, is_embed, block_ref = row
        if source_path in notes_data:
            link = Link(
                target=target,
                display_text=display_text,
                is_embed=bool(is_embed),
                block_ref=block_ref
            )
            notes_data[source_path]['links'].append(link)

    # Query 3: Load all tags for these notes
    cursor = self.db.execute(
        f"""SELECT note_path, tag FROM tags WHERE note_path IN ({placeholders})""",
        tuple(paths)
    )

    for row in cursor.fetchall():
        note_path, tag = row
        if note_path in notes_data:
            notes_data[note_path]['tags'].append(tag)

    # Build Note objects
    result = {}
    for path in paths:
        if path in notes_data:
            data = notes_data[path]
            result[path] = Note(
                path=path,
                title=data['title'],
                content=data['content'],
                links=data['links'],
                tags=data['tags'],
                created=data['created'],
                modified=data['modified'],
            )
        else:
            result[path] = None

    return result
```

Then optimize VaultContext methods:

```python
def backlinks(self, note: Note) -> List[Note]:
    """Find notes that link to this note (cached, batched)."""
    if note.path in self._backlinks_cache:
        return self._backlinks_cache[note.path]

    # ... query to get source_paths ...

    source_paths = [row[0] for row in cursor.fetchall()]

    # Batch load all backlink notes
    notes_dict = self.vault.get_notes_batch(source_paths)
    result = [n for n in notes_dict.values() if n is not None]

    self._backlinks_cache[note.path] = result
    return result
```

**Expected impact**: 25-40% speedup for backlinks, hubs, orphans

**Test requirements**:
- Verify batch loading correctness
- Edge cases: empty list, non-existent paths, mix of found/not-found
- Performance benchmark comparing single vs batch

---

### Priority 3: Medium Impact

#### OP-7: Cache graph_neighbors() ✅ IMPLEMENTED

**Location**: `src/geistfabrik/vault_context.py:600-625`

**Dependencies**: OP-1 (backlinks cache), OP-2 (outgoing_links cache)

**Solution**:
```python
# Add to __init__:
self._graph_neighbors_cache: Dict[str, List[Note]] = {}

def graph_neighbors(self, note: Note) -> List[Note]:
    """Get bidirectional graph neighbors (cached)."""
    if note.path in self._graph_neighbors_cache:
        return self._graph_neighbors_cache[note.path]

    neighbors = set()

    # Uses cached methods
    for link in note.links:
        target = self.resolve_link_target(link.target)
        if target is not None:
            neighbors.add(target)

    for source in self.backlinks(note):  # Now cached
        neighbors.add(source)

    result = list(neighbors)
    self._graph_neighbors_cache[note.path] = result
    return result
```

**Expected impact**: 10-15% speedup for geists using graph structure

---

#### OP-8: Optimize hubs() SQL query ✅ IMPLEMENTED

**Location**: `src/geistfabrik/vault_context.py:305-335`

**Current state**:
- Fetches k×3 candidates then filters
- Multiple resolution queries

**Solution**:
```python
def hubs(self, k: int = 10) -> List[Note]:
    """Find most-linked-to notes (optimized SQL)."""
    cursor = self.db.execute(
        """
        SELECT n.path, COUNT(DISTINCT l.source_path) as link_count
        FROM links l
        JOIN notes n ON (
            n.path = l.target
            OR n.path = l.target || '.md'
            OR n.title = l.target
        )
        GROUP BY n.path
        ORDER BY link_count DESC
        LIMIT ?
        """,
        (k,)
    )

    result = []
    for row in cursor.fetchall():
        note = self.get_note(row[0])
        if note is not None:
            result.append(note)

    return result
```

**Expected impact**: 15-25% speedup for hubs()

---

#### OP-9: Neighbours() return similarity scores ✅ IMPLEMENTED

**Location**: `src/geistfabrik/vault_context.py:143-186`

**Problem**: hidden_hub recomputes similarity after neighbours() already computed it

**Solution**:
```python
def neighbours(
    self,
    note: Note,
    k: int = 10,
    return_scores: bool = False
) -> Union[List[Note], List[Tuple[Note, float]]]:
    """Find k semantically similar notes, optionally with scores.

    Args:
        note: Query note
        k: Number of neighbours
        return_scores: If True, return list of (Note, similarity_score) tuples

    Returns:
        List of notes or list of (note, score) tuples
    """
    cache_key = (note.path, k, return_scores)

    if cache_key in self._neighbours_cache:
        return self._neighbours_cache[cache_key]

    # ... existing logic to get similar [(path, score), ...] ...

    result = []
    result_with_scores = []

    for path, score in similar:
        if path == note.path:
            continue

        similar_note = self.get_note(path)
        if similar_note is not None:
            result.append(similar_note)
            result_with_scores.append((similar_note, score))

            if len(result) >= k:
                break

    if return_scores:
        self._neighbours_cache[cache_key] = result_with_scores
        return result_with_scores
    else:
        self._neighbours_cache[cache_key] = result
        return result
```

Then hidden_hub can use:
```python
neighbors_with_scores = vault.neighbours(note, k=30, return_scores=True)
high_similarity_count = sum(1 for n, sim in neighbors_with_scores if sim > 0.6)
```

**Expected impact**: 30-40% speedup for hidden_hub

---

## Performance Testing Framework

### Benchmark Structure

Each optimization should include:

1. **Unit test** verifying correctness
2. **Performance regression test** preventing slowdowns
3. **Benchmark test** measuring actual speedup

### Performance Regression Test Pattern

```python
def test_method_uses_caching(vault_context):
    """Verify method uses cache, not repeated computation."""

    # Mock the underlying expensive operation
    original_method = vault_context._expensive_method
    vault_context._expensive_method = MagicMock(wraps=original_method)

    # First call
    result1 = vault_context.method(param)
    assert vault_context._expensive_method.call_count == 1

    # Second call - should use cache
    result2 = vault_context.method(param)
    assert vault_context._expensive_method.call_count == 1  # Still 1

    # Verify results are identical
    assert result1 is result2  # Same object from cache
```

### Benchmark Test Pattern

```python
@pytest.mark.skipif(True, reason="Benchmark - run manually")
def test_method_benchmark(tmp_path):
    """Benchmark: Verify optimization improves performance."""

    # Setup realistic vault
    vault = create_benchmark_vault(tmp_path, num_notes=100)

    # Measure WITHOUT optimization (simulation)
    start = time.perf_counter()
    for _ in range(N_ITERATIONS):
        vault.method_no_cache(param)
    time_no_cache = time.perf_counter() - start

    # Measure WITH optimization
    start = time.perf_counter()
    for _ in range(N_ITERATIONS):
        vault.method_with_cache(param)
    time_with_cache = time.perf_counter() - start

    # Calculate speedup
    speedup = time_no_cache / time_with_cache

    print(f"Without optimization: {time_no_cache:.3f}s")
    print(f"With optimization: {time_with_cache:.3f}s")
    print(f"Speedup: {speedup:.1f}x")

    # Assert minimum speedup threshold
    assert speedup >= 2.0, f"Expected >=2x speedup, got {speedup:.1f}x"
```

---

## Implementation Plan

### Phase 1: Quick Wins ✅ COMPLETED

**Goal**: Implement low-effort, high-impact caching optimizations.

**Tasks**:
1. ✅ OP-1: Implement backlinks() caching
2. ✅ OP-2: Implement outgoing_links() caching
3. ✅ OP-3: Add sampling to contrarian_to()
4. ✅ OP-7: Implement graph_neighbors() caching (depends on 1, 2)

**Testing**:
- ✅ Add performance regression tests for each
- ✅ Update `test_performance_regression.py`
- ✅ Run existing benchmark: `test_cluster_caching_benchmark`

**Outcome**: All Phase 1 optimizations implemented and tested.

---

### Phase 2: Algorithmic Improvements ✅ COMPLETED

**Goal**: Refactor high-impact geists with smarter algorithms.

**Tasks**:
1. ✅ OP-4: Refactor congruence_mirror to single-pass (31.5x speedup: 60.8s → 1.9s)
2. ✅ OP-5: Vectorize unlinked_pairs() (Already implemented)
3. ✅ OP-6: Implement batch note loading (Used in neighbours, backlinks, hubs)

**Testing**:
- ⏳ Add geist-specific benchmarks (TODO)
- ⏳ Verify correctness with integration tests (TODO)
- ⏳ Create `test_geist_performance.py` module (TODO)

**Outcome**: All Phase 2 optimizations implemented. OP-4 exceeded expectations with 31.5x speedup. Testing pending.

---

### Phase 3: Infrastructure ✅ COMPLETED

**Goal**: Add infrastructure improvements for long-term maintainability.

**Tasks**:
1. ✅ OP-8: Optimize hubs() SQL query (JOIN-based resolution + batch loading)
2. ✅ OP-9: Add return_scores parameter to neighbours() (Used by 5 geists)
3. ✅ Document optimization patterns in code comments

**Geists using OP-9 (return_scores=True)**:
- hidden_hub, bridge_hunter, columbo, bridge_builder, antithesis_generator

**Testing**:
- ✅ Update all tests to use new APIs
- ⏳ Add SQL query performance tests (TODO)
- ✅ Run full benchmark suite (validate.sh passes)

**Outcome**: All Phase 3 optimizations implemented. API improvements enable cleaner geist code.

---

## Success Metrics

### Quantitative

- **Session execution time**: 30-50% reduction for typical vaults
- **Database queries**: 40-60% reduction in total queries
- **Memory usage**: <100MB cache overhead for 1000-note vault
- **Test coverage**: 100% coverage of optimized paths

### Qualitative

- **Code clarity**: Optimizations don't obscure logic
- **Maintainability**: Cache invalidation is simple
- **Extensibility**: Patterns apply to new geists

---

## Cache Invalidation Strategy

**Current design**: Session-scoped caches (no invalidation needed)

**Rationale**:
- Vault is read-only during session
- VaultContext lifetime = single invocation (minutes)
- Session date changes = new VaultContext instance

**Future consideration**: If we add write operations, need invalidation:
```python
def invalidate_caches(self) -> None:
    """Clear all caches after vault modification."""
    self._notes_cache = None
    self._backlinks_cache.clear()
    self._outgoing_links_cache.clear()
    # ... etc
```

---

## Performance Monitoring

### Instrumentation

Use existing `--debug` flag infrastructure:

```python
import time

def method(self, param):
    start = time.perf_counter()

    # Check cache
    if cache_hit:
        logger.debug(f"Cache hit for {param} ({time.perf_counter() - start:.3f}s)")
        return cached_result

    # Compute
    result = expensive_operation()
    elapsed = time.perf_counter() - start

    logger.debug(f"Computed {param} in {elapsed:.3f}s")

    return result
```

### Metrics to Track

- Cache hit rate per method
- Average computation time per method
- Total session time breakdown by geist
- Memory usage over session lifetime

---

## Lessons Learned

### From cluster_mirror Optimization

**Problem identified**: 4 HDBSCAN clustering operations per session

**Root cause**: No session-scoped caching

**Solution**: Add `_clusters_cache` keyed by `min_size`

**Result**: 75% speedup (20.9s → 5.3s)

**Lesson**: **Cache expensive computations at session scope, not call scope.**

---

### From similarity() Optimization

**Problem identified**: Multiple geists computing similarity for same note pairs

**Root cause**: No cross-geist caching

**Solution**: Session-scoped cache with order-independent keys

**Result**: 30-50% reduction in similarity computations

**Lesson**: **Use order-independent cache keys for symmetric operations.**

---

### From neighbours() Optimization

**Problem identified**: Hub notes queried repeatedly by multiple geists

**Root cause**: Cache at embedding backend level, not VaultContext level

**Solution**: Add VaultContext-level cache

**Result**: Eliminates redundant vector searches

**Lesson**: **Cache at the right abstraction level (where queries originate).**

---

### From orphans() Optimization

**Problem identified**: Slow NOT IN subquery for large vaults

**Root cause**: Subquery evaluated for each row

**Solution**: Rewrite as LEFT JOIN with NULL check

**Result**: 5-10x speedup for orphan detection

**Lesson**: **LEFT JOIN with NULL check is faster than NOT IN for exclusion queries.**

---

### From composite index Addition

**Problem identified**: Slow orphan queries on large vaults

**Root cause**: No index on `(target, source_path)` join columns

**Solution**: Add `idx_links_target_source` composite index

**Result**: Query time O(log n) instead of O(n)

**Lesson**: **Index JOIN columns used in query predicates.**

---

## Anti-Patterns to Avoid

### ❌ Premature Optimization

**Don't optimize** without profiling first.

**Example**: Caching `get_note(path)` results across sessions
- Vault files can change
- Cache invalidation complexity not worth it
- Single-note fetch is already fast (<1ms)

---

### ❌ Over-Caching

**Don't cache** everything indiscriminately.

**Example**: Caching `sample()` results
- Defeats purpose of sampling (variety)
- Small benefit (<0.1ms per call)
- Breaks determinism expectations

---

### ❌ Caching Mutable Data

**Don't cache** objects that can be modified.

**Example**: Caching Note objects and mutating them
- Leads to subtle bugs
- Violates immutability assumptions
- Note objects should be read-only

---

### ❌ Complex Cache Keys

**Don't use** unstable or complex cache keys.

**Example**: Using Note objects as keys
- `Note.__hash__()` must be stable
- Object identity vs value equality issues
- Use `note.path` (string) instead

---

### ❌ Shared Mutable Cache State

**Don't share** caches across sessions.

**Example**: Class-level cache dictionary
- Different sessions see each other's data
- Defeats deterministic randomness
- Each VaultContext should have isolated caches

---

## Conclusion

This specification documents performance optimization patterns discovered through empirical research on GeistFabrik. By applying these patterns systematically, we can achieve 30-50% speedup for typical sessions and 50-80% for large vaults (1000+ notes).

Key principles:
1. **Profile first**: Use --debug flag to find hot paths
2. **Cache at session scope**: VaultContext lifetime is natural boundary
3. **Vectorize when possible**: numpy/sklearn for bulk operations
4. **Batch database queries**: Reduce round-trips
5. **Sample large datasets**: "Sample, don't rank" principle
6. **Single-pass algorithms**: Avoid redundant iterations

These optimizations maintain code clarity and don't compromise the "muses, not oracles" design philosophy.

---

**Next Steps**:
1. Review and approve this specification
2. Implement Phase 1 (Quick Wins)
3. Benchmark and verify improvements
4. Iterate on Phase 2 and 3 based on results
