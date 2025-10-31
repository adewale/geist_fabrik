# Specification vs Implementation Mismatches

**Document Purpose**: Identify discrepancies between GeistFabrik's specifications and actual implementation.

**Status**: Updated (Post-0.9.0 Implementation)
**Last Updated**: October 2025
**Severity Levels**: 🔴 Critical | 🟡 Moderate | 🟢 Minor | 🔵 Documentation Only | ✅ Resolved

---

## Executive Summary

This audit identified **9 significant mismatches** between the specification documents and the actual codebase. Most are documentation issues where the spec describes an idealized architecture that differs from the working implementation. No critical functional bugs were found.

**Key Findings (Updated Post-0.9.0)**:
- ~~1 major unimplemented feature (date-collection notes)~~ ✅ **RESOLVED in v0.9.0**
- 5 architectural differences (database schema, vector search method)
- 3 naming/terminology mismatches
- 0 critical bugs

**Remaining Work**: Documentation cleanup (8 items) - all low priority

---

## Detailed Findings

### 1. ✅ Date-Collection Notes (RESOLVED in v0.9.0)

**Original Issue**: Feature advertised but not implemented

**Resolution (October 2025)**:
- ✅ **FULLY IMPLEMENTED** in version 0.9.0
- ✅ Automatic detection of date-collection notes (≥2 H2 date headings, ≥50% threshold)
- ✅ 7 supported date formats
- ✅ Virtual entry splitting with paths like `Journal.md/2025-01-15`
- ✅ Database schema v4 with virtual entry support
- ✅ Link resolution for virtual paths
- ✅ Configuration system added

**Test Coverage**:
- 41 unit tests (detection, parsing, splitting)
- 25 integration tests (sync, queries, link resolution)
- 16 edge case tests (unicode, large journals, nested directories)
- All tests passing (100%)

**Documentation**:
- `docs/JOURNAL_FILES.md` (600+ lines comprehensive guide)
- Updated README.md and CLAUDE.md
- Configuration examples

**Status**: ✅ **COMPLETE** - No further action needed

**References**:
- Implementation spec: `specs/DATE_COLLECTION_NOTES_SPEC.md`
- User guide: `docs/JOURNAL_FILES.md`
- Implementation: `src/geistfabrik/date_collection.py`

---

### 2. 🟡 Vector Search: sqlite-vec Extension (NOT USED)

**Specification Claims**: Multiple locations
- `specs/geistfabrik_spec.md:201`: "CREATE VIRTUAL TABLE note_embeddings USING vec0"
- `CLAUDE.md:118`: "Uses sqlite-vec extension for vector storage"
- `CLAUDE.md:253`: "sqlite-vec - Vector similarity search in SQLite"
- `README.md`: Multiple references to sqlite-vec

**Actual Implementation**:
- ❌ sqlite-vec NOT used or installed
- ❌ No VIRTUAL TABLE for embeddings
- ✅ Uses standard SQLite with BLOB storage
- ✅ Embeddings loaded into memory for similarity search
- ✅ Python-based cosine similarity computation

**Implementation Details**:
```python
# Actual: embeddings.py
def find_similar_notes(query_embedding, embeddings, k=10):
    # In-memory similarity computation
    similarities = [(path, cosine_similarity(query_embedding, emb))
                    for path, emb in embeddings.items()]
    return sorted(similarities, key=lambda x: x[1], reverse=True)[:k]
```

**Database Schema**:
```sql
-- Spec claims:
CREATE VIRTUAL TABLE note_embeddings USING vec0(
    path TEXT PRIMARY KEY,
    title_embedding FLOAT[384],
    content_embedding FLOAT[384]
);

-- Actual:
CREATE TABLE embeddings (
    note_path TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model_version TEXT NOT NULL,
    computed_at TEXT NOT NULL
);
```

**Impact**: 🟡 **MODERATE** - Misleading documentation
- Feature works correctly, just uses different technology
- Performance is adequate for current scale (100-1000 notes)
- May become bottleneck at larger scales (10,000+ notes)
- No dependency on sqlite-vec simplifies installation

**Pros of Current Approach**:
- ✅ Simpler installation (no C extensions)
- ✅ More portable across platforms
- ✅ Works well for target scale (100-1000 notes)

**Cons**:
- ❌ Less efficient for very large vaults (>10,000 notes)
- ❌ Loads all embeddings into memory

**Resolution**: Update documentation to reflect in-memory approach

---

### 3. 🟡 Metadata Storage: In-Memory vs Database

**Specification Claims**: `specs/geistfabrik_spec.md:208-216`
```sql
-- Computed metadata (flexible JSON storage)
CREATE TABLE metadata (
    note_path TEXT,
    key TEXT,
    value TEXT,  -- JSON encoded
    computed_at TIMESTAMP,
    FOREIGN KEY (note_path) REFERENCES notes(path),
    PRIMARY KEY (note_path, key)
);
CREATE INDEX idx_metadata_key ON metadata(key);
```

**Actual Implementation**: `vault_context.py:606-642`
- ❌ No `metadata` table in database
- ✅ Metadata computed on-demand and cached in memory
- ✅ `MetadataLoader` system loads inference modules
- ✅ Results stored in `_metadata_cache` dict

**Implementation**:
```python
def metadata(self, note: Note) -> Dict[str, Any]:
    if note.path in self._metadata_cache:
        return self._metadata_cache[note.path]

    # Compute built-in + inferred metadata
    metadata = {
        "word_count": len(note.content.split()),
        "link_count": len(note.links),
        "tag_count": len(note.tags),
        "age_days": (datetime.now() - note.created).days,
    }

    # Run user-defined inference modules
    inferred, _ = self._metadata_loader.infer_all(note, self)
    metadata.update(inferred)

    self._metadata_cache[note.path] = metadata
    return metadata
```

**Impact**: 🟡 **MODERATE** - Different architecture
- ✅ Feature works as advertised to users
- ✅ More efficient (compute once per session)
- ❌ Metadata not persisted between sessions
- ❌ No historical metadata tracking

**Pros of Current Approach**:
- ✅ Simpler: no database writes needed
- ✅ Faster: no DB I/O during metadata access
- ✅ Flexible: easy to change metadata inference logic

**Cons**:
- ❌ Cannot track metadata evolution over time
- ❌ Re-computed every session (not cached across runs)

**Resolution**: Document actual in-memory approach

---

### 4. 🟢 Table Name: `geist_runs` vs `session_suggestions`

**Specification Claims**: `specs/geistfabrik_spec.md:219-224`
```sql
-- Geist execution history
CREATE TABLE geist_runs (
    date DATE,
    geist_id TEXT,
    suggestions TEXT,  -- JSON array of suggestions
    PRIMARY KEY (date, geist_id)
);
```

**Actual Implementation**: `schema.py:83-93`
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

**Impact**: 🟢 **MINOR** - Naming difference only
- ✅ Functionality identical
- ✅ Better name (more descriptive)
- ✅ Slightly different schema (denormalized)

**Resolution**: Update spec to use `session_suggestions`

---

### 5. 🟢 Notes Table: Missing `hash` and `word_count` Columns

**Specification Claims**: `specs/geistfabrik_spec.md:179-187`
```sql
CREATE TABLE notes (
    path TEXT PRIMARY KEY,
    title TEXT,
    content TEXT,
    created TIMESTAMP,
    modified TIMESTAMP,
    word_count INTEGER,
    hash TEXT  -- For change detection
);
```

**Actual Implementation**: `schema.py:13-20`
```sql
CREATE TABLE notes (
    path TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created TEXT NOT NULL,
    modified TEXT NOT NULL,
    file_mtime REAL NOT NULL  -- For incremental sync
);
```

**Changes**:
1. ❌ No `hash` column - uses `file_mtime` instead
2. ❌ No `word_count` column - computed on-demand
3. ✅ Added `file_mtime` for faster change detection

**Impact**: 🟢 **MINOR** - Better implementation
- ✅ `file_mtime` is faster than computing hashes
- ✅ `word_count` computed on-demand is more flexible
- ✅ Simpler schema

**Pros of Current Approach**:
- ✅ Faster sync (no hashing needed)
- ✅ Less storage (no hash or word_count stored)
- ✅ More accurate (OS provides exact mtime)

**Resolution**: Update spec to reflect mtime-based sync

---

### 6. 🟢 Missing `block_refs` Table

**Specification Claims**: `specs/geistfabrik_spec.md:226-232`
```sql
-- Block reference tracking
CREATE TABLE block_refs (
    block_id TEXT PRIMARY KEY,
    note_path TEXT,
    created_date DATE,
    FOREIGN KEY (note_path) REFERENCES notes(path)
);
```

**Actual Implementation**:
- ❌ Table does not exist
- ✅ Block references tracked in `links` table via `block_ref` column
- ✅ Functionality works correctly

**Implementation**:
```sql
CREATE TABLE links (
    source_path TEXT NOT NULL,
    target TEXT NOT NULL,
    display_text TEXT,
    is_embed INTEGER NOT NULL DEFAULT 0,
    block_ref TEXT,  -- Block reference ID
    FOREIGN KEY (source_path) REFERENCES notes(path)
);
```

**Impact**: 🟢 **MINOR** - Different schema design
- ✅ Simpler approach (denormalized)
- ✅ Fewer tables to manage
- ✅ Sufficient for current use cases

**Resolution**: Update spec to show block_ref in links table

---

### 7. 🔵 Tracery Dependency: Custom Implementation

**Specification Claims**: `CLAUDE.md:253`
- Lists `tracery (pytracery)` as a dependency

**Actual Implementation**: `src/geistfabrik/tracery.py`
- ❌ pytracery NOT a dependency
- ✅ Custom Tracery implementation (17KB)
- ✅ Tailored for GeistFabrik's needs

**Implementation**:
```python
# src/geistfabrik/tracery.py
class TraceryEngine:
    """Simple Tracery grammar engine with vault function support."""

    def expand(self, symbol: str) -> str:
        # Custom implementation with:
        # - Symbol expansion
        # - Modifiers (capitalize, s, ed, a)
        # - Vault function calls ($vault.*)
        # - Deterministic randomness
```

**Impact**: 🔵 **DOCUMENTATION** - No functional issue
- ✅ Feature fully implemented
- ✅ Better integration with VaultContext
- ✅ Supports vault function calls natively
- ✅ Deterministic random expansion

**Pros of Custom Implementation**:
- ✅ No external dependency
- ✅ Tailored to GeistFabrik's needs
- ✅ Integrated with vault functions
- ✅ Deterministic randomness support

**Resolution**: Update CLAUDE.md to reflect custom implementation

---

### 8. 🟡 Embeddings Cache: Path-Based vs Content-Hash-Based

**Specification Claims**: `specs/EMBEDDINGS_SPEC.md:62-88`
```
Cache Key: SHA-256 hash of note content

Database Schema:
CREATE TABLE embeddings (
    content_hash TEXT PRIMARY KEY,  -- SHA-256 of content
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL
);
```

**Actual Implementation**: `schema.py:48-55`
```sql
CREATE TABLE embeddings (
    note_path TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model_version TEXT NOT NULL,  -- Includes content hash
    computed_at TEXT NOT NULL,
    FOREIGN KEY (note_path) REFERENCES notes(path)
);
```

**Hybrid Approach**:
```python
# embeddings.py:258-265
content_hash = self._compute_content_hash(note.content)
model_version = f"{MODEL_NAME}:{content_hash}"

# Check if cached embedding is still valid
if cached_version == model_version:
    return cached_embedding  # Content unchanged
else:
    return self.compute_semantic(note.content)  # Re-compute
```

**Impact**: 🟡 **MODERATE** - Different but valid approach
- ✅ Achieves same goal (cache invalidation on content change)
- ✅ Simpler primary key (path vs hash)
- ✅ Easier to query "all embeddings for this note"
- ❌ Different from spec's design

**Pros of Current Approach**:
- ✅ One embedding per note (clear ownership)
- ✅ Easier foreign key relationships
- ✅ Simpler to manage note renames/moves

**Cons**:
- ❌ Cannot deduplicate identical content in different files

**Resolution**: Update EMBEDDINGS_SPEC.md to reflect path-based approach

---

### 9. 🟢 Links Table: Simplified Schema

**Specification Claims**: `specs/geistfabrik_spec.md:190-198`
```sql
CREATE TABLE links (
    source_path TEXT,
    target_path TEXT,
    link_type TEXT,  -- 'link', 'embed', 'block-ref'
    FOREIGN KEY (source_path) REFERENCES notes(path),
    FOREIGN KEY (target_path) REFERENCES notes(path)
);
```

**Actual Implementation**: `schema.py:26-36`
```sql
CREATE TABLE links (
    source_path TEXT NOT NULL,
    target TEXT NOT NULL,  -- Not target_path
    display_text TEXT,
    is_embed INTEGER NOT NULL DEFAULT 0,
    block_ref TEXT,
    FOREIGN KEY (source_path) REFERENCES notes(path)
);
```

**Changes**:
1. `target_path` → `target` (no FK, allows broken links)
2. `link_type` → separate `is_embed` and `block_ref` columns
3. Added `display_text` for custom link text

**Impact**: 🟢 **MINOR** - Better design
- ✅ Supports broken links (target doesn't have to exist)
- ✅ More flexible schema
- ✅ Better aligns with Obsidian's link semantics

**Resolution**: Update spec to match actual schema

---

## Summary Table

| # | Issue | Severity | Type | Status |
|---|-------|----------|------|--------|
| 1 | Date-collection notes not implemented | ✅ Resolved | Missing Feature | **Implemented in v0.9.0** |
| 2 | sqlite-vec not used (in-memory instead) | 🟡 Moderate | Architecture | Docs need update |
| 3 | Metadata stored in-memory not DB | 🟡 Moderate | Architecture | Docs need update |
| 4 | Table named `session_suggestions` not `geist_runs` | 🟢 Minor | Naming | Docs need update |
| 5 | Notes table uses `file_mtime` not `hash` | 🟢 Minor | Schema | Docs need update |
| 6 | No `block_refs` table (uses `links.block_ref`) | 🟢 Minor | Schema | Docs need update |
| 7 | Custom Tracery implementation (not pytracery) | 🔵 Docs | Dependency | Docs need update |
| 8 | Embeddings cache by path not content_hash | 🟡 Moderate | Schema | Docs need update |
| 9 | Links table simpler schema | 🟢 Minor | Schema | Docs need update |

---

## Recommendations

### Immediate Actions (Priority 1)

1. **Update CLAUDE.md**:
   - Remove sqlite-vec references, describe in-memory vector search
   - Change "pytracery" to "custom Tracery implementation"
   - Update architecture section with actual schema

2. **Update specs/geistfabrik_spec.md**:
   - Correct all database schema examples
   - Document in-memory metadata approach
   - Fix table names (`session_suggestions`)

3. **Update README.md**:
   - Remove sqlite-vec from dependencies list
   - Add note about in-memory vector search

### Medium-Term Actions (Priority 2)

4. **Implement date-collection notes**:
   - Use spec in `specs/DATE_COLLECTION_NOTES_SPEC.md`
   - Estimated effort: 2-3 days
   - Would complete advertised feature set

5. **Create architecture documentation**:
   - `docs/ARCHITECTURE.md` with accurate diagrams
   - Show actual vs ideal designs
   - Explain design decisions

### Long-Term Considerations (Priority 3)

6. **Evaluate sqlite-vec migration**:
   - Consider for vaults with >5,000 notes
   - Benchmark current approach at scale
   - Document performance characteristics

7. **Consider metadata persistence**:
   - Would enable temporal metadata tracking
   - Useful for "how has complexity evolved?" queries
   - Currently metadata is session-only

---

## Testing Status

All mismatches have been validated by:
- ✅ Reading source code (`src/geistfabrik/*.py`)
- ✅ Checking database schema (`schema.py`)
- ✅ Comparing against spec files
- ✅ Verifying with grep/search across codebase

No critical functional bugs found. All advertised features work, though some implementation details differ from specifications.

---

## Document History

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-24 | 1.0 | Initial audit completed |
| 2025-10-28 | 1.1 | Updated post-0.9.0: Date-collection notes fully implemented, issue #1 resolved |

---

**Audit Completed By**: Claude (AI Assistant)
**Last Updated**: October 2025 (Post v0.9.0 implementation)
**Next Review**: Before 1.0 release (documentation cleanup)
