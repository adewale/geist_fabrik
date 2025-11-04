# GeistFabrik Phase 3: Performance Optimization Plan

This plan implements four major optimizations in sequence, each validated with unit tests and benchmarked before committing. Expected gains: 60-75% total runtime reduction on 10k vault (247s → ~62-90s).

---

## BIG OPTIMIZATION #1: Fix O(N²) Algorithmic Inefficiencies

**Replace list operations with O(1) dict/set alternatives**

**This fixes pattern_finder timeout on 10k vault!**

### All 6 O(N²) Patterns:

#### stats.py (3 occurrences):

1. **Line 591** - `_compute_vault_drift()`:
   ```python
   # BEFORE: O(N²) - list.index() in comprehension
   curr_aligned = np.vstack([curr_emb[curr_paths.index(p)] for p in common_paths])

   # AFTER: O(N) - dict lookup
   path_to_idx = {p: i for i, p in enumerate(curr_paths)}
   curr_aligned = np.vstack([curr_emb[path_to_idx[p]] for p in common_paths])
   ```

2. **Line 973** - `_mmr_diversify()`:
   ```python
   # BEFORE: O(k*N²) - list.index() in nested loops
   for term in remaining:
       term_idx = terms.index(term)

   # AFTER: O(k*N) - dict lookup
   term_to_idx = {t: i for i, t in enumerate(terms)}
   # ... in loop: term_idx = term_to_idx[term]
   ```

3. **Line 966** - `_mmr_diversify()`:
   ```python
   # BEFORE: O(k*N) - list membership in loop
   while len(selected) < k:
       remaining = [t for t in terms if t not in selected]

   # AFTER: O(k) - set membership
   selected_set = set()
   while len(selected_set) < k:
       remaining = [t for t in terms if t not in selected_set]
   ```

#### pattern_finder.py (2 occurrences - **TIMEOUT CULPRIT**):

4-5. **Lines 88, 95** - Clustering loop:
   ```python
   # BEFORE: O(N³) - list.remove() in nested loops
   unclustered = list(notes)
   while len(unclustered) > 5:
       seed = vault.sample(unclustered, k=1)[0]
       unclustered.remove(seed)  # O(N) search + remove

       for note in unclustered[:]:
           if vault.similarity(seed, note) > 0.7:
               unclustered.remove(note)  # O(N) in nested loop

   # AFTER: O(N²) - set.remove()
   unclustered_set = set(notes)
   while len(unclustered_set) > 5:
       seed = vault.sample(list(unclustered_set), k=1)[0]
       unclustered_set.remove(seed)  # O(1)

       cluster = [seed]
       to_remove = []
       for note in list(unclustered_set):
           if vault.similarity(seed, note) > 0.7:
               cluster.append(note)
               to_remove.append(note)
           if len(cluster) >= 5:
               break

       for note in to_remove:
           unclustered_set.remove(note)  # O(1)
   ```

#### vault_context.py (1 occurrence):

6. **Line 619** - `unlinked_pairs()`:
   ```python
   # BEFORE: O(N*M) - list membership check
   recent = self.recent_notes(k=candidate_limit // 2)
   remaining = [n for n in all_notes if n not in recent]

   # AFTER: O(N) - set membership
   recent = self.recent_notes(k=candidate_limit // 2)
   recent_set = set(recent)
   remaining = [n for n in all_notes if n not in recent_set]
   ```

### Implementation Steps:

1. **Write unit tests FIRST** (`tests/unit/test_algorithmic_fixes.py`)
2. **Implement all 6 fixes**
3. **Run validation** (`./scripts/validate.sh`)
4. **Benchmark** (local only - LYT Kit + 10k vault)
5. **Update CHANGELOG.md**
6. **Commit and push**

**Expected Impact**:
- Fixes pattern_finder timeout (critical!)
- Improves stats command on large vaults
- Minor invoke improvement (~2-5%)

---

## BIG OPTIMIZATION #2: sklearn Vectorization + Cache Redundant Norms

**Replace manual implementations with sklearn/scipy + eliminate redundant computations**

### Part A: sklearn/scipy Replacements (12 occurrences):

**Cosine Similarity (10)**:
- `embeddings.py:490-507` - Replace `cosine_similarity()` function
- `embeddings.py:510-541` - Vectorize `find_similar_notes()`
- `vault_context.py:642-646` - Use sklearn for matrix operations
- `function_registry.py:244-249` - Use sklearn
- `convergent_evolution.py:88`
- `concept_drift.py:67, 97-98` (2 places)
- `session_drift.py:130`
- `divergent_evolution.py:86`

**Euclidean Distance (2)**:
- `hermeneutic_instability.py:67`
- `vocabulary_expansion.py:61`

Replace with:
- `sklearn.metrics.pairwise.cosine_similarity()`
- `scipy.spatial.distance.euclidean()`

### Part B: Cache Redundant Norm (1 occurrence):

**concept_drift.py:97-98**:
```python
# BEFORE: Computes drift_vector norm 5 times in loop
drift_vector = last_emb - first_emb

for neighbor in current_neighbors:  # ~5 iterations
    alignment = np.dot(drift_vector, neighbor_emb) / (
        np.linalg.norm(drift_vector) * np.linalg.norm(neighbor_emb)  # redundant!
    )

# AFTER: Cache norm outside loop
drift_vector = last_emb - first_emb
drift_vector_norm = np.linalg.norm(drift_vector)  # Compute once

for neighbor in current_neighbors:
    alignment = np.dot(drift_vector, neighbor_emb) / (
        drift_vector_norm * np.linalg.norm(neighbor_emb)
    )
```

### Implementation Steps:

1. **Unit tests FIRST** (`tests/unit/test_sklearn_migration.py`)
2. **Implement sklearn replacements + norm caching**
3. **Validate** (`./scripts/validate.sh`)
4. **Benchmark** (LYT Kit + 10k vault)
5. **Update CHANGELOG.md**
6. **Commit and push**

**Expected Impact**: 10-15% speedup on geist execution (45s → ~38-40s on 10k vault)

---

## BIG OPTIMIZATION #3: GPU Acceleration

**Enable GPU for embedding computation using existing PyTorch dependency**

### Implementation:

1. Add `_detect_device()` method:
   - Check `torch.cuda.is_available()` (NVIDIA)
   - Check `torch.backends.mps.is_available()` (Apple Silicon)
   - Fall back to CPU with log message

2. Update `embeddings.py:78`:
   ```python
   # Before: device="cpu"
   # After: device=self._detect_device()
   ```

3. Log device selection at startup

### Implementation Steps:

1. **Unit tests** (`tests/unit/test_gpu_acceleration.py`)
2. **Implement device detection**
3. **Validate**
4. **Benchmark** (CPU vs GPU on 10k vault)
5. **Update CHANGELOG.md**
6. **Commit and push**

**Expected Impact**: 80-85% speedup on embeddings (200s → ~30-40s on 10k vault with GPU)

---

## BIG OPTIMIZATION #4: Database Layer

**Batch inserts and pre-compile regex patterns**

### Changes:

1. **Batch INSERT for links** (`vault.py:263-276`):
   ```python
   # BEFORE: Individual execute() in loop
   for link in note.links:
       self.db.execute("INSERT INTO links ...", ...)

   # AFTER: Single executemany()
   link_rows = [(note.path, link.target, ...) for link in note.links]
   self.db.executemany("INSERT INTO links ...", link_rows)
   ```

2. **Batch INSERT for tags** (`vault.py:279-280`):
   ```python
   # BEFORE: Individual execute() in loop
   for tag in note.tags:
       self.db.execute("INSERT INTO tags ...", ...)

   # AFTER: Single executemany()
   tag_rows = [(note.path, tag) for tag in note.tags]
   self.db.executemany("INSERT INTO tags ...", tag_rows)
   ```

3. **Pre-compile regex** (`markdown_parser.py:94, 160`):
   ```python
   # Module-level constants (before functions):
   WIKILINK_PATTERN = re.compile(r"(!?)\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
   TAG_PATTERN = re.compile(r"#([a-zA-Z0-9_/-]+)")

   # Use in functions:
   for match in WIKILINK_PATTERN.finditer(content):
   for match in TAG_PATTERN.finditer(content):
   ```

### Implementation Steps:

1. **Unit tests FIRST** (`tests/unit/test_database_batching.py`)
2. **Implement batching + regex compilation**
3. **Validate**
4. **Benchmark** (sync time on LYT Kit + 10k vault)
5. **Update CHANGELOG.md**
6. **Commit and push**

**Expected Impact**: 15-25% speedup on vault sync

---

## FINAL REVIEW: Check for Hoisted Calculations

**After all 4 optimizations, review for remaining optimization opportunities**

### Review Areas:

1. **embeddings.py - `find_similar_notes()`**:
   - Check if query_embedding reshaping/preprocessing happens in loops
   - Verify no redundant embedding lookups
   - Ensure optimal sklearn usage

2. **Geists using similarity calculations**:
   - Look for embedding fetches inside loops that could be batched
   - Check for repeated similarity calculations on same pairs
   - Verify embeddings are cached appropriately

3. **General pattern search**:
   - Search for `for` loops containing expensive function calls
   - Look for repeated database queries that could be batched
   - Check for calculations that could be moved outside loops

### Process:

1. **After OP-4 is committed**, run comprehensive code review
2. **Document findings** in a review note (not committed)
3. **If minor optimizations found** (< 5% impact): Create GitHub issue for future
4. **If significant patterns found** (> 5% impact): Discuss whether to include in Phase 3 or defer

**Expected Impact**: Identify any remaining low-hanging fruit (likely < 5% additional gains)

---

## Process for Each Big Optimization:

1. ✅ Write unit tests (test-first)
2. ✅ Implement changes
3. ✅ Run validation: `./scripts/validate.sh` (must pass)
4. ✅ Benchmark locally with LYT Kit and 10k vault
5. ✅ Update `CHANGELOG.md` with measured gains
6. ✅ Commit and push
7. ✅ Move to next optimization

---

## Expected Timeline & Impact:

**Before**: 247s on 10k vault (200s embeddings + 45s geists + 2s sync)

- **After OP-1**: ~242s (pattern_finder timeout **FIXED**)
- **After OP-2**: ~215s (45s → 38s geists)
- **After OP-3**: ~53s (200s → 35s embeddings with GPU)
- **After OP-4**: ~45-48s (optimized sync)
- **After Review**: Document any additional opportunities

**Total speedup**:
- **With GPU**: ~81% reduction (247s → ~45s)
- **Without GPU**: ~13% reduction (247s → ~215s)

---

## Notes:

- Benchmarks stay LOCAL (not committed)
- Nothing pushes until validation passes
- Each optimization = separate CHANGELOG entry
- All changes preserve behavioral equivalence (test-verified)
- **OP-1 is critical** - fixes pattern_finder timeout
- Final review identifies future optimization opportunities
