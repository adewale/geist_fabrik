# Bug Report: Tracery Geist Issues

**Date**: 2025-10-21
**Component**: Tracery Geist System
**Status**: RESOLVED

## Summary

Fixed two issues in the tracery geist system:
1. **Parameter naming inconsistency**: Standardized on `count` parameter
2. **Design violation**: Fixed temporal_mirror to follow "Sample, don't rank" principle

---

## Bug 1: Inconsistent `count` Parameter Naming

### Description
Some Tracery geists use `suggestions_per_invocation` while the TraceryGeist loader only recognizes `count`. This causes those geists to default to generating 1 suggestion instead of their intended count.

### Affected Files
- `examples/geists/tracery/note_combinations.yaml` - uses `suggestions_per_invocation: 2`
- `examples/geists/tracery/what_if.yaml` - uses `suggestions_per_invocation: 3`

### Expected Behavior
Geists should generate the specified number of suggestions per invocation.

### Actual Behavior
Geists with `suggestions_per_invocation` default to `count: 1` because the loader doesn't recognize this parameter.

### Code Reference
In `/home/user/geist_fabrik/src/geistfabrik/tracery.py:232`:
```python
count = data.get("count", 1)  # Only reads "count", not "suggestions_per_invocation"
```

### Test Case
1. Load `note_combinations.yaml` which specifies `suggestions_per_invocation: 2`
2. Invoke the geist
3. **Expected**: 2 suggestions generated
4. **Actual**: 1 suggestion generated (defaulted to count=1)

---

## Bug 2: Design Violation - Ranking Instead of Sampling

### Description
The `temporal_mirror` geist violated the core principle "Sample, don't rank" by using deterministic functions `old_notes()` and `recent_notes()` which always return THE oldest and THE newest notes.

This created two problems:
1. **No variety**: With `count: 2`, both suggestions referenced identical notes
2. **Preferential attachment**: Always showing the same notes instead of sampling from a pool

### Root Cause
Functions like `old_notes(k)` and `recent_notes(k)` are deterministic by design - they use SQL ORDER BY to return specific notes. While useful for some use cases, using them directly in geists that need variety violates the "Sample, don't rank" principle.

### Affected File
- `examples/geists/tracery/temporal_mirror.yaml`

### Why This Happens
Deterministic functions like `$vault.old_notes(1)` always return the same note(s) for a given vault state. When the TraceryEngine expands multiple suggestions using the same template, each expansion calls these functions with the same seed state, producing identical note references.

### Code Flow
1. `TraceryGeist.suggest()` loops `count` times (tracery.py:248)
2. Each iteration expands `#origin#` template (tracery.py:251)
3. Template expansion calls `$vault.old_notes(1)` → always returns oldest note
4. Template expansion calls `$vault.recent_notes(1)` → always returns newest note
5. Result: All suggestions reference the same note pair

### Example Output (Before Fix)
```
12 months ago you wrote [[ArcheType]]. Today's [[GeistFabrik Session]] might be the answer
1 years ago you wrote [[ArcheType]]. Today's [[GeistFabrik Session]] suggests you're walking in circles
```
Both suggestions reference the same notes, only timeframe and relationship differ.

### Design Pattern Analysis
After reviewing all geists:

**Correct Usage of count > 1:**
- `orphan_connector.yaml` (count: 2): Has 4 different origin templates asking different questions
- `hub_explorer.yaml` (count: 2): Has 4 different origin templates asking different questions
- These create meaningful variety even with deterministic functions

**Incorrect Usage:**
- `temporal_mirror.yaml`: Had count: 2 but only 1 origin template → redundant suggestions

### The Correct Fix
**Created new sampling functions** that follow "Sample, don't rank":
- `sample_old_notes(k, pool_size)` - Sample k notes from the pool_size oldest notes
- `sample_recent_notes(k, pool_size)` - Sample k notes from the pool_size newest notes

These functions:
1. Get a pool of candidates (e.g., 10 oldest notes)
2. Randomly sample from that pool using VaultContext RNG
3. Create variety as the RNG advances between calls
4. Remain deterministic (same seed = same sequence, but not identical duplicates)

---

## Fixes Implemented

### Fix 1: Standardize on `count` Parameter Only ✅
**Decision**: Use `count` exclusively across the project for clarity and consistency.

**YAML standardization**:
- Updated `examples/geists/tracery/note_combinations.yaml` (suggestions_per_invocation: 2 → count: 2)
- Updated `examples/geists/tracery/what_if.yaml` (suggestions_per_invocation: 3 → count: 3)
- Updated `examples/geists/tracery/random_prompts.yaml` (suggestions_per_invocation: 2 → count: 2)

**Code**: No backwards compatibility - `count` is the only supported parameter (src/geistfabrik/tracery.py:232)

**Result**: Single, clear parameter name throughout the project

### Fix 2: Implement "Sample, Don't Rank" for Temporal Geist ✅

**New Functions** (src/geistfabrik/function_registry.py):
```python
@vault_function("sample_old_notes")
def sample_old_notes(vault, k=1, pool_size=10):
    """Sample k notes from the pool_size oldest notes."""
    old_pool = vault.old_notes(pool_size)
    return vault.sample(old_pool, k)

@vault_function("sample_recent_notes")
def sample_recent_notes(vault, k=1, pool_size=10):
    """Sample k notes from the pool_size newest notes."""
    recent_pool = vault.recent_notes(pool_size)
    return vault.sample(recent_pool, k)
```

**Updated temporal_mirror.yaml**:
- Changed from `$vault.old_notes(1)` → `$vault.sample_old_notes(1, 10)`
- Changed from `$vault.recent_notes(1)` → `$vault.sample_recent_notes(1, 10)`
- Kept `count: 2` to generate variety

**Result**: temporal_mirror now follows "Sample, don't rank" principle and produces varied suggestions

---

## Testing Strategy

### Test 1: Count Parameter Recognition
```python
def test_tracery_geist_count_parameter_recognized():
    """Verify 'count' parameter is correctly read from YAML."""
    # Only 'count' is supported
    geist = TraceryGeist.from_yaml("test_count.yaml")
    assert geist.count == 3
```

### Test 2: Deterministic Function Behavior
```python
def test_deterministic_functions_with_multiple_count():
    """Verify deterministic functions return same notes across expansions."""
    vault = create_test_vault()
    geist = create_geist_with_count_2()

    suggestions = geist.suggest(vault)

    # Extract note references from both suggestions
    notes1 = suggestions[0].notes
    notes2 = suggestions[1].notes

    # Should be identical when using deterministic functions
    assert notes1 == notes2  # This demonstrates the bug
```

### Test 3: Randomized Functions Create Variety
```python
def test_sample_notes_creates_variety():
    """Verify sample_notes() can create different suggestions."""
    vault = create_test_vault(note_count=100)
    geist = create_geist_with_sample_notes_and_count_10()

    suggestions = geist.suggest(vault)
    note_sets = [set(s.notes) for s in suggestions]

    # Should have some variety (not all identical)
    unique_sets = len(set(frozenset(ns) for ns in note_sets))
    assert unique_sets > 1  # At least some variety
```

---

## Related Files

- `src/geistfabrik/tracery.py` - TraceryGeist loader and engine
- `examples/geists/tracery/*.yaml` - All Tracery geist definitions
- `src/geistfabrik/vault_context.py` - Vault functions (deterministic vs randomized)
- `src/geistfabrik/function_registry.py` - Built-in function definitions

---

## Status

- [x] Bug 1 FIXED: Standardized all geists to use `count` parameter only
  - Updated note_combinations.yaml (suggestions_per_invocation → count)
  - Updated what_if.yaml (suggestions_per_invocation → count)
  - Updated random_prompts.yaml (suggestions_per_invocation → count)
  - Code uses only `count` parameter (no backwards compatibility)

- [x] Bug 2 FIXED: temporal_mirror now follows "Sample, don't rank" principle
  - Created sample_old_notes() and sample_recent_notes() functions
  - Updated temporal_mirror.yaml to use sampling functions
  - Kept count: 2 to maintain variety in suggestions
  - Tests updated to expect variety, not redundancy

- [x] Tests corrected to reflect design intent
  - Restored test_tracery_sample_notes_produces_variety_across_expansions
  - Updated integration test expectations for count: 2
  - All tests now align with "Sample, don't rank" principle
