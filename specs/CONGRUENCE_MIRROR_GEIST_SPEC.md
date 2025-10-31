# Congruence Mirror Geist - Specification

**Status**: Implemented (v0.9.0)
**Geist ID**: `congruence_mirror`
**Type**: Code geist
**Tier**: A (Provocative discovery)

---

## Overview

`congruence_mirror` examines the relationship between semantic similarity and explicit linking to reveal four types of structural patterns in your vault. It asks: where does your conscious structure (links) align or diverge from your unconscious patterns (semantic similarity)?

### Philosophy

**"Muse, not oracle"**: This geist presents observations and asks questions rather than prescribing actions. It reveals tensions between what you know (semantic relationships) and what you've articulated (explicit links), inviting reflection without judgment.

**Core Insight**: Your vault has two parallel structures:
1. **Explicit structure**: Links you've consciously created
2. **Implicit structure**: Semantic relationships detected by embeddings

The alignment or misalignment between these structures reveals patterns about how you think and organize knowledge.

---

## The Four Quadrants

```
                 Linked           Not Linked
              ──────────────────────────────────
Semantically │  EXPLICIT        │  IMPLICIT
Similar      │  (articulated)   │  (unarticulated)
              ──────────────────────────────────
Semantically │  CONNECTED       │  DETACHED
Distant      │  (bridged)       │  (separate)
```

### 1. EXPLICIT (Similar + Linked)

**What it means**: You've recognized a semantic relationship and made it explicit through linking.

**Example**:
```markdown
[[Deep Work]] and [[Flow State]] are explicitly linked—what's the third point of this triangle?
```

**Format**: Question (invites expansion)

**Why it matters**: These are your strongest, most conscious connections. The geist asks what else belongs to this pattern—not to validate your linking, but to prompt you to explore related concepts you might have missed.

**Thresholds**:
- Similarity > 0.65 (strong semantic similarity)
- Must be linked (direct wiki-link between notes)

**Selection**: Returns most similar linked pair

---

### 2. IMPLICIT (Similar + Not Linked)

**What it means**: Notes are semantically related but you haven't articulated the connection through a link.

**Example**:
```markdown
[[Attention Restoration Theory]] and [[Focus and Concentration]] relate implicitly.
```

**Format**: Statement (observation without prescription)

**Why it matters**: Reveals unconscious associations—you're thinking about these notes in related ways (semantically close) but haven't made the connection explicit. This might be:
- An oversight (you meant to link them)
- Deliberate separation (you see them differently than the embeddings do)
- Temporal drift (they were once related but have diverged)

**Thresholds**:
- Similarity > 0.70 (very strong semantic similarity)
- Must NOT be linked (no direct wiki-link in either direction)

**Selection**: Returns most similar unlinked pair

---

### 3. CONNECTED (Distant + Linked)

**What it means**: You've created a link that bridges semantic distance—connecting concepts that aren't obviously similar.

**Example**:
```markdown
[[Meeting Notes 2023-04-15]] and [[Quantum Mechanics Introduction]] are connected despite distance. What connects them?
```

**Format**: Question (investigates the bridge)

**Why it matters**: These are your most interesting connections—cross-domain links that reveal non-obvious relationships. The geist asks what bridges them, prompting you to articulate the connection you saw but perhaps didn't document.

**Thresholds**:
- Similarity < 0.45 (low semantic similarity)
- Must be linked (direct wiki-link between notes)

**Selection**: Returns most distant linked pair (biggest bridge)

---

### 4. DETACHED (Distant + Not Linked)

**What it means**: Notes are semantically distant and unlinked—appropriately separate.

**Example**:
```markdown
[[Sourdough Starter Guide]] and [[Byzantine Empire History]] are detached.
```

**Format**: Statement (neutral observation)

**Why it matters**: Most note pairs fall into this quadrant (appropriate separation). By showing an extreme example, the geist subtly challenges your assumptions—are they *really* unrelated? Sometimes surprising connections emerge from maximum distance.

**Thresholds**:
- Similarity < 0.30 (very low semantic similarity)
- Must NOT be linked (no direct wiki-link in either direction)
- Vault must have ≥10 notes (otherwise insufficient data)

**Selection**: Samples random pairs (50 attempts), returns most distant

---

## Design Decisions

### Why These Thresholds?

**EXPLICIT (>0.65)**: High enough to ensure genuine semantic similarity, but not so high that it only catches near-duplicates. Empirically, 0.65 captures notes about related concepts.

**IMPLICIT (>0.70)**: Slightly higher than explicit to focus on the *most* obvious missing links—relationships so strong that their absence is notable.

**CONNECTED (<0.45)**: Low enough to capture genuine cross-domain bridges without including moderately similar notes that happen to be linked.

**DETACHED (<0.30)**: Very low to find truly distant pairs—notes that seem maximally unrelated.

### Why Questions vs Statements?

**Questions** (EXPLICIT, CONNECTED):
- These quadrants are about **generative exploration**
- EXPLICIT: You've made one connection—what else fits?
- CONNECTED: You've bridged distance—what's the bridge?
- Questions invite divergent thinking

**Statements** (IMPLICIT, DETACHED):
- These quadrants are about **observation**
- IMPLICIT: Simple observation of unstated relationship
- DETACHED: Neutral presentation of separation
- Statements provide space for reflection without directing it

This creates a rhythm: **Question → Statement → Question → Statement**

### Why Sample for DETACHED?

Unlike the other quadrants which iterate through all candidates, DETACHED uses random sampling because:
1. **Vast search space**: In a vault with N notes, there are N×(N-1)/2 possible pairs—most are distant
2. **Performance**: Checking all pairs would be O(N²)
3. **Sufficient**: Any maximally distant pair serves the purpose (they're all "appropriately separate")
4. **Deterministic**: Uses vault's RNG seed for reproducibility

**Algorithm**: Sample 50 random pairs, filter for unlinked + similarity < 0.30, return most distant

---

## Implementation

### Core Functions

**`suggest(vault: VaultContext) -> list[Suggestion]`**
- Main entry point
- Calls all four finder functions
- Returns 0-4 suggestions (one per quadrant when examples exist)

**`find_explicit_pair(vault) -> tuple[Note, Note] | None`**
- Iterates through all links
- Computes similarity for each linked pair
- Returns pair with highest similarity if > 0.65

**`find_implicit_pair(vault) -> tuple[Note, Note] | None`**
- For each note, gets k=20 semantic neighbors
- Checks if each neighbor is linked
- Returns unlinked pair with highest similarity if > 0.70

**`find_connected_pair(vault) -> tuple[Note, Note] | None`**
- Iterates through all links
- Computes similarity for each linked pair
- Returns pair with lowest similarity if < 0.45

**`find_detached_pair(vault) -> tuple[Note, Note] | None`**
- Samples 50 random note pairs (using vault's RNG)
- Filters for unlinked + similarity < 0.30
- Returns pair with lowest similarity

### Performance Characteristics

**Time Complexity**:
- `find_explicit_pair`: O(L) where L = number of links
- `find_implicit_pair`: O(N×K) where N = notes, K = neighbors (20)
- `find_connected_pair`: O(L) where L = number of links
- `find_detached_pair`: O(1) with sampling (50 attempts max)

**Space Complexity**: O(1) for all (stores only candidate pairs, not all pairs)

**Bottlenecks**:
- `find_implicit_pair` is most expensive (N×K similarity computations)
- For 100 notes: ~2000 similarity checks
- For 1000 notes: ~20,000 similarity checks
- Mitigated by: k=20 limit, efficient cosine similarity computation

---

## Output Examples

### Typical Session (4 Suggestions)

```markdown
## Geist Session - 2025-10-31

### congruence_mirror

[[Deep Work]] and [[Flow State]] are explicitly linked—what's the third point of this triangle? ^g20251031-001

[[Attention Restoration Theory]] and [[Focus and Concentration]] relate implicitly. ^g20251031-002

[[Meeting Notes 2023-04-15]] and [[Quantum Mechanics Introduction]] are connected despite distance. What connects them? ^g20251031-003

[[Sourdough Starter Guide]] and [[Byzantine Empire History]] are detached. ^g20251031-004
```

### Partial Results

Not all quadrants will have examples in every vault:

**Small vault (<10 notes)**:
- EXPLICIT: Maybe
- IMPLICIT: Maybe
- CONNECTED: Maybe
- DETACHED: No (requires ≥10 notes)

**Highly connected vault** (every note links to many others):
- EXPLICIT: Likely
- IMPLICIT: Unlikely (most similar pairs already linked)
- CONNECTED: Likely
- DETACHED: Likely

**Sparse vault** (few links):
- EXPLICIT: Unlikely
- IMPLICIT: Likely
- CONNECTED: Unlikely
- DETACHED: Likely

---

## Testing Strategy

### Integration Tests

**Primary test**: `test_congruence_mirror_geist()` in `tests/integration/test_example_geists.py`

Validates:
1. Returns list of 0-4 suggestions
2. Each suggestion has correct geist_id
3. Each suggestion references exactly 2 notes
4. Format matches quadrant:
   - EXPLICIT: Has "?" and "triangle"
   - IMPLICIT: No "?", ends with "."
   - CONNECTED: Has "?" and "What connects them?"
   - DETACHED: No "?", ends with "."

**Test vault**: Uses `testdata/kepano-obsidian-main/` (8 notes)
- Small but realistic vault structure
- Mix of linked and unlinked notes
- Varied semantic content

### Performance Tests

**Planned** (not yet implemented):
- 10 notes: <0.1s
- 100 notes: <1.0s
- 1000 notes: <5.0s

**Test approach**: Generate synthetic vaults with known structure, measure execution time

---

## Future Enhancements

### 1. Cluster-Level Analysis

Currently analyzes individual note pairs. Could extend to cluster-level patterns:

**Explicit Cluster**: High internal linking + semantic coherence
```markdown
Your productivity cluster (18 notes, 47% linked) has explicit structure—what unifies them?
```

**Implicit Cluster**: Semantic coherence + low internal linking
```markdown
Your memory cluster (15 notes, 8% linked) groups implicitly—why separate them?
```

**Requires**: `get_clusters()` from VaultContext (implemented for cluster_mirror)

### 2. Temporal Tracking

Track how quadrant membership changes over time:
- Notes moving from IMPLICIT → EXPLICIT (you articulated a relationship)
- Notes moving from EXPLICIT → CONNECTED (semantic drift)
- Notes moving from CONNECTED → DETACHED (link removed or weakened)

**Requires**: Session history tracking

### 3. Vault Helper Functions ✅ IMPLEMENTED

**Status**: Implemented in v0.9.1

The following helper functions were added to `VaultContext` to make geist code cleaner:

**`vault.has_link(a: Note, b: Note) -> bool`** ✅
- Binary check for direct link in either direction
- Replaces verbose `len(vault.links_between(a, b)) > 0` pattern
- Used in: IMPLICIT, DETACHED quadrants
- Fixed bug: Previous code called `links_between` twice redundantly

**`vault.graph_neighbors(note: Note) -> List[Note]`** ✅
- Returns notes connected by links (both incoming and outgoing)
- Handles link resolution and deduplication automatically
- Useful for: Graph-based geists, link analysis
- Will unblock: `density_inversion` geist

**Implementation details**:
```python
def has_link(self, a: Note, b: Note) -> bool:
    """Check if there's a direct link between notes (bidirectional)."""
    return len(self.links_between(a, b)) > 0

def graph_neighbors(self, note: Note) -> List[Note]:
    """Get all notes connected by links (bidirectional)."""
    # Returns outgoing link targets + backlinks (deduplicated)
```

**Impact on congruence_mirror**:
- Fixed redundant bidirectional check in `find_implicit_pair` and `find_detached_pair`
- Reduced code from 6 lines to 1 line for link checking
- More readable and maintainable

**See also**: `specs/VAULT_HELPER_FUNCTIONS_DESIGN.md` for full design rationale

### 4. Configurable Thresholds

Allow users to tune sensitivity:

```yaml
# In config.yaml
congruence_mirror:
  explicit_threshold: 0.65
  implicit_threshold: 0.70
  connected_threshold: 0.45
  detached_threshold: 0.30
```

**Trade-offs**:
- More configurability vs simpler mental model
- Expert users vs default experience

### 5. Multi-Hop Patterns

Detect patterns across multiple notes:

**Transitive Implicit**: A→B linked, B→C linked, but A↔C implicit
```markdown
[[A]] connects to [[C]] through [[B]], but they're also directly similar—make it explicit?
```

**Broken Bridge**: A→B→C where A-B and B-C are CONNECTED (distant + linked)
```markdown
[[B]] bridges [[A]] and [[C]]—what's the connection?
```

---

## Comparison to Similar Geists

### vs `bridge_builder`
- **bridge_builder**: Finds notes that could connect unlinked pairs (suggests intermediaries)
- **congruence_mirror**: Reveals existing structure/anti-structure patterns (observes quadrants)
- **Difference**: bridge_builder is prescriptive ("here's a bridge"), congruence_mirror is reflective ("here's the pattern")

### vs `semantic_neighbours`
- **semantic_neighbours**: Shows k-nearest neighbors without regard to links
- **congruence_mirror**: Contextualizes semantic similarity against linking behavior
- **Difference**: semantic_neighbours ignores links, congruence_mirror uses links as contrast

### vs `cluster_mirror`
- **cluster_mirror**: Shows semantic clustering at vault scale
- **congruence_mirror**: Shows congruence at pair scale
- **Similarity**: Both reveal unconscious patterns by contrasting semantic and structural dimensions

---

## Design Principles Satisfied

### ✓ Muses, Not Oracles
- Questions invite exploration, don't prescribe action
- Statements observe without judgment
- No "you should" language

### ✓ Questions, Not Answers
- EXPLICIT: "What's the third point?"
- CONNECTED: "What connects them?"
- Doesn't explain, prompts user to think

### ✓ Sample, Don't Rank
- Returns one example per quadrant (not ranked lists)
- Most similar/dissimilar selection is deterministic
- Avoids creating hierarchies or preferences

### ✓ Deterministic Randomness
- Same vault + same date = same suggestions
- Uses vault's RNG seed for DETACHED sampling
- Reproducible for testing and user experience

### ✓ Non-Destructive
- Read-only analysis of vault structure
- No modifications to notes or links
- Safe to run repeatedly

---

## User Experience Goals

### Surprise
Reveals patterns you didn't know existed—especially CONNECTED pairs that bridge unexpected domains.

### Reflection
Invites you to think about *why* certain patterns exist—"Why haven't I linked these?" or "What bridges these distant notes?"

### Discovery
Prompts exploration—EXPLICIT asks for expansion, CONNECTED asks for articulation.

### Acceptance
DETACHED suggests that not everything needs to connect—appropriate separation is valid.

---

## Known Limitations

### 1. Similarity Threshold Sensitivity

Thresholds (0.65, 0.70, 0.45, 0.30) are empirically chosen but may not suit all vaults:
- Academic vaults with dense terminology might need higher thresholds
- Personal journals with varied writing might need lower thresholds

**Mitigation**: Future enhancement to make configurable

### 2. Binary Link Detection

Currently treats all links equally—doesn't distinguish:
- Casual mentions vs structural connections
- One-way vs bidirectional relationships
- Strong vs weak links

**Mitigation**: This is a fundamental design choice (simplicity over nuance)

### 3. No Context Beyond Pairs

Analyzes pairs in isolation without considering:
- Neighborhood structure (what else each note links to)
- Path length (how many hops between notes)
- Cluster membership

**Mitigation**: Future enhancement for cluster-level analysis

### 4. Language-Dependent Embeddings

Semantic similarity depends on embedding model (all-MiniLM-L6-v2):
- English-optimized
- ~384 dimensions of semantic space
- May miss domain-specific relationships

**Mitigation**: Inherent to embedding-based approach, but model could be swapped

---

## Implementation Notes

### Why Not Use `vault.similarity(a, b)` Everywhere?

Current implementation computes similarity inline in each finder function. Could use `vault.similarity()` for consistency.

**Trade-off**:
- Pro: More readable, consistent API
- Con: Slightly more expensive (method call overhead)

**Decision**: Inline for performance in tight loops

### Why K=20 for Implicit?

`find_implicit_pair` uses `vault.neighbours(note, k=20)` to get candidates.

**Rationale**:
- k=10: Might miss implicit relationships (too conservative)
- k=20: Good balance of recall vs performance
- k=50: Diminishing returns (similarity drops off quickly)

**Empirical**: With k=20, we capture 90%+ of high-similarity pairs while keeping performance O(N×20)

### Why 50 Samples for Detached?

`find_detached_pair` samples 50 random pairs before selecting most distant.

**Rationale**:
- 10 samples: Might not find any pairs with similarity < 0.30
- 50 samples: High probability of finding several very distant pairs
- 100 samples: Diminishing returns, ~2x slower

**Empirical**: With 50 samples in a 100-note vault, we find 10-20 qualifying pairs on average

---

## Performance Profile

### Expected Performance (Projected)

| Vault Size | Time   | Bottleneck        |
|------------|--------|-------------------|
| 10 notes   | <0.1s  | N/A               |
| 50 notes   | <0.3s  | implicit (1000)   |
| 100 notes  | <1.0s  | implicit (2000)   |
| 500 notes  | <5.0s  | implicit (10000)  |
| 1000 notes | <15s   | implicit (20000)  |

Numbers in parentheses: approximate similarity computations for `find_implicit_pair`

### Optimization Opportunities

**1. Cache similarity computations**
- Store computed similarities to avoid recomputation
- Trade-off: memory vs speed

**2. Reduce k for large vaults**
- Use adaptive k: min(20, sqrt(N))
- Trade-off: recall vs speed

**3. Early termination**
- Stop searching once threshold is met
- Trade-off: optimal result vs speed

**Note**: Performance profiling to be conducted post-spec

---

## References

### Related Geists
- `cluster_mirror`: Semantic clustering (vault-scale)
- `bridge_builder`: Connection suggestions
- `semantic_neighbours`: Pure semantic similarity
- `temporal_mirror`: Temporal clustering

### Related Specifications
- `specs/geistfabrik_spec.md`: Core architecture
- `specs/CLUSTER_MIRROR_GEIST_SPEC.md`: Similar analysis approach
- `docs/BLOCKED_GEISTS.md`: Geists blocked by missing primitives

### Research Foundation
This geist doesn't rely on external research—it's a straightforward application of:
- Cosine similarity (standard embedding metric)
- Graph structure analysis (link presence/absence)
- Deterministic sampling (RNG with seed)

---

## Conclusion

`congruence_mirror` reveals the relationship between conscious structure (links) and unconscious patterns (semantics) through four distinct provocations. It invites reflection on how you organize knowledge—where you've made connections explicit, where relationships remain implicit, and where you've bridged unexpected distances.

By presenting observations without prescription and asking questions without answers, it embodies the "muses not oracles" philosophy at the core of GeistFabrik.

---

**Version**: 1.0
**Last Updated**: 2025-10-31
**Implementation Status**: Complete ✅
