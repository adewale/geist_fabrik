# Bug Report: Tracery Geist Issues

**Date**: 2025-10-21
**Component**: Tracery Geist System
**Status**: Under Investigation

## Summary

Found two related bugs in the Tracery geist system affecting how geists specify the number of suggestions to generate per invocation.

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

## Bug 2: Redundant Suggestions with Deterministic Functions

### Description
When a Tracery geist has:
- `count > 1`
- Only 1 origin template
- Deterministic vault functions (e.g., `old_notes(1)`, `recent_notes(1)`, `hubs(1)`, `orphans(1)`)

The same notes are referenced in multiple suggestions, creating redundancy.

### Affected File (Fixed)
- ✅ `examples/geists/tracery/temporal_mirror.yaml` - **FIXED** by reducing count from 2 to 1

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

### Resolution
For geists with:
- Single origin template
- Deterministic vault functions
- `count` should be 1 to avoid redundancy

---

## Fixes Implemented

### Fix 1: Support Both Parameter Names ✅
**Implemented**: Option A + Option B (best of both)

1. **Code fix** (src/geistfabrik/tracery.py:233):
```python
# Support both "count" and "suggestions_per_invocation" for backwards compatibility
count = data.get("count") or data.get("suggestions_per_invocation", 1)
```

2. **YAML standardization**:
- Updated `examples/geists/tracery/note_combinations.yaml` (suggestions_per_invocation: 2 → count: 2)
- Updated `examples/geists/tracery/what_if.yaml` (suggestions_per_invocation: 3 → count: 3)

**Result**: Backwards compatible with both parameter names, `count` takes precedence, existing geists standardized

### Fix 2: Documentation/Validation
Add validation to warn when geists might produce redundant suggestions:
- Detect single origin template + deterministic functions + count > 1
- Emit warning during geist loading

---

## Testing Strategy

### Test 1: Count Parameter Recognition
```python
def test_suggestions_per_invocation_vs_count():
    """Verify both parameter names work."""
    # Test with "count"
    geist1 = TraceryGeist.from_yaml("test_count.yaml")
    assert geist1.count == 3

    # Test with "suggestions_per_invocation"
    geist2 = TraceryGeist.from_yaml("test_suggestions.yaml")
    assert geist2.count == 3  # Should read suggestions_per_invocation
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

- [x] Bug 2 fixed for temporal_mirror.yaml (count: 2 → count: 1)
- [x] Bug 1 FIXED: TraceryGeist now supports both `count` and `suggestions_per_invocation`
- [x] YAML files standardized to use `count` consistently
- [x] Tests written and added to test_tracery.py
- [ ] Tests pending execution to verify fixes work
