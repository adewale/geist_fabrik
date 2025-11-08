# Geists That Could Benefit From KeyBERT Cluster Names

**Analysis Date**: 2025-11-08
**Context**: Now that KeyBERT provides semantic cluster naming, several other geists could be enhanced with better conceptual labels.

---

## Currently Using Clusters

### 1. cluster_mirror ✅ **Already Enhanced**

**Current status**: Uses KeyBERT by default (as of 2025-11-08)

**What it does**: Shows semantic clusters with named themes

**Before**: "Notes about notes, system, vault, organization"
**After**: "Notes about knowledge management systems, vault organization, note-taking workflows"

---

## Geists That Could Be Enhanced

### 2. concept_cluster 🎯 **High Priority**

**Location**: `src/geistfabrik/default_geists/code/concept_cluster.py`

**What it currently does**:
- Identifies tight semantic clusters (avg similarity > 0.6)
- Suggests organizing notes under a "shared theme"
- BUT: Doesn't actually name the theme!

**Current output**:
```
What if you recognised an emerging cluster around [[Project Management]]?
These notes are tightly related: [[Agile Workflows]], [[Sprint Planning]], [[Team Coordination]].
Could they be organised under a shared theme?
```

**Enhanced with KeyBERT clusters**:
```
What if you recognised an emerging cluster around [[Project Management]]?
These notes form a coherent group about "agile project workflows, sprint planning, team coordination practices".
Could you create an index note called "Agile Team Management"?
```

**Implementation approach**:
```python
# In concept_cluster.py after identifying a cluster:

# Get cluster info with KeyBERT naming
clusters = vault.get_clusters(min_size=3)

# Find which cluster this seed belongs to
for cluster_id, cluster_info in clusters.items():
    if seed in cluster_info["notes"]:
        cluster_theme = cluster_info["label"]  # KeyBERT-generated name

        text = (
            f"What if you recognised an emerging cluster around [[{seed.obsidian_link}]]? "
            f"These notes form a coherent group about \"{cluster_theme}\". "
            f"Could you create an index note organizing this theme?"
        )
```

**Impact**: Users get actionable cluster names instead of vague "shared theme"

---

### 3. temporal_clustering 🎯 **High Priority**

**Location**: `src/geistfabrik/default_geists/code/temporal_clustering.py`

**What it currently does**:
- Groups notes by time period (quarters)
- Identifies periods with high internal semantic similarity
- Compares different "intellectual seasons"
- BUT: Doesn't describe what made each period semantically distinct

**Current output**:
```
Your Q1-2024 notes form a distinct semantic cluster
(including [[Note A]], [[Note B]], [[Note C]])
separate from your Q3-2024 notes
([[Note D]], [[Note E]], [[Note F]]).
Different intellectual seasons?
```

**Enhanced with KeyBERT clusters**:
```
Your Q1-2024 notes cohere around "machine learning experimentation, neural network architectures, model optimization"
while your Q3-2024 notes focus on "production deployment, system reliability, infrastructure scaling".
From research season to engineering season?
```

**Implementation approach**:
```python
# In temporal_clustering.py for each significant period:

# Run clustering on just this time period's notes
quarter_clusters = vault.get_clusters_for_notes(quarter_notes, min_size=3)

# Get dominant theme
if quarter_clusters:
    # Take the largest cluster as representative of the period
    largest_cluster = max(quarter_clusters.values(), key=lambda c: c["size"])
    period_theme = largest_cluster["label"]

    text = (
        f"Your {label} notes cohere around \"{period_theme}\" "
        f"while your {other_label} notes focus on \"{other_theme}\". "
        f"Distinct intellectual seasons?"
    )
```

**Impact**: Users understand WHAT they were thinking about in each period, not just THAT periods differ

---

### 4. pattern_finder 🎯 **High Priority**

**Location**: `src/geistfabrik/default_geists/code/pattern_finder.py`

**What it currently does**:
- Finds semantic clusters of unlinked notes (lines 92-149)
- Asks "What's the common theme you haven't named yet?"
- BUT: Doesn't actually suggest what the theme IS

**Current output**:
```
Found a semantic cluster of similar notes with no links between them:
[[Frontend Architecture]], [[Component Patterns]], [[State Management]].
What's the common theme you haven't named yet?
```

**Enhanced with KeyBERT clusters**:
```
Found a semantic cluster about "react component architecture, frontend state patterns, modern web development"
with no links between the notes: [[Frontend Architecture]], [[Component Patterns]], [[State Management]].
Perhaps create a note called "React Architecture Patterns"?
```

**Implementation approach**:
```python
# In pattern_finder.py when reporting semantic clusters:

# Instead of ad-hoc clustering, use get_clusters
clusters = vault.get_clusters(min_size=3)

for cluster_id, cluster_info in clusters.items():
    cluster_notes = cluster_info["notes"]
    cluster_theme = cluster_info["label"]

    # Check if cluster notes are unlinked
    link_count = ... # existing logic

    if link_count == 0:
        sample = vault.sample(cluster_notes, k=3)
        note_names = ", ".join([f"[[{n.title}]]" for n in sample])

        # Generate suggested note title from theme
        suggested_title = _theme_to_title(cluster_theme)

        text = (
            f"Found a semantic cluster about \"{cluster_theme}\" "
            f"with no links between notes: {note_names}. "
            f"Perhaps create a note called \"{suggested_title}\"?"
        )
```

**Impact**: Users get concrete suggestions for organizing notes, not just questions

---

### 5. hidden_hub 💡 **Medium Priority**

**Location**: `src/geistfabrik/default_geists/code/hidden_hub.py`

**What it currently does**:
- Finds notes semantically related to many others but with few links
- Suggests they might be "hidden hubs"
- BUT: Doesn't characterize WHAT KIND of hub

**Current output**:
```
[[Systems Thinking]] is semantically related to 25 notes
(including [[Complexity]], [[Emergence]], [[Feedback Loops]])
but only has 2 links. Hidden hub? Maybe it's a concept that
connects many of your ideas...
```

**Enhanced with KeyBERT clusters**:
```
[[Systems Thinking]] is semantically related to 25 notes about
"complex systems analysis, feedback loop modeling, emergent behavior patterns"
but only has 2 links. It's a methodological hub connecting your complexity work—
worth making it a proper index note?
```

**Implementation approach**:
```python
# In hidden_hub.py for each hidden hub:

# Get the note's semantic neighborhood
neighbors = vault.neighbours(note, k=30)

# Treat neighbors as a mini-cluster and name it
# Could use get_clusters or directly call KeyBERT labeling
from geistfabrik.stats import EmbeddingMetricsComputer

metrics = EmbeddingMetricsComputer(vault.db)
# Create pseudo-cluster from neighbors
neighbor_texts = [f"{n.title} {vault.read(n)[:200]}" for n in neighbors[:10]]
hub_theme = _extract_theme_from_texts(neighbor_texts)  # Use KeyBERT logic

text = (
    f"[[{note.obsidian_link}]] is semantically related to {count} notes about "
    f"\"{hub_theme}\" but only has {total_links} links. "
    f"It's a conceptual hub connecting your work on this theme—"
    f"worth making it a proper index note?"
)
```

**Impact**: Users understand the hub's ROLE, not just that it's central

---

### 6. concept_drift 💡 **Medium Priority**

**Location**: `src/geistfabrik/default_geists/code/concept_drift.py`

**What it currently does**:
- Tracks how individual notes' embeddings migrate over time
- Says note is "drifting toward" another note
- BUT: Doesn't characterize the DIRECTION of drift thematically

**Current output**:
```
[[Machine Learning Basics]] has semantically migrated since 2024-01.
It's now drifting toward [[Production ML Systems]]—
concept evolving from 2024-01 to 2024-11?
```

**Enhanced with KeyBERT clusters**:
```
[[Machine Learning Basics]] has migrated from "theoretical foundations, algorithm concepts"
toward "production deployment, system reliability, MLOps practices" (2024-01 → 2024-11).
From theory to practice?
```

**Implementation approach**:
```python
# In concept_drift.py when detecting drift:

# Get embeddings at two time points
first_emb = trajectory[0][1]
last_emb = trajectory[-1][1]

# Find clusters of notes near each position
# Find what the note was close to initially
initial_neighbors = vault.neighbours_at_session(note, session=sessions[0], k=10)
current_neighbors = vault.neighbours_at_session(note, session=sessions[-1], k=10)

# Name both neighborhoods
initial_theme = _get_neighborhood_theme(initial_neighbors)
current_theme = _get_neighborhood_theme(current_neighbors)

text = (
    f"[[{note.obsidian_link}]] has migrated from \"{initial_theme}\" "
    f"toward \"{current_theme}\" ({first_date} → {last_date}). "
    f"Conceptual evolution in progress?"
)
```

**Impact**: Users understand the DIRECTION of conceptual change, not just that it changed

---

### 7. convergent_evolution 💡 **Medium Priority**

**Location**: `src/geistfabrik/default_geists/code/convergent_evolution.py`

**What it currently does**:
- Finds note pairs whose embeddings are converging
- Says "two ideas independently developing in the same direction"
- BUT: Doesn't name what direction that is

**Current output**:
```
[[Organizational Design]] and [[Software Architecture]] have been converging
semantically across your last 8 sessions. Two ideas independently developing
in the same direction—time to link them?
```

**Enhanced with KeyBERT clusters**:
```
[[Organizational Design]] and [[Software Architecture]] have been converging
toward "modular system structures, component boundaries, interface design patterns"
across your last 8 sessions. Both developing toward the same underlying principles—
time to link them?
```

**Implementation approach**:
```python
# In convergent_evolution.py when finding convergent pairs:

# Find current shared neighborhood
neighbors_a = vault.neighbours(note_a, k=20)
neighbors_b = vault.neighbours(note_b, k=20)
shared_neighbors = set(neighbors_a) & set(neighbors_b)

if len(shared_neighbors) >= 5:
    # These notes are converging toward a shared conceptual space
    convergence_theme = _get_neighborhood_theme(list(shared_neighbors))

    text = (
        f"[[{note_a.title}]] and [[{note_b.title}]] have been converging "
        f"toward \"{convergence_theme}\" across your last {len(similarities)} sessions. "
        f"Both developing toward the same underlying concept—time to link them?"
    )
```

**Impact**: Users understand the SHARED THEME notes are converging toward

---

## New Geist Ideas Enabled by Cluster Naming

### 8. cluster_evolution 🆕 **New Geist**

**Concept**: Track how cluster themes change over time

**What it would do**:
- Compare clusters across sessions (e.g., monthly)
- Detect when clusters split, merge, or shift themes
- Show thematic evolution of your knowledge base

**Example output**:
```
Your "web development" cluster from Q1 (about "react hooks, component patterns, state management")
has split into two clusters in Q3: "frontend architecture" and "backend services".
Your knowledge is differentiating?
```

**Implementation**:
```python
def suggest(vault: "VaultContext") -> list["Suggestion"]:
    # Get clusters from 2-3 sessions
    sessions = vault.get_recent_sessions(n=3)

    for i, session in enumerate(sessions[:-1]):
        old_clusters = vault.get_clusters_at_session(session)
        new_clusters = vault.get_clusters_at_session(sessions[i+1])

        # Find split/merge/shift events
        # Compare cluster membership and themes
        # Report significant changes
```

---

### 9. theme_emergence 🆕 **New Geist**

**Concept**: Detect when new coherent themes emerge from scattered notes

**What it would do**:
- Track notes that weren't previously clustered
- Detect when they form a new cluster
- Announce the new theme

**Example output**:
```
A new theme is emerging! Five previously scattered notes have coalesced around
"sustainable development practices, environmental impact, circular economy".
Time to start a new area of exploration?
```

---

### 10. cross_cluster_bridges 🆕 **New Geist**

**Concept**: Find notes that bridge multiple clusters

**What it would do**:
- Identify notes that are highly similar to multiple distinct clusters
- Characterize what themes they're bridging
- Suggest synthesis opportunities

**Example output**:
```
[[Systems Thinking]] bridges three clusters:
- "software architecture patterns"
- "organizational design principles"
- "complex systems modeling"

Could this be a meta-pattern connecting multiple domains?
```

---

## Implementation Priority

### Phase 1: Enhance Existing Geists (High Priority)
1. ✅ **cluster_mirror** - Done! Using KeyBERT
2. 🎯 **concept_cluster** - Add cluster theme names
3. 🎯 **temporal_clustering** - Describe period themes
4. 🎯 **pattern_finder** - Name semantic patterns

**Impact**: Immediate value for users, concrete suggestions

**Effort**: Low - just integrate existing `get_clusters()` API

### Phase 2: Enhanced Characterization (Medium Priority)
5. 💡 **hidden_hub** - Characterize hub type
6. 💡 **concept_drift** - Name drift direction
7. 💡 **convergent_evolution** - Name convergence target

**Impact**: Richer conceptual insights

**Effort**: Medium - need to apply KeyBERT to neighborhoods

### Phase 3: New Geist Development (Future)
8. 🆕 **cluster_evolution** - Track theme changes
9. 🆕 **theme_emergence** - Detect new themes
10. 🆕 **cross_cluster_bridges** - Find synthesis points

**Impact**: Novel insights not available without cluster naming

**Effort**: High - new geist logic + cluster integration

---

## Common Implementation Patterns

### Pattern 1: Direct Cluster Use
```python
# For geists that already identify groups of notes
clusters = vault.get_clusters(min_size=3)

for cluster_id, cluster_info in clusters.items():
    theme = cluster_info["label"]  # KeyBERT-generated
    notes = cluster_info["notes"]

    # Use theme in suggestion
    text = f"You have a cluster about \"{theme}\"..."
```

### Pattern 2: Neighborhood Naming
```python
# For geists that find semantically related notes
def _get_neighborhood_theme(notes: List[Note]) -> str:
    """Get KeyBERT theme for a group of notes."""
    from geistfabrik.stats import EmbeddingMetricsComputer

    # Treat neighbors as mini-cluster
    texts = [f"{n.title} {n.content[:200]}" for n in notes]

    # Apply KeyBERT labeling
    metrics = EmbeddingMetricsComputer(vault.db)
    # Would need to expose a public method for this
    theme = metrics._label_cluster_texts(texts, n_terms=3)

    return theme
```

### Pattern 3: Temporal Cluster Comparison
```python
# For geists tracking changes over time
def _compare_cluster_themes(old_cluster, new_cluster) -> str:
    """Compare cluster themes across time."""
    old_theme = old_cluster["label"]
    new_theme = new_cluster["label"]

    if old_theme == new_theme:
        return f"stable theme: {old_theme}"
    else:
        return f"shifted from \"{old_theme}\" to \"{new_theme}\""
```

---

## Helper Functions Needed

To support these enhancements, add to `vault_context.py`:

```python
def get_neighborhood_theme(self, notes: List[Note], n_terms: int = 3) -> str:
    """Get KeyBERT theme for a group of notes.

    Useful for characterizing semantic neighborhoods, hidden hubs,
    drift directions, etc.
    """
    from .stats import EmbeddingMetricsComputer

    # Get note paths
    paths = [n.path for n in notes]

    # Create pseudo-labels (all same cluster)
    labels = np.zeros(len(paths))

    # Use KeyBERT labeling
    metrics = EmbeddingMetricsComputer(self.db)
    cluster_labels = metrics._label_clusters_keybert(paths, labels, n_terms)

    return cluster_labels.get(0, "")


def get_clusters_at_session(self, session_id: int, min_size: int = 5) -> Dict:
    """Get clusters for a specific historical session.

    Enables tracking cluster evolution over time.
    """
    # Similar to get_clusters() but for specific session
    # Would need to load embeddings from that session
    pass
```

---

## Success Metrics

**Quantitative**:
- Number of geists using KeyBERT naming: 1 → 7+
- Suggestions with concrete theme names: 10% → 60%+
- User engagement with cluster-based suggestions

**Qualitative**:
- Users can understand themes without reading notes
- Suggestions provide actionable organization guidance
- Cluster names accurately reflect content

---

## Conclusion

KeyBERT cluster naming unlocks **massive potential** for GeistFabrik geists:

1. **Immediate wins**: 4 geists can be enhanced with minimal effort
2. **Rich characterization**: 3 more geists can provide deeper insights
3. **Novel capabilities**: 3+ new geists become possible

The key insight: **Many geists already find semantic groups but don't name them**. KeyBERT transforms vague pattern detection into concrete conceptual characterization.

**Recommended next action**: Implement Phase 1 enhancements (concept_cluster, temporal_clustering, pattern_finder) to validate the approach before expanding.

---

**Author**: Claude (Sonnet 4.5)
**Status**: Analysis Complete, Ready for Implementation
