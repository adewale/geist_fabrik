# GeistFabrik for Early Adopters

**Welcome, brave soul!** 🎉

This guide shows you how to safely test GeistFabrik (v0.10.1 Beta) and provide valuable feedback.

## What to Expect

**Current Status:**
- ✅ All tests passing (beta quality - see STATUS.md for details)
- ✅ All core features implemented
- ✅ 70 default geists bundled (58 code + 12 Tracery)
- ✅ Read-only vault access (your notes are safe)

**Expect:**
- Rough edges in CLI output
- Occasional unclear error messages
- Performance not optimised for 1000+ notes

**Engine guarantees and trust boundaries:**
- GeistFabrik does not modify source notes; it writes only managed DB/journal state.
- Vault processing is local and no vault content or analytics are uploaded. If the
  bundled model is missing, default online mode may download it from HuggingFace;
  set `GEISTFABRIK_OFFLINE=1` to prohibit that fallback.
- Custom Python geists, metadata modules, and vault functions are trusted arbitrary
  code. They are imported and executed in-process and are not sandboxed.
- Individual geist failures are reported and persistently accounted for.

---

## Three Ways to Test Safely

### Option 1: Sample Vault (Safest - Start Here)

Perfect for first-time exploration. Zero risk to your personal vault.

```bash
# 1. Install GeistFabrik (Python 3.11 or 3.12)
git lfs install
git clone https://github.com/adewale/geist_fabrik.git
cd geist_fabrik
uv sync

# Source clones use Git LFS for the ~88 MB model; verify it is materialized
# with `git lfs pull`. Release wheels include the same model. Set
# GEISTFABRIK_OFFLINE=1 to prohibit HuggingFace fallback downloads.

# 2. Initialise sample vault
uv run geistfabrik init testdata/kepano-obsidian-main

# 3. Run geists and view suggestions
uv run geistfabrik invoke --vault testdata/kepano-obsidian-main --write

# 4. Inspect results
cat "testdata/kepano-obsidian-main/geist journal"/*.md
ls -la testdata/kepano-obsidian-main/_geistfabrik/

# 5. Clean up
rm -rf testdata/kepano-obsidian-main/_geistfabrik
rm -rf "testdata/kepano-obsidian-main/geist journal"
```

**Time:** 15 minutes
**Risk:** None

---

### Option 2: Test Vault Copy (Recommended for Real Testing)

Create a copy of your vault for realistic testing without risk.

```bash
# 1. Create test copy
cp -r ~/Documents/MyVault ~/Documents/MyVault-Test

# 2. Initialise GeistFabrik
uv run geistfabrik init ~/Documents/MyVault-Test

# 3. Preview suggestions (read-only, no files created)
uv run geistfabrik invoke --vault ~/Documents/MyVault-Test

# 4. Check for similar suggestions (diff mode)
uv run geistfabrik invoke --vault ~/Documents/MyVault-Test --diff

# 5. Write session note
uv run geistfabrik invoke --vault ~/Documents/MyVault-Test --write

# 6. Open in Obsidian
# Add ~/Documents/MyVault-Test as vault
# Browse to "geist journal/" folder

# 7. Test individual geists
uv run geistfabrik test temporal_drift --vault ~/Documents/MyVault-Test
uv run geistfabrik test creative_collision --vault ~/Documents/MyVault-Test

# 8. Clean up when done
rm -rf ~/Documents/MyVault-Test
```

**Time:** 1-2 hours
**Risk:** None (copy is disposable)

---

### Option 3: Your Real Vault (For Confident Users)

Use your actual vault. Safe because GeistFabrik is read-only.

```bash
# Optional: Backup first
cp -r ~/Documents/MyVault ~/Documents/MyVault.backup

# 1. Initialise with confirmation prompts
uv run geistfabrik init ~/Documents/MyVault
# You'll see warnings about what GeistFabrik will/won't do

# 2. Preview suggestions (read-only, no files created)
uv run geistfabrik invoke --vault ~/Documents/MyVault

# 3. Compare to previous sessions
uv run geistfabrik invoke --vault ~/Documents/MyVault --diff

# 4. Write your first session note
uv run geistfabrik invoke --vault ~/Documents/MyVault --write

# 5. View in Obsidian
# Navigate to "geist journal/" folder
# Open today's date (YYYY-MM-DD.md)

# 6. Remove if not for you
rm -rf ~/Documents/MyVault/_geistfabrik
rm -rf ~/Documents/MyVault/"geist journal"
# (Your original notes are untouched)
```

**Time:** Ongoing exploration
**Risk:** Very low (read-only access)

---

## What Gets Created

After `geistfabrik init ~/MyVault`:

```
MyVault/
├── _geistfabrik/                    # GeistFabrik's directory
│   ├── vault.db                     # SQLite (notes + embeddings)
│   ├── geists/
│   │   ├── code/                    # 29 Python geists
│   │   └── tracery/                 # 10 YAML geists
│   ├── metadata_inference/          # 3 metadata modules
│   └── vault_functions/             # 2 query functions
└── geist journal/                   # Session notes (--write only)
    └── 2025-10-21.md                # Today's suggestions
```

**Database contents (`vault.db`):**
- Note metadata (titles, links, tags, timestamps)
- Embeddings (384-dim vectors, ~30MB for 1000 notes)
- Session history
- Previous suggestions (for novelty filtering)

**Not stored:**
- Full note content (read on-demand)
- Personal identifiers
- Usage analytics

---

## Safety Features You'll See

### 1. First-Run Warnings

```
⚠️  GeistFabrik will:
   • Read all markdown files in your vault
   • Create a database at _geistfabrik/vault.db
   • Compute embeddings for all notes (stored locally)
   • Create session notes in 'geist journal/' when you invoke with --write

✅ GeistFabrik's engine will NEVER:
   • Modify or delete your existing source notes
   • Upload vault content or analytics

⚠️ Trust boundaries:
   • A missing model may be downloaded from HuggingFace unless offline mode is set
   • Custom Python plugins are trusted arbitrary code and are not sandboxed
```

### 2. Summary Stats After Init

```
📊 Vault Summary:
   Notes found: 247
   Database size: 12.34 MB
   Bundled default geists available: 70 (58 code + 12 Tracery)
```

### 3. Diff Mode

```bash
uv run geistfabrik invoke --vault ~/MyVault --diff
# 🔍 Diff Mode: Comparing to recent sessions...
#   ✨ New: What if you combined [[Note A]] with [[Note B]]?
#   ⚠️  Similar to recent: Consider revisiting [[Old Note]]...
```

---

## Auditing Your Configuration

Every time you run `geistfabrik invoke`, you'll see a configuration audit at the start:

```
============================================================
GeistFabrik Configuration Audit
============================================================
Vault: /path/to/vault
Geists directory: /path/to/vault/_geistfabrik/geists/code
Total geists found: 29
  - Enabled: 29
Filtering: ENABLED (4-stage pipeline)
Sampling: ENABLED (count=5)
Mode: Default
============================================================
```

This shows:
- **Total geists found**: All `.py` files in the geists directory
- **Enabled/Disabled**: Geists can be auto-disabled after 3 failures
- **Filtering**: Whether the 4-stage filter pipeline is active
- **Sampling**: Whether suggestions are sampled down
- **Mode**: Current invocation mode

If you see fewer geists than expected:
- Check that geists are in `_geistfabrik/geists/code/`
- Look for disabled geists (auto-disabled after failures)
- Check the Execution Summary at the end for errors

---

## Common Questions

**Q: Will this slow down Obsidian?**
A: No. GeistFabrik only runs when you invoke it from terminal. Obsidian never sees it.

**Q: What about large vaults?**
A: Tested on 100+ notes. Initial sync for 1000 notes takes 2-5 minutes. After that, incremental syncs are fast.

**Q: Which backend should I use for my vault size?**
A: GeistFabrik offers two vector search backends with different performance characteristics:

**Use InMemory (default)** for:
- Vaults with < 500 notes
- Faster startup (0.1-2ms load time)
- Simpler deployment (no extra dependencies)

**Use SqliteVec** for:
- Vaults with > 1000 notes
- 6x faster queries at 2000 notes
- Better scaling for large vaults

**Benchmark Results:**

| Vault Size | InMemory Query | SqliteVec Query | Speedup |
|------------|----------------|-----------------|---------|
| 100 notes  | 0.20ms        | 0.16ms         | 1.25x   |
| 500 notes  | 1.02ms        | 0.24ms         | 4.16x   |
| 1000 notes | 2.00ms        | 0.37ms         | 5.41x   |
| 2000 notes | 4.02ms        | 0.67ms         | 5.97x   |

To enable SqliteVec in an installed release:
```bash
python -m pip install "geistfabrik[vector-search]"
```

For a source checkout, use `uv sync --extra vector-search`. Then configure:
```yaml
# _geistfabrik/config.yaml
vector_search:
  backend: sqlite-vec
```

Run your own benchmarks from a source checkout:
`uv run python scripts/benchmark_backends.py`

**Q: Can I create custom geists?**
A: Yes! Create `_geistfabrik/geists/code/my_geist.py`:

```python
from geistfabrik import Suggestion

def suggest(vault):
    """Your custom logic."""
    suggestions = []

    for note in vault.notes():
        if interesting_condition(note):
            suggestions.append(Suggestion(
                text=f"What if you explored [[{note.title}]] further?",
                notes=[note.title],
                geist_id="my_geist"
            ))

    return vault.sample(suggestions, k=5)
```

Test it: `uv run geistfabrik test my_geist`

**Q: What if a geist crashes?**
A: System continues. Geists have:
- 5-second timeout
- Error isolation (one failure doesn't stop others)
- Execution logs
- Auto-disable after 3 failures

**Q: Can I remove example geists?**
A: Yes! Delete unwanted geists:
```bash
rm ~/MyVault/_geistfabrik/geists/code/temporal_drift.py
```

---

## Providing Feedback

**Most valuable feedback:**

1. **Useful suggestions:** "This geist suggestion was surprisingly helpful because..."
2. **Unexpected behaviour:** "I expected X but got Y"
3. **Confusion:** "I couldn't figure out how to..."
4. **Errors:** "This error message confused me:"

**How to report:**
- GitHub Issues: https://github.com/adewale/geist_fabrik/issues
- Include: OS, Python version, GeistFabrik version (0.10.1)
- Steps to reproduce
- Expected vs actual behaviour
- Anonymize note titles if needed

---

## Experiment Ideas

### 1. Geist Tournament

Test each geist and rank them:

```bash
for geist in temporal_drift creative_collision bridge_builder; do
    echo "Testing $geist..."
    uv run geistfabrik test $geist
done
```

Which ones resonate? Which feel like noise?

### 2. Custom Geist Development

Create a geist reflecting your thinking:
- Tag archaeologist: Find under-tagged notes
- Link suggester: Connect related notes
- Question extractor: Pull all questions
- Topic mapper: Identify emergent themes

### 3. Temporal Analysis

Run on the same date multiple times:

```bash
# Day 1
uv run geistfabrik invoke --vault ~/MyVault --date 2025-01-15 --write

# Day 30 (vault has evolved)
uv run geistfabrik invoke --vault ~/MyVault --date 2025-01-15 --write --force

# Compare how suggestions changed as your vault grew
```

### 4. Full Geist Firehose (Advanced - Maximum Testing)

⚠️ **DANGER ZONE** ⚠️

Run ALL geists with ALL raw suggestions (no filtering) against a vault copy. This is the most comprehensive test but generates the most output.

**🚨 CRITICAL: Only run against a COPY of your vault, never the original! 🚨**

**Understanding the difference:**
- `--full`: All **filtered** suggestions (quality checks applied, no sampling)
- `--nofilter`: All **raw** suggestions (no filtering, no quality checks)

```bash
# Step 1: Create a fresh copy
cp -r ~/Documents/MyVault ~/Documents/MyVault-FullTest
cd ~/Documents/MyVault-FullTest

# Step 2: Backup (extra safety)
tar -czf ../MyVault-FullTest-backup.tar.gz .

# Step 3: Initialise (70 default geists enabled)
uv run geistfabrik init ~/Documents/MyVault-FullTest

# Step 4a: Try --full first (filtered but not sampled)
uv run geistfabrik invoke --vault ~/Documents/MyVault-FullTest --full --write

# Step 4b: For TRUE firehose, use --nofilter (completely unfiltered)
uv run geistfabrik invoke --vault ~/Documents/MyVault-FullTest --nofilter --write --force

# Step 5: Review the flood of suggestions
cat ~/Documents/MyVault-FullTest/"geist journal"/$(date +%Y-%m-%d).md

# Step 6: Count how many suggestions were generated
grep -c "^## " ~/Documents/MyVault-FullTest/"geist journal"/$(date +%Y-%m-%d).md

# Step 7: Analyze which geists are most active
grep "^## " ~/Documents/MyVault-FullTest/"geist journal"/$(date +%Y-%m-%d).md | \
  sort | uniq -c | sort -rn

# Step 8: Clean up when done
rm -rf ~/Documents/MyVault-FullTest
rm ../MyVault-FullTest-backup.tar.gz
```

**What to expect:**

With `--full` (filtered):
- 10-50 suggestions (quality-checked)
- Redundant suggestions removed
- Notes must exist in vault
- Good for thorough review

With `--nofilter` (raw):
- 50-200+ suggestions (completely unfiltered)
- You'll see EVERYTHING every geist thinks
- May include low-quality, redundant, or broken suggestions
- Some suggestions may reference non-existent notes
- Perfect for understanding raw geist output

**Why this is dangerous:**
- While GeistFabrik never modifies your notes, running with `--nofilter` generates a LOT of data
- The session note can be overwhelming (10+ pages with `--nofilter`)
- You'll see the "raw feed" with all its flaws
- Some geists may crash or timeout (this is expected in beta)

**Best for:**
- Understanding what filtering removes (`--full` vs `--nofilter`)
- Debugging custom geists (see raw output)
- Seeing maximum divergent thinking
- Stress-testing the system
- Understanding vault patterns

**NOT recommended for:**
- Daily use (way too noisy, especially `--nofilter`)
- Your actual vault (use a copy!)
- Production workflows
- First-time users (start with default mode)

---

## Known Limitations (v0.10.1)

1. **Command-line only** - No GUI
2. **English-centric** - Embeddings optimised for English
3. **Obsidian-specific** - Designed for Obsidian vaults
4. **Single vault** - One at a time
5. **Fixed embedding model** - Can't swap without code changes

---

## Emergency Stop

If anything goes wrong:

```bash
# Stop execution: Ctrl+C

# Remove GeistFabrik completely:
rm -rf ~/MyVault/_geistfabrik
rm -rf ~/MyVault/"geist journal"

# Your notes are untouched and safe.
```

---

## Performance Benchmarking for Early Adopters

As an early adopter, you can help us validate performance optimisations by running benchmarks on your vault and reporting results. Your data helps us improve GeistFabrik for everyone!

### Why Your Performance Data Matters

GeistFabrik's performance varies based on:
- **Vault size** (100 vs 3000 notes)
- **Content diversity** (technical vs creative writing)
- **Note structure** (atomic vs long-form)
- **System specs** (CPU, RAM, disk speed)

Your real-world data helps us:
1. Validate optimisations work across different vaults
2. Identify bottlenecks in production use
3. Set realistic performance expectations
4. Prioritise future improvements

### Quick Performance Check

See how fast each geist runs on your vault:

```bash
# Profile all geists with detailed performance breakdown
uv run geistfabrik invoke ~/my-vault --debug --no-filter
```

**Expected output:**
```
============================================================
Performance Profiling (--debug mode)
============================================================

✓ cluster_mirror: 5.259s (1 suggestions)
  Top 5 operations:
    1. __call__ - 3.608s (68.6%)        ← HDBSCAN clustering
    2. _hdbscan_prims - 1.556s (29.6%)  ← Prim's algorithm
    3. <method 'execute'> - 0.016s (0.3%)

✓ creative_collision: 0.142s (3 suggestions)
✓ bridge_builder: 0.089s (2 suggestions)
⚠ slow_geist: 4.213s (1 suggestions)   ← Approaching timeout
✗ timeout_geist: Execution timed out (>5s)
```

**What to report:**
- Geists that take >2s (slow but acceptable)
- Geists approaching timeout (>4s, need optimisation)
- Geists that timeout (>5s, blocking issue)

### Run Cluster Caching Benchmark

Validate the 75% speedup from recent cluster caching optimisation:

```bash
# From GeistFabrik directory
uv run pytest tests/unit/test_cluster_performance.py::test_cluster_caching_benchmark -v -s
```

**Expected results (100 notes):**
```
============================================================
Cluster Caching Benchmark Results
============================================================
Vault size: 100 notes
Clusters found: 5

Without caching: 0.176s (4× HDBSCAN clustering)
With caching:    0.006s (1× clustering + 3× cache hit)
Speedup:         31.0x

Memory usage:
  Peak: 0.0MB
  Current: 0.0MB
============================================================

PASSED
```

**What to report** (GitHub issue template):

```markdown
## Cluster Caching Benchmark Results

- **Vault size**: XXX notes
- **Clusters found**: X
- **Without caching**: X.XXXs
- **With caching**: X.XXXs
- **Speedup**: XX.Xx
- **Memory (peak)**: XX.XMB
- **Operating system**: macOS / Linux / Windows
- **Python version**: 3.11.x
```

### Run Full Performance Test Suite

Validate all performance optimisations:

```bash
# All regression tests (fast, mocked)
uv run pytest tests/unit/test_performance_regression.py -v

# Real-world benchmarks (slower, manual)
uv run pytest tests/unit/test_cluster_performance.py::test_cluster_caching_benchmark -v -s
uv run pytest tests/unit/test_performance_regression.py::test_stats_vectorized_performance -v -s
```

These tests validate:
- ✅ Session-scoped caching (notes, clusters)
- ✅ Vectorized similarity computations (5.4x speedup)
- ✅ Optimised orphan queries (85.6% faster)
- ✅ Composite indexing on links table
- ✅ Efficient graph operations

### Run Phase 1 Optimisation Benchmarks (NEW)

Validate the latest Phase 1 performance improvements:

```bash
# Run all Phase 1 benchmarks
uv run pytest tests/unit/test_phase1_benchmarks.py -m benchmark -v -s
```

**Expected results** (100-note vault):
```
======================================================================
Backlinks Caching Benchmark
======================================================================
Without caching: 0.245s (100 queries)
With caching:    0.021s (100 queries)
Speedup:         11.5x
======================================================================

Contrarian_to Vectorization Benchmark
======================================================================
Vault size: 100 notes
Vectorized time: 0.112s (10 calls)
Per-call: 11.2ms
======================================================================

Phase 1 Integrated Benchmark
======================================================================
Operations:
  - Graph traversal: 20 notes (× 2 passes)
  - Contrarian search: 1 query
  - Unlinked pairs: 50 candidates

Total time: 0.349s
======================================================================
```

**What's tested:**
1. **Backlinks caching** - 10-50x speedup for repeated queries
2. **Graph operations** - Combined caching benefits
3. **Vectorized contrarian_to()** - 50-100x speedup vs loops
4. **Vectorized unlinked_pairs()** - Matrix-based similarity
5. **Integrated workflow** - Real geist usage patterns

**What to report** (GitHub issue template):

```markdown
## Phase 1 Benchmark Results

**Environment:**
- Vault size: XXX notes
- Operating system: macOS / Linux / Windows
- Python version: 3.11.x

**Benchmark results:**
- Backlinks caching speedup: XX.Xx
- Contrarian_to per-call: XX.Xms
- Integrated workflow: X.XXXs

**Notes:**
- Any tests that failed or were unexpectedly slow?
- Did speedups match expectations?
```

---

### Run Phase 2 Optimisation Benchmarks (NEW)

Validate the latest Phase 2 algorithmic improvements:

```bash
# Profile congruence_mirror specifically
uv run geistfabrik test congruence_mirror ~/my-vault --debug
```

**Expected results** (3406-note vault):
```
======================================================================
Congruence_Mirror Performance (OP-4: Single-Pass Optimisation)
======================================================================
✓ congruence_mirror: 1.930s (4 suggestions)

Performance improvements:
  Before optimisation: 60.838s
  After optimisation:  1.930s
  Speedup:             31.5x (97% reduction)

Optimisation techniques:
  - Single-pass algorithm (4 separate passes → 1 combined pass)
  - Cached similarity computations
  - Batch note loading (OP-6)
  - Early sampling (process 100 notes instead of all)
======================================================================
```

**What's tested:**
1. **OP-4**: Single-pass congruence_mirror (31.5x faster)
2. **OP-6**: Batch note loading (3 queries instead of 3×N)
3. **OP-8**: Optimised hubs() SQL query (JOIN-based resolution)
4. **OP-9**: neighbours() with return_scores (avoids recomputation)

**Geists optimised with OP-9** (return_scores=True):
- `hidden_hub` - Avoids recomputing similarity for semantic neighbours
- `bridge_hunter` - Gets scores when finding semantic paths
- `columbo` - Detects contradictions without redundant similarity calls
- `bridge_builder` - Identifies bridge notes efficiently
- `antithesis_generator` - Finds dialectical pairs faster

**What to report** (GitHub issue template):

```markdown
## Phase 2 Benchmark Results

**Environment:**
- Vault size: XXX notes
- Operating system: macOS / Linux / Windows
- Python version: 3.11.x

**Congruence_mirror performance:**
- Execution time: X.XXXs
- Suggestions generated: X
- Speedup vs baseline (if known): XX.Xx

**Other Phase 2 geists to test:**
- `hidden_hub`: X.XXXs
- `bridge_hunter`: X.XXXs
- `columbo`: X.XXXs

**Notes:**
- Did you notice improved performance compared to earlier versions?
- Any geists still slow (>2s)?
```

---

### Report Performance Issues

Found a slow geist? Here's how to report it effectively:

**1. Profile the specific geist:**
```bash
uv run geistfabrik test slow_geist ~/my-vault --timeout 10 --debug
```

**2. Create GitHub issue** with title:
```
[Performance] <geist_name> slow on <vault_size> note vault
```

**3. Use this template:**
```markdown
## Vault Characteristics

- **Total notes**: XXX
- **Average note length**: ~XXX words
- **Vault structure**: daily notes / atomic notes / mixed
- **Operating system**: macOS / Linux / Windows
- **Python version**: 3.11.x

## Performance Profile

From: `uv run geistfabrik test <geist_name> ~/my-vault --debug`

```
✓ geist_name: 5.259s (1 suggestions)
  Top 5 operations:
    1. operation_name - 3.608s (68.6%)
    2. other_operation - 1.556s (29.6%)
```

## Session Times

- **First run** (cold cache): ~XX seconds
- **Daily use** (warm cache): ~XX seconds

## Observations

- Does it timeout (>5s)?
- Is it consistently slow?
- Which operation takes most time?
```

### Expected Performance by Vault Size

| Vault Size | First Run | Daily Use | Status |
|------------|-----------|-----------|--------|
| 100 notes | 1-2s | <1s | ✅ Excellent |
| 500 notes | 5-8s | 2-3s | ✅ Good |
| 1000 notes | 14s | 3-5s | ✅ Acceptable |
| 3000 notes | 45s | 8-12s | ✅ Tolerable |
| 5000 notes | 2-3min | 15-20s | 🟡 Marginal |
| 10000+ notes | 5-10min | 30-60s | 🔴 Consider GPU |

**Note**: "First run" = initial embedding computation. "Daily use" = cached embeddings.

### Understanding Cold vs Warm Start Performance

The 7-10x performance difference between "First Run" and "Daily Use" reflects GeistFabrik's **cold start** vs **warm start** behaviour:

**Cold Start** (First Run):
- Happens when embeddings need to be computed from scratch
- Triggers on:
  - First time you invoke GeistFabrik on your vault
  - After deleting `_geistfabrik/vault.db`
  - When vault content has significantly changed
- Time breakdown for 1000 notes:
  - Embedding computation: ~2-3 minutes (100-200ms per note)
  - Geist execution: ~10-20 seconds
  - **Total: 3-4 minutes**

**Warm Start** (Daily Use):
- Happens when embeddings are already cached in database
- Triggers on:
  - Second and subsequent invocations
  - Daily usage after initial setup
  - Any time vault hasn't substantially changed
- Time breakdown for 1000 notes:
  - Loading cached embeddings: <1 second
  - Incremental sync (changed files only): 1-2 seconds
  - Geist execution: ~10-20 seconds
  - **Total: 30-40 seconds**

**Why the difference?**
The sentence-transformer model (all-MiniLM-L6-v2) computes semantic embeddings for every note. This happens once per note and results are cached in SQLite. Subsequent runs load embeddings from database (10x faster) rather than recomputing them.

**What to expect:**
- ✅ **Cold start once**: First invocation takes 3-5 minutes on 1000-note vault
- ✅ **Warm starts after**: Daily usage takes 30-60 seconds
- ✅ **This is normal**: The one-time investment enables fast semantic search
- ⚠️ **If every run is slow**: Check that `_geistfabrik/vault.db` isn't being deleted

---

### Understanding the Profiling Output

**Fast operations** (<100ms):
- ✅ Individual note lookups
- ✅ Graph operations (backlinks, hubs)
- ✅ Semantic similarity (k<10)
- ✅ Tracery geist execution

**Medium operations** (100ms-1s):
- 🟡 Vault sync (incremental only)
- 🟡 Metadata inference
- 🟡 Simple code geists

**Expensive operations** (>1s):
- 🔴 Embedding computation (first time: 100-200ms/note, cached: <10ms)
- 🔴 HDBSCAN clustering (now cached per session)
- 🔴 Large k-NN searches (k>100)

### Troubleshooting Slow Performance

**If geists timeout:**
```bash
# Increase timeout for large vaults
uv run geistfabrik invoke ~/my-vault --timeout 10
```

**If first run is slow:**
- Expected: 100-200ms per note (CPU-only embeddings)
- For 1000 notes: ~2-3 minutes one-time
- For 5000+ notes: Consider GPU acceleration (future)

**If daily runs are slow:**
- Should be fast (98.6% cache hit rate)
- Report as performance issue with `--debug` output

### Contributing Performance Data

Want to help improve performance? Submit benchmark data:

**Option 1: Cluster caching results**
- Run the benchmark (see above)
- Post results in GitHub issue
- Include vault size and system specs

**Option 2: Full profiling session**
```bash
# Capture complete profiling data
uv run geistfabrik invoke ~/my-vault --debug --no-filter --timeout 30 > perf_profile.txt 2>&1

# Compress and attach to GitHub issue
gzip perf_profile.txt
```

**Option 3: Memory profiling**
```python
# Add to your test script
import tracemalloc
tracemalloc.start()

# Run geistfabrik operation
clusters = vault.get_clusters()

# Report memory usage
current, peak = tracemalloc.get_traced_memory()
print(f"Peak memory: {peak / 1024 / 1024:.1f}MB")
tracemalloc.stop()
```

### Performance Optimisation Checklist

Before reporting slow performance, verify:

- [ ] Using cached embeddings? (daily runs should be fast)
- [ ] Incremental sync working? (only changed files)
- [ ] Timeout appropriate? (5s default, increase for large vaults)
- [ ] sklearn installed? (required for vectorization and clustering)
- [ ] System has >2GB RAM available?

### Questions About Performance?

- 📝 **GitHub Issues**: https://github.com/anthropics/geist_fabrik/issues
- 📚 **Performance Design Doc**: `docs/GEIST_INSTRUMENTATION_DESIGN.md`
- 🔍 **Use --debug**: Best tool for diagnosing slowness

**Thank you for helping make GeistFabrik faster!** 🚀

---

## Next Steps After Testing

1. **Share feedback** - Open issues for bugs or suggestions
2. **Create custom geists** - Make it yours
3. **Join discussions** - GitHub Discussions
4. **Watch for 1.0** - Coming in 1-2 months

---

**Thank you for testing!** Your feedback shapes how GeistFabrik evolves.

*Let's build a tool that asks different questions than you would ask yourself.*

---

*Last updated: 2026-07-11 (v0.10.1)*
