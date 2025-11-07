# Temporal Embeddings Research and New Geist Proposals

**Date**: 2025-11-07
**Status**: Research Complete, Implementation Proposed

## Executive Summary

This document presents research-grounded proposals for new geists that leverage GeistFabrik's temporal embeddings infrastructure. Based on academic literature in diachronic embeddings, semantic change detection, and temporal knowledge graphs, we propose 7 new geists that detect patterns invisible to current implementations.

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

### 1. **stability_anomaly** - Conformity Law Violations

**Academic Grounding**: Hamilton et al. (2016) - Law of Conformity

**Concept**: Frequently-referenced notes (high link density) should drift slowly due to semantic anchoring. When core concepts drift rapidly, it signals fundamental reconceptualization.

**Detection Method**:
```python
# For each note with >10 backlinks:
expected_drift = ALPHA / (link_count + EPSILON)  # Inverse frequency
actual_drift = mean([cosine_distance(emb[t], emb[t+1])
                     for t in last_5_sessions])
anomaly_score = actual_drift - expected_drift

# Flag if anomaly_score > 0.05
```

**Example Output**:
> Your understanding of "Emergence" has shifted significantly (drift: 0.18) despite being a central concept in your vault (32 backlinks). What fundamental insight challenged this anchor?

**Implementation File**: `src/geistfabrik/default_geists/stability_anomaly.py`

**Why It's Valuable**: Detects when foundational concepts are being reconsidered, suggesting intellectual paradigm shifts.

---

### 2. **polysemy_evolution** - Innovation Law Application

**Academic Grounding**: Hamilton et al. (2016) - Law of Innovation

**Concept**: Notes serving multiple semantic roles (high context diversity) should evolve faster. Track which context-cluster is currently dominant.

**Detection Method**:
```python
# Measure context diversity
backlink_contexts = [vault.embedding(link_note) for link_note in backlinks]
polysemy_score = average_pairwise_distance(backlink_contexts)

# Cluster contexts into semantic groups
from sklearn.cluster import DBSCAN
context_clusters = DBSCAN(eps=0.3).fit(backlink_contexts)

# Track dominant cluster over sessions
current_dominant = most_common_cluster(context_clusters, current_session)
historical_dominant = most_common_cluster(context_clusters, 5_sessions_ago)

# Flag if dominant cluster changed
```

**Example Output**:
> "Feedback loops" has shifted from primarily appearing in systems-thinking contexts to design patterns. This note's polysemous nature (5 distinct context clusters) makes it a conceptual bridge. Which domain is pulling harder now?

**Implementation File**: `src/geistfabrik/default_geists/polysemy_evolution.py`

**Why It's Valuable**: Reveals how bridge concepts between domains evolve, showing intellectual integration patterns.

---

### 3. **temporal_wave_classifier** - Bump/Shift/Cycle Detection

**Academic Grounding**: CatViz temporal pattern classification

**Concept**: Classify note relevance trajectories as:
- **Bumps**: Temporary spikes (project work, events)
- **Shifts**: Permanent changes (learning, reconceptualization)
- **Cycles**: Periodic patterns (seasonal interests, annual reviews)

**Detection Method**:
```python
# For each note, compute similarity trajectory to current embedding
trajectory = [cosine_similarity(emb_history[t], emb_current)
              for t in range(-20, 0)]

# FFT to detect periodicity
fft_result = np.fft.fft(detrend(trajectory))
dominant_freq = argmax(power_spectrum[1:])

if dominant_power / total_power > 0.3:
    pattern = "cycle"
    period = 1 / dominant_freq
elif permanent_mean_shift_detected(trajectory):
    pattern = "shift"
elif temporary_spike_detected(trajectory):
    pattern = "bump"
```

**Example Output (Cycle)**:
> "Garden planning" shows a 12-session cycle (approx. yearly). Notes cluster around it each spring, then disperse. Your thinking has seasons.

**Example Output (Shift)**:
> "Machine learning" underwent a permanent semantic shift 8 sessions ago. Your understanding fundamentally changed—what was the catalyst?

**Example Output (Bump)**:
> "Conference notes" spiked in relevance 3 sessions ago, then returned to baseline. What temporary convergence occurred?

**Implementation File**: `src/geistfabrik/default_geists/temporal_wave_classifier.py`

**Why It's Valuable**: Surfaces temporal patterns invisible to single-session analysis, revealing intellectual rhythms.

---

### 4. **semantic_displacement** - Cross-Temporal Distance Tracking

**Academic Grounding**: Hamilton et al. (2016) global displacement metric with Procrustes alignment

**Concept**: Compare embeddings across large time gaps (6-12 months) using Procrustes alignment to normalize coordinate systems. Identify notes with maximum conceptual displacement.

**Detection Method**:
```python
# Get embeddings from current session and 6 months ago
current_embeds = vault.session.embeddings
historical_embeds = vault.get_session(6_months_ago).embeddings

# Find anchor notes (unchanged content)
anchors = find_unchanged_notes(current, historical)

# Compute Procrustes transformation W
W = procrustes_align(historical_embeds[anchors], current_embeds[anchors])

# Apply alignment
aligned_historical = {path: W @ emb for path, emb in historical_embeds.items()}

# Compute displacement for all notes
displacements = {
    path: cosine_distance(aligned_historical[path], current_embeds[path])
    for path in common_notes
}

# Surface top 5 movers
```

**Example Output**:
> Compared to 6 months ago, "Personal knowledge management" has moved furthest in semantic space (displacement: 0.47). You're thinking about this fundamentally differently now.

**Implementation File**: `src/geistfabrik/default_geists/semantic_displacement.py`

**Why It's Valuable**: Reveals long-term conceptual evolution invisible to session-to-session comparisons.

---

### 5. **concept_coherence_monitor** - ADWIN-Inspired Cluster Drift

**Academic Grounding**: ADWIN (Adaptive Windowing) for concept drift detection

**Concept**: Monitor whether note clusters (by tag or MOC) are becoming more/less semantically coherent over time. Detect when concept boundaries blur or crystallize.

**Detection Method**:
```python
# For each tag, compute cluster coherence history
def cluster_coherence(notes, session):
    embeddings = [session.embedding(note) for note in notes]
    return average_pairwise_similarity(embeddings)

coherence_history = [
    cluster_coherence(notes_with_tag, vault.get_session(offset=-i))
    for i in range(10)
]

# Apply ADWIN to detect change points
older_window = coherence_history[:5]
recent_window = coherence_history[5:]

if mean(recent_window) - mean(older_window) > 0.2:
    alert("coherence increasing - concepts crystallizing")
elif mean(older_window) - mean(recent_window) > 0.2:
    alert("coherence decreasing - boundaries blurring")
```

**Example Output (Decreasing)**:
> Notes tagged #systems-thinking are becoming less coherent (coherence dropped 0.28 over 10 sessions). Concept boundaries may be blurring. Time to reorganize or split the tag?

**Example Output (Increasing)**:
> Notes tagged #creativity are converging (coherence increased 0.31). Your understanding is consolidating around a more unified framework.

**Implementation File**: `src/geistfabrik/default_geists/concept_coherence_monitor.py`

**Why It's Valuable**: Detects when mental models need reorganization or when understanding is maturing.

---

### 6. **link_semantics_drift** - Relationship Evolution Tracker

**Academic Grounding**: Temporal Knowledge Graph Embeddings (context-aware relations)

**Concept**: In TKGE, relations have temporal semantics: (subject, relation, object, time). In Obsidian, links are relationships. Track how the *meaning* of links evolves by comparing embedding of surrounding context over time.

**Detection Method**:
```python
# For each [[link]] from note A to note B:
def get_link_context_embedding(source_note, target, session):
    # Find paragraph containing [[target]] in source_note
    link_pattern = f"[[{target.title}]]"
    link_position = source_note.content.index(link_pattern)
    context = extract_paragraph(source_note.content, link_position)
    return vault.embed_text(context)

# Compare context embeddings across sessions
earliest_context = get_link_context_embedding(A, B, first_session_with_link)
current_context = get_link_context_embedding(A, B, current_session)

context_drift = cosine_distance(earliest_context, current_context)

# Flag if drift > 0.3
```

**Example Output**:
> The link from "Second brain" to "Zettelkasten" has evolved. Originally embedded in discussions of tools, now appears in contexts about thinking processes. The relationship's meaning shifted from technical to conceptual.

**Implementation File**: `src/geistfabrik/default_geists/link_semantics_drift.py`

**Why It's Valuable**: Reveals how understanding of connections evolves, suggesting when links need annotation or splitting.

**Implementation Note**: Requires tracking link creation times (could use git history or file modification dates as proxy).

---

### 7. **seasonal_resonance** - Enhanced Periodicity Detection

**Academic Grounding**: Fourier-based periodicity detection + CatViz cycles

**Concept**: Extend existing `seasonal_patterns` geist with:
1. Multi-scale periodicity (monthly, quarterly, yearly)
2. Phase-shift detection (patterns arriving earlier/later each cycle)
3. Harmonic analysis (nested cycles)

**Detection Method**:
```python
# For each note, compute embedding trajectory
trajectory = vault.get_embeddings_history(note, sessions=50)

# Multi-resolution FFT
periods = detect_multiple_periods(trajectory)  # Returns [(period, strength)]

# Detect phase shifts
if len(periods) > 0:
    dominant_period = periods[0][0]
    phase_current = compute_phase(trajectory[-dominant_period:])
    phase_previous = compute_phase(trajectory[-2*dominant_period:-dominant_period])
    phase_shift = phase_current - phase_previous

# Detect harmonics (e.g., 3-month + 12-month cycles)
harmonics = find_harmonic_relationships(periods)
```

**Example Output**:
> "Productivity systems" shows nested cycles: 3-month minor (quarterly reviews) and 12-month major (yearly planning). This year, the 3-month cycle is arriving 2 weeks earlier—you're front-loading reflection.

**Implementation File**: `src/geistfabrik/default_geists/seasonal_resonance.py`

**Why It's Valuable**: Reveals complex temporal rhythms in thinking, suggesting optimal review schedules.

---

## Implementation Priority and Roadmap

### Phase 1: Low-Hanging Fruit (Immediate Implementation)

**Target**: Next release (0.10.0)

1. **stability_anomaly** - Minimal complexity, high value
   - Uses existing link counts and embedding history
   - Single SQL query for backlinks
   - ~100 lines of code

2. **polysemy_evolution** - Moderate complexity
   - Requires sklearn for clustering (already a dependency)
   - ~150 lines of code

3. **concept_coherence_monitor** - Simple ADWIN implementation
   - Works with existing tag structure
   - ~120 lines of code

**Estimated Effort**: 2-3 days for all three

---

### Phase 2: Medium Complexity (Next Iteration)

**Target**: Release 0.11.0

4. **temporal_wave_classifier** - Requires FFT/signal processing
   - Add scipy as dependency (lightweight)
   - Implement detrending and pattern classification
   - ~200 lines of code

5. **semantic_displacement** - Requires Procrustes implementation
   - Implement alignment caching for performance
   - ~250 lines of code

**Estimated Effort**: 3-4 days

---

### Phase 3: Research Extensions (Future)

**Target**: Release 0.12.0+

6. **link_semantics_drift** - Requires link tracking infrastructure
   - Add link creation timestamps to database schema
   - Implement context extraction
   - ~300 lines of code + schema migration

7. **seasonal_resonance** - Enhancement of existing geist
   - Multi-resolution FFT
   - Phase shift detection
   - ~200 lines of code

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

These 7 proposed geists leverage GeistFabrik's temporal embeddings architecture in ways grounded by rigorous academic research. They detect patterns invisible to single-session analysis:

1. **stability_anomaly**: When core concepts drift (conformity law)
2. **polysemy_evolution**: How bridge concepts evolve (innovation law)
3. **temporal_wave_classifier**: Bump/shift/cycle patterns
4. **semantic_displacement**: Long-term conceptual evolution
5. **concept_coherence_monitor**: Cluster drift detection
6. **link_semantics_drift**: Relationship meaning evolution
7. **seasonal_resonance**: Multi-scale periodicity

Each geist embodies GeistFabrik's "muses, not oracles" philosophy—surfacing provocative questions about intellectual evolution rather than prescriptive answers.

**Next Steps**:
1. Review and approve proposals
2. Implement Phase 1 geists (stability_anomaly, polysemy_evolution, concept_coherence_monitor)
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
