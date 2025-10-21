# GeistFabrik Geist Catalog

## Purpose

This document catalogs ALL geists mentioned in any GeistFabrik documentation, categorizes them by implementation status, and identifies which ones are practical to build with our current infrastructure.

**Date**: 2025-10-21
**Audit scope**: All markdown files, code examples, and specs

---

## Summary

| Category | Count |
|----------|-------|
| **Implemented & Tested** | 13 (10 code + 3 Tracery) |
| **Documented - Buildable Now** | 5 |
| **Documented - Missing Infrastructure** | 6 |
| **Total Documented Geists** | 24 |

---

## 1. Implemented Geists (13)

### Code Geists (10)

Located in `examples/geists/code/`

| Geist | File | Description | Has Tests? |
|-------|------|-------------|------------|
| **temporal_drift** | `temporal_drift.py` | Find stale but important notes | ✅ Yes |
| **creative_collision** | `creative_collision.py` | Suggest unexpected note pairs | ✅ Yes |
| **bridge_builder** | `bridge_builder.py` | Connect disconnected clusters | ✅ Yes |
| **complexity_mismatch** | `complexity_mismatch.py` | Find complexity/importance gaps | ✅ Yes |
| **question_generator** | `question_generator.py` | Reframe statements as questions | ✅ Yes |
| **link_density_analyzer** | `link_density_analyzer.py` | Analyse link patterns | ✅ Yes |
| **task_archaeology** | `task_archaeology.py` | Find old incomplete tasks | ✅ Yes |
| **concept_cluster** | `concept_cluster.py` | Identify emergent themes | ✅ Yes |
| **stub_expander** | `stub_expander.py` | Develop short connected notes | ✅ Yes |
| **recent_focus** | `recent_focus.py` | Connect recent to old work | ✅ Yes |

### Tracery Geists (3)

Located in `examples/geists/tracery/`

| Geist | File | Description | Has Tests? |
|-------|------|-------------|------------|
| **random_prompts** | `random_prompts.yaml` | General creative prompts | ✅ Yes |
| **note_combinations** | `note_combinations.yaml` | Combine random notes creatively | ✅ Yes |
| **what_if** | `what_if.yaml` | "What if" prompts for divergent thinking | ✅ Yes |

---

## 2. Documented Geists - Buildable Now (5)

These geists are documented in specs but not yet implemented. **They CAN be built with existing VaultContext methods.**

### island_hopper (aka "Island Hopper")

**Source**: `specs/geistfabrik_spec.md:1323-1358`
**Description**: Find notes that could bridge disconnected clusters
**Status**: ⚠️ BLOCKED - Missing infrastructure

**Required methods**:
- ❌ `vault.find_clusters(min_size, max_size)` - NOT IMPLEMENTED
- ✅ `vault.similarity(note, c)` - EXISTS
- ✅ `vault.sample(items, k)` - EXISTS

**Complexity**: High (requires clustering algorithm)
**Buildable**: ❌ No - Need to implement `find_clusters()` first

---

### hidden_hub

**Source**: `specs/geistfabrik_spec.md:1361-1388`
**Description**: Find semantically central notes that aren't well-linked
**Status**: ⚠️ BLOCKED - Missing infrastructure

**Required methods**:
- ✅ `vault.backlinks(note)` - EXISTS
- ❌ `vault.neighbours(note, k=50)` - EXISTS but returns similar notes, not "neighbours" by centrality
- ✅ `vault.sample(items, k)` - EXISTS

**Complexity**: Medium (need to define "semantic centrality")
**Buildable**: ⚠️ Partial - Can approximate using `neighbours()` as semantic neighbours

---

### bridge_hunter

**Source**: `specs/geistfabrik_spec.md:1390-1413`
**Description**: Find semantic paths where no graph path exists
**Status**: ⚠️ BLOCKED - Missing infrastructure

**Required methods**:
- ✅ `vault.unlinked_pairs(k)` - EXISTS
- ❌ `vault.semantic_path(a, b, max_hops)` - NOT IMPLEMENTED

**Complexity**: High (requires pathfinding algorithm in embedding space)
**Buildable**: ❌ No - Need to implement `semantic_path()` first

---

### density_inversion

**Source**: `specs/geistfabrik_spec.md:1415-1456`
**Description**: Detect mismatches between link structure and semantic structure
**Status**: ⚠️ BLOCKED - Missing infrastructure

**Required methods**:
- ❌ `vault.get_graph_neighbors(note)` - NOT IMPLEMENTED (different from semantic neighbours)
- ❌ `vault.has_link(n1, n2)` - NOT IMPLEMENTED
- ✅ `vault.similarity(n1, n2)` - EXISTS

**Complexity**: Medium
**Buildable**: ❌ No - Need graph traversal methods

---

### vocabulary_expansion

**Source**: `specs/geistfabrik_spec.md:1458-1499`
**Description**: Track semantic space coverage over time
**Status**: ⚠️ BLOCKED - Missing infrastructure

**Required methods**:
- ❌ `vault.get_recent_sessions(n)` - NOT IMPLEMENTED
- ❌ `session.get_all_embeddings()` - EXISTS in Session, but multi-session tracking not supported

**Complexity**: Medium (requires temporal embedding analysis)
**Buildable**: ❌ No - Need session history tracking

---

### temporal_mirror (Tracery)

**Source**: `specs/geistfabrik_spec.md:1300-1317`
**Description**: Compare old and new notes temporally
**Status**: ✅ BUILDABLE NOW

**Required methods**:
- ❌ `$vault.old_notes(1)` - Function doesn't exist, but method does: `vault.old_notes(k)`
- ❌ `$vault.recent_notes(1)` - Function doesn't exist, but method does: `vault.recent_notes(k)`

**Complexity**: Low
**Buildable**: ✅ YES - Just need to register vault functions
**Action needed**: Create vault functions wrapping `old_notes()` and `recent_notes()`

---

## 3. Documented Geists - Missing Infrastructure (6)

### columbo

**Source**: `CLAUDE.md:128` (mentioned in examples)
**Description**: Not specified (name only)
**Status**: ⬜ UNDEFINED

**Analysis**: No implementation details found. Possibly a placeholder or planned geist.

---

### drift

**Source**: `CLAUDE.md:131` (mentioned in examples)
**Description**: Not specified (name only)
**Status**: ⚠️ Possibly duplicate of `temporal_drift`

**Analysis**: Likely referring to existing `temporal_drift.py` geist.

---

### skeptic

**Source**: `CLAUDE.md:131` (mentioned in examples)
**Description**: Not specified (name only)
**Status**: ⬜ UNDEFINED

**Analysis**: No implementation details found. Conceptually could challenge note claims or assumptions.

---

## 4. Infrastructure Gap Analysis

### Missing VaultContext Methods

To build all documented geists, we would need:

| Method | Used By | Priority |
|--------|---------|----------|
| `find_clusters(min_size, max_size)` | island_hopper | Medium |
| `semantic_path(a, b, max_hops)` | bridge_hunter | Medium |
| `get_graph_neighbors(note)` | density_inversion | Low |
| `has_link(a, b)` | density_inversion | Low |
| `get_recent_sessions(n)` | vocabulary_expansion | High |

### Missing Vault Functions

To build Tracery geists, we need vault functions:

| Function | Wraps Method | Used By | Priority |
|----------|--------------|---------|----------|
| `$vault.old_notes(k)` | `vault.old_notes(k)` | temporal_mirror | High |
| `$vault.recent_notes(k)` | `vault.recent_notes(k)` | temporal_mirror | High |

---

## 5. Buildability Classification

### ✅ Can Build Now (1)

1. **temporal_mirror** - Just needs vault function registration

### ⚠️ Can Approximate (1)

1. **hidden_hub** - Can use existing `neighbours()` as proxy for semantic centrality

### ❌ Blocked by Infrastructure (4)

1. **island_hopper** - Needs clustering algorithm
2. **bridge_hunter** - Needs semantic pathfinding
3. **density_inversion** - Needs graph traversal methods
4. **vocabulary_expansion** - Needs session history tracking

### ⬜ Undefined (3)

1. **columbo** - No specification
2. **drift** - Likely duplicate of temporal_drift
3. **skeptic** - No specification

---

## 6. Recommendations

### Immediate Actions (Today)

1. ✅ **Build temporal_mirror** (Tracery)
   - Create vault functions for `old_notes()` and `recent_notes()`
   - Add YAML geist file
   - Write unit test

2. ✅ **Approximate hidden_hub** (Code)
   - Use existing `neighbours()` and `backlinks()` methods
   - Document limitations
   - Write unit test

### Do NOT Implement (Per User Directive)

The user explicitly said: "Keep track of which geists proved to be impractical with our current infrastructure but do NOT change the infrastructure to support these geists."

Therefore, do NOT implement:
- `find_clusters()`
- `semantic_path()`
- `get_graph_neighbors()` / `has_link()`
- `get_recent_sessions()` / session history

Instead, **document these as blocked** in final report.

---

## 7. Testing Strategy

### Unit Test Requirements

All new geists must have:
- ✅ Stub-based tests (NOT mocks)
- ✅ Use existing test vault (`testdata/kepano-obsidian-main/`)
- ✅ Fast execution (< 1 second per test)
- ✅ Deterministic output (use session seed)

### CI Impact

Current CI time: ~30 seconds for unit tests

Adding 2 new geists:
- temporal_mirror: +0.5s (Tracery expansion)
- hidden_hub: +1.0s (embedding similarity checks)

**Projected total**: ~31.5 seconds (well under limits)

---

## 8. Next Steps

1. Create vault functions for `old_notes` and `recent_notes`
2. Implement `temporal_mirror.yaml` Tracery geist
3. Implement `hidden_hub.py` code geist (approximated version)
4. Write unit tests for both
5. Document blocked geists in final report
6. Run performance benchmarks
