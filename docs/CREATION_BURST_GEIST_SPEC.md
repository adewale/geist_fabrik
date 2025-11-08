# Creation Burst Geist Specification

**Date**: 2025-11-08
**Status**: Proposed

## Overview

A geist that identifies days when you created multiple notes (5+) and asks what was special about those moments of creative productivity. This starts simple (metadata-only) but has a natural evolution path toward temporal embedding analysis.

---

## Phase 1: Basic Version (Metadata Only)

### Purpose
Surface "burst days" of creative activity and provoke reflection on what conditions led to productive note-taking sessions.

### Detection Method

```python
def suggest(vault: "VaultContext") -> List[Suggestion]:
    """Find days when 5+ notes were created and ask what was special."""

    # Query: Group notes by creation date, count per day
    cursor = vault.db.execute("""
        SELECT DATE(created) as creation_date,
               COUNT(*) as note_count,
               GROUP_CONCAT(title, '|') as note_titles
        FROM notes
        WHERE NOT path LIKE 'geist journal/%'
        GROUP BY DATE(created)
        HAVING note_count >= 5
        ORDER BY note_count DESC
    """)

    burst_days = cursor.fetchall()

    if not burst_days:
        return []

    # Randomly select one burst day
    day_date, count, titles_str = vault.sample(burst_days, k=1)[0]
    note_titles = titles_str.split('|')

    # Generate suggestion
    # ...
```

### Output Examples

**Basic provocation:**
```
On 2024-03-15, you created 7 notes: [[Systems Thinking]], [[Emergence]],
[[Feedback Loops]], [[Complexity]], [[Adaptation]], [[Resilience]], [[Networks]].
What was special about that day?
```

**With temporal context:**
```
On 2024-03-15, you created 8 notes in a single day—your most productive burst
in the last 6 months. What conditions created that flow state?
```

**Comparative framing:**
```
You created 6 notes on 2024-03-15, but haven't had a burst like that since.
What was different then?
```

### Implementation File
`src/geistfabrik/default_geists/code/creation_burst.py`

### Configuration
```yaml
geists:
  creation_burst:
    enabled: true
    min_notes: 5  # Minimum notes to qualify as a "burst"
    max_days_to_show: 3  # Sample from top N burst days
```

---

## Phase 2: Semantic Coherence Analysis (Temporal Embeddings)

### Enhanced Purpose
Not just "you created many notes," but "you created many notes **about the same thing**" vs. "you created many notes **about diverse topics**." This reveals whether bursts are focused deep dives or exploratory wandering.

### Detection Method

```python
def suggest(vault: "VaultContext") -> List[Suggestion]:
    """Analyze semantic coherence of notes created on burst days."""

    # Step 1: Find burst days (same as Phase 1)
    burst_days = _get_burst_days(vault, min_notes=5)

    if not burst_days:
        return []

    # Step 2: For each burst day, compute semantic coherence
    scored_bursts = []
    for day_date, note_titles in burst_days:
        notes = [vault.get_note_by_title(title) for title in note_titles]

        # Get current embeddings for those notes
        embeddings = [vault.embedding(note) for note in notes]

        # Compute pairwise similarity (coherence metric)
        coherence = _compute_cluster_coherence(embeddings)

        scored_bursts.append({
            'date': day_date,
            'notes': note_titles,
            'coherence': coherence,
            'count': len(note_titles)
        })

    # Step 3: Pick interesting pattern and generate provocation
    # ...
```

### Coherence Metric

```python
def _compute_cluster_coherence(embeddings: List[np.ndarray]) -> float:
    """
    Compute average pairwise cosine similarity.

    Returns:
        Float between 0 (scattered) and 1 (tightly clustered)
    """
    if len(embeddings) < 2:
        return 1.0

    similarities = []
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            similarities.append(sim)

    return np.mean(similarities)
```

### Output Examples

**Coherent burst (high similarity):**
```
On 2024-03-15, you created 7 notes that all cluster tightly around systems thinking
(coherence: 0.82). Was this a deep dive day? [[Systems Thinking]], [[Emergence]],
[[Feedback Loops]], [[Complexity]], [[Adaptation]], [[Resilience]], [[Networks]]
```

**Scattered burst (low similarity):**
```
On 2024-03-15, you created 8 notes about completely different topics (coherence: 0.31).
Exploratory wandering or intellectual chaos? [[Fermentation]], [[Git Workflows]],
[[Mortality]], [[Recursion]], [[Jazz]], [[Democracy]], [[Mushrooms]], [[Tide Pools]]
```

**Mixed pattern:**
```
On 2024-03-15, you created 6 notes, but they split into two clusters:
3 about systems thinking, 3 about creativity. Were you bridging two domains?
```

---

## Phase 3: Temporal Trajectory Analysis (Full Temporal Embeddings)

### Enhanced Purpose
Track what happened to burst-day notes over time. Did they:
- **Converge** (started diverse, became coherent as you connected them)?
- **Diverge** (started related, drifted apart as thinking evolved)?
- **Remain stable** (coherence unchanged over time)?

### Detection Method

```python
def suggest(vault: "VaultContext") -> List[Suggestion]:
    """Track how burst-day note clusters evolve over time."""

    # Step 1: Find burst days with session history
    burst_days = _get_burst_days_with_history(vault, min_notes=5, min_sessions=5)

    for day_date, note_paths in burst_days:
        # Step 2: Compute coherence trajectory across sessions
        sessions = _get_sessions_since_date(vault, day_date)

        coherence_trajectory = []
        for session_id in sessions:
            # Get embeddings from that session
            embeddings = []
            for path in note_paths:
                emb = _get_note_embedding_for_session(vault, path, session_id)
                if emb is not None:
                    embeddings.append(emb)

            if len(embeddings) >= 2:
                coherence = _compute_cluster_coherence(embeddings)
                coherence_trajectory.append(coherence)

        # Step 3: Classify trajectory pattern
        pattern = _classify_trajectory(coherence_trajectory)

        # Step 4: Generate provocation based on pattern
        # ...
```

### Trajectory Classification

```python
def _classify_trajectory(coherence_over_time: List[float]) -> str:
    """
    Classify how coherence changed over time.

    Returns: "convergent", "divergent", "stable", "volatile"
    """
    if len(coherence_over_time) < 3:
        return "stable"

    first_third = np.mean(coherence_over_time[:len(coherence_over_time)//3])
    last_third = np.mean(coherence_over_time[-len(coherence_over_time)//3:])

    delta = last_third - first_third
    volatility = np.std(coherence_over_time)

    if volatility > 0.15:
        return "volatile"
    elif delta > 0.15:
        return "convergent"
    elif delta < -0.15:
        return "divergent"
    else:
        return "stable"
```

### Output Examples

**Convergent pattern:**
```
On 2024-03-15, you created 7 diverse notes (coherence: 0.31), but over the next
6 months they've converged into a tight cluster (now: 0.78). You were exploring
the edges of an idea that's now crystallizing. [[Systems Thinking]], [[Emergence]],
[[Jazz]], [[Mycelium]], [[Democracy]], [[Ant Colonies]], [[Markets]]
```

**Divergent pattern:**
```
On 2024-03-15, you created 6 tightly related notes about systems thinking (coherence: 0.84),
but they've drifted apart over time (now: 0.43). Same topic, but your understanding
has fragmented—losing the thread or discovering nuance?
```

**Stable pattern:**
```
On 2024-03-15, you created 5 notes about complexity science that formed a tight cluster
and have stayed that way for 8 months. Foundational day? [[Emergence]], [[Feedback Loops]],
[[Self-Organization]], [[Phase Transitions]], [[Critical Points]]
```

**Volatile pattern:**
```
On 2024-03-15, you created 8 notes whose coherence keeps changing—sometimes clustered,
sometimes scattered. Are these notes still searching for their relationship to each other?
```

---

## Implementation Roadmap

### Phase 1: Basic (Next Release - 0.10.0)
**Effort**: 2-3 hours
**Dependencies**: None (uses existing database)
**Complexity**: Low

```python
# src/geistfabrik/default_geists/code/creation_burst.py
# ~80 lines of code
# Single SQL query + sampling + provocation generation
```

### Phase 2: Coherence (Release 0.11.0)
**Effort**: 4-5 hours
**Dependencies**: Current embeddings (no history needed)
**Complexity**: Medium

Adds:
- Coherence computation utility
- Clustering analysis
- Enhanced provocations based on coherence patterns

### Phase 3: Trajectory (Release 0.12.0+)
**Effort**: 6-8 hours
**Dependencies**: Session embeddings history
**Complexity**: High

Adds:
- Session-by-session coherence tracking
- Trajectory classification
- Temporal pattern detection
- Integration with other temporal geists

---

## Evolution Path: From Simple to Sophisticated

```
Phase 1: "You created 7 notes on this day. What was special?"
         ↓
Phase 2: "You created 7 tightly related notes. Was this a deep dive?"
         ↓
Phase 3: "You created 7 diverse notes that converged over 6 months.
         You were exploring edges of an idea that's now crystallizing."
```

Each phase asks a more sophisticated question, but **Phase 1 is already valuable** as a simple temporal provocation.

---

## Why This Matters

### Immediate Value (Phase 1)
- Surfaces forgotten productive days
- Provokes reflection on creative conditions
- Zero computation overhead
- Works from day 1 with any vault

### Medium-term Value (Phase 2)
- Distinguishes focused deep dives from exploratory wandering
- Reveals burst patterns (are your bursts coherent or chaotic?)
- Helps understand note-taking modes

### Long-term Value (Phase 3)
- Tracks intellectual trajectories from their inception
- Reveals which bursts were "productive" (led to coherence)
- Identifies bursts that were false starts (immediate divergence)
- Shows when scattered explorations crystallize into understanding

---

## Technical Notes

### SQL Query Optimization

```sql
-- Efficient query with date grouping
CREATE INDEX IF NOT EXISTS idx_notes_created_date ON notes(DATE(created));

-- Query runs in <1ms even with 10k notes
SELECT DATE(created) as creation_date,
       COUNT(*) as note_count
FROM notes
WHERE NOT path LIKE 'geist journal/%'
GROUP BY DATE(created)
HAVING note_count >= ?
ORDER BY note_count DESC;
```

### Configuration Options

```yaml
geists:
  creation_burst:
    enabled: true
    min_notes: 5           # Threshold for "burst"
    max_suggestions: 1     # How many burst days to show per session
    include_coherence: false  # Phase 2 feature flag
    include_trajectory: false # Phase 3 feature flag
```

### Testing Strategy

**Phase 1 Tests:**
```python
def test_creation_burst_basic():
    """Test burst detection with known data."""
    vault = create_test_vault()

    # Create burst day: 2024-03-15 with 6 notes
    burst_date = datetime(2024, 3, 15)
    for i in range(6):
        vault.add_note(f"Note {i}", created=burst_date)

    # Create normal day: 2024-03-16 with 2 notes
    normal_date = datetime(2024, 3, 16)
    for i in range(2):
        vault.add_note(f"Other {i}", created=normal_date)

    suggestions = creation_burst.suggest(vault.context())

    # Should detect the burst day
    assert len(suggestions) == 1
    assert "2024-03-15" in suggestions[0].text
    assert suggestions[0].notes == 6
```

**Phase 2 Tests:**
```python
def test_creation_burst_coherence():
    """Test coherence analysis of burst days."""
    # Create coherent burst (all about same topic)
    coherent_notes = create_related_notes(6, topic="systems")
    coherence = _compute_cluster_coherence([vault.embedding(n) for n in coherent_notes])
    assert coherence > 0.7  # High coherence

    # Create scattered burst (diverse topics)
    scattered_notes = create_diverse_notes(6)
    coherence = _compute_cluster_coherence([vault.embedding(n) for n in scattered_notes])
    assert coherence < 0.4  # Low coherence
```

**Phase 3 Tests:**
```python
def test_creation_burst_trajectory():
    """Test coherence trajectory classification."""
    # Convergent pattern: low → high
    convergent = [0.3, 0.4, 0.5, 0.65, 0.75, 0.8]
    assert _classify_trajectory(convergent) == "convergent"

    # Divergent pattern: high → low
    divergent = [0.8, 0.75, 0.6, 0.5, 0.4, 0.35]
    assert _classify_trajectory(divergent) == "divergent"
```

---

## Connection to Other Geists

### Complements
- **temporal_clustering**: Burst days might form distinct temporal clusters
- **session_drift**: Burst notes that drift significantly post-creation
- **seasonal_echo**: Are bursts seasonal? Do they happen at specific times?
- **crystallization**: Track if burst clusters sharpen or blur over time

### Extends
- **recent_focus**: Bursts are extreme cases of focused activity
- **on_this_day**: Anniversary bursts ("Every March you have a burst about X")

---

## Open Questions

1. **Threshold tuning**: Is 5 notes the right threshold? Should it be vault-size dependent?
   - Small vault (100 notes): 3+ might be a burst
   - Large vault (5000 notes): 10+ might be more meaningful

2. **Multi-day bursts**: Should we detect burst *periods* (3-day sprints)?

3. **Burst types**: Could classify bursts by link structure:
   - **Star burst**: All notes link to a central MOC
   - **Chain burst**: Notes link sequentially (narrative)
   - **Isolated burst**: Notes don't link to each other (diverse exploration)

4. **Negative space**: Should we also detect "drought periods" (no notes for 30+ days)?

---

## Success Metrics

**Phase 1** succeeds if:
- Surfaces forgotten productive days
- Provokes "oh yeah, I remember that!" responses
- Runs in <100ms

**Phase 2** succeeds if:
- Distinguishes coherent vs. scattered bursts accurately
- Reveals patterns in note-taking modes
- Adds <500ms to execution time

**Phase 3** succeeds if:
- Tracks meaningful intellectual trajectories
- Identifies bursts that led to lasting insights
- Demonstrates value of temporal embedding history

---

## Next Steps

1. **Implement Phase 1** in next development session
2. Add unit tests with synthetic burst data
3. Test on real vaults to tune threshold
4. Document in GEIST_CATALOG.md
5. Consider Phase 2 after temporal embeddings are stable
