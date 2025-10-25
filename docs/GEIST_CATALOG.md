# GeistFabrik Geist Catalog

## Purpose

This document catalogs ALL geists mentioned in any GeistFabrik documentation, categorizes them by implementation status, and identifies which ones are practical to build with our current infrastructure.

**Date**: 2025-10-22 (Updated)
**Audit scope**: All markdown files, code examples, and specs
**Status**: All buildable geists implemented ✅

---

## Summary

| Category | Count |
|----------|-------|
| **Default Geists** | 45 (36 code + 9 Tracery) |
| **Example Geists** | 0 (all examples are now defaults) |
| **Total Geists** | 45 |

---

## 1. Default Geists (45)

These geists ship bundled with GeistFabrik in the package. They provide immediate value on first run and are fully production-ready, having passed comprehensive quality audits per `specs/geist_validation_spec.md`.

### Code Geists (36)

Located in `src/geistfabrik/default_geists/code/`

All 36 code geists pass all quality checks with 100% compliance:
- ✅ Required: suggest() function, proper signature, valid Python, correct return type
- ✅ Recommended: Module docstrings, type hints, function docstrings, no dangerous imports

| Geist ID | Description | Status |
|----------|-------------|--------|
| **anachronism_detector** | Identifies notes with temporal inconsistencies | ✅ Implemented |
| **antithesis_generator** | Generates antithetical perspectives for synthesis | ✅ Implemented |
| **assumption_challenger** | Questions implicit assumptions in notes | ✅ Implemented |
| **blind_spot_detector** | Identifies semantic gaps in recent thinking | ✅ Implemented |
| **bridge_builder** | Connects disconnected clusters | ✅ Implemented |
| **bridge_hunter** | Finds semantic paths without graph paths | ✅ Implemented |
| **columbo** | Asks "just one more thing" style questions | ✅ Implemented |
| **complexity_mismatch** | Finds complexity/importance gaps | ✅ Implemented |
| **concept_cluster** | Identifies emergent themes | ✅ Implemented |
| **concept_drift** | Tracks semantic drift over time | ✅ Implemented |
| **convergent_evolution** | Finds notes developing toward each other | ✅ Implemented |
| **creative_collision** | Suggests unexpected note pairs | ✅ Implemented |
| **density_inversion** | Detects link/semantic structure mismatches | ✅ Implemented |
| **dialectic_triad** | Creates thesis-antithesis pairs for synthesis | ✅ Implemented |
| **divergent_evolution** | Finds notes developing away from each other | ✅ Implemented |
| **hermeneutic_instability** | Detects interpretive drift | ✅ Implemented |
| **hidden_hub** | Finds semantically central but under-linked notes | ✅ Implemented |
| **island_hopper** | Bridges disconnected clusters | ✅ Implemented |
| **link_density_analyser** | Analyses link patterns | ✅ Implemented |
| **metadata_driven_discovery** | Finds unexpected metadata patterns | ✅ Implemented |
| **method_scrambler** | Suggests random methodology combinations | ✅ Implemented |
| **on_this_day** | Surfaces notes from same date in previous years | ✅ Implemented |
| **pattern_finder** | Identifies recurring patterns | ✅ Implemented |
| **question_generator** | Reframes statements as questions | ✅ Implemented |
| **recent_focus** | Connects recent to old work | ✅ Implemented |
| **scale_shifter** | Suggests different scales of analysis | ✅ Implemented |
| **seasonal_patterns** | Identifies seasonal thinking rhythms | ✅ Implemented |
| **seasonal_revisit** | Revisits notes from previous seasons | ✅ Implemented |
| **session_drift** | Tracks how understanding evolves across sessions | ✅ Implemented |
| **structure_diversity_checker** | Detects repetitive writing patterns | ✅ Implemented |
| **stub_expander** | Develops short connected notes | ✅ Implemented |
| **task_archaeology** | Finds old incomplete tasks | ✅ Implemented |
| **temporal_clustering** | Groups notes by temporal patterns | ✅ Implemented |
| **temporal_drift** | Finds stale but important notes | ✅ Implemented |
| **temporal_mirror** | Compares notes from different time periods | ✅ Implemented |
| **vocabulary_expansion** | Tracks semantic space coverage over time | ✅ Implemented |

### Tracery Geists (9)

Located in `src/geistfabrik/default_geists/tracery/`

All 9 Tracery geists pass quality checks with 99% compliance:
- ✅ Required: Valid YAML, type field, id field, tracery grammar with origin
- ✅ Recommended: Description field, valid vault function calls, defined symbols

| Geist ID | Description | Status |
|----------|-------------|--------|
| **contradictor** | Challenges existing notes by suggesting opposite perspectives | ✅ Implemented |
| **hub_explorer** | Highlights hub notes with many connections | ✅ Implemented |
| **note_combinations** | Suggests combining random notes in creative ways | ✅ Implemented |
| **orphan_connector** | Suggests connections for orphaned notes | ✅ Implemented |
| **perspective_shifter** | Suggests viewing notes through different lenses | ✅ Implemented |
| **random_prompts** | Generates random creative prompts | ✅ Implemented |
| **semantic_neighbours** | Shows semantic neighbourhoods | ✅ Implemented |
| **transformation_suggester** | Showcases all Tracery modifiers | ✅ Implemented |
| **what_if** | Generates "What if" prompts for divergent thinking | ✅ Implemented |

---

## 2. Quality Audit Results

All 45 default geists were audited against quality standards defined in `specs/geist_validation_spec.md` on 2025-10-23.

### Code Geists Audit (36 geists)
- **ERRORS**: 0
- **WARNINGS**: 0 (1 minor issue fixed: dead code in hidden_hub.py)
- **PASS RATE**: 100%

All code geists comply with:
- Required standards: suggest() function, correct signature, valid Python, proper return types
- Recommended standards: Module docstrings, type hints, function docstrings, no dangerous imports
- Geist IDs match filenames
- No dangerous imports (os.system, subprocess, eval, exec, socket, http)

### Tracery Geists Audit (9 geists)
- **ERRORS**: 0
- **WARNINGS**: 0 (1 minor issue fixed: missing description in contradictor.yaml)
- **PASS RATE**: 100%

All Tracery geists comply with:
- Required standards: Valid YAML, type field, id field, tracery grammar with origin
- Recommended standards: Description fields, valid vault function calls, defined symbols
- All vault function references validated against function_registry
- No undefined symbol references

---

## 3. Implementation Notes

### Vault Functions Implemented

All required vault functions for Tracery geists have been implemented:

- ✅ `$vault.orphans(k)` - Used by orphan_connector
- ✅ `$vault.hubs(k)` - Used by hub_explorer
- ✅ `$vault.neighbours(note, k)` - Used by semantic_neighbours
- ✅ `$vault.sample_notes(k)` - Used by various Tracery geists
- ✅ `$vault.random_note_title()` - Used by contradictor

### Geists with Simplified Implementations

Some geists initially spec'd with complex infrastructure requirements were implemented using simplified approaches that work with existing VaultContext methods:

1. **island_hopper** - Uses sampling and similarity checks instead of full clustering
2. **bridge_hunter** - Uses direct similarity comparisons instead of semantic pathfinding
3. **density_inversion** - Uses link counting and semantic similarity instead of graph traversal
4. **vocabulary_expansion** - Uses single-session embedding analysis instead of multi-session tracking

These simplified implementations maintain the core intent of the geists while working within current infrastructure.

---

## 4. Testing Strategy

### Unit Test Requirements

All 45 default geists have comprehensive tests that:
- ✅ Use stub-based testing (NOT mocks)
- ✅ Use existing test vault (`testdata/kepano-obsidian-main/`)
- ✅ Execute quickly (< 1 second per test)
- ✅ Provide deterministic output (using session seeds)

### CI Impact

All geist tests execute quickly and remain well under CI time limits, maintaining fast feedback loops for development.

---

## 5. Status Summary

**Status**: All 45 default geists fully implemented, tested, and quality-audited ✅

### What Changed (2025-10-23 Update)

**Expansion from 14 to 45 default geists:**
- Previously: 5 code geists + 9 Tracery geists = 14 defaults
- Now: 36 code geists + 9 Tracery geists = 45 defaults
- All example geists promoted to defaults (examples/ directory repurposed for documentation)

**Quality improvements:**
- Fixed dead code in hidden_hub.py
- Added missing description to contradictor.yaml
- Comprehensive audit against validation spec standards
- 100% pass rate on all quality checks

### Implementation History

1. ✅ Created vault functions for Tracery geists
2. ✅ Implemented all Tracery geists (9 total)
3. ✅ Implemented all code geists (36 total)
4. ✅ Wrote comprehensive unit tests for all geists
5. ✅ Conducted quality audit per validation spec
6. ✅ Fixed identified quality issues
7. ✅ Moved contrarian_to() to built-in vault function
8. ✅ Updated all documentation to reflect 45 defaults
