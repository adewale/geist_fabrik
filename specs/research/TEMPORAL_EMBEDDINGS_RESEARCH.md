# Temporal Embeddings in GeistFabrik: Approach, Implementation, and Academic Context

**Document Type**: Research Analysis
**Version**: 1.0
**Date**: 2025-11-06
**Purpose**: Explain temporal embeddings approach with academic grounding

---

## Core Approach

GeistFabrik implements a **session-based temporal embedding system** that fundamentally reconceptualizes how personal knowledge management systems represent notes. Rather than treating embeddings as static snapshots of semantic meaning, GeistFabrik computes fresh embeddings at each session, creating a **temporal trace of evolving understanding**.

### Technical Architecture

Each embedding consists of **387 dimensions**:

**Semantic Component (384 dimensions)** — `src/geistfabrik/embeddings.py:114-124`
- Generated using the `all-MiniLM-L6-v2` sentence-transformer model
- L2-normalised to unit length
- Captures semantic meaning via BERT-based architecture
- Cached based on content hash (SHA-256) for performance

**Temporal Component (3 dimensions)** — `src/geistfabrik/embeddings.py:150-175`
1. **Note Age**: `(session_date - note_created).days / 365.0`
   - Linear normalisation to years
   - Distinguishes fresh vs. established thinking

2. **Creation Season**: `sin(2π × creation_day_of_year / 365)`
   - Cyclical encoding capturing when note was written
   - Range: [-1, +1] representing seasonal position

3. **Session Season**: `sin(2π × session_day_of_year / 365)`
   - Cyclical encoding capturing when session occurs
   - Enables detection of seasonal reading patterns

The key architectural insight is the **two-tier caching strategy** — `src/geistfabrik/embeddings.py:364-460`:
- Semantic embeddings cached indefinitely (content-addressable)
- Temporal features recomputed each session
- Combined embeddings stored per session in `session_embeddings` table

This achieves ~90% cache hit rates while maintaining temporal sensitivity.

## Academic Grounding

### 1. Temporal Knowledge Graphs

GeistFabrik's approach aligns with recent developments in **Temporal Knowledge Graph Embedding (TKGE)** research. The 2024 survey by Cheng et al. in *Knowledge-Based Systems* notes that "a large amount of structured knowledge exists only within a specific period" and emphasizes that **time sensitivity varies across semantic relationships**.

Recent TKGE models address two key challenges that GeistFabrik also tackles:

**Challenge 1: Distinguishing Temporal States**
The TLT-KGE (Timeline-Traced Knowledge Graph Embedding) approach notes that "current models have difficulty distinguishing representations of the same entity or relation at different timestamps." GeistFabrik addresses this by storing separate embeddings per session in the `session_embeddings` table, creating an explicit temporal index.

**Challenge 2: Irregular Intervals**
The ODETKGE model uses neural ODEs to "track TKG dynamics with irregular intervals." GeistFabrik achieves this more simply through on-demand session computation — embeddings are computed whenever invoked, naturally handling irregular intervals without specialised models.

### 2. Semantic Drift and Concept Evolution

GeistFabrik operationalizes **semantic drift** — the phenomenon where concepts shift meaning over time. Research on "Dynamic Word Embeddings for Evolving Semantic Discovery" (Yao et al., WSDM 2018) demonstrates that "word evolution refers to the changing meanings and associations of words throughout time."

The `session_drift` geist (`src/geistfabrik/default_geists/code/session_drift.py:49-57`) implements this by computing:

```python
drift = 1.0 - cosine_similarity(current_embedding, previous_embedding)
```

When drift exceeds 0.15 (15% change), the system suggests interpretive shift has occurred. This threshold is empirically determined but reflects findings from knowledge graph research that "embeddings exploited in supervised stream learning can learn prediction models robust to concept drifts."

### 3. Hermeneutic Theory and Interpretive Variance

The `hermeneutic_instability` geist (`src/geistfabrik/default_geists/code/hermeneutic_instability.py`) draws implicitly on **hermeneutic circle** theory, though the implementation is computational rather than philosophical.

**Hermeneutic Circle**: Friedrich Schleiermacher's interpretive framework posits that "understanding involved repeated circular movements between the parts and the whole." Heidegger later reconceptualized this: "understanding is not merely a cognitive process but a fundamental aspect of how we exist in the world."

GeistFabrik computationalizes this insight by measuring **interpretive variance across sessions**:

```python
embeddings_array = np.array(embeddings)  # Multiple sessions
mean_embedding = np.mean(embeddings_array, axis=0)
distances = [euclidean(emb, mean_embedding) for emb in embeddings_array]
instability = np.mean(distances)
```

High instability (>0.2) indicates a note that "means different things in different contexts" — precisely the hermeneutic insight that meaning emerges from the interaction between text and interpreter's situated understanding.

### 4. Extended Cognition and Personal Knowledge Management

GeistFabrik embodies principles from **extended cognition** (Clark & Chalmers, 1998) and recent PKM research. A 2025 ACM paper on "From Personal Knowledge Management to the Second Brain to the Personal AI Companion" traces the evolution from static archives to dynamic thinking partners.

Traditional PKM systems treat notes as **static artifacts**. GeistFabrik treats them as **dynamic objects whose meaning evolves** — the vault becomes what Gordon Brander calls a "muse, not oracle," asking different questions as your thinking evolves.

The temporal embeddings enable the system to track:
- **Convergent Evolution**: Notes developing toward each other (unlinked)
- **Divergent Evolution**: Linked notes growing apart
- **Anachronism Detection**: Recent notes resembling old thinking
- **Seasonal Rhythms**: Annual patterns in intellectual focus

## Novel Contributions

### 1. Session-Scoped Temporal Features

Unlike TKGE approaches that embed time as a learned representation, GeistFabrik uses **explicit temporal features** (age, seasons). This makes the model **interpretable** — you can understand *why* similarity changed (note aged, seasonal mismatch) rather than having temporal effects buried in learned weights.

### 2. Hybrid Caching Architecture

The separation of semantic (cached) and temporal (recomputed) components is novel. Most dynamic embedding approaches recompute everything or cache everything. GeistFabrik's hybrid approach achieves:
- **Performance**: 90% cache hits, ~10s recomputation for 1000 notes
- **Temporal sensitivity**: Every session has fresh temporal context
- **Storage efficiency**: Only 387 dims × 4 bytes × N notes × M sessions

### 3. Hermeneutic Computing

The `hermeneutic_instability` geist represents a rare computational implementation of interpretive theory. While sentiment analysis and topic modelling track *content* changes, GeistFabrik tracks *understanding* changes — detecting when your reading of an unchanged note shifts.

This is philosophically significant: it acknowledges that meaning is **co-created between text and reader**, not inherent to text alone.

### 4. Temporal Pattern Discovery

The `temporal_clustering` geist (`src/geistfabrik/default_geists/code/temporal_clustering.py`) discovers **intellectual seasons** — quarterly or monthly patterns in thinking. This connects to:
- **Chronobiology**: Seasonal affective patterns influence cognition
- **Self-knowledge**: Revealing unconscious rhythms enables metacognition
- **PKM Design**: Systems should adapt to user's natural cycles, not impose artificial regularity

## Implications and Future Directions

### For PKM Systems

**Implication 1: Static Embeddings Are Insufficient**
Traditional "related notes" features using static embeddings miss temporal dynamics. GeistFabrik demonstrates that **when** you read matters as much as **what** you read.

**Implication 2: Personal AI Requires Temporal Context**
As personal AI assistants integrate with knowledge bases, they need temporal awareness. A note about "productivity systems" written in 2020 (optimisation-focused) may have different implications in 2025 (meaning-focused) even with identical content.

**Implication 3: Privacy-Preserving Personalization**
GeistFabrik's local-first architecture (all embeddings computed locally, stored in SQLite) demonstrates that sophisticated personalization doesn't require cloud telemetry. The session-based approach creates rich temporal profiles entirely offline.

### For Research Directions

**Research Question 1: Optimal Temporal Feature Design**
Current features (age, seasons) are simple. Could circadian rhythms, weekly patterns, or life events (moves, jobs) improve temporal modelling?

**Research Question 2: Predictive Temporal Embeddings**
Could the system predict *future* interpretive drift? If note similarity is increasing over 6 sessions, will they converge?

**Research Question 3: Collaborative Temporal Knowledge**
How do temporal embeddings extend to shared knowledge bases? Do different readers show divergent interpretive trajectories?

**Research Question 4: Temporal Attention Mechanisms**
Rather than fixed weights (semantic: 99.2%, temporal: 0.8%), could attention mechanisms learn when temporal context matters more?

### Philosophical Implications

**Implication 1: Computational Hermeneutics**
GeistFabrik suggests that interpretive theory can be operationalized computationally. The "hermeneutic circle" becomes a measurable variance across embedding trajectories.

**Implication 2: Dynamic Identity**
If notes' meanings evolve, and notes constitute thinking, then the system models **cognitive change** not just information storage. The vault becomes a mirror showing you how you've changed.

**Implication 3: Time as First-Class Dimension**
Most digital systems treat time as metadata (created_at, modified_at). GeistFabrik treats time as **constitutive of meaning** — notes don't *have* timestamps, they *exist in time*.

## Existing Temporal Geists Analysis

### Currently Implemented (3 geists)

1. **session_drift** — Compares embeddings between consecutive sessions
2. **hermeneutic_instability** — Measures variance across multiple sessions
3. **temporal_clustering** — Identifies time-period-based semantic clusters

### Coverage Assessment

**Strengths**:
- Drift detection (interpretive change)
- Instability detection (unsettled meaning)
- Temporal clustering (intellectual seasons)

**Gaps**:
- No convergent evolution tracking
- No divergent evolution detection
- Limited seasonal pattern discovery
- No anachronism detection
- No temporal trajectory analysis (trends over time)
- No session-to-session momentum tracking

## Potential Advanced Temporal Geists

### 1. Convergent Evolution Detector

**Concept**: Find pairs of unlinked notes whose similarity has been increasing over multiple sessions.

**Implementation Sketch**:
```python
def convergent_evolution(vault: VaultContext) -> List[Suggestion]:
    """Detect notes converging toward each other over time."""
    # Get last 6 sessions
    sessions = get_recent_sessions(vault, 6)

    # For each note pair (without existing link)
    for note_a, note_b in unlinked_pairs(vault):
        trajectory = []
        for session in sessions:
            sim = compute_similarity_at_session(note_a, note_b, session)
            trajectory.append(sim)

        # Detect positive trend
        if is_converging(trajectory, min_increase=0.2, final_threshold=0.7):
            suggest_link(note_a, note_b, trajectory)
```

**Value**: Catches parallel thinking developing unconsciously.

### 2. Divergent Evolution Detector

**Concept**: Find linked notes whose similarity has been decreasing — outdated connections.

**Implementation Sketch**:
```python
def divergent_evolution(vault: VaultContext) -> List[Suggestion]:
    """Detect linked notes growing apart."""
    sessions = get_recent_sessions(vault, 6)

    for link in vault.all_links():
        trajectory = similarity_trajectory(link.source, link.target, sessions)

        if is_diverging(trajectory, min_decrease=0.3):
            suggest_review(link, trajectory)
```

**Value**: Questions old connections that may no longer fit your thinking.

### 3. Seasonal Resonance Detector

**Concept**: Find notes that become more relevant during specific seasons, detected across multiple years.

**Implementation Sketch**:
```python
def seasonal_resonance(vault: VaultContext) -> List[Suggestion]:
    """Detect notes with seasonal relevance patterns."""
    # Group sessions by month across years
    monthly_sessions = group_by_month(vault.all_sessions())

    for note in vault.notes():
        # For each month, compute average similarity to that month's notes
        monthly_affinity = {}
        for month, sessions in monthly_sessions.items():
            avg_sim = compute_monthly_affinity(note, sessions)
            monthly_affinity[month] = avg_sim

        # Detect strong seasonal pattern (peak month > others)
        if has_seasonal_pattern(monthly_affinity, min_difference=0.15):
            peak_month = max_month(monthly_affinity)
            suggest_seasonal_note(note, peak_month)
```

**Value**: "Your December notes consistently explore mortality/meaning — this appears to be your 'winter contemplation' period."

### 4. Anachronism Detector

**Concept**: Recent notes that semantically resemble thinking from years ago more than recent thinking.

**Implementation Sketch**:
```python
def anachronism_detector(vault: VaultContext) -> List[Suggestion]:
    """Find recent notes that feel 'out of time'."""
    recent_notes = vault.recent_notes(k=20, max_age_days=30)

    for note in recent_notes:
        current_emb = vault.get_embedding(note.path)

        # Compare to different time periods
        similarity_by_period = {}
        for year in range(current_year - 3, current_year + 1):
            period_notes = notes_from_year(vault, year)
            avg_sim = average_similarity(current_emb, period_notes)
            similarity_by_period[year] = avg_sim

        # Anachronism: higher similarity to old period than recent
        if similarity_by_period[current_year - 2] > similarity_by_period[current_year]:
            suggest_anachronism(note, similarity_by_period)
```

**Value**: "This recent note resembles your 2022 thinking (0.81) more than 2025 (0.15) — intentional return or stuck pattern?"

### 5. Velocity Tracker

**Concept**: Track rate of semantic change — which notes are evolving rapidly vs. stable?

**Implementation Sketch**:
```python
def semantic_velocity(vault: VaultContext) -> List[Suggestion]:
    """Measure how fast notes are changing in embedding space."""
    sessions = get_recent_sessions(vault, 10)

    for note in vault.notes():
        embeddings = [get_embedding(note, s) for s in sessions]

        # Compute velocity (distance travelled per session)
        velocity = compute_velocity(embeddings)

        if velocity > threshold_high:
            suggest_rapid_evolution(note, velocity)
        elif velocity < threshold_low and note.is_important():
            suggest_stagnation(note, velocity)
```

**Value**: "[[Emergence]] has high semantic velocity — your understanding is evolving rapidly" vs "[[Project Management]] has been stable for 12 sessions — established framework?"

### 6. Temporal Bridge Finder

**Concept**: Find notes that bridge different temporal clusters — concepts that connect past and present thinking.

**Implementation Sketch**:
```python
def temporal_bridge_finder(vault: VaultContext) -> List[Suggestion]:
    """Find notes that connect different time periods."""
    old_notes = vault.old_notes(k=50, min_age_days=365)
    recent_notes = vault.recent_notes(k=50, max_age_days=90)

    # Find notes that are similar to BOTH periods
    for candidate in vault.notes():
        sim_to_old = average_similarity(candidate, old_notes)
        sim_to_recent = average_similarity(candidate, recent_notes)

        # Bridge: high similarity to both distinct periods
        if sim_to_old > 0.65 and sim_to_recent > 0.65:
            suggest_bridge(candidate, sim_to_old, sim_to_recent)
```

**Value**: "[[Systems thinking]] bridges your 2022 notes on complexity and 2025 notes on emergence — it's a conceptual through-line."

### 7. Session Momentum Detector

**Concept**: Detect when consecutive sessions show systematic shift in a particular direction.

**Implementation Sketch**:
```python
def session_momentum(vault: VaultContext) -> List[Suggestion]:
    """Detect systematic directional shift across sessions."""
    sessions = get_recent_sessions(vault, 6)

    # Compute centroid (average embedding) for each session
    centroids = [compute_session_centroid(vault, s) for s in sessions]

    # Measure movement between centroids
    momentum_vector = compute_momentum(centroids)

    # Find notes most aligned with momentum direction
    aligned_notes = find_aligned_notes(vault, momentum_vector)

    if has_strong_momentum(momentum_vector):
        suggest_momentum(aligned_notes, direction_description(momentum_vector))
```

**Value**: "Your last 6 sessions show momentum toward philosophical/relational thinking (0.7 shift from mechanistic). Notes driving this: [[Relationality]], [[Emergence as ontology]]."

### 8. Interpretive Rhythm Tracker

**Concept**: Some notes might show cyclical patterns in how they're interpreted — regular oscillation.

**Implementation Sketch**:
```python
def interpretive_rhythm(vault: VaultContext) -> List[Suggestion]:
    """Detect cyclical patterns in how notes are interpreted."""
    sessions = vault.all_sessions()  # Need longer history

    for note in vault.notes():
        embeddings = [get_embedding(note, s) for s in sessions]

        # Detect periodicity using FFT or autocorrelation
        period, strength = detect_periodicity(embeddings)

        if strength > threshold and period > 0:
            # E.g., period=12 sessions ≈ monthly cycle
            suggest_rhythmic_interpretation(note, period, strength)
```

**Value**: "[[Productivity systems]] shows interpretive rhythm — you reconsider it every ~3 months, alternating between enthusiasm and skepticism."

## Conclusion

GeistFabrik's temporal embeddings represent a synthesis of:
- **TKGE research** (temporal knowledge graphs)
- **NLP advances** (sentence transformers, efficient embedding)
- **Hermeneutic theory** (interpretive variance, meaning co-creation)
- **PKM principles** (local-first, user agency, divergent tools)

The technical achievement is modest — 3 additional dimensions, session-based storage. The conceptual achievement is significant: demonstrating that **knowledge management systems can track understanding, not just information**.

As Heidegger reconceptualized the hermeneutic circle as fundamental to existence, GeistFabrik reconceptualizes embeddings as fundamental to *evolving existence* — your notes change because *you* change, and tracking that evolution is the point.

---

## References

**Academic Literature**:
- Cheng, K., et al. (2024). "A survey on temporal knowledge graph embedding: Models and applications." *Knowledge-Based Systems*.
- Yao, Z., et al. (2018). "Dynamic Word Embeddings for Evolving Semantic Discovery." *WSDM*.
- Clark, A., & Chalmers, D. (1998). "The Extended Mind." *Analysis*, 58(1), 7-19.

**Technical Specifications**:
- `specs/EMBEDDINGS_SPEC.md` — Language-independent specification
- `docs/TEMPORAL_EMBEDDINGS_EXAMPLES.md` — Usage examples and value proposition

**Implementation References**:
- `src/geistfabrik/embeddings.py:114-224` — Core temporal embedding computation
- `src/geistfabrik/embeddings.py:364-460` — Session-based caching strategy
- `src/geistfabrik/default_geists/code/session_drift.py` — Drift detection implementation
- `src/geistfabrik/default_geists/code/hermeneutic_instability.py` — Interpretive variance implementation
- `src/geistfabrik/default_geists/code/temporal_clustering.py` — Temporal pattern discovery

---

**Document Version**: 1.0
**Last Updated**: 2025-11-06
**Author**: Research analysis for GeistFabrik temporal embeddings system
