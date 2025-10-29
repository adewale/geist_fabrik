# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- 1.0 release with production-ready stability
- Enhanced documentation for early adopters

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
- 45 bundled default geists (36 code geists, 9 Tracery geists)
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
