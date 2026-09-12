# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Vault synchronization now updates stable note paths in place, invalidates only
  current-content semantic caches, and preserves historical session embeddings;
  removed virtual-note paths still cascade cleanly. Synchronizers acquire the
  SQLite writer lock before filesystem discovery and validate the complete scan
  again before committing deletions, rolling back and retrying a changing vault.
  Schema v10 fingerprints exact file identity and nanosecond metadata, so a
  same-path replacement cannot hide behind a preserved coarse modification time.
- Every SQLite writer now owns an explicit transaction, rejects a pre-existing
  transaction, and rolls back failures so another component cannot accidentally
  publish partial work. Expensive embedding inference runs before the write lock,
  with optimistic version validation preventing stale results from overwriting a
  newer concurrent commit.
- sqlite-vec search projections are instance-private, explicitly disposable TEMP
  tables, preventing cross-session replacement and connection-lifetime buildup.
  Sessions now own their backend lifecycle, clean up on command/context exit, and
  safely recreate an explicitly closed backend. Production connections load the
  installed sqlite-vec package with extension loading immediately disabled again;
  TEMP cleanup needs no main-database writer lock. Obsolete durable `vec_search`
  projections are removed only when they match GeistFabrik's exact historical
  schema, without touching stored session embeddings or unrelated virtual tables.
- Embedding metric caches are schema-v9 derived records keyed by exact ordered
  paths, embedding bytes, label inputs, configuration, algorithm, and dependency
  identity. KeyBERT-labelled metrics remain computable but are not persisted
  because the loader does not expose a trustworthy model-artifact identity. Cache
  provenance reads only the bounded text prefix actually consumed by labelers.
- Schema version and structure checks now occur under the same writer lock as
  migration, closing a mixed-version downgrade race. The supported migration
  floor is explicit at v3; frozen v3 and v4 databases preserve durable rows,
  while older versions fail without modification.
- Cosine similarity uses scale-safe float64 normalization, rejects non-finite
  inputs and mismatched shapes, preserves tiny-vector self-similarity, and is
  clamped to its mathematical `[-1, 1]` range.
- Replaced the false database-corruption recovery check with an honest
  fail-without-overwrite contract and documented backup/rebuild recovery limits.
  Added frozen-v3/v4 migration coverage, mid-write rollback fault injection, and an
  actual child-process interruption/recovery test for journal reconciliation.
- CI now binds `uv` to the declared Python matrix interpreter and asserts the
  runtime version, so the full 3.12 lane no longer silently executes on 3.11.
- Project-wide Hypothesis review replaced false-green case, frontmatter, cosine,
  and partial-configuration properties with structured independent oracles that
  cover valid stacked frontmatter, real ASCII case variants, non-unit 384/387-D
  vectors, and every configuration section.
- Pattern Finder now compares notes in bounded similarity batches, eliminating
  the Python 3.12 CI timeout without reintroducing corpus sampling. Its regression
  test deterministically proves that notes beyond the historical 500-note cutoff
  are examined and can produce a suggestion.

### Packaging and release engineering
- Release wheels and source distributions now include the materialized
  Apache-2.0 `all-MiniLM-L6-v2` snapshot as an importlib resource, with
  provenance, checksums, and third-party license notice. Source-checkout and
  online HuggingFace fallback behaviour remains available.
- Added a required isolated package-smoke CI lane covering LFS materialization,
  artifact metadata/content/size, sdist-to-wheel reproducibility, clean wheel
  installation, console entry points, and real inference with empty caches and
  offline mode enforced.
- Consolidated pytest configuration in `pyproject.toml`, added explicit
  `artifact`/`production_model` markers, narrowed model stubbing to the external
  constructor, and made the fast CI/validation dependency, marker, timeout,
  offline, and branch-coverage contracts identical.
- Completed release metadata with MIT licensing, canonical project URLs,
  classifiers and keywords, and constrained supported Python to tested 3.11
  and 3.12. Updated model, offline, testing, and early-adopter documentation.

### Correctness, security, and type safety
- Unified path, title, section, block, and virtual-journal link resolution behind
  one ambiguity-aware index used by graph, filtering, similarity, and statistics
  consumers. Windows separators are normalized for matching and folder
  exclusions while database identities are preserved. Private-path boundaries
  now fail closed across every colliding literal or interpreted alias, and
  transactional resolver snapshots cannot survive a rollback.
- Date-collection parsing now ignores headings inside code, normalizes arbitrary
  YAML tag scalars before SQLite storage, includes parser/configuration identity
  in source fingerprints, preserves anchors, and updates stable virtual entries
  without discarding their historical session rows.
- Plugin loaders now publish modules under loader-private identities and stage
  decorated functions per registry, so concurrent vaults and failed imports
  cannot overwrite or leak one another's module or decorator state. Import
  interruptions and export-resolution failures restore `sys.modules` as well.
  `test-all` reports both code and Tracery load failures in its total.
- Temporal readers consistently exclude sessions after the replay date. Cluster
  computation has one configured implementation, handles small vaults, clears
  stale assignments, and versions persisted labels by algorithm settings.
- Repaired production dispatch of the existing v4–v8 additive SQLite
  migrations without a schema-version bump; future-version and ambiguous
  unversioned databases are rejected without mutation.
- Configuration now loads once from `_geistfabrik/config.yaml`, rejects every
  malformed/unknown field before command side effects, and validates bounded
  numeric, enum, mapping, allowlist, and filtering contracts.
- Journal creation/replacement is containment- and directory-identity-checked,
  serialized by the SQLite write lock, portable when hard links are unavailable,
  durably recoverable after interruption/process death, and exactly mirrored in
  `session_suggestions`.
- Explicit `test` and `test-all` runs exercise and can recover auto-disabled
  geists; normal invocation continues to respect disabled status.
- Code and Tracery geists now share timeout, error, profiling, persistent
  failure, and disable lifecycle behavior; debug timeouts count identically.
- Added bounded YAML, incremental Tracery output/preprocessing limits, Markdown
  file/structure limits, suggestion/session quotas, and managed-path containment
  checks. Custom Python plugins
  remain trusted code, not a sandbox, and hard interruption remains unavailable
  on Windows/non-main threads.
- Added pinned Astral `ty==0.0.69` as an additive whole-project warnings-as-errors
  gate alongside strict mypy, and repaired production/test typing contracts
  without a diagnostic baseline or global ignores.
- CI and local validation now enforce true branch-only coverage with an explicit
  compatible `coverage>=7.7` dependency instead of relying on combined statement
  coverage or a transitive tool version.
- Strengthened false-green tests, removed core-dependency and committed-fixture
  skips, made mtime tests deterministic, and separated benchmarks from the fast
  suite while retaining executable acceptance checks.
- Reconciled maintained guides, examples, status files, and specifications with
  the shipped CLI, Tracery preprocessing rules, bundled-geist configuration,
  clustering defaults, optional dependencies, and source-note-safe persistence
  behavior. Shipped vault-function examples now use the `count` convention,
  return Tracery-safe links, and avoid colliding with built-ins.

## [0.10.0] - 2026-06-12

### Breaking Changes
- **Pre-1.0 API consistency pass** (geist-facing `VaultContext` API). Custom
  geists must update; bundled geists, examples, and docs are already updated.
  - `note.obsidian_link` → **`note.link_text`** (the property returns link
    *text* without brackets; the old name implied it included them).
  - Result-count parameters are now uniformly **`count`** (were `k`/`limit`):
    `vault.sample(x, k=3)` → `vault.sample(x, count=3)`; likewise `neighbours`,
    `hubs`, `orphans`, `old_notes`, `recent_notes`, `random_notes`,
    `unlinked_pairs`, `recent_session_ids`, `get_cluster_representatives`, and
    the vector backends' `find_similar`/`find_similar_notes`. Descriptive
    params (`min_size`, `min_backlinks`, `candidate_limit`, `min_per_day`) are
    unchanged. `semantic_clusters` keeps `count` (seeds) and adds
    `neighbour_count` (per-seed neighbours).
  - **British spelling**: `graph_neighbors` → `graph_neighbours`,
    `k_hop_neighborhood` → `k_hop_neighbourhood`.
  - **`VaultContext.get_clusters()`** now returns `dict[int, Cluster]` (the
    typed dataclass) instead of `dict[int, dict[str, Any]]`; access fields as
    `cluster.notes`, `cluster.formatted_label`, etc.
  - **Action required**: update custom geists. No database rebuild needed.
- **Schema v8 — `geist_status` table** (persistent per-geist failure tracking).
  - **What changed**: a geist is now disabled after N *consecutive* failures
    (config `geist_execution.max_failures`, default 3), persisted across sessions; a
    successful run resets the count. Previously the counter was in-memory and
    could never reach the threshold.
  - **Action required**: none — additive migration applied automatically.
    Re-enable a disabled geist by fixing it and running
    `geistfabrik test <geist> <vault>`; a successful diagnostic run resets it.
    Normal invocation intentionally skips disabled geists.
- **Schema v7 — `session_embeddings.cluster_label`** column added (additive
  migration; fixes `cluster_evolution_tracker`, which queried a column that
  never existed). No rebuild required.
- **Virtual note title format change**: Fixed virtual note titles to exclude filename prefix
  - **What changed**: Virtual note titles now store ONLY the heading text (e.g., "2024 February 18") instead of the deeplink format (e.g., "Exercise journal#2024 February 18")
  - **Why**: The old format stored "filename#heading" in the title field, causing suggestions to display as `[[Exercise journal#Exercise journal#2024 February 18]]` (double filename prefix)
  - **Correct behaviour**:
    - `note.title` = `"2024 February 18"` (just the heading text)
    - `note.link_text` = `"Exercise journal#2024 February 18"` (property combines them)
    - Suggestions use `[[{note.link_text}]]` = `[[Exercise journal#2024 February 18]]`
  - **Action required**: Users with existing databases showing doubled filenames in virtual note links must rebuild:
    ```bash
    rm -rf <vault>/_geistfabrik/vault.db*
    uv run geistfabrik invoke <vault>
    ```
  - **Impact**: Existing vaults will show incorrect deeplinks (double filename prefix) until database is rebuilt
  - **Test coverage**: Added `test_year_month_day_obsidian_link_format()` integration test to prevent regression
  - **Reference**: Obsidian deeplink syntax: https://help.obsidian.md/Linking+notes+and+files/Internal+links#Link+to+a+heading+in+a+note

### Changed
- **Cluster Labelling**: Enhanced cluster naming with configurable KeyBERT method
  - **New default**: KeyBERT (semantic similarity) replaces c-TF-IDF for cluster labels
  - **Impact**: Cluster names will be more descriptive and semantically coherent
    - Before: "notes, knowledge, system, management" (single keywords)
    - After: "knowledge management systems, evergreen note-taking" (multi-word phrases)
  - **Migration**: Existing users will see different cluster names in new sessions
  - **Revert option**: Set `clustering.labeling_method: tfidf` in config.yaml to use old method
  - **Configuration**:
    ```yaml
    clustering:
      labeling_method: keybert  # or "tfidf" for legacy behaviour
      min_cluster_size: 5
      n_label_terms: 4
    ```
  - **Technical**: KeyBERT uses semantic similarity to cluster centroids vs frequency-based TF-IDF
  - **Performance**: ~0.1s overhead per cluster (measured on 2-cluster test: c-TF-IDF 0.004s, KeyBERT 0.194s)
    - Absolute overhead is minimal (~0.2s for typical session with 2-3 clusters)
    - Quality improvement easily justifies the small time cost
  - **Fallback**: Gracefully falls back to simple labels if sentence-transformers model unavailable

### Removed
- **congruence_mirror geist** - Removed due to scalability issues on large vaults
  - Timed out (60+ seconds) on vaults with 10,000+ notes and hundreds of thousands of links
  - O(L) algorithm processed all links individually causing 891,104 sklearn validation calls
  - Functionality partially covered by bridge_builder (IMPLICIT quadrant) and hidden_hub
  - Specification and historical documentation preserved for reference
  - Later entries in this release section that describe `congruence_mirror`
    optimisation or pre-consistency American API names record work from the
    development cycle that was superseded by this removal/API pass; they are
    historical notes, not current extension guidance.

### Performance
- **June 2026 perf pass** (before/after in `benchmarks/RESULTS_2026-06.md`,
  reproducible via `benchmarks/perf_before_after.py`):
  - `orphans()` O(N·M) → O(N+M) set-difference (the LEFT-JOIN `OR` was
    non-sargable; ~179× on a 6k-note synthetic vault).
  - `filter_diversity`/`filter_novelty` per-pair Python cosine loops →
    BLAS matrix operations (~1281× at S=200); novelty now uses bounded blocks
    across suggestions/history to cap peak memory in long histories.
  - `find_similar` top-k via `argpartition` (13× on the sort step;
    end-to-end is matmul-bound).
  - `island_hopper`, graph `find_bridges`/`detect_structural_holes` batch
    their similarity matrices; `detect_structural_holes` gains a candidate cap.
  - Sync stale-note deletion uses a temp table instead of `NOT IN (?,…)`,
    removing the SQLite variable-count hard cap (>32k notes).
  - Encode threads bounded via `threadpoolctl` instead of global
    `OMP_NUM_THREADS` env mutation at import.
  - `session_embeddings` retention window bounds unbounded DB growth.
- **BIG OPTIMISATION #1**: Fixed O(N²) algorithmic inefficiencies (6 locations)
  - **CRITICAL**: Fixed pattern_finder timeout on large vaults (10k+ notes)
    - Replaced O(N³) list.remove() in nested loops with O(N²) set.remove() (pattern_finder.py:88, 95)
  - Optimised stats command for large vaults:
    - Dict lookup instead of list.index() in vault drift computation (stats.py:591)
    - Dict lookup instead of list.index() in MMR term selection (stats.py:973)
    - Set membership instead of list membership in MMR loop (stats.py:966)
  - Optimised unlinked_pairs for large vaults:
    - Set membership instead of list membership (vault_context.py:619)
  - Added comprehensive unit tests (tests/unit/test_algorithmic_fixes.py)
  - Expected impact: Fixes timeouts on 10k vault, minor ~2-5% overall improvement

- **BIG OPTIMISATION #2**: sklearn vectorization + cache redundant norms (13 locations)
  - **Vectorized operations**: Replaced manual cosine similarity loops with sklearn
    - embeddings.py: cosine_similarity() function and find_similar_notes() batch computation
    - concept_drift.py: sklearn cosine similarity (2 places) + cached drift_vector norm
    - convergent_evolution.py: sklearn for similarity trajectory
    - divergent_evolution.py: sklearn for similarity trajectory
    - session_drift.py: sklearn in _calculate_drift()
  - **Euclidean distance**: Replaced np.linalg.norm with scipy.spatial.distance.euclidean
    - hermeneutic_instability.py: scipy for embedding distance from mean
    - vocabulary_expansion.py: scipy for centroid distance calculations
  - **Cached redundant norm**: Eliminated 5× redundant drift_vector norm in concept_drift.py loop
  - Added comprehensive unit tests (tests/unit/test_sklearn_migration.py)
  - Expected impact: 10-15% speedup on geist execution phase

- **BIG OPTIMISATION #3**: sklearn configuration tuning with benchmarking suite
  - **Optimisation flags**: Three tunable sklearn optimisations for large vaults (10k+ notes)
    - `assume_finite=True`: Skip NaN/inf validation (21% speedup, 23.2s → 19.4s avg)
    - `force_all_finite=False`: Relaxed validation in pairwise operations
    - NumPy array optimisations via environment variables
  - **Benchmarking infrastructure**: Comprehensive test harness for optimisation validation
    - scripts/benchmark_optimizations.py: Test 8 configs × 9 geists = 72 runs
    - scripts/analyze_benchmarks.py: Correctness validation + performance analysis
    - scripts/benchmark_config.py: Shared configuration for consistency
    - MD5 hash validation ensures optimisations don't change results
  - **Results on 10k vault**: All optimisations preserve correctness (identical outputs)
    - opt1_assume_finite: 21% faster overall, 24% faster on antithesis_generator
    - No timeouts with any configuration (120s timeout limit)
    - All configs produce identical suggestion hashes (validated via MD5)
  - **Implementation**: Environment variable configuration in embeddings.py
    - Allows A/B testing different optimisation strategies
    - Safe fallback to conservative defaults
  - See docs/SKLEARN_OPTIMIZATION_BENCHMARK.md for detailed methodology

### Added
- **Reflective lenses framework**: 11 new default geists that use observable
  linguistic and behavioural signals instead of speculative sentiment labels.
  - Code geists: `attention_shift`, `self_and_other`, `sentence_variance`,
    `surprisal`, `temporal_voice`, `this_time_last_year`,
    `uncertainty_mapper`, and `voice_absence`.
  - Tracery geists: `questioning_mind`, `temporal_contrast`, and
    `unexpected_neighbour`.
  - New typed voice analysis (`VoiceMetadata`) measures tense, pronouns,
    questions, hedging, sentence variance, and related structural signals in
    pure Python.
  - New cached `VaultContext` helpers: `voice()`, `surprisal_scores()`, and
    attention-shift/neighbour-churn analysis for reflective geists.
  - New vault functions for Tracery: `past_focused_notes`,
    `future_focused_notes`, `self_focused_notes`, `we_notes`,
    `uncertain_notes`, `questioning_notes`, `surprising_notes`, and
    `attention_shifted_notes`.
  - Comprehensive tests for voice analysis, reflective code geists, reflective
    Tracery geists, vault functions, and surprisal/churn properties.
- **NEW GEISTS**: Two temporal burst geists for detecting creative bursts
  - `creation_burst` - Detects days with 3+ notes created, asks provocative questions about productive moments
  - `burst_evolution` - Tracks how notes from burst days have evolved over time using drift analysis
  - Comprehensive unit tests (tests/unit/test_creation_burst.py, tests/unit/test_burst_evolution.py)
- Vault helper functions for cleaner code patterns:
  - `vault.has_link(a, b)` - Bidirectional link checking (src/geistfabrik/vault_context.py:523-535)
  - `vault.graph_neighbors(note)` - Get notes connected by links (src/geistfabrik/vault_context.py:537-562)
  - `vault.outgoing_links(note)` - Get notes this note links to (src/geistfabrik/vault_context.py:211-228)
- Database migration tests for schema version changes (tests/unit/test_sqlite_persistence.py)
  - Test v5→v6 migration correctness (6 tests)
  - Verify migration idempotency
  - Validate composite index creation
- Performance regression tests (tests/unit/test_performance_regression.py)
  - 8 tests covering caching, indexing, vectorization
  - Prevents future performance regressions
  - Documents optimisation patterns
- Real performance profiling with validated measurements
  - `scripts/profile_congruence_mirror.py` - Profiling script
  - `docs/congruence_mirror_profile_results.json` - Raw performance data
  - All vault sizes (10-1000 notes) meet performance targets with 36-99% headroom
- **DEBUGGING**: Performance instrumentation system with `--debug` flag
  - Function-level profiling using Python's cProfile
  - Detailed performance breakdown for timeouts and slow geists (>80% of timeout)
  - Smart pattern-based suggestions (HDBSCAN clustering, semantic searches, all_notes processing)
  - ProfileStats and GeistExecutionProfile dataclasses for execution tracking
  - Error handling to prevent profiling failures from crashing geist execution
  - See `docs/GEIST_INSTRUMENTATION_DESIGN.md` for complete design
- **PERFORMANCE**: Session-scoped cluster caching (75% speedup for cluster_mirror)
  - Eliminates redundant HDBSCAN clustering within session
  - get_clusters() results cached by min_size parameter
  - get_cluster_representatives() accepts optional clusters parameter
  - cluster_mirror geist optimised: 4 clusterings → 1 clustering
  - Comprehensive performance tests validate optimisation
- **PERFORMANCE (Phase 2)**: Batch note loading infrastructure (OP-6)
  - `vault.get_notes_batch(paths)` loads N notes in 3 queries instead of 3×N
  - Eliminates database query overhead by 66% for batch operations
  - Used by neighbours(), backlinks(), hubs() methods
  - Implementation: src/geistfabrik/vault.py
- **PERFORMANCE (Phase 2)**: neighbours() with return_scores parameter (OP-9)
  - Optional `return_scores=True` returns similarity scores with neighbours
  - Avoids recomputing similarities already computed during k-NN search
  - Type-safe implementation using `@overload` with `Literal` types
  - Used by 5 geists: hidden_hub, bridge_hunter, columbo, bridge_builder, antithesis_generator
  - Eliminates 50-100 redundant similarity computations per session

### Changed
- **PERFORMANCE (Phase 2)**: Single-pass congruence_mirror algorithm (OP-4)
  - Refactored from 4 separate passes to 1 combined pass
  - Before: 60.838s, After: 1.930s on 3406-note vault
  - Actual speedup: 31.5x (97% reduction)
  - Multiplicative effect: single-pass (4x) + cached similarity (3x) + cached links (2x) + batch loading (1.3x)
  - Implementation: src/geistfabrik/default_geists/code/congruence_mirror.py
- **PERFORMANCE (Phase 2)**: Optimised hubs() SQL query (OP-8)
  - Uses JOIN to resolve link targets in SQL instead of Python
  - Eliminates k×3 oversampling pattern
  - Combined with batch loading (OP-6) for maximum efficiency
  - 15-25% faster hub queries
- **PERFORMANCE**: Session-level caching for `vault.notes()` calls
  - Reduces redundant file system operations within same session
  - Cached at VaultContext level for consistency
  - 98.6% reduction in redundant I/O operations
- **PERFORMANCE**: Vectorized similarity matrix computation in stats module
  - Uses `sklearn.metrics.pairwise.cosine_similarity` when available
  - Replaces O(n²) nested loops with vectorized NumPy operations
  - 5.4x speedup for embedding similarity calculations
- **PERFORMANCE**: Optimised graph operations using `itertools.combinations`
  - `concept_cluster` geist now uses combinations instead of nested loops
  - Cleaner code with identical functionality
- Improved orphan query performance with optimised SQL
  - Changed from `NOT IN (subquery)` to `LEFT JOIN` pattern
  - 85.6% faster orphan queries with composite indexing
  - Better query plan and index utilisation
- Refactored 4 geist files to use new helper functions:
  - congruence_mirror.py - outgoing_links() and has_link()
  - density_inversion.py - graph_neighbors()
  - divergent_evolution.py - outgoing_links()
  - method_scrambler.py - outgoing_links()
  - 80-85% reduction in link resolution boilerplate

### Fixed
- Redundant `vault.notes()` calls in 8 geist files:
  - congruence_mirror.py (3 functions)
  - metadata_driven_discovery.py (3 functions)
  - on_this_day.py (1 function)
  - seasonal_revisit.py (1 function)
- Redundant `links_between()` calls in congruence_mirror
  - Now uses `has_link()` helper (eliminates duplicate bidirectional check)
- Line number references in documentation after helper function additions
  - Fixed 14 references across 4 documentation files
  - All references now accurate to actual source code locations

### Documentation
- **NEW**: `docs/PERFORMANCE_OPTIMIZATION_RESULTS.md` - Comprehensive performance optimisation results
  - All Phase 1, 2, and 3 optimisations (OP-1 through OP-9)
  - Measured results: 38-46% session speedup, 86.3% cache hit rate, 69MB memory on 1000-note vault
  - Benchmark summary, cache hit rates, memory usage, testing coverage
  - Replaces and consolidates earlier performance documentation
- **NEW**: `docs/PERFORMANCE_COMPARISON_2025_10_31.md` - Real performance measurements
  - Session execution 16% faster overall (16.8s → 14.1s for 1000 notes)
  - Geist phase 56% faster (4.8s → 2.1s)
  - Similarity computations 5.4x speedup
  - Comprehensive scalability analysis with real data
- **NEW**: `docs/LIST_VS_ITERATOR_ANALYSIS.md` - Memory efficiency analysis
  - Comprehensive analysis of 15 VaultContext methods
  - Memory overhead <100 KB for 10,000-note vault (negligible)
  - Recommendation: Keep lists (better usability, no breaking changes)
- Updated `specs/performance_optimization_spec.md` - All phases marked complete
  - Phase 1, 2, and 3 status: ✅ COMPLETED
  - Includes measured 31.5x speedup for OP-4 (congruence_mirror)
  - Documents 5 geists using OP-9 (return_scores)
- Updated `README_EARLY_ADOPTERS.md` - Added Phase 2 benchmark section
  - Instructions for profiling congruence_mirror and other Phase 2 geists
  - Expected results and reporting template for early adopters
- Updated `specs/VAULT_HELPER_FUNCTIONS_DESIGN.md` to "✅ Implemented" status
- Updated `examples/README.md` with helper function demonstrations
- Updated `STATUS.md` with accurate test counts (513 total, 100% passing)

### Database Schema

#### v6 (2025-10-31)
- Added composite index `idx_links_target_source ON links(target, source_path)`
  - Optimizes orphan detection queries (85.6% faster)
  - Improves LEFT JOIN performance for backlink operations
  - Migration from v5 handled automatically

### Performance
- **Overall session execution**: 16% faster (16.8s → 14.1s)
- **Geist execution phase**: 56% faster (4.8s → 2.1s)
- **Similarity computations**: 5.4x speedup
- **Orphan queries**: 85.6% faster
- **Memory increase**: Minimal (+2MB, <1%)

## [0.9.0] - 2025-10-29

### Added
- Pluggable vector search backend architecture for extensibility
- `SqliteVecBackend` implementation using sqlite-vec extension
- Benchmarking suite for comparing vector search backend performance
- Comprehensive test suite for vector search backends with known-answer tests

### Changed
- Vector search now uses pluggable backend system (default: BruteForceSqliteBackend)
- Improved test coverage and reliability for vector search operations

### Fixed
- Critical bug: corrected cosine distance computation (was using L2 distance)
- macOS SQLite compatibility issues with extension loading
- CI test failures related to sqlite-vec dependency loading
- Replaced `pytest.importorskip` with explicit `SQLITE_VEC_LOADABLE` checks

### Documentation
- Added comprehensive vector search backends documentation
- Updated documentation to reflect v0.9.0 implementation reality

## [0.4.0] - 2025-10-28

### Added
- Date-collection notes support for journal files with date headings
- Year-Month-Day date format support (e.g., "2022 August 8")
- Virtual entry system for notes split from journal files

### Changed
- Optimised date-collection processing to eliminate vault duplication

### Fixed
- Hub explorer variety tests updated for new preprocessing behaviour

## [0.3.0] - 2025-10-27

### Added
- 47 bundled default geists (38 code geists, 9 Tracery geists)
- Comprehensive quality audit and geist writing guide
- Default geists system with auto-loading from package

### Changed
- Expanded default geists from 14 to 45 with quality improvements
- Removed `--examples` flag; all geists now bundled by default
- Moved example geists to learning materials (not for installation)

### Fixed
- Integration tests updated to use bundled default geists
- Test file paths corrected to reference bundled geists

### Documentation
- Updated documentation to emphasize bundled defaults over examples
- Added default geists specification with implementation status

## [0.2.0] - 2025-10-25

### Added
- Tracery vault function pre-population for deterministic sampling
- Comprehensive unit tests for all Tracery geists
- Metadata inference failure tracking
- Centralized configuration module for magic numbers
- CLI validation command for geist verification

### Changed
- Deterministic geist execution using config file order
- Standardised on `count` parameter (removed `suggestions_per_invocation`)
- Made Note objects hashable for cleaner deduplication

### Fixed
- Unhashable type errors in method_scrambler and density_inversion geists
- Type conversion for Tracery function arguments
- Non-deterministic test failures
- Missing type parameters for mypy --strict compliance

### Documentation
- Added comprehensive technical codebase audit (38 findings)
- Added CI validation guide to prevent build failures
- Added post-mortem analysis for PR #30 CI failures
- Added critical development workflow section to CLAUDE.md

## [0.1.0] - 2025-10-21

### Added
- Core vault layer with SQLite persistence and incremental sync
- Embedding computation using sentence-transformers (all-MiniLM-L6-v2)
- Temporal embeddings combining semantic and temporal features
- VaultContext providing rich execution environment for geists
- Tracery grammar support for declarative geist authoring
- Metadata inference system with extensible modules
- Vault functions registry for Tracery integration
- Filtering pipeline (boundary, novelty, diversity, quality checks)
- Session journal output with block IDs for linking
- CLI with multiple invocation modes (default, full, single geist, replay)
- Test suite with comprehensive unit and integration tests
- Pre-commit hooks (ruff linting/formatting, YAML validation)
- Bundled sentence-transformers model for offline use

### Features
- 14 initial code geists demonstrating diverse suggestion patterns
- Support for both code geists (Python) and Tracery geists (YAML)
- Deterministic randomness based on date seed
- Read-only vault access (never destructive)
- Local-first architecture (no network required)
- Three-dimensional extensibility (metadata, functions, geists)

### Documentation
- Complete technical specification (~1500 lines)
- Design philosophy and vision documents
- Tracery research and implementation notes
- Architecture diagram
- Early adopters README
- Testing summary and results
- Contributing guidelines

[unreleased]: https://github.com/adewale/geist_fabrik/compare/v0.10.0...HEAD
[0.10.0]: https://github.com/adewale/geist_fabrik/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/adewale/geist_fabrik/compare/v0.4.0...v0.9.0
[0.4.0]: https://github.com/adewale/geist_fabrik/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/adewale/geist_fabrik/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/adewale/geist_fabrik/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/adewale/geist_fabrik/releases/tag/v0.1.0
