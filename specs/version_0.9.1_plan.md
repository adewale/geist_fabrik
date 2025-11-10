# GeistFabrik Version 0.9.1 Plan

**Purpose**: Documentation cleanup and final polishing before 1.0 release
**Status**: Planning
**Target Release**: December 2025
**Estimated Effort**: 2-3 days

---

## Overview

Version 0.9.0 completed all core features, including the date-collection notes implementation. Version 0.9.1 focuses exclusively on **documentation cleanup** to align specifications with the actual implementation before the 1.0 release.

**No new features** - only documentation fixes.

---

## Current State (v0.9.0)

✅ **All Features Complete**:
- Core vault parsing and SQLite persistence
- Embeddings (sentence-transformers, in-memory vector search)
- VaultContext with semantic search and graph operations
- Code and Tracery geist execution
- Filtering and session notes
- Temporal embeddings
- Metadata and function extensibility
- CLI with multiple invocation modes
- Date-collection notes (NEW in 0.9.0)
- 45 bundled geists (35 code, 10 Tracery)

✅ **Test Coverage**:
- 316 unit tests
- 90 integration tests
- All passing (100%)

❌ **Documentation Issues**:
- 8 spec-implementation mismatches (all documentation-only)
- sqlite-vec mentioned but not used
- Schema diagrams out of date
- Tracery dependency listed incorrectly

---

## Goals for 0.9.1

### Primary Goal
Align all documentation with actual implementation so specifications are **source of truth** again.

### Secondary Goals
- Verify installation instructions
- Update dependency lists
- Ensure all examples work
- Prepare release notes for 1.0

---

## Tasks

### 1. Fix CLAUDE.md (Priority 1)

**Issues**:
- Multiple references to `sqlite-vec` extension (not used)
- Lists `tracery (pytracery)` as dependency (we use custom implementation)
- Architecture section shows sqlite-vec in persistence layer

**Changes Needed**:
```diff
- sqlite-vec - Vector similarity search in SQLite
+ In-memory vector similarity search (Python cosine similarity)

Dependencies:
- sentence-transformers>=2.2.0
- pyyaml>=6.0
- - tracery (pytracery)
+ (Custom Tracery implementation included)

Architecture:
- Uses sqlite-vec extension for vector storage
+ Embeddings stored as BLOBs, loaded into memory for similarity search
```

**Files**: `CLAUDE.md`
**Effort**: 30 minutes

---

### 2. Update specs/geistfabrik_spec.md (Priority 1)

**Issues**:
- Database schema shows sqlite-vec VIRTUAL TABLE
- Table names differ from implementation (`geist_runs` vs `session_suggestions`)
- Notes table schema missing `is_virtual`, `source_file`, `entry_date`
- Links table schema differs
- Embeddings table schema differs

**Changes Needed**:

**Notes Table** (add virtual entry support):
```sql
CREATE TABLE notes (
    path TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created TEXT NOT NULL,
    modified TEXT NOT NULL,
    file_mtime REAL NOT NULL,
    is_virtual INTEGER DEFAULT 0,
    source_file TEXT,
    entry_date TEXT
);
```

**Embeddings Table** (actual schema):
```sql
CREATE TABLE embeddings (
    note_path TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model_version TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    FOREIGN KEY (note_path) REFERENCES notes(path)
);
```

**Session Suggestions Table** (correct name):
```sql
CREATE TABLE session_suggestions (
    session_date TEXT NOT NULL,
    geist_id TEXT NOT NULL,
    suggestion_text TEXT NOT NULL,
    block_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_date, block_id)
);
```

**Files**: `specs/geistfabrik_spec.md`
**Effort**: 1 hour

---

### 3. Update README.md (Priority 1)

**Issues**:
- Dependencies section may list sqlite-vec
- No mention of in-memory vector search approach

**Changes Needed**:
- Remove sqlite-vec from dependencies
- Add note about in-memory vector search being suitable for 100-1000 notes
- Mention custom Tracery implementation

**Files**: `README.md`
**Effort**: 15 minutes

---

### 4. Update specs/EMBEDDINGS_SPEC.md (Priority 2)

**Issues**:
- Shows content-hash based caching as primary key
- Actual implementation uses path-based primary key with content hash in `model_version`

**Changes Needed**:
Document the hybrid approach:
```sql
-- Cache key: note path
-- Cache invalidation: content hash in model_version string
CREATE TABLE embeddings (
    note_path TEXT PRIMARY KEY,  -- Path-based, not content-hash
    embedding BLOB NOT NULL,
    model_version TEXT NOT NULL,  -- Includes content hash for invalidation
    computed_at TEXT NOT NULL
);
```

**Files**: `specs/EMBEDDINGS_SPEC.md`
**Effort**: 30 minutes

---

### 5. Verify Installation Instructions (Priority 2)

**Tasks**:
- Test fresh install following README
- Verify all dependencies install correctly
- Test on both macOS and Linux (if possible)
- Ensure model downloads work

**Files**: `README.md`, `docs/INSTALLATION.md` (if exists)
**Effort**: 1 hour (testing)

---

### 6. Update Dependency Documentation (Priority 2)

**Current dependencies** (from pyproject.toml):
```toml
dependencies = [
    "sentence-transformers>=2.2.0",
    "pyyaml>=6.0",
]
```

**Ensure all docs reflect**:
- Only 2 runtime dependencies
- Custom Tracery (no external dependency)
- In-memory vector search (no sqlite-vec)
- Standard SQLite (included in Python)

**Files**: `README.md`, `CLAUDE.md`, `specs/geistfabrik_spec.md`
**Effort**: 15 minutes

---

### 7. Test All Examples (Priority 3)

**Tasks**:
- Verify example geists in `examples/` still work
- Test example vault functions
- Test example metadata modules
- Update any broken examples

**Files**: `examples/**/*`
**Effort**: 1 hour

---

### 8. Prepare 1.0 Release Notes (Priority 3)

**Tasks**:
- Create `CHANGELOG.md` entry for 1.0
- Highlight major features
- Document breaking changes (if any)
- Migration guide from pre-1.0 versions

**Files**: `CHANGELOG.md` (new), `docs/MIGRATION.md` (new)
**Effort**: 1 hour

---

## Non-Goals (Deferred to 2.0)

These are explicitly **NOT** in scope for 0.9.1 or 1.0:

- ❌ Implementing sqlite-vec (current approach works fine)
- ❌ Persistent metadata storage (in-memory is sufficient)
- ❌ New geists (45 is plenty)
- ❌ Performance optimisations beyond current (fast enough)
- ❌ Weighted distributions for Tracery (deferred to 2.0)
- ❌ Geist validation spec features (deferred)

---

## Success Criteria

Version 0.9.1 is ready when:

1. ✅ All 8 documentation mismatch issues resolved
2. ✅ Fresh install works from README instructions
3. ✅ All specs match implementation
4. ✅ No mentions of unimplemented features in docs
5. ✅ Release notes prepared for 1.0
6. ✅ All tests still passing (316 unit + 90 integration)

---

## Timeline

**Week 1** (3 days):
- Day 1: Fix CLAUDE.md, README.md, geistfabrik_spec.md (Tasks 1-3)
- Day 2: Fix EMBEDDINGS_SPEC.md, verify installation, test examples (Tasks 4-7)
- Day 3: Prepare release notes, final review (Task 8)

**Release**: End of Week 1

---

## 1.0 Release Checklist

After 0.9.1 documentation cleanup:

- [ ] All documentation tests pass
- [ ] All code tests pass (316 unit + 90 integration)
- [ ] Installation verified on macOS and Linux
- [ ] Examples tested and working
- [ ] CHANGELOG.md complete
- [ ] Migration guide written (if needed)
- [ ] Version bumped to 1.0.0 in:
  - [ ] `pyproject.toml`
  - [ ] `src/geistfabrik/__init__.py`
- [ ] Git tag created: `v1.0.0`
- [ ] GitHub release created with release notes
- [ ] (Optional) PyPI publication

---

## Post-1.0 Vision

**GeistFabrik 2.0 will focus on**:
- Philosophical refinement (double down on "muses not oracles")
- Geist quality over quantity
- Possible removal of "maintenance" geists (Tier C)
- Enhanced Tracery features (weighted distributions)
- Community geist sharing

**See**: `docs/GeistFabrik2.0_Wishlist.md` for detailed vision

---

## Document History

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-28 | 1.0 | Initial 0.9.1 plan created |

**Author**: Claude (AI Assistant)
**Status**: Draft - Ready for Implementation
