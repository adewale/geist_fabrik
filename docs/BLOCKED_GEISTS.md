# Blocked Geists - Infrastructure Gap Analysis

**Date**: 2025-10-21
**Purpose**: Document geists mentioned in specs that cannot be built with current infrastructure

**Per user directive**: "Keep track of which geists proved to be impractical with our current infrastructure but do NOT change the infrastructure to support these geists. Just capture them."

---

## Summary

| Status | Count | Geists |
|--------|-------|--------|
| ✅ **Buildable & Built** | 14 | All code and Tracery geists in examples/ + temporal_mirror |
| ⚠️ **Blocked by Missing Infrastructure** | 4 | island_hopper, bridge_hunter, density_inversion, vocabulary_expansion |
| ⚠️ **Approximated** | 1 | hidden_hub (built approximation, not full spec) |
| ⬜ **Undefined** | 3 | columbo, drift, skeptic |

---

## Blocked Geists (4)

These geists are documented in `specs/geistfabrik_spec.md` but **cannot be built** with current VaultContext API.

### 1. island_hopper

**Source**: `specs/geistfabrik_spec.md:1323-1358`

**Description**: Find notes that could bridge disconnected clusters

**Why Blocked**:
- ❌ Requires `vault.find_clusters(min_size, max_size)` - NOT IMPLEMENTED
- Would need graph clustering algorithm (e.g., Louvain, modularity-based)
- Complex implementation (50-100+ lines of graph analysis code)

**What It Needs**:
```python
def find_clusters(self, min_size: int = 3, max_size: int = 10) -> List[Set[Note]]:
    """Find disconnected clusters in the note graph.

    Uses modularity-based clustering on the link graph.
    Returns list of note sets representing clusters.
    """
    # Would need to implement clustering algorithm here
    pass
```

**Estimated Effort**: 2-3 hours (clustering algorithm + integration + tests)

**Priority**: Medium (interesting for vault structure analysis)

---

### 2. bridge_hunter

**Source**: `specs/geistfabrik_spec.md:1390-1413`

**Description**: Find semantic paths where no graph path exists

**Why Blocked**:
- ❌ Requires `vault.semantic_path(a, b, max_hops)` - NOT IMPLEMENTED
- Would need A* or beam search through embedding space
- Must avoid graph-connected notes (only semantic paths)
- Complex pathfinding logic

**What It Needs**:
```python
def semantic_path(self, a: Note, b: Note, max_hops: int = 5) -> List[Note]:
    """Find semantic path between notes using embeddings.

    Uses A* search with cosine similarity as heuristic.
    Avoids direct graph connections.
    """
    # Would need to implement semantic pathfinding here
    pass
```

**Estimated Effort**: 3-4 hours (A* implementation + heuristic tuning + tests)

**Priority**: Medium (creative feature, good for discovery)

---

### 3. density_inversion

**Source**: `specs/geistfabrik_spec.md:1415-1456`

**Description**: Detect mismatches between link structure and semantic structure

**Why Blocked**:
- ❌ Requires `vault.get_graph_neighbors(note)` - NOT IMPLEMENTED
- ❌ Requires `vault.has_link(a, b)` - NOT IMPLEMENTED
- Needs explicit graph traversal (different from semantic neighbours)

**What It Needs**:
```python
def get_graph_neighbors(self, note: Note) -> List[Note]:
    """Get notes connected by links (not semantic similarity).

    Returns: List of notes linked to/from given note.
    """
    # Forward links + backlinks (graph structure only)
    pass

def has_link(self, a: Note, b: Note) -> bool:
    """Check if there's a direct link between two notes.

    Returns: True if a links to b OR b links to a
    """
    pass
```

**Estimated Effort**: 1-2 hours (simple graph queries + tests)

**Priority**: Low (interesting insight, but not essential)

---

### 4. vocabulary_expansion

**Source**: `specs/geistfabrik_spec.md:1458-1499`

**Description**: Track semantic space coverage over time

**Why Blocked**:
- ❌ Requires `vault.get_recent_sessions(n)` - NOT IMPLEMENTED
- ❌ Requires session history tracking across multiple runs
- Current Session model is per-invocation only
- Would need persistent session storage + retrieval

**What It Needs**:
```python
def get_recent_sessions(self, n: int = 5) -> List[Session]:
    """Get recent session history.

    Loads embeddings from past sessions to track
    semantic drift over time.
    """
    # Would need to store and retrieve session metadata
    pass
```

**Database Schema Changes Needed**:
```sql
CREATE TABLE session_history (
    session_id INTEGER PRIMARY KEY,
    session_date TEXT NOT NULL,
    note_count INTEGER,
    semantic_coverage REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Estimated Effort**: 4-6 hours (schema migration + session history API + retrieval logic + tests)

**Priority**: High for temporal features, but significant architectural change

---

## Approximated Geists (1)

### hidden_hub

**Source**: `specs/geistfabrik_spec.md:1361-1388`

**Description**: Find semantically central notes that aren't well-linked

**Status**: ⚠️ Could be approximated (NOT built yet)

**What's Available**:
- ✅ `vault.backlinks(note)` - Get incoming links
- ✅ `vault.neighbours(note, k)` - Get semantically similar notes
- ❌ Spec calls for `vault.neighbours()` to mean something different (centrality-based)

**Approximation Strategy**:
```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find semantically central notes (approximation)."""
    suggestions = []

    for note in vault.notes():
        # Actual link count (incoming + outgoing)
        incoming = len(vault.backlinks(note))
        outgoing = len(note.links)
        link_count = incoming + outgoing

        # Semantic neighbours as proxy for centrality
        # (Not true centrality, but approximation)
        semantic_neighbors = vault.neighbours(note, k=50)
        semantic_centrality = len(semantic_neighbors)

        # High semantic neighbours, low links = potential hidden hub
        if semantic_centrality > 20 and link_count < 5:
            suggestions.append(Suggestion(
                text=f"[[{note.title}]] is semantically similar to "
                     f"{semantic_centrality} notes but only has {link_count} links—"
                     f"hidden hub?",
                notes=[note.title],
                geist_id="hidden_hub"
            ))

    return vault.sample(suggestions, k=3)
```

**Limitations of Approximation**:
- True centrality would need PageRank or betweenness centrality
- `neighbours()` returns k-nearest by embedding, not by graph centrality
- Results will differ from spec's intent

**Decision**: NOT built, per user directive to only track blocked geists

---

## Undefined Geists (3)

These are mentioned in documentation but have no specifications.

### 1. columbo

**Mentioned**: `CLAUDE.md:128` in example command: `geistfabrik invoke --geist columbo`

**Status**: ⬜ No implementation details, no spec

**Speculation**: Name suggests "detective" style questioning (Columbo TV character)

**Action**: Cannot build without specification

---

### 2. drift

**Mentioned**: `CLAUDE.md:131` in example command: `geistfabrik invoke --geists columbo,drift,skeptic`

**Status**: ⬜ Possibly duplicate of `temporal_drift`

**Analysis**: We already have `temporal_drift.py` which tracks note staleness. "drift" might be:
- Abbreviated name for `temporal_drift`
- Different concept (semantic drift, not temporal)

**Action**: Assume it refers to existing `temporal_drift` geist

---

### 3. skeptic

**Mentioned**: `CLAUDE.md:131` in example command: `geistfabrik invoke --geists columbo,drift,skeptic`

**Status**: ⬜ No implementation details, no spec

**Speculation**: Could challenge note claims, find contradictions, or question assumptions

**Action**: Cannot build without specification

---

## Infrastructure Gaps Summary

### Missing VaultContext Methods

| Method | Required By | Complexity | Estimated Effort |
|--------|-------------|------------|------------------|
| `find_clusters(min_size, max_size)` | island_hopper | High | 2-3 hours |
| `semantic_path(a, b, max_hops)` | bridge_hunter | High | 3-4 hours |
| `get_graph_neighbors(note)` | density_inversion | Low | 1 hour |
| `has_link(a, b)` | density_inversion | Low | 30 mins |
| `get_recent_sessions(n)` | vocabulary_expansion | High | 4-6 hours |

**Total Estimated Effort**: 11-14.5 hours to unblock all geists

### Missing Database Schema

**Session History** (for vocabulary_expansion):
- Requires storing session metadata across runs
- Current design is session-per-invocation (stateless)
- Would need schema migration + backward compatibility

---

## Recommendations

### Do NOT Implement (Per User Directive)

**User said**: "Keep track of which geists proved to be impractical with our current infrastructure but do NOT change the infrastructure to support these geists."

Therefore:
- ❌ Do NOT implement missing VaultContext methods
- ❌ Do NOT add session history tracking
- ❌ Do NOT build approximations of blocked geists
- ✅ DO document what's missing (this document)

### If Requirements Change Later

**Low-hanging fruit** (if user changes directive):
1. `get_graph_neighbors()` + `has_link()` - Simple, 1.5 hours total
2. Could unblock density_inversion immediately

**High-value additions**:
1. `get_recent_sessions()` - Enables temporal analysis (vocabulary_expansion)
2. Session history opens door to drift analysis, usage patterns

**Complex features** (defer unless requested):
1. `find_clusters()` - Requires choosing clustering algorithm
2. `semantic_path()` - Complex pathfinding, needs careful design

---

## Testing Impact

**Blocked geists**: 0 tests (cannot test what doesn't exist)

**Built geists**: 17 tests, all passing in 0.13s

**CI impact of blocked geists**: None (they don't exist in codebase)

---

## Conclusion

- **4 geists blocked** by missing infrastructure
- **11-14.5 hours** to unblock all of them
- **NOT implementing** per user directive
- **Documentation complete** - this file + `docs/GEIST_CATALOG.md`

All buildable geists are built, tested, and passing. Blocked geists are documented with clear explanations of what's missing.
