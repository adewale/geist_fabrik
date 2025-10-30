# Semantic Gap Geist Specification

**Version:** 1.0
**Status:** Design Proposal
**Target Release:** Post-1.0
**Related:** STATS_COMMAND_SPEC.md

---

## 1. Overview

The **Semantic Gap Geist** is a proposed geist that identifies underexplored regions in a vault's semantic space—areas where concepts exist but remain underdeveloped, unconnected, or sparsely represented.

Unlike existing geists that focus on connecting existing notes (bridge_builder, bridge_hunter) or exploring isolated regions (island_hopper), the Semantic Gap Geist discovers **conceptual voids**: areas in the semantic space that are reachable from existing notes but not yet explored.

### Key Characteristics

- **Detects absence, not presence**: Finds where concepts *should* exist but don't
- **Uses density analysis**: Identifies sparse regions in embedding space
- **Generates exploratory suggestions**: "What if you explored the space between X and Y?"
- **Complements existing geists**: Works alongside bridge and island geists
- **Requires embeddings**: Cannot function without vector representations

---

## 2. Motivation

### The Problem

Vaults often develop **local clusters** of related notes with **conceptual gaps** between them:

```
Cluster A: Machine Learning         Cluster B: Philosophy of Mind
  ├─ Neural Networks                   ├─ Consciousness
  ├─ Deep Learning                     ├─ Qualia
  └─ Transformers                      └─ Intentionality

          [GAP: AI Ethics, Alignment, Interpretability]
```

The gap between these clusters represents **unexplored conceptual space**—ideas that would naturally bridge these domains but haven't been written about yet.

### Why Existing Geists Don't Solve This

| Geist | What It Does | Why It Misses Gaps |
|-------|-------------|-------------------|
| **bridge_builder** | Finds unlinked but semantically similar notes | Only works with existing notes |
| **bridge_hunter** | Identifies potential connections across clusters | Suggests linking existing content |
| **island_hopper** | Finds isolated notes with no links | Focuses on existing isolated content |
| **temporal_drift** | Tracks meaning changes over time | Requires existing notes to evolve |

**Semantic Gap Geist fills the void**: It suggests **concepts to explore** rather than **notes to link**.

---

## 3. What Are Semantic Gaps?

A **semantic gap** is a region in embedding space that:

1. **Is reachable** from existing notes (within conceptual distance)
2. **Is sparsely populated** (few or no notes nearby)
3. **Is situated between clusters** (in the "space between" concepts)
4. **Represents conceptual potential** (meaningful exploration opportunity)

### Types of Gaps

#### Type 1: Inter-Cluster Gaps
**Definition**: Voids between distinct conceptual clusters

**Example**:
```
Cluster A: Software Engineering
Cluster B: Urban Planning

Gap: "Systems thinking applied to cities" (unwritten)
```

**Suggestion**:
> "What if you explored the space between [[Software Architecture]] and [[City Design]]? Consider: How do modular systems inform urban development?"

---

#### Type 2: Density Holes
**Definition**: Sparse regions within a cluster's convex hull

**Example**:
```
Cluster: Philosophy
  Dense: Ethics, Metaphysics, Epistemology
  Sparse: Philosophy of Technology (few notes)

Gap: "Ethical implications of AI" (underexplored)
```

**Suggestion**:
> "Your philosophy notes mention [[Ethics]] and [[Consciousness]], but you haven't explored the ethical dimensions of emerging technology. What might you discover in this space?"

---

#### Type 3: Boundary Extensions
**Definition**: Conceptual space just beyond current cluster boundaries

**Example**:
```
Cluster: Personal Productivity
  Current: GTD, Zettelkasten, Time Blocking
  Extension: Energy management, decision fatigue

Gap: "Cognitive load and productivity" (not yet written)
```

**Suggestion**:
> "Your productivity system focuses on time management, but what about cognitive energy? Consider exploring the space between [[Time Blocking]] and cognitive science."

---

## 4. Detection Approaches

The Semantic Gap Geist uses **four complementary approaches** to identify gaps. A hybrid implementation is recommended.

---

### Approach 1: Density-Based Detection (LOF)

**Method**: Local Outlier Factor (LOF) to find low-density regions

**Algorithm**:
```python
from sklearn.neighbors import LocalOutlierFactor

def detect_density_gaps(embeddings, contamination=0.1):
    """
    Find low-density regions using Local Outlier Factor.

    Args:
        embeddings: np.ndarray of note embeddings (n_notes, dim)
        contamination: Proportion of points to flag as gaps (default 0.1)

    Returns:
        List of (gap_index, lof_score) tuples
    """
    lof = LocalOutlierFactor(
        n_neighbors=20,
        contamination=contamination,
        novelty=False
    )

    # Fit and predict (-1 = outlier/gap)
    predictions = lof.fit_predict(embeddings)
    scores = lof.negative_outlier_factor_

    # Return indices of gaps (low density points)
    gaps = [(i, scores[i]) for i in range(len(predictions))
            if predictions[i] == -1]

    # Sort by severity (most extreme LOF scores)
    gaps.sort(key=lambda x: x[1])

    return gaps
```

**Pros**:
- Fast and well-established
- Identifies local density variations
- Tunable sensitivity (contamination parameter)

**Cons**:
- Flags existing notes as "gaps" (needs post-filtering)
- Sensitive to parameter choice
- May miss inter-cluster gaps

**Use Case**: Finding **underexplored notes** within clusters (Type 2: Density Holes)

---

### Approach 2: Inter-Cluster Gap Detection

**Method**: Identify midpoints between clusters with low note density

**Algorithm**:
```python
from sklearn.cluster import HDBSCAN
from scipy.spatial.distance import cdist

def detect_intercluster_gaps(embeddings, labels, k_nearest=5, threshold=0.5):
    """
    Find gaps between clusters by checking midpoint density.

    Args:
        embeddings: np.ndarray of note embeddings
        labels: Cluster labels from HDBSCAN
        k_nearest: Number of nearest neighbors to check
        threshold: Distance threshold for "empty" space

    Returns:
        List of (gap_position, cluster_a, cluster_b, gap_score) tuples
    """
    gaps = []
    unique_labels = [l for l in set(labels) if l != -1]

    # Compute cluster centroids
    centroids = {}
    for label in unique_labels:
        cluster_points = embeddings[labels == label]
        centroids[label] = cluster_points.mean(axis=0)

    # Check all pairs of clusters
    for i, label_a in enumerate(unique_labels):
        for label_b in unique_labels[i+1:]:
            # Midpoint between centroids
            midpoint = (centroids[label_a] + centroids[label_b]) / 2

            # Distance to k nearest notes
            distances = cdist([midpoint], embeddings)[0]
            nearest_k = sorted(distances)[:k_nearest]
            avg_distance = sum(nearest_k) / k_nearest

            # If midpoint is far from all notes, it's a gap
            if avg_distance > threshold:
                gap_score = avg_distance
                gaps.append((midpoint, label_a, label_b, gap_score))

    # Sort by gap severity
    gaps.sort(key=lambda x: x[3], reverse=True)

    return gaps
```

**Pros**:
- Explicitly finds inter-cluster voids
- Returns coordinates for gap exploration
- Naturally provides context (which clusters border the gap)

**Cons**:
- Requires clustering as prerequisite
- May miss gaps within clusters
- Computationally expensive for many clusters

**Use Case**: Finding **conceptual bridges** between domains (Type 1: Inter-Cluster Gaps)

---

### Approach 3: Coverage-Based Detection (Convex Hull)

**Method**: Find embedding space regions that are **reachable** but **unoccupied**

**Algorithm**:
```python
from scipy.spatial import ConvexHull
from scipy.spatial.distance import cdist

def detect_coverage_gaps(embeddings, n_candidates=100, min_distance=0.3):
    """
    Find unoccupied regions within the convex hull of embeddings.

    Args:
        embeddings: np.ndarray of note embeddings
        n_candidates: Number of random points to sample
        min_distance: Minimum distance to nearest note to qualify as gap

    Returns:
        List of (gap_position, distance_to_nearest) tuples
    """
    # Reduce dimensionality for convex hull computation (high-dim hull is expensive)
    from sklearn.decomposition import PCA
    pca = PCA(n_components=10)
    embeddings_reduced = pca.fit_transform(embeddings)

    # Compute convex hull in reduced space
    hull = ConvexHull(embeddings_reduced)

    # Sample random points within bounding box
    mins = embeddings_reduced.min(axis=0)
    maxs = embeddings_reduced.max(axis=0)
    candidates = np.random.uniform(mins, maxs, size=(n_candidates, embeddings_reduced.shape[1]))

    # Filter to points inside hull
    from scipy.spatial import Delaunay
    delaunay = Delaunay(embeddings_reduced[hull.vertices])
    inside_hull = [c for c in candidates if delaunay.find_simplex(c) >= 0]

    # Find candidates far from any existing note
    gaps = []
    for candidate in inside_hull:
        # Project back to full embedding space
        candidate_full = pca.inverse_transform([candidate])[0]

        # Distance to nearest note
        distances = cdist([candidate_full], embeddings)[0]
        nearest_distance = distances.min()

        if nearest_distance > min_distance:
            gaps.append((candidate_full, nearest_distance))

    # Sort by distance (most isolated gaps first)
    gaps.sort(key=lambda x: x[1], reverse=True)

    return gaps
```

**Pros**:
- Finds true "empty space" within reachable region
- Doesn't require clustering
- Discovers gaps that other methods miss

**Cons**:
- Convex hull computation expensive in high dimensions (requires PCA)
- Difficult to generate natural language suggestions (no nearby notes for context)
- Random sampling may miss systematic gaps

**Use Case**: Finding **unexplored conceptual space** at boundaries (Type 3: Boundary Extensions)

---

### Approach 4: Vendi Score-Guided Detection

**Method**: Use Vendi Score to identify clusters with low internal diversity, then suggest exploration

**Algorithm**:
```python
import numpy as np
from sklearn.cluster import HDBSCAN

def detect_lowdiversity_clusters(embeddings, labels, vendi_threshold=5.0):
    """
    Find clusters with low internal diversity (low Vendi Score).

    Args:
        embeddings: np.ndarray of note embeddings
        labels: Cluster labels from HDBSCAN
        vendi_threshold: Clusters below this Vendi Score are flagged

    Returns:
        List of (cluster_id, vendi_score, notes) tuples
    """
    from sklearn.metrics.pairwise import cosine_similarity

    low_diversity_clusters = []
    unique_labels = [l for l in set(labels) if l != -1]

    for label in unique_labels:
        cluster_embeddings = embeddings[labels == label]

        if len(cluster_embeddings) < 3:
            continue  # Skip tiny clusters

        # Compute similarity matrix
        S = cosine_similarity(cluster_embeddings)

        # Compute Vendi Score (eigenvalue-based diversity)
        eigenvalues = np.linalg.eigvalsh(S)
        eigenvalues = eigenvalues[eigenvalues > 1e-10]  # Filter near-zero

        if len(eigenvalues) == 0:
            vendi_score = 0.0
        else:
            # Shannon entropy of eigenvalue distribution
            eigenvalues = eigenvalues / eigenvalues.sum()
            entropy = -np.sum(eigenvalues * np.log(eigenvalues + 1e-10))
            vendi_score = np.exp(entropy)

        if vendi_score < vendi_threshold:
            cluster_indices = np.where(labels == label)[0]
            low_diversity_clusters.append((label, vendi_score, cluster_indices))

    # Sort by lowest diversity first
    low_diversity_clusters.sort(key=lambda x: x[1])

    return low_diversity_clusters
```

**Pros**:
- Identifies conceptually narrow clusters
- Provides clear context (cluster notes) for suggestions
- Eigenvalue-based diversity is theoretically grounded

**Cons**:
- Doesn't provide gap *location* (only identifies clusters needing diversification)
- Requires clustering
- Computationally expensive (eigenvalue decomposition)

**Use Case**: Guiding users to **broaden existing topics** (Type 2: Density Holes)

---

## 5. Hybrid Implementation (Recommended)

Combine all four approaches to maximize coverage:

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """
    Semantic Gap Geist: Identify underexplored conceptual space.

    Combines four detection methods:
    1. Density-based (LOF) - Finds sparse regions
    2. Inter-cluster gaps - Finds voids between clusters
    3. Coverage-based - Finds empty space within hull
    4. Vendi-guided - Identifies narrow clusters
    """
    suggestions = []

    # Get embeddings for current session
    embeddings = vault.get_all_embeddings()  # Returns np.ndarray
    notes = list(vault.notes())

    if len(notes) < 20:
        # Too few notes for meaningful gap detection
        return []

    # ==== Method 1: Density-Based Gaps (LOF) ====
    density_gaps = detect_density_gaps(embeddings, contamination=0.05)

    for gap_idx, lof_score in density_gaps[:3]:  # Top 3 gaps
        gap_note = notes[gap_idx]

        # Find nearest neighbors for context
        neighbors = vault.find_similar(gap_note.path, k=5)
        neighbor_titles = [n.title for n, _ in neighbors[1:4]]

        suggestions.append(Suggestion(
            text=f"What if you deepened your exploration around [[{gap_note.title}]]? "
                 f"This area feels sparsely developed compared to nearby concepts like {', '.join(neighbor_titles)}.",
            notes=[gap_note.title] + neighbor_titles,
            geist_id="semantic_gap"
        ))

    # ==== Method 2: Inter-Cluster Gaps ====
    from sklearn.cluster import HDBSCAN
    clusterer = HDBSCAN(min_cluster_size=5, min_samples=3)
    labels = clusterer.fit_predict(embeddings)

    intercluster_gaps = detect_intercluster_gaps(embeddings, labels, threshold=0.5)

    for gap_pos, cluster_a, cluster_b, gap_score in intercluster_gaps[:2]:  # Top 2
        # Get representative notes from each cluster
        notes_a = [notes[i] for i in range(len(notes)) if labels[i] == cluster_a]
        notes_b = [notes[i] for i in range(len(notes)) if labels[i] == cluster_b]

        if not notes_a or not notes_b:
            continue

        # Pick one note from each cluster
        rep_a = vault.sample(notes_a, k=1)[0]
        rep_b = vault.sample(notes_b, k=1)[0]

        suggestions.append(Suggestion(
            text=f"What if you explored the conceptual space between [[{rep_a.title}]] "
                 f"and [[{rep_b.title}]]? There's an unexplored middle ground here.",
            notes=[rep_a.title, rep_b.title],
            geist_id="semantic_gap"
        ))

    # ==== Method 3: Low-Diversity Clusters (Vendi Score) ====
    low_diversity = detect_lowdiversity_clusters(embeddings, labels, vendi_threshold=3.0)

    for cluster_id, vendi_score, cluster_indices in low_diversity[:2]:  # Top 2
        cluster_notes = [notes[i] for i in cluster_indices]
        sample_notes = vault.sample(cluster_notes, k=3)

        suggestions.append(Suggestion(
            text=f"Your notes on {', '.join(['[[' + n.title + ']]' for n in sample_notes])} "
                 f"form a tight conceptual cluster. What perspectives are missing? "
                 f"Consider exploring adjacent or contrasting ideas.",
            notes=[n.title for n in sample_notes],
            geist_id="semantic_gap"
        ))

    # ==== Method 4: Coverage Gaps (Convex Hull) ====
    coverage_gaps = detect_coverage_gaps(embeddings, n_candidates=50, min_distance=0.4)

    for gap_pos, distance in coverage_gaps[:1]:  # Top 1 (expensive, so fewer)
        # Find nearest notes to provide context
        distances = cdist([gap_pos], embeddings)[0]
        nearest_indices = distances.argsort()[:3]
        context_notes = [notes[i] for i in nearest_indices]

        suggestions.append(Suggestion(
            text=f"There's unexplored conceptual territory near {', '.join(['[[' + n.title + ']]' for n in context_notes])}. "
                 f"What ideas haven't you written about yet in this space?",
            notes=[n.title for n in context_notes],
            geist_id="semantic_gap"
        ))

    # Sample down to 5 suggestions
    return vault.sample(suggestions, k=5)
```

---

## 6. Example Suggestions

### Example 1: Inter-Cluster Gap
**Vault State**: User has clusters on "Quantum Physics" and "Eastern Philosophy"

**Suggestion**:
> "What if you explored the conceptual space between [[Quantum Entanglement]] and [[Buddhist Non-Duality]]? There's an unexplored middle ground here."

**Why it works**: Identifies a genuine interdisciplinary gap that the user might find fascinating.

---

### Example 2: Density Hole
**Vault State**: User has many ethics notes but few on technology ethics

**Suggestion**:
> "What if you deepened your exploration around [[AI Safety]]? This area feels sparsely developed compared to nearby concepts like [[Utilitarianism]], [[Trolley Problem]], [[Moral Agency]]."

**Why it works**: Points to an underexplored niche within an existing interest area.

---

### Example 3: Low-Diversity Cluster
**Vault State**: User has 15 notes on "GTD" but all from the same perspective

**Suggestion**:
> "Your notes on [[Getting Things Done]], [[Weekly Review]], [[Next Actions]] form a tight conceptual cluster. What perspectives are missing? Consider exploring adjacent or contrasting ideas."

**Why it works**: Encourages diversification of thinking within a well-explored topic.

---

### Example 4: Coverage Gap
**Vault State**: User has notes on "Machine Learning" and "Biology" but nothing on "Computational Biology"

**Suggestion**:
> "There's unexplored conceptual territory near [[Neural Networks]], [[Evolution]], [[Genetics]]. What ideas haven't you written about yet in this space?"

**Why it works**: Identifies a boundary region the user might naturally expand into.

---

## 7. Comparison to Existing Geists

| Geist | Focus | Input | Output |
|-------|-------|-------|--------|
| **bridge_builder** | Connect existing notes | Unlinked similar notes | "Consider linking [[A]] to [[B]]" |
| **bridge_hunter** | Cross-cluster connections | Clusters + notes | "[[A]] and [[B]] could bridge these topics" |
| **island_hopper** | Isolated notes | Notes with no links | "[[A]] is isolated—connect it?" |
| **temporal_drift** | Meaning evolution | Note embeddings over time | "[[A]]'s meaning has shifted—revisit?" |
| **semantic_gap** (NEW) | Conceptual voids | Embedding space density | "What if you explored the space between [[A]] and [[B]]?" |

**Unique value**: Semantic Gap is the **only geist that suggests concepts to create** rather than connections to make.

---

## 8. Implementation Details

### File Location
```
<vault>/_geistfabrik/geists/code/semantic_gap.py
```

### Dependencies
```python
# Standard library
from typing import List

# GeistFabrik
from geistfabrik import Suggestion, VaultContext

# External (add to pyproject.toml)
from sklearn.neighbors import LocalOutlierFactor
from sklearn.cluster import HDBSCAN
from sklearn.decomposition import PCA
from scipy.spatial import ConvexHull, Delaunay
from scipy.spatial.distance import cdist
import numpy as np
```

### Configuration
Add to `config.yaml`:

```yaml
geists:
  semantic_gap:
    enabled: false  # Disabled by default (computationally expensive)
    lof_contamination: 0.05  # Proportion of points to flag as gaps
    min_cluster_size: 5  # HDBSCAN parameter
    vendi_threshold: 3.0  # Low diversity threshold
    coverage_samples: 50  # Number of points to sample in convex hull
```

### Performance Considerations

| Vault Size | Expected Runtime | Memory Usage |
|------------|-----------------|--------------|
| 100 notes  | ~0.5s          | ~10 MB       |
| 500 notes  | ~2s            | ~50 MB       |
| 1000 notes | ~5s            | ~100 MB      |
| 2000 notes | ~12s           | ~200 MB      |

**Recommendation**: Disable by default, let power users opt in.

---

## 9. Testing Strategy

### Unit Tests

```python
# tests/unit/test_semantic_gap.py

def test_density_gaps_detection():
    """LOF correctly identifies low-density regions."""
    # Create synthetic embeddings with a gap
    cluster_a = np.random.randn(50, 10) + [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    cluster_b = np.random.randn(50, 10) + [5, 5, 5, 5, 5, 5, 5, 5, 5, 5]
    outlier = np.array([[2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5]])

    embeddings = np.vstack([cluster_a, cluster_b, outlier])

    gaps = detect_density_gaps(embeddings, contamination=0.01)

    # Outlier should be detected
    assert len(gaps) > 0
    assert gaps[0][0] == 100  # Index of outlier

def test_intercluster_gaps():
    """Inter-cluster gap detection finds midpoints."""
    cluster_a = np.random.randn(30, 10) + [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    cluster_b = np.random.randn(30, 10) + [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]

    embeddings = np.vstack([cluster_a, cluster_b])
    labels = np.array([0]*30 + [1]*30)

    gaps = detect_intercluster_gaps(embeddings, labels, threshold=2.0)

    assert len(gaps) > 0
    # Gap position should be roughly at midpoint [5, 5, 5, ...]
    gap_pos = gaps[0][0]
    assert 3 < gap_pos[0] < 7
```

### Integration Tests

```python
# tests/integration/test_semantic_gap_geist.py

def test_semantic_gap_on_sample_vault(sample_vault):
    """Semantic gap geist runs without errors on sample vault."""
    vault_context = VaultContext(sample_vault)

    from geistfabrik.default_geists.semantic_gap import suggest

    suggestions = suggest(vault_context)

    assert isinstance(suggestions, list)
    assert all(isinstance(s, Suggestion) for s in suggestions)
    assert all(s.geist_id == "semantic_gap" for s in suggestions)

def test_semantic_gap_requires_minimum_notes(small_vault):
    """Semantic gap returns empty for vaults with < 20 notes."""
    # small_vault has only 10 notes
    vault_context = VaultContext(small_vault)

    from geistfabrik.default_geists.semantic_gap import suggest

    suggestions = suggest(vault_context)

    assert suggestions == []  # Should return empty list
```

---

## 10. User Experience Considerations

### When to Enable

**Good fit**:
- Vaults with 100+ notes
- Users interested in discovering blind spots
- Research-oriented note-taking
- Users comfortable with abstract suggestions

**Poor fit**:
- Vaults with < 50 notes (insufficient data)
- Users preferring concrete, actionable suggestions
- Vaults with highly specialized/narrow domains
- Performance-sensitive environments

### Suggestion Tone

Semantic Gap suggestions should be:
- **Exploratory**: "What if...?" not "You should..."
- **Curious**: Emphasize discovery over completion
- **Concrete**: Reference specific notes for grounding
- **Non-judgmental**: Gaps are opportunities, not failures

**Good**:
> "What if you explored the space between [[Quantum Mechanics]] and [[Free Will]]? There's conceptual territory here you haven't written about yet."

**Bad**:
> "You're missing notes on Quantum Free Will. Your vault has a gap here that needs filling."

---

## 11. Future Enhancements

### Phase 2 Features (Post-1.0)

1. **Gap Tracking**: Store identified gaps in database, track when they're filled
2. **Gap Evolution**: Visualize how gaps change as vault grows
3. **User Feedback**: Let users mark gaps as "interesting" or "irrelevant"
4. **Topological Data Analysis**: Use persistent homology for gap detection
5. **LLM-Assisted Gap Naming**: Use Claude/GPT-4 to name conceptual gaps
6. **Gap Prioritization**: Rank gaps by "interestingness" using metadata

### Integration with Stats Command

The `stats` command (see STATS_COMMAND_SPEC.md) will display:
- Number of identified gaps
- Gap severity distribution
- Largest inter-cluster gaps
- Clusters with lowest internal diversity

This provides **quantitative context** before generating suggestions.

---

## 12. Open Questions

1. **Should gaps be cached?**
   - Pro: Expensive computation
   - Con: Gaps change as vault evolves
   - Proposal: Cache for 24 hours with invalidation on new notes

2. **How many gaps to detect?**
   - Current: Top 2-3 per method (8-12 total, sampled to 5)
   - Alternative: Adaptive based on vault size

3. **Should we suggest specific topics?**
   - Current: Abstract "space between X and Y"
   - Alternative: Use LLM to generate topic names (e.g., "AI Ethics")
   - Trade-off: Specificity vs. prescriptiveness

4. **How to handle noise in clustering?**
   - HDBSCAN labels some points as noise (-1)
   - Should we treat noise points as gaps?
   - Proposal: Yes, but with lower priority

---

## 13. Success Metrics

The Semantic Gap Geist succeeds when:

1. **Users discover blind spots**: "I didn't realize I hadn't explored this!"
2. **Suggestions feel actionable**: Users can translate gaps into note ideas
3. **False positives are rare**: Gaps should feel meaningful, not random
4. **Complements other geists**: Works alongside bridge/island geists without redundancy
5. **Performance is acceptable**: < 10s runtime for 1000-note vaults

---

## 14. References

### Academic Papers
- Breunig et al. (2000): "LOF: Identifying Density-Based Local Outliers"
- Friedman & Rafsky (1979): "Multivariate Generalizations of the Wald-Wolfowitz Test"
- Carlsson (2009): "Topology and Data" (Persistent Homology)

### Related Geists in GeistFabrik
- `bridge_builder.py` - Unlinked similar notes
- `bridge_hunter.py` - Cross-cluster connections
- `island_hopper.py` - Isolated notes
- `temporal_drift.py` - Meaning evolution

### External Tools
- Obsidian Graph View - Visualizes note connections
- Obsidian Canvas - Manual spatial arrangement
- Roam Research - Bidirectional links

---

## 15. Appendix: Full Example Output

**Vault**: 200 notes on philosophy, computer science, and personal productivity

**Session**: 2025-10-30

**Semantic Gap Geist Output**:

```markdown
## Semantic Gap Geist

What if you explored the conceptual space between [[Formal Logic]] and [[Meditation Practice]]? There's an unexplored middle ground here.

What if you deepened your exploration around [[API Design]]? This area feels sparsely developed compared to nearby concepts like [[Software Architecture]], [[Design Patterns]], [[Code Review]].

Your notes on [[GTD]], [[Weekly Review]], [[Time Blocking]] form a tight conceptual cluster. What perspectives are missing? Consider exploring adjacent or contrasting ideas.

There's unexplored conceptual territory near [[Machine Learning]], [[Cognitive Science]], [[Learning Theory]]. What ideas haven't you written about yet in this space?

What if you explored the space between [[Phenomenology]] and [[User Experience Design]]? There's conceptual territory here you haven't written about yet.
```

**User Experience**: User reads these and thinks:
- "Formal logic and meditation—interesting! I've been reading about mindfulness in philosophy but haven't connected it to symbolic logic."
- "API design is indeed underdeveloped. I have lots of implementation notes but no design principles."
- "My GTD notes are all from David Allen—maybe I should explore critiques or alternative systems."

**Outcome**: User creates new notes:
- "Meditation as Formal Practice.md"
- "API Design Principles.md"
- "Critique of GTD.md"

The gaps have been productively filled.

---

**End of Specification**
