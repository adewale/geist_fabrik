# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Cluster Labeling**: Enhanced cluster naming with configurable KeyBERT method
  - **New default**: KeyBERT (semantic similarity) replaces c-TF-IDF for cluster labels
  - **Impact**: Cluster names will be more descriptive and semantically coherent
    - Before: "notes, knowledge, system, management" (single keywords)
    - After: "knowledge management systems, evergreen note-taking" (multi-word phrases)
  - **Migration**: Existing users will see different cluster names in new sessions
  - **Revert option**: Set `clustering.labeling_method: tfidf` in config.yaml to use old method
  - **Configuration**:
    ```yaml
    clustering:
      labeling_method: keybert  # or "tfidf" for legacy behavior
      min_cluster_size: 5
      n_label_terms: 4
    ```
  - **Technical**: KeyBERT uses semantic similarity to cluster centroids vs frequency-based TF-IDF
  - **Performance**: ~0.5-1s slower per cluster, but significantly better label quality
  - **Fallback**: Gracefully falls back to simple labels if sentence-transformers model unavailable

### Removed
- **congruence_mirror geist** - Removed due to scalability issues on large vaults
  - Timed out (60+ seconds) on vaults with 10,000+ notes and hundreds of thousands of links
  - O(L) algorithm processed all links individually causing 891,104 sklearn validation calls
  - Functionality partially covered by bridge_builder (IMPLICIT quadrant) and hidden_hub
  - Specification and historical documentation preserved for reference

### Performance
- **BIG OPTIMIZATION #1**: Fixed O(N²) algorithmic inefficiencies (6 locations)
  - **CRITICAL**: Fixed pattern_finder timeout on large vaults (10k+ notes)
    - Replaced O(N³) list.remove() in nested loops with O(N²) set.remove() (pattern_finder.py:88, 95)
  - Optimized stats command for large vaults:
    - Dict lookup instead of list.index() in vault drift computation (stats.py:591)
    - Dict lookup instead of list.index() in MMR term selection (stats.py:973)
    - Set membership instead of list membership in MMR loop (stats.py:966)
  - Optimized unlinked_pairs for large vaults:
    - Set membership instead of list membership (vault_context.py:619)
  - Added comprehensive unit tests (tests/unit/test_algorithmic_fixes.py)
  - Expected impact: Fixes timeouts on 10k vault, minor ~2-5% overall improvement

- **BIG OPTIMIZATION #2**: sklearn vectorization + cache redundant norms (13 locations)
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

- **BIG OPTIMIZATION #3**: sklearn configuration tuning with benchmarking suite
  - **Optimization flags**: Three tunable sklearn optimizations for large vaults (10k+ notes)
    - `assume_finite=True`: Skip NaN/inf validation (21% speedup, 23.2s → 19.4s avg)
    - `force_all_finite=False`: Relaxed validation in pairwise operations
    - NumPy array optimizations via environment variables
  - **Benchmarking infrastructure**: Comprehensive test harness for optimization validation
    - scripts/benchmark_optimizations.py: Test 8 configs × 9 geists = 72 runs
    - scripts/analyze_benchmarks.py: Correctness validation + performance analysis
    - scripts/benchmark_config.py: Shared configuration for consistency
    - MD5 hash validation ensures optimizations don't change results
  - **Results on 10k vault**: All optimizations preserve correctness (identical outputs)
    - opt1_assume_finite: 21% faster overall, 24% faster on antithesis_generator
    - No timeouts with any configuration (120s timeout limit)
    - All configs produce identical suggestion hashes (validated via MD5)
  - **Implementation**: Environment variable configuration in embeddings.py
    - Allows A/B testing different optimization strategies
    - Safe fallback to conservative defaults
  - See docs/SKLEARN_OPTIMIZATION_BENCHMARK.md for detailed methodology

### Added
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
  - Documents optimization patterns
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
  - cluster_mirror geist optimized: 4 clusterings → 1 clustering
  - Comprehensive performance tests validate optimization
- **PERFORMANCE (Phase 2)**: Batch note loading infrastructure (OP-6)
  - `vault.get_notes_batch(paths)` loads N notes in 3 queries instead of 3×N
  - Eliminates database query overhead by 66% for batch operations
  - Used by neighbours(), backlinks(), hubs() methods
  - Implementation: src/geistfabrik/vault.py
- **PERFORMANCE (Phase 2)**: neighbours() with return_scores parameter (OP-9)
  - Optional `return_scores=True` returns similarity scores with neighbors
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
- **PERFORMANCE (Phase 2)**: Optimized hubs() SQL query (OP-8)
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
- **PERFORMANCE**: Optimized graph operations using `itertools.combinations`
  - `concept_cluster` geist now uses combinations instead of nested loops
  - Cleaner code with identical functionality
- Improved orphan query performance with optimized SQL
  - Changed from `NOT IN (subquery)` to `LEFT JOIN` pattern
  - 85.6% faster orphan queries with composite indexing
  - Better query plan and index utilization
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
- **NEW**: `docs/PERFORMANCE_OPTIMIZATION_RESULTS.md` - Comprehensive performance optimization results
  - All Phase 1, 2, and 3 optimizations (OP-1 through OP-9)
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
- Optimized date-collection processing to eliminate vault duplication

### Fixed
- Hub explorer variety tests updated for new preprocessing behavior

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
- Standardized on `count` parameter (removed `suggestions_per_invocation`)
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

[unreleased]: https://github.com/adewale/geistfabrik/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/adewale/geistfabrik/compare/v0.4.0...v0.9.0
[0.4.0]: https://github.com/adewale/geistfabrik/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/adewale/geistfabrik/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/adewale/geistfabrik/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/adewale/geistfabrik/releases/tag/v0.1.0
