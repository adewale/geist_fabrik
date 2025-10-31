# Changelog

All notable changes to GeistFabrik will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Vault helper functions for cleaner code patterns:
  - `vault.has_link(a, b)` - Bidirectional link checking (src/geistfabrik/vault_context.py:504-516)
  - `vault.graph_neighbors(note)` - Get notes connected by links (src/geistfabrik/vault_context.py:518-543)
  - `vault.outgoing_links(note)` - Get notes this note links to (src/geistfabrik/vault_context.py:211-228)
- Database migration tests for schema version changes (tests/unit/test_sqlite_persistence.py)
  - Test v5→v6 migration correctness (6 tests)
  - Verify migration idempotency
  - Validate composite index creation
- Performance regression tests (tests/unit/test_performance_regression.py)
  - 8 tests covering caching, indexing, vectorization
  - Prevents future performance regressions
  - Documents optimization patterns

### Changed
- **PERFORMANCE**: Session-level caching for `vault.notes()` calls
  - Reduces redundant file system operations within same session
  - Cached at VaultContext level for consistency
  - Geists updated to cache `vault.notes()` before loops (8 files)
- **PERFORMANCE**: Vectorized similarity matrix computation in stats module
  - Uses `sklearn.metrics.pairwise.cosine_similarity` when available
  - Replaces O(n²) nested loops with vectorized NumPy operations
  - Estimated 50-70% speedup for embedding similarity calculations
- **PERFORMANCE**: Optimized graph operations using `itertools.combinations`
  - `concept_cluster` geist now uses combinations instead of nested loops
  - Cleaner code with identical functionality
- Improved orphan query performance with optimized SQL
  - Changed from `NOT IN (subquery)` to `LEFT JOIN` pattern
  - Better query plan and index utilization

### Fixed
- Redundant `vault.notes()` calls in 8 geist files:
  - congruence_mirror.py (3 functions)
  - metadata_driven_discovery.py (3 functions)
  - on_this_day.py (1 function)
  - seasonal_revisit.py (1 function)
- Redundant `links_between()` calls in congruence_mirror
  - Now uses `has_link()` helper (eliminates duplicate bidirectional check)

### Documentation
- **PERFORMANCE_COMPARISON_2025_10_31.md** - Before/after analysis with measurements
  - Session execution 16% faster overall
  - Geist phase 56% faster
  - Similarity computations 5.4x speedup
  - Comprehensive scalability analysis

### Database Schema

#### v6 (2025-10-31)
- Added composite index `idx_links_target_source ON links(target, source_path)`
  - Optimizes orphan detection queries (85.6% faster)
  - Improves LEFT JOIN performance for backlink operations
  - Migration from v5 handled automatically

## [0.9.0] - 2025-10-21

### Initial Release
- Complete implementation of GeistFabrik divergence engine
- 45 bundled geists (35 code, 10 Tracery)
- Temporal embeddings with session tracking
- Comprehensive test suite (402 unit, 91 integration tests)
- Full documentation and specifications

---

[Unreleased]: https://github.com/yourusername/geistfabrik/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/yourusername/geistfabrik/releases/tag/v0.9.0
