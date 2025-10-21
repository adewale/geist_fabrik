# GeistFabrik Geist Catalog

## Purpose

This document catalogs ALL geists mentioned in any GeistFabrik documentation, categorizes them by implementation status, and identifies which ones are practical to build with our current infrastructure.

**Date**: 2025-10-21 (Updated)
**Audit scope**: All markdown files, code examples, and specs
**Status**: All buildable geists implemented ✅

---

## Summary

| Category | Count |
|----------|-------|
| **Implemented & Tested** | 17 (10 code + 7 Tracery) |
| **Documented - Buildable Now** | 0 |
| **Documented - Missing Infrastructure** | 7 |
| **Total Documented Geists** | 24 |

---

## 1. Implemented Geists (17)

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

### Tracery Geists (7)

Located in `examples/geists/tracery/`

| Geist | File | Description | Has Tests? |
|-------|------|-------------|------------|
| **random_prompts** | `random_prompts.yaml` | General creative prompts | ✅ Yes |
| **note_combinations** | `note_combinations.yaml` | Combine random notes creatively | ✅ Yes |
| **what_if** | `what_if.yaml` | "What if" prompts for divergent thinking | ✅ Yes |
| **temporal_mirror** | `temporal_mirror.yaml` | Compare old and new notes temporally | ✅ Yes |
| **orphan_connector** | `orphan_connector.yaml` | Suggest connections for orphaned notes | ✅ Yes |
| **hub_explorer** | `hub_explorer.yaml` | Highlight hub notes with many connections | ✅ Yes |
| **semantic_neighbours** | `semantic_neighbours.yaml` | Show semantic neighbourhoods | ✅ Yes |

---

## 2. Documented Geists - Buildable Now (0)

These geists are documented in specs but not yet implemented. **They CAN be built with existing VaultContext methods.**

**Note**: All previously "buildable" geists have now been implemented.

---

## 3. Documented Geists - Missing Infrastructure (7)

### island_hopper

**Source**: `specs/geistfabrik_spec.md:1323-1358`
**Description**: Find notes that could bridge disconnected clusters
**Status**: ❌ BLOCKED - Missing infrastructure

**Required methods**:
- ❌ `vault.find_clusters(min_size, max_size)` - NOT IMPLEMENTED
- ✅ `vault.similarity(note, c)` - EXISTS
- ✅ `vault.sample(items, k)` - EXISTS

**Complexity**: High (requires clustering algorithm)

---

### bridge_hunter

**Source**: `specs/geistfabrik_spec.md:1390-1413`
**Description**: Find semantic paths where no graph path exists
**Status**: ❌ BLOCKED - Missing infrastructure

**Required methods**:
- ✅ `vault.unlinked_pairs(k)` - EXISTS
- ❌ `vault.semantic_path(a, b, max_hops)` - NOT IMPLEMENTED

**Complexity**: High (requires pathfinding algorithm in embedding space)

---

### density_inversion

**Source**: `specs/geistfabrik_spec.md:1415-1456`
**Description**: Detect mismatches between link structure and semantic structure
**Status**: ❌ BLOCKED - Missing infrastructure

**Required methods**:
- ❌ `vault.get_graph_neighbors(note)` - NOT IMPLEMENTED (different from semantic neighbours)
- ❌ `vault.has_link(n1, n2)` - NOT IMPLEMENTED
- ✅ `vault.similarity(n1, n2)` - EXISTS

**Complexity**: Medium

---

### vocabulary_expansion

**Source**: `specs/geistfabrik_spec.md:1458-1499`
**Description**: Track semantic space coverage over time
**Status**: ❌ BLOCKED - Missing infrastructure

**Required methods**:
- ❌ `vault.get_recent_sessions(n)` - NOT IMPLEMENTED
- ❌ `session.get_all_embeddings()` - EXISTS in Session, but multi-session tracking not supported

**Complexity**: Medium (requires temporal embedding analysis)

---

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

~~To build Tracery geists, we need vault functions:~~

**All required vault functions have been implemented.**

Previously needed (now ✅ implemented):
- ✅ `$vault.old_notes(k)` - Used by temporal_mirror
- ✅ `$vault.recent_notes(k)` - Used by temporal_mirror
- ✅ `$vault.orphans(k)` - Used by orphan_connector
- ✅ `$vault.hubs(k)` - Used by hub_explorer
- ✅ `$vault.neighbours(note, k)` - Used by semantic_neighbours
- ✅ `$vault.sample_notes(k)` - Used by various Tracery geists

---

## 5. Buildability Classification

### ✅ Can Build Now (0)

**All buildable geists have been implemented.**

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

### Completed Actions ✅

1. ✅ **Built temporal_mirror** (Tracery)
   - Created vault functions for `old_notes()` and `recent_notes()`
   - Added YAML geist file
   - Wrote unit test

2. ✅ **Built orphan_connector** (Tracery)
   - Uses `$vault.orphans(k)` function
   - Added YAML geist file
   - Wrote unit test

3. ✅ **Built hub_explorer** (Tracery)
   - Uses `$vault.hubs(k)` function
   - Added YAML geist file
   - Wrote unit test

4. ✅ **Built semantic_neighbours** (Tracery)
   - Uses `$vault.neighbours(note, k)` function
   - Added YAML geist file
   - Wrote unit test

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

All geist tests execute quickly and remain well under CI time limits.

---

## 8. Status Summary

**All buildable geists have been implemented and tested.**

### Completed ✅
1. ✅ Created vault functions (`old_notes`, `recent_notes`, `orphans`, `hubs`, `neighbours`, `sample_notes`)
2. ✅ Implemented all Tracery geists (7 total)
3. ✅ Implemented all code geists (10 total)
4. ✅ Wrote comprehensive unit tests
5. ✅ Documented blocked geists in section 3

### Blocked Geists (Do NOT implement per user directive) ❌
- island_hopper - Requires clustering algorithm
- bridge_hunter - Requires semantic pathfinding
- density_inversion - Requires graph traversal methods
- vocabulary_expansion - Requires session history tracking

### Undefined Geists ⬜
- columbo - No specification found
- drift - Likely duplicate of temporal_drift
- skeptic - No specification found
