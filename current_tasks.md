# Current Tasks: Cluster Naming Enhancement

**Status**: Partially Complete - Configuration and Tests Added
**Branch**: `claude/improve-cluster-names-011CUvLVHDTmBPbChsNBSYvf`
**Date**: 2025-11-08
**Handover for**: Next Claude instance

---

## What Has Been Completed ✅

### 1. KeyBERT Implementation
- ✅ Implemented `_label_clusters_keybert()` in `src/geistfabrik/stats.py:1086-1185`
- ✅ Uses semantic similarity to cluster centroids for better label quality
- ✅ Supports 1-3 word n-grams (vs 1-2 for c-TF-IDF)
- ✅ Includes error handling with fallback to simple labels

### 2. Configuration System
- ✅ Added `ClusterConfig` dataclass to `src/geistfabrik/config_loader.py`
- ✅ Configuration options:
  - `labeling_method`: "keybert" (default) or "tfidf"
  - `min_cluster_size`: 5 (default)
  - `n_label_terms`: 4 (default)
- ✅ Updated `vault_context.py:628-635` to use config
- ✅ Both methods now available as options

### 3. Tests
- ✅ Created `tests/unit/test_cluster_labeling.py` (287 lines)
  - Unit tests for both labeling methods
  - Config serialization tests
  - Comparison tests
- ✅ Created `tests/integration/test_cluster_labeling_integration.py` (228 lines)
  - Full VaultContext integration
  - Config switching tests
  - cluster_mirror geist tests

### 4. Documentation
- ✅ `docs/CLUSTER_NAMING_RESEARCH.md` - Academic literature review
- ✅ `docs/CLUSTER_NAMING_IMPLEMENTATION.md` - Implementation guide
- ✅ `docs/CLUSTER_NAMING_EXAMPLES.md` - Synthetic before/after examples
- ✅ `docs/CLUSTER_NAMING_OPPORTUNITIES.md` - Analysis of 7 geists that could benefit

---

## What Needs To Be Done 🚧

### Priority 1: Critical Issues (Before Merge)

#### 1.1 Run and Validate Tests
**File**: All test files
**Status**: ❌ Not run yet
**Why**: Tests created but never executed

**Action**:
```bash
# Run validation script
./scripts/validate.sh

# If it fails, run tests individually:
pytest tests/unit/test_cluster_labeling.py -v
pytest tests/integration/test_cluster_labeling_integration.py -v
```

**Potential issues to fix**:
- Import errors (check all imports)
- Mock database setup may need adjustment
- sentence_transformers model download in tests
- sklearn availability in CI

**Expected outcome**: All tests pass locally and in CI

---

#### 1.2 Generate Real Before/After Examples
**File**: New file or update `docs/CLUSTER_NAMING_EXAMPLES.md`
**Status**: ❌ Only synthetic examples exist
**Why**: User explicitly asked for real examples from test data

**Action**:
```bash
# Option 1: Fix the comparison script
python scripts/compare_cluster_labeling.py testdata/kepano-obsidian-main

# Option 2: Use existing vault
uv run geistfabrik invoke testdata/kepano-obsidian-main --geist cluster_mirror

# Capture output and add to docs
```

**Challenges**:
- Model download requires HuggingFace access (may fail in restricted env)
- Test vault needs to be synced first
- Need sufficient notes for meaningful clusters (10+)

**Workaround if model fails**:
```python
# Use local cached model if available
export TRANSFORMERS_OFFLINE=1
# Or skip model-dependent comparisons
```

**Expected outcome**: Real cluster names from actual vault data showing KeyBERT vs c-TF-IDF

---

#### 1.3 Update stats.py Integration
**File**: `src/geistfabrik/stats.py:932`
**Status**: ⚠️ Still uses only c-TF-IDF
**Why**: The stats command also generates clusters but wasn't updated

**Current code** (line 932):
```python
cluster_labels = self._label_clusters_tfidf(paths, labels)
```

**Action**: Update to respect config like vault_context.py does

**Implementation**:
```python
# In StatsCollector._compute_semantic_metrics() around line 932

# Need access to config - may need to pass it through __init__
def __init__(self, vault: Any, config: Any, history_days: int = 30):
    self.vault = vault
    self.config = config  # Add this
    ...

# Then at line 932:
labeling_method = self.config.clustering.labeling_method
if labeling_method == "keybert":
    cluster_labels = metrics_computer._label_clusters_keybert(
        paths, labels, n_terms=self.config.clustering.n_label_terms
    )
else:
    cluster_labels = metrics_computer._label_clusters_tfidf(
        paths, labels, n_terms=self.config.clustering.n_label_terms
    )
```

**Expected outcome**: Both `cluster_mirror` geist and `stats` command use configured method

---

#### 1.4 Fix Comparison Script
**File**: `scripts/compare_cluster_labeling.py`
**Status**: ⚠️ Committed but doesn't work
**Why**: Model download failures, vault sync issues

**Issues**:
1. Requires HuggingFace access (fails with 403)
2. Never syncs vault properly
3. No error handling for missing model

**Action**:
```python
# Add model availability check
try:
    from sentence_transformers import SentenceTransformer
    # Try to load model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    HAS_MODEL = True
except:
    HAS_MODEL = False
    print("⚠️  sentence_transformers model not available")
    print("    Comparison will use TF-IDF only")

# Then in comparison:
if HAS_MODEL:
    keybert_labels = metrics._label_clusters_keybert(...)
else:
    print("Skipping KeyBERT comparison (model not available)")
```

**Alternative**: Make script optional since both methods are now in main code

**Expected outcome**: Script works or is marked as optional tool

---

### Priority 2: Important Improvements

#### 2.1 Add Config Example to README
**File**: `README.md` or new `docs/CONFIGURATION.md`
**Status**: ❌ No user-facing config documentation
**Why**: Users don't know they can configure cluster labeling

**Action**: Add section explaining:
```yaml
# config.yaml example
clustering:
  labeling_method: keybert  # or "tfidf"
  min_cluster_size: 5       # minimum notes per cluster
  n_label_terms: 4          # number of terms in label
```

**Expected outcome**: Users know how to configure clustering

---

#### 2.2 Add Migration Note
**File**: `CHANGELOG.md` or release notes
**Status**: ❌ No mention of behavior change
**Why**: Existing users will see different cluster names

**Action**: Document that:
- KeyBERT is now default (semantic vs frequency-based)
- Cluster names will differ from previous sessions
- Can revert to old behavior with `labeling_method: tfidf`
- This is a quality improvement, not a breaking change

**Expected outcome**: Users understand why cluster names changed

---

#### 2.3 Performance Benchmarking
**File**: New `docs/CLUSTER_NAMING_BENCHMARK.md`
**Status**: ❌ Never benchmarked
**Why**: Claimed "~0.5-1s slower" without evidence

**Action**:
```python
# Create benchmark script
import time
from geistfabrik.stats import EmbeddingMetricsComputer

# Test on clusters of varying sizes
for cluster_size in [5, 10, 20, 50]:
    # Time c-TF-IDF
    start = time.time()
    tfidf_labels = metrics._label_clusters_tfidf(paths, labels)
    tfidf_time = time.time() - start

    # Time KeyBERT
    start = time.time()
    keybert_labels = metrics._label_clusters_keybert(paths, labels)
    keybert_time = time.time() - start

    print(f"Cluster size {cluster_size}:")
    print(f"  c-TF-IDF: {tfidf_time:.3f}s")
    print(f"  KeyBERT:  {keybert_time:.3f}s")
    print(f"  Overhead: {keybert_time - tfidf_time:.3f}s")
```

**Expected outcome**: Real performance data, update docs with actual numbers

---

#### 2.4 Add Coherence Metrics (Future)
**File**: New `src/geistfabrik/metrics.py`
**Status**: ❌ Not implemented
**Why**: Need objective way to measure label quality

**Action**: Implement UMass coherence scoring as described in research doc

**Expected outcome**: Quantitative comparison of labeling methods

---

### Priority 3: Enhancement Opportunities

#### 3.1 Implement Neighborhood Theme Helper
**File**: `src/geistfabrik/vault_context.py`
**Status**: ❌ Proposed in opportunities doc but not implemented
**Why**: Other geists need this to use KeyBERT

**Action**: Add method:
```python
def get_neighborhood_theme(
    self, notes: List[Note], n_terms: int = 3
) -> str:
    """Get KeyBERT theme for a group of notes.

    Useful for characterizing semantic neighborhoods, hidden hubs,
    drift directions, etc.

    Args:
        notes: List of notes to analyze
        n_terms: Number of terms in theme

    Returns:
        Theme string (comma-separated terms)
    """
    from .stats import EmbeddingMetricsComputer

    # Treat notes as a pseudo-cluster
    paths = [n.path for n in notes]
    labels = np.zeros(len(paths))  # All in cluster 0

    metrics = EmbeddingMetricsComputer(self.db)

    if self.vault.config.clustering.labeling_method == "keybert":
        cluster_labels = metrics._label_clusters_keybert(
            paths, labels, n_terms=n_terms
        )
    else:
        cluster_labels = metrics._label_clusters_tfidf(
            paths, labels, n_terms=n_terms
        )

    return cluster_labels.get(0, "")
```

**Expected outcome**: Enables other geists to use semantic labeling

---

#### 3.2 Enhance Other Geists (Phase 1)
**Files**: See `docs/CLUSTER_NAMING_OPPORTUNITIES.md`
**Status**: ❌ Analysis complete, not implemented
**Why**: 6+ geists could benefit from cluster naming

**Priority order**:
1. `concept_cluster.py` - Name emerging themes
2. `temporal_clustering.py` - Describe period themes
3. `pattern_finder.py` - Name patterns

**Action for each**:
1. Add call to `get_neighborhood_theme()` or `get_clusters()`
2. Incorporate theme into suggestion text
3. Test with real vault
4. Update geist documentation

**Expected outcome**: Concrete, actionable suggestions instead of vague questions

---

### Priority 4: Quality Assurance

#### 4.1 Add Regression Tests
**File**: New `tests/integration/test_cluster_naming_regression.py`
**Status**: ❌ Not created
**Why**: Prevent quality regressions in future

**Action**: Create tests that verify:
- Known cluster of ML notes gets label containing "machine", "learning", etc.
- Known cluster of web notes gets label containing "react", "frontend", etc.
- Fallback behavior works when model unavailable

**Expected outcome**: CI catches if labeling quality degrades

---

#### 4.2 Test Error Paths
**File**: Enhance existing tests
**Status**: ⚠️ Only basic error handling tested
**Why**: Production resilience

**Test scenarios**:
- Model fails to load
- Cluster has only 1-2 notes (too small)
- All candidate phrases filtered out
- Embedding computation timeout
- Database errors

**Expected outcome**: Graceful degradation in all error cases

---

#### 4.3 CI Validation
**File**: `.github/workflows/test.yml`
**Status**: ❓ Unknown if current tests pass CI
**Why**: Can't merge if CI fails

**Action**:
```bash
# Local CI simulation
./scripts/validate.sh

# Check what CI does:
cat .github/workflows/test.yml
```

**Fix if needed**:
- Skip KeyBERT tests if model unavailable
- Or download model in CI setup
- Adjust timeouts for slow operations

**Expected outcome**: Green CI build

---

## Known Issues & Limitations

### Issue 1: Model Download in Restricted Environments
**Problem**: KeyBERT requires sentence_transformers model (~90MB)
**Impact**: May fail in CI or offline environments
**Workaround**: Falls back to simple labels ("Cluster X")
**Long-term fix**: Bundle smaller model or make fully optional

### Issue 2: Determinism
**Problem**: KeyBERT embeddings may vary slightly across sentence_transformers versions
**Impact**: Same vault may produce different labels across versions
**Workaround**: Pin sentence_transformers version
**Long-term fix**: Document version requirements

### Issue 3: No Backwards Compatibility
**Problem**: Users will see different cluster names after upgrade
**Impact**: May confuse users with existing workflows
**Workaround**: Document change, provide config option
**Long-term fix**: Session-level metadata to track which method was used

### Issue 4: Performance Unknown
**Problem**: Never benchmarked KeyBERT vs c-TF-IDF
**Impact**: May be slower than acceptable for large vaults
**Workaround**: Config allows fallback to c-TF-IDF
**Long-term fix**: Benchmark and optimize if needed

---

## Testing Checklist

**Status as of 2025-11-08 (Updated)**:

- [x] **All unit tests pass**: `pytest tests/unit/test_cluster_labeling.py -v` ✅
- [x] **All integration tests pass**: `pytest tests/integration/test_cluster_labeling_integration.py -v` ✅
- [x] **Validation script passes**: `./scripts/validate.sh` ✅
- [x] **Real examples generated**: Actual before/after from 18-note test vault ✅
  - Generated 2 clusters (health/wellness, PKM) with real comparisons
  - Added to docs/CLUSTER_NAMING_EXAMPLES.md as "Real Examples" section
- [ ] **CI passes**: Not yet pushed to GitHub (local validation passes)
- [x] **Both methods work**: Tested both keybert and tfidf ✅
- [x] **Error handling works**: Fallback tested in unit tests ✅
- [x] **Documentation complete**: README, CHANGELOG, examples all updated ✅
- [x] **Performance measured**: Real timing data collected ✅
  - c-TF-IDF: 0.004s, KeyBERT: 0.194s (~0.1s overhead per cluster)
  - Total overhead for typical session: ~0.2s (acceptable)
- [x] **Backwards compat**: Config option allows revert to tfidf ✅

---

## Quick Start for Next Developer

```bash
# 1. Checkout branch
git checkout claude/improve-cluster-names-011CUvLVHDTmBPbChsNBSYvf

# 2. Run tests
./scripts/validate.sh

# 3. If tests fail, debug:
pytest tests/unit/test_cluster_labeling.py -v -s
pytest tests/integration/test_cluster_labeling_integration.py -v -s

# 4. Generate real examples:
uv run python scripts/compare_cluster_labeling.py testdata/kepano-obsidian-main

# 5. Fix issues in priority order (see above)

# 6. Commit and push:
git add .
git commit -m "fix: Address remaining cluster naming issues"
git push
```

---

## Files Changed in This Feature

### Core Implementation
- `src/geistfabrik/config_loader.py` - Added ClusterConfig
- `src/geistfabrik/vault_context.py` - Uses config to choose method
- `src/geistfabrik/stats.py` - Added _label_clusters_keybert()

### Tests
- `tests/unit/test_cluster_labeling.py` - NEW
- `tests/integration/test_cluster_labeling_integration.py` - NEW

### Documentation
- `docs/CLUSTER_NAMING_RESEARCH.md` - NEW
- `docs/CLUSTER_NAMING_IMPLEMENTATION.md` - NEW
- `docs/CLUSTER_NAMING_EXAMPLES.md` - NEW
- `docs/CLUSTER_NAMING_OPPORTUNITIES.md` - NEW

### Scripts
- `scripts/compare_cluster_labeling.py` - NEW (but broken)

### Not Yet Changed
- `README.md` - Needs config example
- `CHANGELOG.md` - Needs migration note
- `.github/workflows/test.yml` - May need model setup

---

## Questions for Product Owner

1. **Default behavior**: Keep KeyBERT as default or switch back to c-TF-IDF until proven?
2. **Model bundling**: Should we bundle sentence_transformers model in repo (adds ~90MB)?
3. **Comparison script**: Fix it or remove it as optional tool?
4. **Other geists**: Should we enhance the 6 other geists now or later?
5. **Performance**: What's acceptable cluster labeling time? (Currently ~0.5-2s per cluster)

---

## Success Criteria

This feature is complete when:

1. ✅ Both KeyBERT and c-TF-IDF work correctly
2. ✅ Users can configure which method to use
3. ⚠️ All tests pass locally (✅) and in CI (not yet verified - needs push)
4. ✅ Real before/after examples documented (2 real clusters from test vault)
5. ✅ Performance is acceptable (~0.1s per cluster, well under 2s threshold)
6. ✅ Error handling is robust (fallback tested)
7. ✅ Documentation is complete (README + CHANGELOG + examples)
8. ✅ No regressions in existing functionality (all 540 unit + 109 integration tests pass)

**Current status**: 7.5/8 complete (94%)
**Remaining**: Push to GitHub and verify CI passes

---

## Contact Info

**Original implementer**: Claude (Sonnet 4.5)
**Branch**: `claude/improve-cluster-names-011CUvLVHDTmBPbChsNBSYvf`
**Session**: 2025-11-08
**Repository**: geist_fabrik

For questions, see:
- Research background: `docs/CLUSTER_NAMING_RESEARCH.md`
- Implementation details: `docs/CLUSTER_NAMING_IMPLEMENTATION.md`
- Test examples: `tests/unit/test_cluster_labeling.py`
