# Vault Helper Functions Design

**Date**: 2025-10-31
**Status**: Proposed
**Related**: `specs/CONGRUENCE_MIRROR_GEIST_SPEC.md`, `docs/BLOCKED_GEISTS.md`

---

## Motivation

While implementing `congruence_mirror`, several patterns emerged that would benefit from dedicated helper methods in `VaultContext`:

1. **Verbose link checking**: `len(vault.links_between(a, b)) > 0` is common but verbose
2. **Manual link iteration**: Iterating through `note.links` and resolving targets manually
3. **No graph neighbor abstraction**: Need to combine outgoing links + backlinks manually

These helpers would:
- Make geist code more readable and maintainable
- Provide consistent APIs for common operations
- Unblock geists in `docs/BLOCKED_GEISTS.md` (specifically `density_inversion`)
- Fix a bug in `congruence_mirror` where `links_between` is called redundantly

---

## Current State Analysis

### Existing VaultContext Methods (Relevant to Links)

**Already implemented**:
```python
def links_between(self, a: Note, b: Note) -> List[Link]:
    """Find all links between two notes (bidirectional).

    Returns links in both directions: a→b and b→a
    """
    # Already checks both directions!
    links_ab = [link for link in a.links if link_matches_note(link.target, b)]
    links_ba = [link for link in b.links if link_matches_note(link.target, a)]
    return links_ab + links_ba
```

```python
def backlinks(self, note: Note) -> List[Note]:
    """Find notes that link to this note."""
    # Returns List[Note]
```

```python
def resolve_link_target(self, target: str) -> Optional[Note]:
    """Resolve a wiki-link target to a Note."""
```

### Current Usage Patterns in congruence_mirror

**Pattern 1: Checking if two notes are linked**
```python
# Current (verbose):
links_ab = vault.links_between(note, neighbor)
links_ba = vault.links_between(neighbor, note)  # BUG: Redundant!
is_linked = len(links_ab) > 0 or len(links_ba) > 0

# Should be:
is_linked = len(vault.links_between(note, neighbor)) > 0

# Proposed helper:
is_linked = vault.has_link(note, neighbor)
```

**Pattern 2: Getting all linked notes**
```python
# Current (manual iteration):
for note in vault.notes():
    for link in note.links:
        target = vault.resolve_link_target(link.target)
        if not target:
            continue
        # Use target...

# Proposed helper:
for note in vault.notes():
    for neighbor in vault.graph_neighbors(note):
        # Use neighbor...
```

---

## Proposed Helper Functions

### 1. `has_link(a: Note, b: Note) -> bool`

**Purpose**: Simplified boolean check for link existence

**Signature**:
```python
def has_link(self, a: Note, b: Note) -> bool:
    """Check if there's a direct link between two notes (bidirectional).

    Returns True if a links to b OR b links to a.

    Args:
        a: First note
        b: Second note

    Returns:
        True if notes are linked, False otherwise
    """
```

**Implementation**:
```python
def has_link(self, a: Note, b: Note) -> bool:
    """Check if there's a direct link between two notes (bidirectional)."""
    return len(self.links_between(a, b)) > 0
```

**Usage**:
```python
# Before:
is_linked = len(vault.links_between(a, b)) > 0

# After:
is_linked = vault.has_link(a, b)
```

**Benefits**:
- More readable: `has_link` is clearer intent than `len(...) > 0`
- Consistent with graph terminology (has_edge, has_connection)
- Shorter, less verbose
- Avoids double-checking bug (links_between already bidirectional)

### 2. `graph_neighbors(note: Note) -> List[Note]`

**Purpose**: Get all notes connected by links (outgoing + incoming)

**Signature**:
```python
def graph_neighbors(self, note: Note) -> List[Note]:
    """Get all notes connected to this note by links (bidirectional).

    Returns notes that:
    - This note links to (outgoing links)
    - Link to this note (incoming links / backlinks)

    Args:
        note: Query note

    Returns:
        List of connected notes (no duplicates)
    """
```

**Implementation**:
```python
def graph_neighbors(self, note: Note) -> List[Note]:
    """Get all notes connected to this note by links (bidirectional)."""
    neighbors = set()

    # Add outgoing link targets
    for link in note.links:
        target = self.resolve_link_target(link.target)
        if target is not None:
            neighbors.add(target)

    # Add incoming link sources (backlinks)
    for source in self.backlinks(note):
        neighbors.add(source)

    return list(neighbors)
```

**Usage**:
```python
# Before:
for link in note.links:
    target = vault.resolve_link_target(link.target)
    if not target:
        continue
    # Process target...

# After:
for neighbor in vault.graph_neighbors(note):
    # Process neighbor...
```

**Benefits**:
- Abstracts away link resolution complexity
- Handles both directions automatically
- Removes None-checking boilerplate
- Deduplicates bidirectional links
- Consistent with semantic `neighbours()` API

### 3. Alternative: `outgoing_links(note: Note) -> List[Note]`

**Purpose**: Sometimes you only want outgoing links (not backlinks)

**Signature**:
```python
def outgoing_links(self, note: Note) -> List[Note]:
    """Get notes this note links to (outgoing links only).

    Args:
        note: Source note

    Returns:
        List of target notes (no duplicates)
    """
```

**Implementation**:
```python
def outgoing_links(self, note: Note) -> List[Note]:
    """Get notes this note links to (outgoing links only)."""
    targets = []
    seen = set()

    for link in note.links:
        target = self.resolve_link_target(link.target)
        if target is not None and target.path not in seen:
            targets.append(target)
            seen.add(target.path)

    return targets
```

**Usage**:
```python
# Before:
for link in note.links:
    target = vault.resolve_link_target(link.target)
    if not target:
        continue
    # Process target...

# After:
for target in vault.outgoing_links(note):
    # Process target...
```

**Rationale**: `graph_neighbors()` combines incoming + outgoing, but sometimes you need just one direction

---

## Impact Analysis

### Geists That Would Benefit

**1. congruence_mirror** (already implemented)
- **Before**: 6 lines to check if linked (with bug)
- **After**: 1 line with `has_link()`
- **Before**: Manual link iteration + resolution in 2 places
- **After**: `graph_neighbors()` in loops
- **LOC reduction**: ~20 lines → ~12 lines (40% reduction)

**2. density_inversion** (blocked)
From `docs/BLOCKED_GEISTS.md`:
> Needs: For each note, count graph neighbors (linked) vs semantic neighbors (similar)

```python
# With helpers:
for note in vault.notes():
    graph_degree = len(vault.graph_neighbors(note))
    semantic_degree = len(vault.neighbours(note, k=20))

    if graph_degree > semantic_degree * 2:
        # High graph density, low semantic density
        suggestions.append(...)
```

**Status**: Unblocked by `graph_neighbors()`

**3. bridge_builder** (approximated)
Current implementation could be simplified:
```python
# Before: Manual link checking
for candidate in candidates:
    if any(vault.links_between(candidate, target) for target in [a, b]):
        continue

# After:
for candidate in candidates:
    if vault.has_link(candidate, a) or vault.has_link(candidate, b):
        continue
```

**4. island_hopper** (blocked)
Needs graph traversal - `graph_neighbors()` would be fundamental primitive

**5. orphan_connector** (default geist)
Could simplify logic with `graph_neighbors()`

### Code Quality Improvements

**Readability**:
- `has_link(a, b)` is self-documenting
- `graph_neighbors()` clearly states intent
- Reduces cognitive load (no link resolution boilerplate)

**Correctness**:
- Fixes bug in congruence_mirror (redundant bidirectional check)
- Centralizes link resolution logic (less chance of inconsistency)
- Handles edge cases (None targets) in one place

**Performance**:
- No performance regression (same underlying operations)
- `has_link()` could short-circuit on first link found (micro-optimization)

---

## Implementation Plan

### Phase 1: Add Helpers to VaultContext
1. Implement `has_link(a, b) -> bool`
2. Implement `graph_neighbors(note) -> List[Note]`
3. Optionally implement `outgoing_links(note) -> List[Note]`

### Phase 2: Add Tests
Create `tests/unit/test_vault_context_helpers.py`:
```python
def test_has_link_bidirectional():
    """Test has_link returns True for both directions."""

def test_has_link_returns_false():
    """Test has_link returns False for unlinked notes."""

def test_graph_neighbors_includes_outgoing():
    """Test graph_neighbors includes notes linked to."""

def test_graph_neighbors_includes_backlinks():
    """Test graph_neighbors includes notes linking to this note."""

def test_graph_neighbors_deduplicates():
    """Test bidirectional links don't appear twice."""
```

### Phase 3: Refactor congruence_mirror
Fix the redundant `links_between` calls:
```python
# Before:
links_ab = vault.links_between(note, neighbor)
links_ba = vault.links_between(neighbor, note)
is_linked = len(links_ab) > 0 or len(links_ba) > 0

# After:
is_linked = vault.has_link(note, neighbor)
```

### Phase 4: Documentation
Update `specs/CONGRUENCE_MIRROR_GEIST_SPEC.md` to reference these helpers in the "Future Enhancements" section.

---

## Alternative Designs Considered

### Alternative 1: Make `links_between()` Return Bool with Flag
```python
def links_between(self, a: Note, b: Note, as_bool: bool = False) -> List[Link] | bool:
    ...
```

**Rejected**: Type inconsistency, violates single responsibility

### Alternative 2: Property on Note Object
```python
@property
def graph_neighbors(self) -> List[Note]:
    ...
```

**Rejected**: Note objects are immutable data, shouldn't have vault context dependencies

### Alternative 3: Free Functions in Utility Module
```python
# geistfabrik/graph_utils.py
def has_link(vault: VaultContext, a: Note, b: Note) -> bool:
    ...
```

**Rejected**: Less discoverable, breaks VaultContext encapsulation

---

## Open Questions

### 1. Should `graph_neighbors()` handle virtual notes?
Virtual notes (date headings) appear in `vault.notes()` but may not resolve properly.

**Decision**: Yes, same handling as `backlinks()` - skip notes that don't resolve

### 2. Should we cache `graph_neighbors()` results?
Could cache per-note if called multiple times.

**Decision**: No caching initially - premature optimization. Add if profiling shows bottleneck.

### 3. Should `outgoing_links()` be included in Phase 1?
It's useful but not strictly necessary for current use cases.

**Decision**: Implement if trivial during Phase 1, otherwise defer to Phase 5 (post-1.0)

---

## Success Criteria

1. ✅ `has_link()` and `graph_neighbors()` implemented and tested
2. ✅ `congruence_mirror` refactored to use new helpers
3. ✅ `density_inversion` unblocked and implementable
4. ✅ All tests pass (unit + integration)
5. ✅ No performance regression on `congruence_mirror`

---

## Timeline

- **Design**: Complete (this document)
- **Implementation**: ~1 hour
- **Testing**: ~30 minutes
- **Refactoring**: ~15 minutes
- **Total**: ~2 hours

---

## References

- `specs/CONGRUENCE_MIRROR_GEIST_SPEC.md` - Original motivation
- `docs/BLOCKED_GEISTS.md` - Geists that would benefit
- `src/geistfabrik/vault_context.py` - Implementation target
- `src/geistfabrik/default_geists/code/congruence_mirror.py` - Primary use case
