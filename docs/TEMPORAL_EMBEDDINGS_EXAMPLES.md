# Temporal Embeddings: Examples & Value Proposition

**Purpose**: Demonstrate the unique value of temporal embeddings through concrete examples
**Audience**: Users, contributors, anyone evaluating GeistFabrik

---

## What Are Temporal Embeddings?

**Traditional Embeddings** (like most note-taking apps):
- Capture **what** a note says
- Static snapshot of semantic meaning
- Computed once, reused forever

**Temporal Embeddings** (GeistFabrik's innovation):
- Capture **what** a note says **and when**
- Dynamic: recomputed each session
- Track how your **understanding** evolves over time
- Enable entirely new classes of insights

---

## The Three Dimensions

### 1. Semantic Embeddings (384 dimensions)

**What**: Meaning derived from note content via sentence-transformers

**Example**:
```
Note: "Machine learning uses neural networks for pattern recognition"

Semantic embedding: [0.23, -0.45, 0.67, ...]  (384 numbers)

Similar notes:
- "Deep learning architectures" (similarity: 0.85)
- "AI and pattern matching" (similarity: 0.78)
- "Cooking recipes" (similarity: 0.12)
```

**Value**: Find semantically related notes, even without explicit links

---

### 2. Temporal Features: Note Age (1 dimension)

**What**: How old the note is at the time of the session

**Computation**:
```
Note created: 2023-06-15
Session date: 2025-01-15
Age: 579 days → normalized to 0.579
```

**Why It Matters**:
- Recent notes cluster separately from old notes
- Enables "fresh thinking vs established ideas" distinction
- Tracks intellectual evolution over years

---

### 3. Temporal Features: Seasonal Cycles (2 dimensions)

**What**: When the note was written + when you're reading it

**Computation**:
```
Note written: June 15 (day 166) → sin((166/365)*2π) = 0.978 (summer)
Session date: Jan 15 (day 15)  → sin((15/365)*2π) = 0.258 (winter)
```

**Why It Matters**:
- Captures annual rhythms in thinking
- "Winter thinking" vs "summer thinking"
- Reveals unconscious seasonal patterns

---

## Compelling Examples

### Example 1: Session Drift

**Scenario**: Your understanding of "emergence" evolves over time

**March 2024 Session**:
```
Note: "Emergence in complex systems"
Embedding (simplified): [0.8 mechanism, 0.2 relationality, 0.1 philosophy]

Similar notes:
1. "Reductionism and causality" (0.82)
2. "Systems thinking" (0.75)
3. "Causal mechanisms" (0.70)
```

**September 2024 Session** (6 months later, **same note, unchanged content**):
```
Note: "Emergence in complex systems"  [CONTENT IDENTICAL]
Embedding (simplified): [0.3 mechanism, 0.7 relationality, 0.4 philosophy]

Similar notes:
1. "Relational ontology" (0.81)
2. "Interconnection and meaning" (0.78)
3. "Beyond reductionism" (0.73)
```

**Geist Suggestion**:
> **Session Drift Detected**: Your understanding of [[Emergence in complex systems]] has shifted significantly since March. It now clusters with [[Relational ontology]] instead of [[Causal mechanisms]]. Your thinking has migrated from mechanistic to relational frameworks. What changed?

**Value**: Reveals **intellectual evolution** even when notes don't change. Tracks shifts in how you interpret concepts.

---

### Example 2: Hermeneutic Instability

**Scenario**: A note keeps re-embedding differently each session

**Sessions**:
```
2024-06-01: Embedding A → clusters with "politics"
2024-07-01: Embedding B → clusters with "philosophy"
2024-08-01: Embedding C → clusters with "personal growth"
2024-09-01: Embedding D → clusters with "systems thinking"
```

**Variance**: High (embedding changes significantly each session)

**Geist Suggestion**:
> **Hermeneutic Instability**: [[Democracy and emergence]] has been interpreted differently in each of your last 4 sessions—high embedding variance detected. This note seems to touch on unsettled ideas that shift meaning based on context. Perhaps it's connecting multiple evolving threads?

**Value**: Identifies notes at **intellectual crossroads**. These are often the most generative—ideas that haven't crystallized yet.

---

### Example 3: Convergent Evolution

**Scenario**: Two unlinked notes gradually develop toward each other

**Jan 2024**:
```
Note A: "Permaculture design principles"
Note B: "Organizational resilience"
Similarity: 0.25 (semantically distant)
```

**Apr 2024**:
```
Similarity: 0.42 (moving closer)
```

**Jul 2024**:
```
Similarity: 0.61 (clearly related now)
```

**Oct 2024**:
```
Similarity: 0.78 (very similar)
```

**Geist Suggestion**:
> **Convergent Evolution**: [[Permaculture design principles]] and [[Organizational resilience]] have been converging semantically for 9 months. They're now 78% similar despite having no links between them. Time to connect them? They seem to be developing toward the same idea about adaptive systems.

**Value**: Suggests connections **at the moment of convergence**. Catches parallel thinking you're developing unconsciously.

---

### Example 4: Temporal Clustering

**Scenario**: Your Q2 2024 notes form a distinct semantic cluster

**Analysis**:
```
Q1 2024 notes: Cluster around "productivity, systems, optimization"
Q2 2024 notes: Cluster around "meaning, philosophy, relationships"
Q3 2024 notes: Cluster around "creativity, play, experimentation"
Q4 2024 notes: Return to "systems, structure, planning"
```

**Geist Suggestion**:
> **Temporal Clustering**: Your Q2-2024 notes form a distinct semantic cluster separate from Q1 and Q3. That quarter was your "meaning-making season"—you wrote almost exclusively about philosophy and relationships. This pattern seems to recur annually: Q2 is when you question systems and explore meaning.

**Value**: Reveals **intellectual seasons**. Helps you understand your natural rhythms and creative cycles.

---

### Example 5: Anachronism Detection

**Scenario**: A recent note feels "out of time"

**Recent Note** (2025-01-10):
```
Title: "Building resilient systems through redundancy"
Content: [discusses backup systems, fail-safes, defensive design]

Embedding similarity to time periods:
- 2022 notes: 0.81 (HIGH)
- 2023 notes: 0.42
- 2024 notes: 0.18
- Recent 2025 notes: 0.15 (LOW)
```

**Geist Suggestion**:
> **Anachronism Detected**: Your recent note [[Building resilient systems]] semantically resembles your 2022 thinking (0.81 similarity) more than your current 2025 thinking (0.15). You're circling back to defensive design after 3 years of exploring emergent/organic approaches. Intentional return or unnoticed regression?

**Value**: Highlights when you're **revisiting old ideas**. Sometimes this is valuable (integrating past insights), sometimes it's a warning sign (stuck in old patterns).

---

### Example 6: Seasonal Patterns

**Scenario**: Writing patterns correlate with seasons

**Analysis**:
```
December sessions (over 3 years):
- "mortality" appears in similar notes: winter 2022, 2023, 2024
- Cluster around "finitude", "meaning", "legacy"

June sessions:
- "growth" and "possibility" dominate
- Cluster around "expansion", "experimentation"
```

**Geist Suggestion**:
> **Seasonal Pattern**: You consistently write about [[mortality]] and [[finitude]] in December sessions (detected across 3 years). Your winter thinking tends toward reflection and meaning-making. In contrast, your June notes emphasize growth and possibility. This appears to be an unconscious annual rhythm in your intellectual life.

**Value**: Reveals **cyclical patterns** in thinking. Helps you understand your cognitive seasons and work with them intentionally.

---

### Example 7: Divergent Evolution

**Scenario**: Two linked notes are growing apart

**Jan 2023** (when you linked them):
```
Note A: "Effective Altruism"
Note B: "Utilitarian Ethics"
Similarity: 0.88 (very similar)
Link: [[Effective Altruism]] ← linked to → [[Utilitarian Ethics]]
```

**Jan 2025** (2 years later):
```
Similarity: 0.42 (significantly diverged)

Note A now clusters with: "systemic change", "power dynamics"
Note B still clusters with: "moral philosophy", "consequentialism"
```

**Geist Suggestion**:
> **Divergent Evolution**: [[Effective Altruism]] and [[Utilitarian Ethics]] were 88% similar when you linked them in 2023. They've since diverged to 42% similarity. Your EA thinking has shifted toward power and systems, while your ethics notes remain philosophical. Do these notes still belong together, or has your thinking outgrown this connection?

**Value**: Questions **outdated links**. Your vault should evolve as your thinking does—not all old connections still make sense.

---

## Geist Examples Enabled by Temporal Embeddings

### 1. Session Drift (Core)

```python
def session_drift(vault: VaultContext) -> List[Suggestion]:
    """Find notes whose meaning has shifted between sessions."""
    suggestions = []

    for note in vault.notes():
        # Get embeddings from last 2 sessions
        embeddings = vault.get_embedding_history(note.path, limit=2)

        if len(embeddings) < 2:
            continue

        # Compare embeddings
        similarity = cosine_similarity(embeddings[0], embeddings[1])

        # Low similarity = high drift
        if similarity < 0.7:  # 30% drift threshold
            suggestions.append(Suggestion(
                text=f"Your understanding of [[{note.title}]] shifted "
                     f"significantly since last session (drift: {1-similarity:.2%}). "
                     f"What changed in your thinking?",
                notes=[note.title],
                geist_id="session_drift"
            ))

    return suggestions
```

---

### 2. Convergent Evolution

```python
def convergent_evolution(vault: VaultContext) -> List[Suggestion]:
    """Find unlinked notes developing toward each other."""
    suggestions = []

    # Get embedding history for all notes
    for note_a in vault.notes():
        for note_b in vault.notes():
            if note_a.path >= note_b.path:  # Avoid duplicates
                continue

            if vault.links_between(note_a, note_b):  # Skip if already linked
                continue

            # Get similarity over last 6 sessions
            trajectory = []
            for session_id in range(-6, 0):  # Last 6 sessions
                emb_a = vault.get_embedding_at_session(note_a.path, session_id)
                emb_b = vault.get_embedding_at_session(note_b.path, session_id)
                if emb_a is not None and emb_b is not None:
                    sim = cosine_similarity(emb_a, emb_b)
                    trajectory.append(sim)

            if len(trajectory) < 3:
                continue

            # Check if similarity is increasing
            if trajectory[-1] > 0.7 and trajectory[-1] > trajectory[0] + 0.2:
                suggestions.append(Suggestion(
                    text=f"[[{note_a.title}]] and [[{note_b.title}]] have been "
                         f"converging for {len(trajectory)} sessions "
                         f"({trajectory[0]:.0%} → {trajectory[-1]:.0%} similar). "
                         f"Time to link them?",
                    notes=[note_a.title, note_b.title],
                    geist_id="convergent_evolution"
                ))

    return vault.sample(suggestions, k=5)  # Sample to avoid overwhelm
```

---

### 3. Temporal Cluster Detective

```python
def temporal_clusters(vault: VaultContext) -> List[Suggestion]:
    """Identify notes that cluster by time period."""
    suggestions = []

    # Group notes by quarter
    quarters = {}
    for note in vault.notes():
        quarter = f"{note.created.year}-Q{(note.created.month-1)//3 + 1}"
        if quarter not in quarters:
            quarters[quarter] = []
        quarters[quarter].append(note)

    # For each quarter, find what's semantically distinct
    for quarter, notes in quarters.items():
        if len(notes) < 5:
            continue

        # Get average embedding for this quarter
        quarter_emb = average_embedding([vault.get_embedding(n.path) for n in notes])

        # Compare to other quarters
        other_quarters = [q for q in quarters.keys() if q != quarter]
        other_emb = average_embedding([
            vault.get_embedding(n.path)
            for q in other_quarters
            for n in quarters[q]
        ])

        similarity = cosine_similarity(quarter_emb, other_emb)

        if similarity < 0.6:  # Distinct cluster
            # Find dominant themes
            sample_notes = vault.sample(notes, k=3)
            suggestions.append(Suggestion(
                text=f"Your {quarter} notes form a distinct semantic cluster "
                     f"(only {similarity:.0%} similar to other periods). "
                     f"That quarter focused on: " +
                     ", ".join([f"[[{n.title}]]" for n in sample_notes]),
                notes=[n.title for n in sample_notes],
                geist_id="temporal_clusters"
            ))

    return suggestions
```

---

### 4. Seasonal Pattern Detector

```python
def seasonal_patterns(vault: VaultContext) -> List[Suggestion]:
    """Find concepts that recur seasonally."""
    suggestions = []

    # Get all session dates
    sessions = vault.get_all_sessions()

    # Group by month
    month_notes = {i: [] for i in range(1, 13)}
    for session in sessions:
        month = session.date.month
        notes = vault.get_notes_from_session(session.id)
        month_notes[month].extend(notes)

    # For each month, find recurring themes
    for month, notes in month_notes.items():
        if len(notes) < 10:  # Need enough data
            continue

        # Find most common note topics (by clustering)
        embeddings = [vault.get_embedding(n.path) for n in notes]
        centroid = average_embedding(embeddings)

        # Find notes closest to this month's centroid
        representative = vault.find_similar(centroid, k=3)

        # Check if this pattern repeats across years
        years_with_pattern = count_years_matching_pattern(
            vault, month, representative
        )

        if years_with_pattern >= 2:
            month_name = calendar.month_name[month]
            suggestions.append(Suggestion(
                text=f"**{month_name} Pattern** (detected across {years_with_pattern} years): "
                     f"You consistently explore {', '.join([f'[[{n.title}]]' for n in representative])} "
                     f"in {month_name}. This appears to be a seasonal rhythm in your thinking.",
                notes=[n.title for n in representative],
                geist_id="seasonal_patterns"
            ))

    return suggestions
```

---

## Why This Matters

### For Individual Users

1. **Self-Knowledge**: Understand your intellectual rhythms and patterns
2. **Serendipity**: Discover connections developing unconsciously
3. **Evolution Tracking**: See how your thinking changes over time
4. **Pattern Breaking**: Notice when you're stuck in old thinking
5. **Timing**: Get suggestions at the right moment (convergence, drift)

### For Knowledge Work

1. **Dynamic PKM**: Your vault evolves as you do
2. **Temporal Context**: Notes exist in time, not just semantic space
3. **Emergence**: Ideas develop through repeated encounters
4. **Feedback Loops**: System adapts to how you actually think
5. **Divergent Tool**: Generates questions, not answers

### Competitive Advantage

**Other note-taking apps**:
- Static embeddings
- "Related notes" that never change
- No temporal awareness

**GeistFabrik**:
- Dynamic, session-based embeddings
- Tracks intellectual evolution
- Temporal patterns and rhythms
- Detects convergence and drift
- Questions old connections

---

## Technical Enablers

**Why This Wasn't Possible Before**:
1. **Storage**: Storing embeddings per session was prohibitive
   - **Now**: SQLite handles it easily (~30MB for 1000 notes × 20 sessions)

2. **Computation**: Re-embedding was too slow
   - **Now**: sentence-transformers + caching makes it practical

3. **Vector Search**: Comparing across sessions required specialized DBs
   - **Now**: sqlite-vec extension provides vector similarity

4. **Local-First**: Tracking was privacy-invasive
   - **Now**: All computation local, no telemetry

**GeistFabrik makes it practical**:
- Incremental sync (only reprocess changed notes)
- Semantic embedding cache (90% cache hit rate)
- Efficient batch processing (15-20x speedup)
- SQLite storage (portable, fast, simple)

---

## Implementation Notes

### Storage Cost

```
Per note per session:
- 387 dimensions × 4 bytes (float32) = 1,548 bytes (~1.5KB)

For 1000 notes over 20 sessions:
- 1000 × 20 × 1.5KB = ~30MB

For 10,000 notes over 100 sessions:
- 10,000 × 100 × 1.5KB = ~1.5GB
```

**Mitigation**:
- Prune old sessions (keep first, last N, significant changes)
- Compress embeddings (quantize float32 to int8)
- Archive to cold storage

### Computation Cost

```
Fresh embedding computation:
- 1000 notes × 0.1s = ~100s per session
- Acceptable for "ritual invocation" pattern
- Cache reduces repeat computation to ~10s
```

### Query Performance

```
Similarity search across sessions:
- 1000 notes: <50ms (linear scan)
- 10,000 notes: ~500ms (linear scan)
- With ANN index (HNSW): <10ms for any size
```

---

## Example Session Output

```markdown
# GeistFabrik Session – 2025-01-15

## session_drift ^g20250115-001
Your understanding of [[Emergence in complex systems]] has shifted significantly since December (drift: 37%). It now clusters with [[Relational ontology]] instead of [[Causal mechanisms]]. Your thinking migrated from mechanistic to relational frameworks. What changed?

## convergent_evolution ^g20250115-002
[[Permaculture principles]] and [[Organizational resilience]] have been converging for 9 months (25% → 78% similar). They're developing toward the same idea about adaptive systems. Time to connect them?

## seasonal_pattern ^g20250115-003
**December Pattern** (detected across 3 years): You consistently explore [[Mortality]], [[Meaning]], and [[Legacy]] in December. This appears to be a seasonal rhythm—winter thinking tends toward reflection and finitude.

## anachronism ^g20250115-004
Your recent note [[Building resilient systems]] resembles your 2022 thinking (81% similar) more than your current 2025 thinking (15%). You're circling back to defensive design after 3 years of emergent approaches. Intentional or unconscious?

## divergent_evolution ^g20250115-005
[[Effective Altruism]] and [[Utilitarian Ethics]] were 88% similar when you linked them in 2023. They've since diverged to 42% similarity. Your EA thinking shifted toward systems/power while ethics remained philosophical. Does this link still make sense?
```

---

## Conclusion

**Temporal embeddings transform PKM from static archive to dynamic companion**:

- Not just "what do my notes say" but "how is my thinking evolving"
- Not just "related notes" but "notes converging over time"
- Not just "connections" but "connections that should be questioned"
- Not just "themes" but "seasonal rhythms and patterns"

**The vault becomes a mirror that shows you how you change**.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-21
**See Also**:
- `specs/geistfabrik_spec.md` - Technical specification
- `specs/EMBEDDINGS_SPEC.md` - Implementation details
- `docs/LESSONS_LEARNED.md` - Project retrospective
