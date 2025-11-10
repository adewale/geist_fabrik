# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GeistFabrik** is a Python-based divergence engine for Obsidian vaults that generates creative suggestions through both code and Tracery grammars. The name comes from German for "spirit factory" - the system is called GeistFabrik, and individual generative prompts are called "geists."

Inspired by Gordon Brander's work on tools for thought, it implements "muses, not oracles" - suggestions that are provocative rather than prescriptive, generating "What if...?" questions rather than answers.

## Current Project State

**Version**: 0.9.0 (Beta)
**Status**: Feature-complete, approaching 1.0 release
**Tests**: All passing ✅ (100%)
**Code**: ~10,500 lines across 15 source modules

This repository contains:
- **src/geistfabrik/**: Complete implementation of all core modules
  - **default_geists/**: 51 bundled geists (42 code, 9 Tracery) - automatically available
    - _Counts programmatically verified via src/geistfabrik/default_geists/__init__.py_
- **tests/**: Comprehensive test suite (all passing)
- **examples/**: Learning materials demonstrating extension patterns (NOT for installation)
- **specs/**: Original technical specifications (all implemented)
- **testdata/**: Sample Obsidian vault notes from kepano's vault for testing
- **models/**: Bundled sentence-transformers model (all-MiniLM-L6-v2) in Git LFS

The system is fully functional and operational. All phases of the specification have been implemented.

### Default Geists vs Examples

**Important distinction:**
- **Default geists** (src/geistfabrik/default_geists/): 51 bundled geists that work automatically
  - Users can enable/disable via config.yaml
  - No installation needed - they're part of the package
- **Examples** (examples/): Learning materials showing extension patterns
  - NOT meant to be installed into vaults
  - Demonstrate how to write custom geists, functions, metadata modules
  - For reference and learning only

## Development Workflow (CRITICAL)

**BEFORE COMMITTING OR PUSHING CODE, ALWAYS FOLLOW THIS WORKFLOW:**

### Pre-Commit (Automatic)
Pre-commit hooks run automatically on `git commit`:
- Ruff linting and formatting
- Trailing whitespace removal
- YAML validation
- Basic checks

### Before Pushing (MANDATORY)

**Run the validation script:**
```bash
./scripts/validate.sh
```

This script runs the **exact same checks as CI**:
1. `ruff check src/ tests/` - Linting
2. `mypy src/ --strict` - Type checking (STRICT MODE)
3. `python scripts/detect_unused_tables.py` - Database validation
4. `pytest tests/unit -v` - Unit tests
5. `pytest tests/integration -v -m "not slow"` - Integration tests

**If validate.sh passes, CI will pass. If it fails, DO NOT PUSH.**

### Common Mistakes to Avoid

❌ **NEVER** run custom variations of CI checks:
```bash
# These are WRONG and will cause CI failures
mypy src/geistfabrik --ignore-missing-imports
mypy src/ --config-file mypy.ini
pytest tests/ -k "unit"
```

✅ **ALWAYS** use the validated script:
```bash
./scripts/validate.sh
```

### Type Checking Requirements

CI uses `mypy --strict` which requires:
- Explicit type parameters for generics: `dict[str, Any]` not `dict`
- Type hints on all function parameters and returns
- No implicit `Any` types

**Type Hint Style**: GeistFabrik uses **modern Python 3.9+ syntax** (PEP 585) for built-in types:
- Use `list[Type]`, `dict[K, V]`, `tuple[T, ...]` (lowercase, no imports)
- NOT `List[Type]`, `Dict[K, V]`, `Tuple[T, ...]` (from `typing`)

**Example - Missing Type Parameters** (This will fail CI):
```python
# ❌ WRONG - Missing type parameters
def from_dict(cls, data: dict) -> Config:  # dict needs [str, Any]
    pass

# ✅ CORRECT - Type parameters provided
from typing import Any

def from_dict(cls, data: dict[str, Any]) -> Config:
    pass
```

**Example - Geist Return Type**:
```python
# ✅ CORRECT - Modern syntax
def suggest(vault: "VaultContext") -> list["Suggestion"]:
    return []
```

### Why This Matters

**Lesson from PR #30**: Skipping validate.sh causes CI failures that waste hours of debugging time. The validation script exists specifically to prevent this. Use it.

**See**: `docs/CI_VALIDATION_GUIDE.md` and `docs/POST_MORTEM_PR30.md` for detailed explanation.

### Optimisation Lessons (Phase 3B Rollback)

**Context**: In November 2025, several "optimisations" were introduced to improve geist performance on large vaults (10k+ notes). After benchmarking and analysis, these optimisations were rolled back because they **reduced suggestion quality** while providing minimal performance gains.

**Key Lessons**:

1. **Profile First, Optimise Second**
   - **What happened**: pattern_finder added sampling (500 notes from 10k vault) without profiling
   - **Reality**: Phrase extraction was the bottleneck (67.7% of time), not corpus iteration
   - **Impact**: Saved ~20s but lost 95% pattern coverage
   - **Lesson**: Measure before optimising—intuition often misleads about bottlenecks

2. **Respect Session-Scoped Caches**
   - **What happened**: scale_shifter switched from `similarity()` to `batch_similarity()`
   - **Reality**: `batch_similarity()` bypasses session cache that other geists populate
   - **Impact**: Recomputed similarities already cached, losing 15-25% speedup potential
   - **Lesson**: Individual `similarity()` calls > batch calls when cache is warm

3. **Quality Wins Over Speed**
   - **What happened**: Both optimisations prioritised speed over accuracy
   - **Reality**: Users prefer slightly slower geists that generate good suggestions
   - **Impact**: Reduced suggestion quality led to worse user experience
   - **Lesson**: A 5-second geist that works > 2-second geist that doesn't

**Current Performance Status** (post-rollback):
- ✅ pattern_finder: 76s on 10k vault, full coverage, quality suggestions
- ✅ scale_shifter: Cache-aware, benefits from warm cache
- ✅ All 51 geists: Pass timeout thresholds on production vaults

**Implementation Guidance**:
- Use `similarity()` not `batch_similarity()` for cache benefits
- Build lookup structures (sets, dicts) instead of O(N) repeated searches
- Profile with `cProfile` before optimising—don't guess bottlenecks
- Adaptive sampling: `min(N, max(50, len(notes)//10))` not fixed sizes
- See `docs/POST_MORTEM_PHASE3B.md` for detailed salvage analysis

**Regression Prevention**:
- Regression tests: `tests/integration/test_phase3b_regression.py`
- Performance guidance: `docs/WRITING_GOOD_GEISTS.md` (Performance Guidance section)
- Static checks: Tests verify no `batch_similarity` in cache-sensitive geists

## Core Architecture

GeistFabrik uses a two-layer architecture for understanding Obsidian vaults:

### Layer 1: Vault (Raw Data)
- Python class that provides read-only access to vault files
- Parses Markdown files, extracts links/tags/metadata
- Handles both atomic notes and date-collection notes
- Syncs filesystem changes to SQLite database incrementally
- Computes embeddings using sentence-transformers (all-MiniLM-L6-v2)
- Stores embeddings as SQLite BLOBs, loads into memory for similarity search

### Layer 2: VaultContext (Rich Execution Context)
- Wraps the Vault with intelligence and utilities
- What geists actually receive when they execute
- Provides semantic search, graph operations, metadata access
- Includes deterministic randomness (same seed = same results)
- Manages function registry for extensibility

### Persistence: SQLite
- Single database at `<vault>/_geistfabrik/vault.db`
- Stores notes, links, embeddings (as BLOBs), execution history
- Incremental updates (only reprocess changed files)
- Fast indexed queries for graph operations
- Vector similarity computed in-memory using NumPy cosine distance

### Geist Types
1. **Code geists**: Python functions in `<vault>/_geistfabrik/geists/code/` that receive VaultContext and return Suggestions
2. **Tracery geists**: YAML files in `<vault>/_geistfabrik/geists/tracery/` using Tracery grammar with `$vault.*` function calls

### Output: Session Notes
- Each session creates `<vault>/geist journal/YYYY-MM-DD.md`
- Contains suggestions with geist identifiers and block IDs (`^gYYYYMMDD-NNN`)
- Sessions are linkable and embeddable like any Obsidian note

## Key Design Principles

1. **Muses, not oracles** - Provocative, not prescriptive
2. **Questions, not answers** - "What if...?" not "Here's how"
3. **Sample, don't rank** - Random sampling to avoid preferential attachment
4. **Intermittent invocation** - User-initiated, not continuous background
5. **Local-first** - No network required, embeddings computed locally
6. **Deterministic randomness** - Same date + vault = same output
7. **Never destructive** - Read-only vault access, only writes session notes
8. **Extensible at every layer** - Metadata, functions, and geists are all user-extensible

## Key Architectural Decisions

### Vault Function Link Formatting (Consistent API)

**Design Principle**: All vault functions return Obsidian wikilinks with brackets already included.

**The Consistent Pattern**:

```python
# ALL vault functions return bracketed links:
sample_notes(3) → ["[[Note A]]", "[[Note B]]", "[[Note C]]"]
orphans(2) → ["[[Orphan 1]]", "[[Orphan 2]]"]
semantic_clusters(2, 3) → ["[[Seed]]|||[[N1]], [[N2]]"]  # Delimiter-separated but still bracketed

# Templates use function results as-is (NO additional brackets):
origin: "Check out #note#"  # ✓ Correct
origin: "[[#note#]]"         # ✗ Wrong - produces [[[[Note]]]]
```

**Why This Matters**:
- **Consistency**: Developers don't need to remember different patterns for different functions
- **Simplicity**: Templates just use `#symbol#` - no bracket logic needed
- **Correctness**: Eliminates bugs from forgetting to add brackets to specific references

**The Cluster Pattern** (for advanced use cases):

Some vault functions bundle multiple related notes using delimiters to work around Tracery's preprocessing order:

```python
# Problem: Can't pass expanded symbols to vault functions
$vault.neighbours(#note#, 3)  # ✗ Fails - #note# not expanded during preprocessing

# Solution: Cluster functions bundle seed + related notes with delimiters
semantic_clusters(2, 3) → ["[[Seed]]|||[[N1]], [[N2]]"]

# Custom modifiers extract parts:
cluster: ["$vault.semantic_clusters(2, 3)"]
seed: ["#cluster.split_seed#"]           # Extracts "[[Seed]]"
neighbours: ["#cluster.split_neighbours#"]  # Extracts "[[N1]], [[N2]]"

# Template uses extracted values (already bracketed):
origin: "#seed# shares space with #neighbours#"
```

**Implementation locations**:
- Pattern implementation: `src/geistfabrik/function_registry.py::semantic_clusters()`
- Custom modifiers: `src/geistfabrik/tracery.py::_split_seed()`, `_split_neighbours()`
- Validation: `src/geistfabrik/tracery.py::_validate_grammar()`
- Documentation: `specs/tracery_research.md` (Designing Tracery-Safe Vault Functions section)
- Tests: `tests/unit/test_tracery.py::test_tracery_split_*_modifier()`, `tests/unit/test_tracery_geists.py::test_semantic_clusters_*`

**Future cluster functions** (post-1.0, see `docs/GeistFabrik2.0_Wishlist.md`):
- `contrarian_clusters(count, k)` - Seed + contrarian notes
- `temporal_clusters(count, k)` - Seed + temporally related notes
- `bridge_clusters(count)` - Two distant notes + their bridge
- `tag_clusters(count, k)` - Tag + notes with that tag

**Historical Note**: Before v0.9.1, GeistFabrik had an API inconsistency where simple functions returned bare text and cluster functions returned bracketed links. This was fixed in a breaking change (commit d080f66) to establish the current consistent pattern where ALL functions return bracketed links.

### Lessons Learned: API Consistency (November 2025)

**Context**: In November 2025, a bug was discovered in the `semantic_neighbours` Tracery geist where neighbour note references were missing `[[...]]` brackets. Investigation revealed a deeper API design issue.

**The Problem**:
- **Original Design** (pre-v0.9.1): Simple vault functions returned bare text (`"Note Title"`), while cluster functions returned bracketed links (`"[[Note Title]]"`)
- **Why it existed**: Cluster functions needed to bundle multiple notes with delimiters, making bracket addition in templates difficult
- **The bug**: Missing brackets in neighbour references because developers forgot which pattern applied where

**The Investigation**:
1. **Immediate fix** (commit 3efc96c): Documented the API inconsistency as intentional, added comprehensive tests
2. **Root cause analysis**: Realized the two-pattern API was a design flaw, not a necessary trade-off
3. **Better solution** (commit d080f66): Breaking change to make ALL functions return bracketed links

**The Breaking Change**:
- Updated 7 vault functions to return bracketed links: `sample_notes()`, `old_notes()`, `recent_notes()`, `random_note_title()`, `orphans()`, `hubs()`, `neighbours()`
- Updated 7 Tracery geists to remove `[[...]]` from templates
- Result: **Consistent API** - all functions follow the same pattern

**Why This Was The Right Call**:
- ✅ **Eliminates confusion**: Developers don't need to remember two patterns
- ✅ **Prevents bugs**: No more forgetting to add brackets to specific references
- ✅ **Simplifies templates**: Just use `#symbol#`, never `[[#symbol#]]`
- ✅ **Acceptable timing**: Pre-1.0, so breaking changes are expected

**Key Lesson**: API consistency is more important than avoiding breaking changes in beta. When you discover a fundamental design flaw, fix it immediately rather than documenting it as "intentional".

**See Also**:
- Commit 3efc96c: Initial documentation of the inconsistency
- Commit d080f66: Breaking change implementing consistent API
- `specs/tracery_research.md`: Updated technical documentation
- `tests/unit/test_tracery_geists.py`: Regression tests to prevent similar bugs

## Three-Dimensional Extensibility

1. **Metadata Inference** (`<vault>/_geistfabrik/metadata_inference/`)
   - Modules export `infer(note, vault) -> Dict`
   - Add properties like complexity, sentiment, reading_time
   - Properties flow through VaultContext, not Note objects
   - Notes stay lightweight; intelligence lives in context

2. **Vault Functions** (`<vault>/_geistfabrik/vault_functions/`)
   - Decorated with `@vault_function("name")`
   - Bridge between metadata and Tracery
   - Automatically available as `$vault.function_name()` in Tracery
   - Critical: Each metadata type needs a function to be Tracery-accessible

3. **Geists** (`<vault>/_geistfabrik/geists/code/` and `<vault>/_geistfabrik/geists/tracery/`)
   - Code geists: Full Python with VaultContext access
   - Tracery geists: Declarative YAML using registered functions
   - All geists run every session; filtering prevents overwhelm

## Temporal Embeddings

A key architectural feature: GeistFabrik computes fresh embeddings for all notes at each session, enabling:
- Tracking how understanding of notes evolves over time
- Detecting interpretive drift even when content doesn't change
- Discovering temporal patterns and seasonal thinking rhythms
- Identifying notes developing toward or away from each other

Embeddings combine semantic (384 dims from sentence-transformers) with temporal features (3 dims: note age, creation season, session season).

## Data Structures

### Note (Immutable)
```python
@dataclass
class Note:
    path: str                    # Relative path or virtual path
    title: str                   # Note title
    content: str                 # Full markdown content
    links: List[Link]            # Outgoing [[links]]
    tags: List[str]              # #tags found in note
    created: datetime            # File creation or entry date
    modified: datetime           # File modification time
    # Virtual entry fields (for date-collection notes)
    is_virtual: bool = False     # True for journal entries
    source_file: str | None = None  # Source file for virtual entries
    entry_date: date | None = None  # Date from heading for virtual entries
```

**Virtual Entries**: Notes with `is_virtual=True` are split from journal files with date headings. They have synthetic paths like `Journal.md/2025-01-15` and can be linked, queried, and referenced like regular notes. See `docs/JOURNAL_FILES.md` for details.

### Suggestion
```python
@dataclass
class Suggestion:
    text: str           # 1-2 sentence suggestion (variable length)
    notes: List[str]    # Referenced note titles
    geist_id: str       # Identifier of creating geist
    title: str = None   # Optional suggested note title
```

## Invocation Modes

The CLI supports:

```bash
# Default: filtered + sampled (~5 suggestions)
uv run geistfabrik invoke ~/my-vault

# Single geist mode
uv run geistfabrik invoke ~/my-vault --geist columbo

# Multiple geists mode
uv run geistfabrik invoke ~/my-vault --geists columbo,drift,skeptic

# Full firehose (all filtered suggestions, 50-200+)
uv run geistfabrik invoke ~/my-vault --full

# Replay specific session
uv run geistfabrik invoke ~/my-vault --date 2025-01-15

# Test single geist during development
uv run geistfabrik test my_geist ~/test-vault --date 2025-01-15

# Test all geists
uv run geistfabrik test-all ~/test-vault
```

## Implementation Approach

The following approach was used to implement GeistFabrik:

1. **Start with Vault layer**: File parsing, SQLite schema, incremental sync
2. **Add embeddings**: Integrate sentence-transformers with in-memory vector search
3. **Build VaultContext**: Semantic search, graph queries, sampling utilities
4. **Create core functions**: Built-in vault functions for common queries
5. **Implement geist execution**: Loading, timeout handling, error logging
6. **Add filtering pipeline**: Boundary, novelty, diversity, quality checks
7. **Build journal output**: Session note generation with block IDs
8. **Enable extensibility**: Module loading for metadata/functions/geists
9. **Add temporal embeddings**: Session-based embedding computation and storage
10. **Create CLI**: Argument parsing for different invocation modes

## Dependencies

Core dependencies include:
- `sentence-transformers` - Local embedding computation (all-MiniLM-L6-v2 model)
- `pyyaml` - YAML parsing for Tracery geists and configuration
- Custom Tracery implementation (included, no external dependency)
- Python standard library for Markdown parsing, SQLite, NumPy for vector operations

## Testing Strategy

The `testdata/kepano-obsidian-main/` directory contains real Obsidian notes for testing:
- Mix of daily notes (2023-09-12.md, 2023-09-30.md)
- Topic notes (Minimal Theme.md, Evergreen notes.md)
- Project notes (2023 Japan Trip.md)
- Provides realistic vault structure for development

### Critical Testing Lessons Learned

During the vector search backend implementation, we discovered a **critical bug** (L2 distance instead of cosine distance) that was missed by tests. This led to significant improvements in our testing approach:

#### The Four Pillars of Robust Testing

1. **Fail Loudly in CI**
   - Tests must not skip silently in CI environments
   - Use `os.environ.get("CI")` to enforce critical test requirements
   - Example: `if os.environ.get("CI") and not DEPENDENCY_AVAILABLE: pytest.fail()`

2. **Test Extension/Dependency Loading**
   - Don't assume dependencies load correctly
   - Explicitly test that extensions are callable
   - Verify version numbers and functionality

3. **Use Known-Answer Tests**
   - Test mathematical ground truths (e.g., orthogonal vectors → 0.0 similarity)
   - These catch fundamental algorithm bugs (like wrong distance metrics)
   - More valuable than fuzzy integration tests for catching logic errors

4. **Always-Run Integration Tests**
   - Some tests should NEVER skip, even without optional dependencies
   - Test the default path unconditionally
   - Optionally test enhanced paths when dependencies available
   - Use `if DEPENDENCY_AVAILABLE:` pattern, not `pytest.skip()`

#### Example: Robust Test Structure

```python
# Module-level check
try:
    import optional_dependency
    DEPENDENCY_AVAILABLE = True
except ImportError:
    DEPENDENCY_AVAILABLE = False

# Fail loudly in CI
if os.environ.get("CI") and not DEPENDENCY_AVAILABLE:
    pytest.fail("optional_dependency required in CI")

# Always-run integration test
def test_core_functionality(db):
    """Test core path (NEVER SKIPS)."""
    backend = DefaultBackend(db)
    # ... test default behaviour ...

    # Test enhanced path if available
    if DEPENDENCY_AVAILABLE:
        enhanced = EnhancedBackend(db)
        # ... test and compare ...

# Known-answer test
def test_mathematical_ground_truth():
    """Test known mathematical property."""
    # e.g., orthogonal vectors should have 0.0 cosine similarity
    result = compute_similarity([1, 0, 0], [0, 1, 0])
    assert abs(result - 0.0) < 1e-6  # Catches wrong distance metric
```

**Key Insight**: Test coverage ≠ Test execution. High coverage is meaningless if tests skip silently.

## Key Files to Reference

- `specs/geistfabrik_spec.md` - Complete technical specification (~1500 lines)
- `specs/geistfabrik_vision.md` - Design philosophy and user experience goals
- `specs/tracery_research.md` - Background on Tracery grammar system
- `README.md` - High-level project description

## Common Development Patterns

### Geist Count Management (Single Source of Truth)

**DO NOT** hardcode geist counts anywhere in the codebase or documentation. Instead:

**Use the programmatic constants**:
```python
from geistfabrik.default_geists import (
    CODE_GEIST_COUNT,
    TRACERY_GEIST_COUNT,
    TOTAL_GEIST_COUNT,
)
```

**How it works**:
- `src/geistfabrik/default_geists/__init__.py` counts files programmatically using `Path.glob()`
- These constants are the single source of truth for all geist counts
- Automated tests verify that documentation stays synchronised (see `tests/unit/test_geist_count_consistency.py`)
- Tests will fail if README.md or CLAUDE.md mention outdated counts

**When adding/removing geists**:
1. Add/remove the geist file (*.py or *.yaml)
2. Run tests - they will verify counts automatically update
3. No manual documentation updates needed for counts

**Why this matters**: Prevents drift between actual geist counts and documentation, eliminating the need to manually update counts in multiple places.

### Adding a Metadata Module
1. Create `<vault>/_geistfabrik/metadata_inference/module_name.py`
2. Export `infer(note: Note, vault: VaultContext) -> Dict`
3. Add to `_geistfabrik/config.yaml` enabled_modules list
4. System auto-loads and detects key conflicts on startup

### Adding a Vault Function
1. Create `<vault>/_geistfabrik/vault_functions/function_name.py`
2. Use decorator: `@vault_function("function_name")`
3. Function automatically available in Tracery as `$vault.function_name()`
4. Add to config.yaml enabled_modules for verification

### Adding a Code Geist
1. Create `<vault>/_geistfabrik/geists/code/geist_name.py`
2. Export `suggest(vault: VaultContext) -> List[Suggestion]`
3. Include timeout handling (30 second default)
4. Return empty list if no quality suggestions found

### Adding a Tracery Geist
1. Create `<vault>/_geistfabrik/geists/tracery/geist_name.yaml`
2. Use format:
   ```yaml
   type: geist-tracery
   id: geist_name
   tracery:
     origin: "template with #symbols#"
     symbols: ["$vault.function_call(args)"]
   ```

## Error Handling Philosophy

From the spec:
- Geists execute with 30-second timeout (configurable)
- After 3 failures, geist automatically disabled
- Error logs include test command to reproduce: `geistfabrik test geist_id /path/to/vault --date YYYY-MM-DD`
- System continues if individual geists fail
- Metadata conflicts detected at startup, not runtime

## Performance Targets

- Handle 100+ geists via execution and filtering
- Fast startup via incremental SQLite sync (only changed files)
- Sub-second semantic search queries
- 5-minute effort to add new capability at any extensibility layer
- 1000 notes × 20 sessions = ~30MB embedding storage

## Breaking Database Changes (Pre-1.0 Policy)

**Current Policy (versions < 1.0)**: We do NOT provide automatic database migrations. Users must manually delete and rebuild their database when breaking changes occur.

**When you make a breaking database change:**

1. **Document it in CHANGELOG.md under `## [Unreleased]` > `### Breaking Changes`**:
   - Clearly describe what changed
   - Explain why users need to rebuild
   - Provide exact rebuild instructions
   - Example format:
   ```markdown
   ### Breaking Changes
   - **Virtual note titles**: Changed virtual note title format to exclude filename prefix
     - **Why**: Older databases store titles as "Journal#2025-01-15" instead of "2025-01-15"
     - **Action required**: Delete and rebuild database:
       ```bash
       rm -rf <vault>/_geistfabrik/vault.db*
       uv run geistfabrik invoke <vault>
       ```
     - **Impact**: Existing vaults will show incorrect deeplinks until database is rebuilt
   ```

2. **Update relevant documentation** to reflect the new behaviour

3. **Add regression tests** to prevent the bug from reoccurring

**Post-1.0 Policy**: After the 1.0 release, we will implement automatic database schema migrations for all breaking changes. Users will never need to manually delete their databases.

**What counts as a breaking change**:
- Changes to how data is stored in the database (column formats, title formats, path formats)
- Changes to database schema (new tables, altered columns, changed indexes)
- Changes to how existing data is interpreted or displayed

**What is NOT breaking**:
- Bug fixes that don't affect stored data
- Performance optimisations that preserve existing behaviour
- New features that add data without changing existing data

## Qualitative Success Metrics

GeistFabrik succeeds when suggestions generate:
- **Surprise** - Unexpected connections
- **Delight** - Reading journal feels like opening a gift
- **Serendipity** - Right suggestion at unexpected moment
- **Divergence** - Pull thinking in new directions
- **Questions** - "What if...?" not "Here's the answer"
- **Play** - Exploratory, not obligatory

The system should ask different questions than you would ask yourself.
