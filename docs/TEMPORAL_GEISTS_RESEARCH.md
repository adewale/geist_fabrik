# Temporal Embeddings Research and New Geist Proposals

**Date**: 2025-11-07
**Status**: Research Complete, Implementation Proposed

## Executive Summary

This document presents research-grounded proposals for new geists that leverage GeistFabrik's temporal embeddings infrastructure. Based on academic literature in diachronic embeddings, semantic change detection, and temporal knowledge graphs, we propose 7 new geists that use temporal data to **ask provocative questions**, not report analytics.

**Key Principle**: Temporal embeddings are a DETECTION MECHANISM, not the SUGGESTION ITSELF. These geists detect patterns in how understanding evolves, then ask what those patterns MEAN.

## Research Foundation

### Academic Sources

1. **Hamilton et al. (2016)** - "Diachronic Word Embeddings Reveal Statistical Laws of Semantic Change"
   - Laws of conformity (frequency) and innovation (polysemy)
   - Procrustes alignment for cross-temporal comparison
   - Validated across 200 years, 4 languages, 6 corpora

2. **Cheng et al. (2024)** - "A Survey on Temporal Knowledge Graph Embedding"
   - 7 categories of TKGE methods
   - Time-aware transformation techniques
   - Relationship evolution tracking

3. **CatViz Framework** - Temporal Pattern Classification
   - Bumps: Temporary spikes in relevance
   - Shifts: Permanent semantic reorientation
   - Cycles: Periodic/seasonal patterns

4. **Bifet & Gavaldà (2007)** - ADWIN Algorithm
   - Adaptive windowing for concept drift
   - Statistical change detection
   - Applied to cluster coherence monitoring

### GeistFabrik's Implementation Strengths

- **Session-based architecture**: Every session creates fresh embeddings
- **Historical preservation**: `session_embeddings` table stores all past embeddings
- **Hybrid embeddings**: 384 semantic + 3 temporal dimensions
- **Two-tier caching**: Semantic cached, temporal recomputed (90% cache hit rate)
- **Direct SQL access**: Geists can query full embedding history

## Proposed Geists

---

### 1. **foundation_tremor** - When Anchors Shift

**Academic Grounding**: Hamilton et al. (2016) - Law of Conformity (core concepts should drift slowly)

**What It Detects**: Central notes (high link density) whose meaning has shifted unexpectedly across recent sessions.

**Detection Method**:
```python
# For each note with >10 backlinks:
expected_drift = ALPHA / (link_count + EPSILON)  # Inverse frequency
actual_drift = mean([cosine_distance(emb[t], emb[t+1])
                     for t in last_5_sessions])

# Flag if actual_drift > expected_drift + threshold
```

**Example Suggestions**:
> "[[Emergence]] is a foundation in your vault (32 backlinks), but your understanding is shifting underneath it. What if the ground itself is moving?"

> "[[Systems Thinking]] anchors many notes, yet you're reading it differently now. Are you revising a core assumption?"

> "[[Feedback Loops]] connects everywhere, but its meaning is drifting. What if this destabilizes more than you realize?"

**Why It Works**: Uses temporal data to detect the pattern, then asks what the instability MEANS rather than reporting the numbers. Provocative, not analytical.

**Implementation File**: `src/geistfabrik/default_geists/foundation_tremor.py`

---

### 2. **bridge_migration** - When Connectors Change Allegiance

**Academic Grounding**: Hamilton et al. (2016) - Law of Innovation (polysemous concepts evolve faster)

**What It Detects**: Notes that bridge multiple contexts, tracking which context-cluster is currently dominant and whether that's changed.

**Detection Method**:
```python
# Measure context diversity from backlinks
backlink_contexts = [vault.embedding(link_note) for link_note in backlinks]
context_clusters = cluster_contexts(backlink_contexts)

# Track which cluster dominates now vs. 5 sessions ago
current_dominant = most_common_cluster(context_clusters, current_session)
historical_dominant = most_common_cluster(context_clusters, 5_sessions_ago)

# Flag if dominant cluster shifted
```

**Example Suggestions**:
> "[[Feedback Loops]] used to appear mostly in your systems-thinking notes, but now it's showing up in design patterns. What if it's migrating between domains?"

> "[[Emergence]] links to both science and philosophy, but lately science is winning. Which perspective is fading—and should it?"

> "[[Recursion]] bridges programming and metaphor. It's shifting toward metaphor. What if you're thinking less like a programmer?"

**Why It Works**: Detects the context shift, then asks what the migration MEANS. Not "you have 5 context clusters" but "which domain is winning?"

**Implementation File**: `src/geistfabrik/default_geists/bridge_migration.py`

---

### 3. **seasonal_echo** - Detecting Thinking Rhythms

**Academic Grounding**: CatViz temporal pattern classification (bumps/shifts/cycles)

**What It Detects**: Notes whose relevance follows periodic patterns (seasonal interests, annual rhythms).

**Detection Method**:
```python
# Compute similarity trajectory over last 20 sessions
trajectory = [cosine_similarity(emb_history[t], emb_current)
              for t in range(-20, 0)]

# FFT to detect periodicity
fft_result = np.fft.fft(detrend(trajectory))
# Classify as cycle if strong periodic component
```

**Example Suggestions**:
> "Every spring you orbit back to [[Garden Planning]]. What if your thinking has seasons you haven't acknowledged?"

> "[[Productivity Systems]] comes back every 3 months like clockwork. What if the cycle IS the system?"

> "[[Annual Review]] appears once a year, but the notes around it change. Same ritual, different insights each time?"

**Why It Works**: Uses FFT to detect cycles, but asks about the MEANING of periodicity rather than reporting "12-session cycle detected."

**Implementation File**: `src/geistfabrik/default_geists/seasonal_echo.py`

---

### 4. **time_traveler** - Long-Distance Conceptual Journeys

**Academic Grounding**: Hamilton et al. (2016) global displacement with Procrustes alignment

**What It Detects**: Notes whose meaning has traveled the furthest distance over 6-12 months (using aligned embeddings to normalize coordinate systems).

**Detection Method**:
```python
# Get embeddings from current and 6 months ago
current_embeds = vault.session.embeddings
historical_embeds = vault.get_session(6_months_ago).embeddings

# Procrustes alignment using anchor notes
W = procrustes_align(historical_embeds, current_embeds, anchors)
aligned_historical = {path: W @ emb for path, emb in historical_embeds.items()}

# Find maximum displacement
displacements = {path: cosine_distance(aligned_historical[path], current_embeds[path])
                 for path in common_notes}
```

**Example Suggestions**:
> "Six months ago you thought about [[Personal Knowledge Management]] completely differently. What if the old version still has something to teach you?"

> "[[Creativity]] has traveled the furthest in semantic space since winter. Are you discovering it or inventing it?"

> "[[Systems Thinking]] moved more than any other note this year. What if you're not refining the concept—you're replacing it?"

**Why It Works**: Uses Procrustes alignment to find long-term drift, then asks what the journey reveals rather than reporting displacement scores.

**Implementation File**: `src/geistfabrik/default_geists/time_traveler.py`

---

### 5. **crystallization** - When Concepts Sharpen or Blur

**Academic Grounding**: ADWIN (Adaptive Windowing) for concept drift detection

**What It Detects**: Tag clusters or MOCs becoming more/less semantically coherent over time—concepts either crystallizing into clarity or fragmenting into ambiguity.

**Detection Method**:
```python
# For each tag, compute cluster coherence over last 10 sessions
coherence_history = [
    average_pairwise_similarity(notes_with_tag, session)
    for session in recent_sessions
]

# ADWIN: detect change points
if coherence_increasing(coherence_history):
    pattern = "crystallizing"
elif coherence_decreasing(coherence_history):
    pattern = "fragmenting"
```

**Example Suggestions**:
> "Notes tagged #systems-thinking are scattering. Are the boundaries blurring naturally, or are you losing the thread?"

> "#creativity notes are converging into a tighter cluster. What if your understanding is narrowing—is that good or bad?"

> "#productivity used to be coherent, now it's fragmenting. What if the concept is breaking apart as you learn more?"

**Why It Works**: Detects coherence changes, then asks whether fragmentation/convergence is good or bad rather than just reporting the shift.

**Implementation File**: `src/geistfabrik/default_geists/crystallization.py`

---

### 6. **link_evolution** - When Connections Change Meaning

**Academic Grounding**: Temporal Knowledge Graph Embeddings (context-aware relations)

**What It Detects**: Links whose surrounding context has shifted over time—the connection itself remains but its MEANING has evolved.

**Detection Method**:
```python
# For each [[link]] from note A to note B:
# Extract paragraph surrounding the link at creation vs. now
earliest_context = extract_link_context(A, B, first_session_with_link)
current_context = extract_link_context(A, B, current_session)

# Compare context embeddings
context_drift = cosine_distance(
    vault.embed_text(earliest_context),
    vault.embed_text(current_context)
)

# Flag if drift > 0.3
```

**Example Suggestions**:
> "When you linked [[Second Brain]] to [[Zettelkasten]], it was about tools. Now the context is about thinking. What if the link stayed but the relationship evolved?"

> "[[Emergence]] → [[Complexity]]: You created this link 6 months ago in a scientific context. Now you're using it metaphorically. Same connection, different meaning?"

> "The link from [[Design]] to [[Systems]] used to be about process. Now it's about philosophy. What if you need two different links?"

**Why It Works**: Uses context drift detection, but asks about the EVOLUTION of understanding rather than just reporting "context changed."

**Implementation File**: `src/geistfabrik/default_geists/link_evolution.py`

**Implementation Note**: Requires link creation timestamps (use git history or first appearance in session_embeddings).

---

### 7. **forgotten_return** - The Boomerang Pattern

**Academic Grounding**: Temporal trajectory analysis (departure and return)

**What It Detects**: Notes that were semantically central, became peripheral, and are now returning to relevance—the intellectual boomerang.

**Detection Method**:
```python
# Track note's similarity to vault center over time
trajectory = []
for session in last_20_sessions:
    similarity_to_center = compute_centrality(note, session)
    trajectory.append(similarity_to_center)

# Detect U-shaped pattern (high → low → high)
if is_u_shaped(trajectory):
    departure_point = argmin(trajectory)
    # Note departed, now returning
```

**Example Suggestions**:
> "You orbited away from [[Metacognition]] for months, now you're circling back. Same place, different altitude?"

> "[[First Principles]] was central last spring, faded all summer, now it's returning. What if you needed the detour to really see it?"

> "[[Emergence]] dropped out of your thinking, now it's re-emerging. Are you returning to old ground or discovering it fresh?"

**Why It Works**: Detects the departure-and-return pattern, then asks about the JOURNEY rather than reporting "centrality decreased 30% then increased 25%."

**Implementation File**: `src/geistfabrik/default_geists/forgotten_return.py`

---

## Implementation Priority and Roadmap

### Phase 1: Low-Hanging Fruit (Immediate Implementation)

**Target**: Next release (0.10.0)

1. **foundation_tremor** - Minimal complexity, high value
   - Uses existing link counts and embedding history
   - Single SQL query for backlinks
   - ~100 lines of code
   - **Question**: "What if the ground itself is moving?"

2. **seasonal_echo** - Moderate complexity
   - Simple FFT-based periodicity detection
   - ~120 lines of code
   - **Question**: "What if your thinking has seasons?"

3. **forgotten_return** - Simple trajectory analysis
   - Track centrality over time
   - ~100 lines of code
   - **Question**: "Same place, different altitude?"

**Estimated Effort**: 2-3 days for all three

---

### Phase 2: Medium Complexity (Next Iteration)

**Target**: Release 0.11.0

4. **bridge_migration** - Context clustering analysis
   - Cluster backlink contexts to detect domain shifts
   - ~150 lines of code
   - **Question**: "Which domain is winning?"

5. **time_traveler** - Requires Procrustes implementation
   - Implement alignment caching for performance
   - ~250 lines of code
   - **Question**: "Are you discovering it or inventing it?"

**Estimated Effort**: 3-4 days

---

### Phase 3: Research Extensions (Future)

**Target**: Release 0.12.0+

6. **crystallization** - ADWIN-based coherence tracking
   - Track tag cluster coherence over time
   - ~150 lines of code
   - **Question**: "Are the boundaries blurring naturally, or are you losing the thread?"

7. **link_evolution** - Requires link tracking infrastructure
   - Add link creation timestamps to database schema
   - Implement context extraction
   - ~300 lines of code + schema migration
   - **Question**: "Same connection, different meaning?"

**Estimated Effort**: 4-5 days

---

## Technical Implementation Notes

### Database Schema Extensions

**For link_semantics_drift**, add link creation tracking:

```sql
-- New table
CREATE TABLE link_history (
    source_path TEXT,
    target_path TEXT,
    created_session_id INTEGER,
    link_context TEXT,  -- Surrounding paragraph
    PRIMARY KEY (source_path, target_path),
    FOREIGN KEY (created_session_id) REFERENCES sessions(session_id)
);

-- Populated incrementally: when a new link is detected, record creation session
```

### New Dependencies

```toml
# Add to pyproject.toml
[project.optional-dependencies]
temporal = [
    "scipy>=1.11.0",  # For signal processing (FFT, detrending)
]

# scipy is well-maintained, pure Python fallbacks available
```

### Procrustes Alignment Utility

Create shared utility for multiple geists:

```python
# src/geistfabrik/temporal_utils.py

import numpy as np
from typing import Dict, List

class SessionAligner:
    """
    Efficiently align embedding spaces across sessions using Procrustes.
    Caches transformations to avoid recomputation.
    """

    def __init__(self, vault):
        self.vault = vault
        self.alignment_cache: Dict[tuple, np.ndarray] = {}

    def align_embeddings(
        self,
        session1_id: int,
        session2_id: int,
        min_anchors: int = 20
    ) -> np.ndarray:
        """
        Compute Procrustes transformation from session1 → session2.

        Returns: W matrix such that W @ embedding_session1 ≈ embedding_session2
        """
        cache_key = (session1_id, session2_id)

        if cache_key in self.alignment_cache:
            return self.alignment_cache[cache_key]

        # Find anchor notes (unchanged content)
        anchors = self._find_anchor_notes(session1_id, session2_id, min_anchors)

        if len(anchors) < min_anchors:
            # Not enough anchors, return identity
            return np.eye(387)

        # Get embeddings for anchors
        session1 = self.vault.get_session(session1_id)
        session2 = self.vault.get_session(session2_id)

        X = np.array([session1.embedding(note) for note in anchors])
        Y = np.array([session2.embedding(note) for note in anchors])

        # Center
        X_centered = X - X.mean(axis=0)
        Y_centered = Y - Y.mean(axis=0)

        # SVD-based Procrustes: W = V @ U^T
        U, _, Vt = np.linalg.svd(Y_centered.T @ X_centered)
        W = U @ Vt

        # Cache
        self.alignment_cache[cache_key] = W

        return W

    def _find_anchor_notes(
        self,
        session1_id: int,
        session2_id: int,
        min_anchors: int
    ) -> List[Note]:
        """
        Find notes with unchanged content between sessions.
        Use content hash for fast comparison.
        """
        # Query database for notes in both sessions
        rows = self.vault.db.execute("""
            SELECT
                se1.note_path,
                n1.content_hash as hash1,
                n2.content_hash as hash2
            FROM session_embeddings se1
            JOIN session_embeddings se2
                ON se1.note_path = se2.note_path
            JOIN notes n1 ON se1.note_path = n1.path
            JOIN notes n2 ON se2.note_path = n2.path
            WHERE se1.session_id = ?
                AND se2.session_id = ?
                AND n1.content_hash = n2.content_hash
            LIMIT ?
        """, (session1_id, session2_id, min_anchors * 2)).fetchall()

        # Convert to Note objects
        anchors = [self.vault.get_note(row[0]) for row in rows]

        return anchors[:min_anchors * 2]  # Buffer for robustness
```

### Signal Processing Utilities

```python
# src/geistfabrik/temporal_utils.py (continued)

from scipy import signal
from scipy.fft import fft, fftfreq

def detect_temporal_pattern(
    trajectory: List[float],
    min_period: int = 3,
    max_period: int = None
) -> str:
    """
    Classify time series as bump, shift, or cycle.

    Args:
        trajectory: List of similarity values over time
        min_period: Minimum cycle length to detect
        max_period: Maximum cycle length (default: len(trajectory)//2)

    Returns: One of "bump", "shift", "cycle", "noise"
    """
    if max_period is None:
        max_period = len(trajectory) // 2

    # Detrend
    detrended = signal.detrend(trajectory)

    # FFT for periodicity detection
    fft_result = fft(detrended)
    power_spectrum = np.abs(fft_result) ** 2
    freqs = fftfreq(len(trajectory))

    # Find dominant frequency (excluding DC component)
    positive_freqs = freqs[1:len(freqs)//2]
    positive_power = power_spectrum[1:len(power_spectrum)//2]

    if len(positive_power) == 0:
        return "noise"

    dominant_idx = np.argmax(positive_power)
    dominant_freq = positive_freqs[dominant_idx]
    dominant_power = positive_power[dominant_idx]
    total_power = np.sum(power_spectrum)

    # Check for cycle
    if dominant_power / total_power > 0.3:  # Strong periodic component
        period = int(1 / abs(dominant_freq)) if dominant_freq != 0 else len(trajectory)
        if min_period <= period <= max_period:
            return "cycle"

    # Check for shift (permanent mean change)
    first_half = trajectory[:len(trajectory)//2]
    second_half = trajectory[len(trajectory)//2:]

    mean_shift = abs(np.mean(second_half) - np.mean(first_half))
    if mean_shift > 0.2:  # Significant mean shift
        return "shift"

    # Check for bump (temporary spike)
    mean_val = np.mean(trajectory)
    max_val = np.max(trajectory)

    if max_val - mean_val > 0.3:  # Significant spike
        peak_idx = np.argmax(trajectory)
        # Check if spike returns to baseline
        if peak_idx < len(trajectory) - 2:
            post_spike_mean = np.mean(trajectory[peak_idx+1:])
            if abs(post_spike_mean - mean_val) < 0.1:
                return "bump"

    return "noise"


def detect_periods(
    trajectory: List[float],
    n_periods: int = 3
) -> List[tuple[int, float]]:
    """
    Detect multiple periodicities in time series.

    Returns: List of (period, strength) tuples, sorted by strength
    """
    detrended = signal.detrend(trajectory)

    # Compute FFT
    fft_result = fft(detrended)
    power_spectrum = np.abs(fft_result) ** 2
    freqs = fftfreq(len(trajectory))

    # Only positive frequencies
    positive_freqs = freqs[1:len(freqs)//2]
    positive_power = power_spectrum[1:len(power_spectrum)//2]

    # Find peaks
    peak_indices = signal.find_peaks(positive_power, height=0.1*np.max(positive_power))[0]

    # Convert to periods and strengths
    periods = []
    for idx in peak_indices:
        freq = positive_freqs[idx]
        if freq != 0:
            period = int(1 / abs(freq))
            strength = positive_power[idx] / np.sum(positive_power)
            periods.append((period, strength))

    # Sort by strength
    periods.sort(key=lambda x: x[1], reverse=True)

    return periods[:n_periods]
```

---

## Performance Considerations

### Computational Complexity

| Geist | Time Complexity | Space Complexity | Notes |
|-------|----------------|------------------|-------|
| stability_anomaly | O(N × S) | O(1) | N=notes, S=sessions |
| polysemy_evolution | O(N × L²) | O(N × L) | L=avg backlinks |
| concept_coherence_monitor | O(T × C²) | O(T × C) | T=tags, C=notes per tag |
| temporal_wave_classifier | O(N × S log S) | O(N × S) | FFT overhead |
| semantic_displacement | O(N × D²) | O(N × D) | D=embedding dim, alignment |
| link_semantics_drift | O(E × S) | O(E) | E=edges (links) |
| seasonal_resonance | O(N × S log S) | O(N × S) | Multi-resolution FFT |

**Mitigation Strategies**:
1. **Sampling**: Process subset of notes (already standard practice)
2. **Caching**: Store Procrustes transformations, FFT results
3. **Incremental updates**: Only recompute on new sessions
4. **Lazy evaluation**: Compute patterns on-demand, not every session

### Session Time Budget

Current average session time: ~30 seconds for 47 geists on 1000-note vault.

**Target**: +7 geists should add no more than 5-10 seconds.

**Allocation**:
- Phase 1 geists (3): +2 seconds each = +6 seconds
- Phase 2 geists (2): +3 seconds each = +6 seconds
- Phase 3 geists (2): +4 seconds each = +8 seconds

**Total**: +20 seconds (acceptable for enhanced insights)

**Optimization**: Run expensive geists (FFT-based) only once per week using config:
```yaml
geists:
  temporal_wave_classifier:
    enabled: true
    frequency: weekly  # New parameter
  seasonal_resonance:
    enabled: true
    frequency: weekly
```

---

## Testing Strategy

### Unit Tests

Each geist needs:
1. **Known-answer tests**: Synthetic embedding trajectories with known patterns
2. **Edge case tests**: Empty history, single session, unchanged notes
3. **Performance tests**: 1000-note vault within time budget

**Example**:
```python
# tests/unit/test_stability_anomaly.py

def test_stability_anomaly_detects_central_drift():
    """Test that high-link-count notes with drift are flagged."""
    # Create synthetic vault
    vault = create_test_vault()

    # Create note with high link count
    central_note = vault.add_note("Central Concept")
    for i in range(15):
        other_note = vault.add_note(f"Link {i}")
        vault.add_link(other_note, central_note)

    # Simulate drift over 5 sessions
    for session in range(5):
        vault.sync()
        # Manually inject drift into embedding
        central_note.content += f" {random_text()}"

    # Run geist
    suggestions = stability_anomaly.suggest(vault.context())

    # Assert central note is flagged
    assert any(central_note.title in s.notes for s in suggestions)
    assert len(suggestions) > 0
```

### Integration Tests

Test full pipeline on `testdata/kepano-obsidian-main/`:
```python
def test_all_temporal_geists_on_real_vault():
    """Ensure all temporal geists complete without errors."""
    vault = Vault("testdata/kepano-obsidian-main")

    # Simulate 10 sessions
    for _ in range(10):
        vault.sync()
        vault.session.date += timedelta(days=7)

    # Run all temporal geists
    geists = [
        stability_anomaly,
        polysemy_evolution,
        concept_coherence_monitor,
        temporal_wave_classifier,
        semantic_displacement,
        link_semantics_drift,
        seasonal_resonance,
    ]

    for geist in geists:
        try:
            suggestions = geist.suggest(vault.context())
            assert isinstance(suggestions, list)
        except Exception as e:
            pytest.fail(f"{geist.__name__} failed: {e}")
```

### Regression Tests

Prevent Phase 3B-style regressions:
```python
def test_no_batch_similarity_in_temporal_geists():
    """Ensure temporal geists use cache-aware similarity()."""
    temporal_geists = [
        "stability_anomaly.py",
        "polysemy_evolution.py",
        # ... etc
    ]

    for geist_file in temporal_geists:
        source = Path(f"src/geistfabrik/default_geists/{geist_file}").read_text()
        assert "batch_similarity" not in source, \
            f"{geist_file} uses batch_similarity, which bypasses cache"
```

---

## Documentation Requirements

### User-Facing Documentation

**Update**: `docs/GEIST_CATALOG.md`

Add section:
```markdown
## Temporal Pattern Geists

These geists track how your understanding evolves over time using session-based embeddings.

### stability_anomaly
Detects when core concepts (frequently linked) drift unexpectedly. Based on the Law of Conformity (Hamilton et al. 2016).

**When it triggers**: Central notes with >10 backlinks showing >0.15 drift per session.

**Example**: "Your understanding of 'Systems Thinking' has shifted significantly despite its centrality..."

**Configuration**: Adjust `min_backlinks` and `drift_threshold` in config.yaml.

[... similar entries for each geist ...]
```

### Developer Documentation

**Create**: `docs/TEMPORAL_GEIST_DEVELOPMENT.md`

Guide for developers writing temporal geists:
- How to query `session_embeddings` table
- When to use Procrustes alignment
- Signal processing patterns (FFT, detrending)
- Performance optimization tips
- Testing temporal patterns

---

## Academic Validation Opportunities

GeistFabrik is uniquely positioned to contribute to academic research:

### Novel Research Area: "Personal Semantic Change"

**Gap**: Existing research studies large corpora (Wikipedia, news). Personal vaults have different dynamics:
- Small scale (100s-1000s notes vs. millions of documents)
- Intentional curation vs. natural language evolution
- Individual cognition vs. collective language change

**Opportunity**: Publish findings on personal knowledge temporal dynamics.

**Potential Venues**:
- ACM RecSys (recommender systems)
- CHI (human-computer interaction)
- CIKM (information and knowledge management)
- PIM Workshop (personal information management)

### Collaboration Opportunities

**Reach out to**:
- **William Hamilton** (McGill, Stanford) - Diachronic embeddings pioneer
- **Nina Tahmasebi** (Gothenburg) - Semantic change detection
- **Gordon Brander** (Subconscious) - Tools for thought, original inspiration

**Proposed Study**: "Temporal Patterns in Personal Knowledge: A 12-Month Longitudinal Study"
- Recruit 50 active PKM users
- Track embedding evolution over 1 year
- Validate laws of conformity/innovation at personal scale
- Publish findings + release anonymized dataset

---

## Conclusion

These 7 proposed geists leverage GeistFabrik's temporal embeddings architecture in ways grounded by rigorous academic research. They use temporal data as a DETECTION mechanism, then ask PROVOCATIVE QUESTIONS about what patterns mean:

1. **foundation_tremor**: "What if the ground itself is moving?" (conformity law violations)
2. **bridge_migration**: "Which domain is winning?" (polysemous concept evolution)
3. **seasonal_echo**: "What if your thinking has seasons?" (periodicity detection)
4. **time_traveler**: "Are you discovering it or inventing it?" (long-term displacement)
5. **crystallization**: "Are you losing the thread?" (cluster coherence drift)
6. **link_evolution**: "Same connection, different meaning?" (relationship semantics)
7. **forgotten_return**: "Same place, different altitude?" (departure and return)

Each geist embodies GeistFabrik's "muses, not oracles" philosophy—using temporal analysis to ask questions you wouldn't ask yourself, not to report measurements you could calculate.

**Next Steps**:
1. Review and approve proposals
2. Implement Phase 1 geists (foundation_tremor, seasonal_echo, forgotten_return)
3. Add to test suite with known-answer tests
4. Document in GEIST_CATALOG.md
5. Release in version 0.10.0

---

## References

**Core Papers**:
1. Hamilton, W. L., et al. (2016). "Diachronic Word Embeddings Reveal Statistical Laws of Semantic Change." ACL 2016.
2. Cheng, R., et al. (2024). "A Survey on Temporal Knowledge Graph Embedding." arXiv preprint.
3. Kutuzov, A., et al. (2018). "Diachronic word embeddings and semantic shifts: a survey." arXiv:1806.03537.
4. Bifet, A., & Gavaldà, R. (2007). "Learning from Time-Changing Data with Adaptive Windowing." SIAM SDM 2007.

**Resources**:
- HistWords Project: https://nlp.stanford.edu/projects/histwords
- TKGE Survey: https://github.com/TKGE-Survey/TKGE-Survey
- GeistFabrik Codebase: /src/geistfabrik/
