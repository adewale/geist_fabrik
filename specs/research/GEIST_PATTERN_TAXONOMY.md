# GeistFabrik Pattern Taxonomy

**A deep analysis of reusable computational and conceptual patterns across all GeistFabrik geists**

This taxonomy identifies the fundamental patterns that geists follow, going beyond surface naming to discover underlying computational/conceptual architectures. Each pattern is transferable across different data types (emotions, concepts, topics, relationships).

---

## Table of Contents

1. [Temporal Patterns](#temporal-patterns)
2. [Spatial/Topological Patterns](#spatialtopological-patterns)
3. [Comparison/Contrast Patterns](#comparisoncontrast-patterns)
4. [Discovery/Pattern Recognition](#discoverypattern-recognition)
5. [Generation/Transformation Patterns](#generationtransformation-patterns)
6. [Dialectic/Questioning Patterns](#dialecticquestioning-patterns)
7. [Archaeology/Excavation Patterns](#archaeologyexcavation-patterns)
8. [Meta-Patterns](#meta-patterns)
9. [Multidimensional Movement Patterns](#multidimensional-movement-patterns)
10. [Pattern Combinations](#pattern-combinations)
11. [Missing Patterns](#missing-patterns)

---

## 1. Temporal Patterns

Patterns that analyze how things change, persist, or relate across time.

### 1.1 DRIFT (Trajectory Analysis)

**Computational Signature**: Track embedding vectors across sessions, compute distance from origin

**What it does**: Measures how far something has moved from its starting point in semantic space

**Examples**:
- `concept_drift` - tracks notes' semantic migration over time
- `session_drift` - compares current vs previous session interpretation
- Proposed: `sentiment_drift`, `emotional_drift`, `topic_drift`

**Key Algorithm**:
```python
trajectory = get_embeddings_across_sessions(note)
drift_vector = trajectory[-1] - trajectory[0]
drift_magnitude = norm(drift_vector)
```

**Transferability**: Works with ANY time-series of vectors (emotions, topics, complexity scores)

---

### 1.2 VELOCITY (Rate of Change)

**Computational Signature**: Compare consecutive time windows, detect acceleration/deceleration

**What it does**: Measures rate of change, not just total change

**Examples**:
- `drift_velocity_anomaly` - detects accelerating semantic drift
- Proposed: `emotional_velocity`, `complexity_velocity`

**Key Algorithm**:
```python
windowed_rates = [
    distance(trajectory[i], trajectory[i+1])
    for i in range(len(trajectory)-1)
]
acceleration = rate[-1] > rate[0] * threshold
```

**Transferability**: Works with any scalar or vector time series

---

### 1.3 FLIP/REVERSAL (Polarity Change)

**Computational Signature**: Detect sign changes or threshold crossings

**What it does**: Identifies when something transitions from one state to its opposite

**Examples**:
- Proposed: `valence_flip` - tracks sentiment polarity reversals
- Could apply to: topic focus, writing style, abstraction level

**Key Algorithm**:
```python
for i in range(len(trajectory)-1):
    if sign(trajectory[i]) != sign(trajectory[i+1]):
        yield FlipEvent(time=i, before=trajectory[i], after=trajectory[i+1])
```

**Transferability**: Works with any signed scalar (sentiment, stance, agreement)

---

### 1.4 BURST (Temporal Clustering)

**Computational Signature**: Group events by timestamp, detect density spikes

**What it does**: Finds moments of concentrated activity

**Examples**:
- `creation_burst` - days with multiple notes created
- `burst_evolution` - tracks how burst notes evolve
- Proposed: `emotional_burst`, `editing_burst`, `tagging_burst`

**Key Algorithm**:
```python
events_by_day = group_by(events, key=lambda e: e.date)
burst_days = [
    (day, events)
    for day, events in events_by_day.items()
    if len(events) >= threshold
]
```

**Transferability**: Works with any timestamped events

---

### 1.5 INERTIA/PERSISTENCE (Non-Change Detection)

**Computational Signature**: Identify entities with low drift despite surrounding change

**What it does**: Finds anchors - things that DON'T change when similar things do

**Examples**:
- `burst_evolution` (implicitly) - identifies "stable" notes from burst
- Proposed: `emotional_inertia` - notes that maintain sentiment despite edits

**Key Algorithm**:
```python
all_drift_scores = [calculate_drift(note) for note in notes]
median_drift = median(all_drift_scores)
persistent = [n for n in notes if calculate_drift(n) < median_drift * 0.3]
```

**Transferability**: Inverse of drift - works anywhere drift works

---

### 1.6 CONVERGENCE/DIVERGENCE (Trajectory Direction)

**Computational Signature**: Compare distance between two entities across time

**What it does**: Detects whether things are developing toward or away from each other

**Examples**:
- `convergent_evolution` - notes developing in same direction
- `divergent_evolution` - linked notes growing apart
- Proposed: `emotional_convergence`, `topic_convergence`

**Key Algorithm**:
```python
distances = [
    distance(trajectory_a[i], trajectory_b[i])
    for i in range(len(trajectory_a))
]
is_converging = distances[-1] < distances[0] - threshold
is_diverging = distances[-1] > distances[0] + threshold
```

**Transferability**: Works with any pair of time-series vectors

---

### 1.7 MIRROR (Temporal Reflection)

**Computational Signature**: Compare entities from different time periods

**What it does**: Juxtaposes past vs present to reveal evolution

**Examples**:
- `temporal_mirror` - compares notes from different vault eras
- Proposed: `emotional_mirror` - past vs present emotional states

**Key Algorithm**:
```python
periods = divide_into_temporal_periods(items, n=10)
period_a, period_b = sample(periods, k=2)
item_a = sample(period_a, k=1)
item_b = sample(period_b, k=1)
return compare(item_a, item_b, temporal_context=True)
```

**Transferability**: Works with any temporally-organized collection

---

### 1.8 CYCLICAL/SEASONAL (Rhythmic Patterns)

**Computational Signature**: Group by calendar features (month, season), detect recurrence

**What it does**: Finds patterns that repeat on annual/seasonal cycles

**Examples**:
- `seasonal_patterns` - topics that recur at specific times
- Proposed: `mood_seasonality`, `creativity_cycles`

**Key Algorithm**:
```python
by_month = group_by(notes, key=lambda n: n.created.month)
for month, notes in by_month.items():
    if high_intra_cluster_similarity(notes):
        # Check across years
        by_year = group_by(notes, key=lambda n: n.created.year)
        if len(by_year) >= 2 and cross_year_similarity(by_year) > threshold:
            yield SeasonalPattern(month=month, notes=notes)
```

**Transferability**: Works with any timestamped entities

---

### 1.9 ARC/TRAJECTORY (Directional Evolution)

**Computational Signature**: Fit curve to time series, identify shape (rising, falling, U-shaped)

**What it does**: Characterizes the shape/direction of change over time

**Examples**:
- Proposed: `emotional_arc` - narrative emotional trajectory
- Could apply to: complexity evolution, connectivity growth

**Key Algorithm**:
```python
trajectory = get_time_series(entity)
shape = characterize_trajectory(trajectory)  # linear, exponential, cyclical, etc.
if shape == "rising":
    return f"{entity} shows growth pattern"
elif shape == "U-shaped":
    return f"{entity} shows recovery pattern"
```

**Transferability**: Works with any scalar time series

---

## 2. Spatial/Topological Patterns

Patterns that analyze position, connectivity, and structure in abstract spaces.

### 2.1 BRIDGE (Path Finding)

**Computational Signature**: Find intermediate nodes that connect distant nodes

**What it does**: Discovers stepping-stone paths through semantic or graph space

**Examples**:
- `bridge_hunter` - finds semantic paths between unlinked notes
- `bridge_builder` - suggests notes that could connect clusters
- Proposed: `emotional_bridge` - notes that connect different emotional states

**Key Algorithm**:
```python
def find_bridge(start, end, max_hops=3):
    candidates = get_neighbours(start, k=10)
    for mid in candidates:
        if similarity(mid, end) > threshold:
            return [start, mid, end]
    # Try 3-hop paths
    for mid1 in get_neighbours(start, k=10):
        for mid2 in get_neighbours(end, k=10):
            if similarity(mid1, mid2) > threshold:
                return [start, mid1, mid2, end]
```

**Transferability**: Works in any space with distance/similarity metric

---

### 2.2 HUB (Centrality Detection)

**Computational Signature**: Measure connectivity (graph) or semantic relatedness (embeddings)

**What it does**: Finds nodes that are central to many others

**Examples**:
- `hidden_hub` - semantically central but under-linked notes
- Graph hubs (high degree centrality)
- Proposed: `emotional_contagion` - notes that influence emotional tone of linked notes

**Key Algorithm**:
```python
# Semantic hub
for note in notes:
    semantic_neighbors = count_similar_notes(note, threshold=0.6)
    graph_links = count_links(note)
    if semantic_neighbors > 10 and graph_links < 5:
        yield HiddenHub(note)

# Graph hub
graph_degree = [len(note.links) + len(backlinks(note)) for note in notes]
hubs = [n for n in notes if graph_degree(n) > percentile(graph_degree, 90)]
```

**Transferability**: Works in any network (social, semantic, citation)

---

### 2.3 ISLAND/ISOLATION (Disconnection Detection)

**Computational Signature**: Find nodes with low connectivity or distant from clusters

**What it does**: Identifies orphaned or disconnected entities

**Examples**:
- `island_hopper` - finds notes that could connect disconnected clusters
- Orphan detection (zero backlinks)
- Proposed: `emotional_isolation` - notes with unique emotional signatures

**Key Algorithm**:
```python
for note in notes:
    graph_neighbors = get_graph_neighbors(note)
    semantic_neighbors = get_semantic_neighbors(note, threshold=0.5)
    if len(graph_neighbors) < 2 and len(semantic_neighbors) < 3:
        yield Island(note)
```

**Transferability**: Inverse of hub - works wherever hub works

---

### 2.4 CLUSTER/CONSTELLATION (Grouping)

**Computational Signature**: Apply clustering algorithm (HDBSCAN, k-means), identify coherent groups

**What it does**: Discovers natural groupings in high-dimensional space

**Examples**:
- `cluster_mirror` - reveals semantic vault structure
- `cluster_evolution_tracker` - tracks cluster migrations
- `temporal_clustering` - finds notes that cluster by era
- Proposed: `mood_constellation` - groups notes by emotional signature

**Key Algorithm**:
```python
embeddings = get_embeddings(notes)
clusters = HDBSCAN(embeddings, min_cluster_size=5)
labels = generate_labels(clusters)  # c-TF-IDF
for cluster_id, label in labels.items():
    members = [n for n in notes if clusters[n] == cluster_id]
    representatives = get_closest_to_centroid(members, k=3)
    yield Cluster(label=label, members=members, reps=representatives)
```

**Transferability**: Works with any vector embeddings

---

### 2.5 BOUNDARY/PERIPHERY (Edge Detection)

**Computational Signature**: Find nodes at cluster boundaries or between communities

**What it does**: Identifies entities that straddle multiple groups

**Examples**:
- `island_hopper` (implicitly) - notes near clusters but not in them
- Proposed: `boundary_crosser` - notes that bridge different topic clusters

**Key Algorithm**:
```python
clusters = get_clusters(notes)
for note in notes:
    cluster_memberships = [
        (cluster_id, distance_to_centroid(note, cluster))
        for cluster_id, cluster in clusters.items()
    ]
    # Sort by distance
    closest_two = sorted(cluster_memberships, key=lambda x: x[1])[:2]
    if closest_two[0][1] < threshold and closest_two[1][1] < threshold * 1.5:
        yield BoundaryNote(note, clusters=[closest_two[0][0], closest_two[1][0]])
```

**Transferability**: Works with any clustered space

---

## 3. Comparison/Contrast Patterns

Patterns that identify differences, mismatches, or contradictions.

### 3.1 MISMATCH (Discrepancy Detection)

**Computational Signature**: Compare two metrics, flag when they diverge

**What it does**: Finds cases where expected correlation doesn't hold

**Examples**:
- `complexity_mismatch` - complexity vs importance discrepancy
- `density_inversion` - link density vs semantic density mismatch
- Proposed: `sentiment_content_mismatch` - positive words but negative sentiment

**Key Algorithm**:
```python
for entity in entities:
    metric_a = calculate_metric_a(entity)
    metric_b = calculate_metric_b(entity)
    expected_b = predict_b_from_a(metric_a)
    if abs(metric_b - expected_b) > threshold:
        yield Mismatch(entity, metric_a, metric_b, expected_b)
```

**Transferability**: Works with any pair of correlated metrics

---

### 3.2 PARADOX/CONTRADICTION (Internal Inconsistency)

**Computational Signature**: Detect opposing signals within or between entities

**What it does**: Finds logical or semantic contradictions

**Examples**:
- `columbo` - detects contradictions between notes
- Proposed: `dialectic_tension` - notes with internal contradictions
- Proposed: `mixed_feelings` - notes with conflicting emotional markers

**Key Algorithm**:
```python
for note_a in notes:
    for note_b in get_similar_notes(note_a, k=10):
        positive_markers_a = count_markers(note_a, positive_words)
        negative_markers_b = count_markers(note_b, negative_words)
        semantic_similarity = similarity(note_a, note_b)

        if semantic_similarity > 0.7 and positive_markers_a > 2 and negative_markers_b > 2:
            yield Contradiction(note_a, note_b)
```

**Transferability**: Works with any entities that have measurable stance/polarity

---

### 3.3 SCALE/ABSTRACTION SHIFT (Level Change)

**Computational Signature**: Classify abstraction level, suggest opposite

**What it does**: Identifies perspective scale and suggests zooming in/out

**Examples**:
- `scale_shifter` - suggests viewing concepts at different abstraction levels
- Proposed: `detail_zoom` - expand sparse notes, condense verbose notes

**Key Algorithm**:
```python
abstract_markers = ["theory", "principle", "concept", "framework"]
concrete_markers = ["example", "case", "instance", "specific"]

for note in notes:
    content = read(note).lower()
    abstract_score = sum(1 for m in abstract_markers if m in content)
    concrete_score = sum(1 for m in concrete_markers if m in content)

    if abstract_score >= 3 and concrete_score <= 1:
        concrete_examples = find_similar_notes(note, high_concrete_score)
        yield ScaleShift(note, direction="zoom_in", examples=concrete_examples)
    elif concrete_score >= 3 and abstract_score <= 1:
        frameworks = find_similar_notes(note, high_abstract_score)
        yield ScaleShift(note, direction="zoom_out", frameworks=frameworks)
```

**Transferability**: Works with any hierarchical dimension (detail, specificity, scope)

---

### 3.4 INVERSION (Opposite Finding)

**Computational Signature**: Find semantic opposites or contrarians

**What it does**: Identifies entities that negate or oppose others

**Examples**:
- `blind_spot_detector` - finds underexplored semantic opposites
- Proposed: `emotional_opposite` - notes with opposite emotional tone

**Key Algorithm**:
```python
def find_opposite(entity, all_entities):
    # Method 1: Semantic negation (embeddings)
    entity_emb = get_embedding(entity)
    negated_emb = -entity_emb  # Simple inversion
    candidates = get_nearest(negated_emb, all_entities)

    # Method 2: Linguistic markers
    if has_positive_markers(entity):
        candidates = [e for e in all_entities if has_negative_markers(e)]

    return candidates[0] if candidates else None
```

**Transferability**: Works in any space with notion of opposition (sentiment, stance, direction)

---

## 4. Discovery/Pattern Recognition

Patterns that find hidden structures or recurring themes.

### 4.1 PATTERN/THEME EXTRACTION (Repetition Finding)

**Computational Signature**: Extract features (n-grams, topics), count occurrences across entities

**What it does**: Discovers recurring themes that appear in multiple places

**Examples**:
- `pattern_finder` - identifies repeated phrases across unconnected notes
- Proposed: `emotional_theme` - recurring emotional patterns

**Key Algorithm**:
```python
phrase_to_notes = defaultdict(list)
for note in notes:
    phrases = extract_phrases(note, n=3)  # 3-word phrases
    for phrase in phrases:
        if is_significant(phrase):  # Filter stop words
            phrase_to_notes[phrase].append(note)

for phrase, notes in phrase_to_notes.items():
    if len(notes) >= 3:
        unlinked = [n for n in notes if not connected_to_others(n, notes)]
        if len(unlinked) >= 3:
            yield Pattern(phrase=phrase, notes=unlinked)
```

**Transferability**: Works with any text or feature extraction method

---

### 4.2 OUTLIER/ANOMALY DETECTION (Statistical Deviation)

**Computational Signature**: Compute distribution, identify values > N standard deviations from mean

**What it does**: Finds unusual cases that deviate from the norm

**Examples**:
- `metadata_outlier_detector` - finds unusual metadata values
- Proposed: `intensity_spike` - emotional outliers

**Key Algorithm**:
```python
metric_values = [calculate_metric(entity) for entity in entities]
mean = statistics.mean(metric_values)
std = statistics.stdev(metric_values)

outliers = [
    entity
    for entity in entities
    if abs(calculate_metric(entity) - mean) > threshold * std
]
```

**Transferability**: Works with any numerical metric

---

### 4.3 GAP/ABSENCE DETECTION (Missing Element Finding)

**Computational Signature**: Identify unexplored regions in semantic or feature space

**What it does**: Finds what's NOT there - blind spots, voids

**Examples**:
- `blind_spot_detector` - identifies underexplored semantic areas
- Proposed: `emotional_absence` - missing emotional perspectives

**Key Algorithm**:
```python
# Method 1: Semantic coverage
all_space = sample_semantic_space(granularity=100)
covered = [region for region in all_space if has_notes_nearby(region)]
gaps = [region for region in all_space if region not in covered]

# Method 2: Contrarian finding
for recent_note in get_recent_notes(k=5):
    opposite = find_semantic_opposite(recent_note)
    if opposite and days_since_modified(opposite) > 180:
        yield BlindSpot(active=recent_note, neglected=opposite)
```

**Transferability**: Works in any space where coverage can be measured

---

## 5. Generation/Transformation Patterns

Patterns that create new ideas by transforming existing ones.

### 5.1 COLLISION/JUXTAPOSITION (Forced Combination)

**Computational Signature**: Randomly sample distant entities, suggest combination

**What it does**: Forces unexpected pairings to spark creativity

**Examples**:
- `creative_collision` - suggests unexpected note combinations
- Proposed: `mood_collision` - combine notes with contrasting emotions

**Key Algorithm**:
```python
for _ in range(attempts):
    entity_a, entity_b = random.sample(entities, k=2)
    similarity = calculate_similarity(entity_a, entity_b)

    # Look for moderately dissimilar (not too close, not too far)
    if 0.2 < similarity < 0.5:
        yield Collision(entity_a, entity_b)
```

**Transferability**: Works with any entity collection

---

### 5.2 SCAMPER/TRANSFORMATION (Systematic Variation)

**Computational Signature**: Apply transformation templates (substitute, combine, adapt, etc.)

**What it does**: Systematically generates variations using creative operators

**Examples**:
- `method_scrambler` - applies SCAMPER technique
- Could apply to: emotional reframing, perspective shifting

**Key Algorithm**:
```python
operations = {
    "substitute": "What if you replaced {a} with {b}?",
    "combine": "What if you merged {a} and {b}?",
    "adapt": "What if you adapted {a} to work like {b}?",
    "modify": "What if you amplified/reduced aspects of {a}?",
    "eliminate": "What if you removed parts of {a}?",
    "reverse": "What if you inverted the relationship between {a} and {b}?"
}

for entity in sample(entities):
    related = get_related_entities(entity)
    operation, template = random.choice(operations.items())
    yield Transformation(operation, template.format(a=entity, b=random.choice(related)))
```

**Transferability**: Template-based - works with any entity type

---

### 5.3 ANTITHESIS/NEGATION (Opposition Generation)

**Computational Signature**: Identify claims, generate systematic negations

**What it does**: Creates dialectical opposites

**Examples**:
- `antithesis_generator` - creates contrarian viewpoints
- Proposed: `emotional_antithesis` - suggest opposite emotional framing

**Key Algorithm**:
```python
for note in notes:
    claim_strength = count_assertion_markers(note)
    if claim_strength >= 3:
        existing_antithesis = find_opposing_notes(note)
        if existing_antithesis:
            yield StrengtenDialectic(thesis=note, antithesis=existing_antithesis)
        else:
            antithesis_title = f"Anti-{note.title}"
            yield CreateAntithesis(thesis=note, suggested_title=antithesis_title)
```

**Transferability**: Works with any entity that makes claims or has polarity

---

## 6. Dialectic/Questioning Patterns

Patterns that challenge, question, or provoke deeper thinking.

### 6.1 SOCRATIC/QUESTIONING (Assumption Challenge)

**Computational Signature**: Detect certainty markers, flag for questioning

**What it does**: Identifies unjustified assumptions and asks for evidence

**Examples**:
- `assumption_challenger` - identifies implicit assumptions
- `columbo` - questions contradictions
- Proposed: `emotional_assumption` - "Why do you assume X makes you feel Y?"

**Key Algorithm**:
```python
certainty_markers = ["obviously", "clearly", "must be", "always", "never"]
hedging_markers = ["maybe", "perhaps", "might", "could", "possibly"]

for note in notes:
    certainty_count = count_markers(note, certainty_markers)
    if certainty_count >= 2:
        # Find related notes with hedging language
        similar = get_similar_notes(note)
        for other in similar:
            hedging_count = count_markers(other, hedging_markers)
            if hedging_count >= 2:
                yield Question(
                    f"What assumptions underlie the certainty in {note}?"
                )
```

**Transferability**: Works with any text that makes claims

---

### 6.2 SYNTHESIS (Dialectical Resolution)

**Computational Signature**: Identify thesis/antithesis pairs, suggest higher-level integration

**What it does**: Asks for reconciliation of opposing viewpoints

**Examples**:
- `antithesis_generator` (partial) - suggests synthesis when finding dialectical pairs
- Proposed: `emotional_synthesis` - reconcile conflicting emotional responses

**Key Algorithm**:
```python
for note_a in notes:
    for note_b in get_similar_notes(note_a):
        if seem_opposed(note_a, note_b):  # High similarity but opposite markers
            synthesis_title = f"Synthesis: {note_a.title} + {note_b.title}"
            yield SynthesisProposal(
                thesis=note_a,
                antithesis=note_b,
                suggested_title=synthesis_title,
                question="What higher-level perspective reconciles these?"
            )
```

**Transferability**: Works wherever opposition/tension exists

---

## 7. Archaeology/Excavation Patterns

Patterns that unearth forgotten or buried information.

### 7.1 ARCHAEOLOGY (Temporal Excavation)

**Computational Signature**: Filter by age + status, surface old incomplete items

**What it does**: Finds forgotten tasks, abandoned ideas

**Examples**:
- `task_archaeology` - finds old incomplete tasks
- Proposed: `joy_archaeology` - find notes you loved but abandoned
- Proposed: `question_archaeology` - find old unanswered questions

**Key Algorithm**:
```python
for note in notes:
    days_old = (now - note.modified).days
    has_incomplete_tasks = metadata(note).get("has_tasks", False)
    incomplete_count = metadata(note).get("incomplete_tasks", 0)

    if has_incomplete_tasks and incomplete_count > 0 and days_old > 30:
        yield ArchaeologicalFind(
            note=note,
            age_days=days_old,
            incomplete_tasks=incomplete_count,
            question=f"Are these {incomplete_count} tasks still relevant?"
        )
```

**Transferability**: Works with any timestamped incomplete/unresolved items

---

### 7.2 CRYSTALLIZATION/TRAP DETECTION (Over-Optimization Warning)

**Computational Signature**: Detect excessive optimization on single dimension

**What it does**: Warns when over-indexing on one metric

**Examples**:
- Proposed: `affect_labeling_trap` - over-analyzing emotions kills spontaneity
- Could apply to: productivity optimization, perfect organization

**Key Algorithm**:
```python
for note in notes:
    optimization_markers = count_markers(note, ["optimize", "improve", "perfect", "maximize"])
    if optimization_markers > threshold:
        related_notes = get_notes_on_same_topic(note)
        spontaneity_markers = count_markers(related_notes, ["spontaneous", "intuitive", "flow"])

        if spontaneity_markers < optimization_markers * 0.3:
            yield OverOptimizationWarning(
                note=note,
                question="Is optimizing this dimension killing something valuable?"
            )
```

**Transferability**: Meta-pattern applicable to any over-indexing behavior

---

## 8. Meta-Patterns

Patterns about patterns - higher-order structures.

### 8.1 MIRRORING (Reflection Without Interpretation)

**Computational Signature**: Present pattern, ask user to interpret

**What it does**: Shows structure without prescribing meaning - pure provocation

**Examples**:
- `cluster_mirror` - "What do these clusters remind you of?"
- Could apply to: emotional patterns, temporal rhythms

**Philosophy**: This is the purest "muse not oracle" pattern - the geist surfaces pattern but doesn't interpret it

**Key Algorithm**:
```python
pattern = detect_pattern(data)
representatives = sample_representatives(pattern)
return f"Pattern: {describe(pattern)}\nExamples: {representatives}\n\nWhat does this remind you of?"
```

**Transferability**: Meta-pattern - wraps any pattern detection algorithm

---

### 8.2 EVOLUTION TRACKING (Meta-Temporal)

**Computational Signature**: Track how patterns themselves change over time

**What it does**: Patterns about how patterns evolve

**Examples**:
- `cluster_evolution_tracker` - tracks cluster migrations
- `burst_evolution` - tracks how burst patterns evolve
- Proposed: `pattern_evolution` - track how recurring themes shift

**Key Algorithm**:
```python
current_pattern = detect_pattern(current_data)
historical_patterns = [detect_pattern(session_data) for session_data in past_sessions]

for entity in entities:
    current_state = get_pattern_membership(entity, current_pattern)
    past_state = get_pattern_membership(entity, historical_patterns[-2])

    if current_state != past_state:
        yield PatternMigration(
            entity=entity,
            from_pattern=past_state,
            to_pattern=current_state
        )
```

**Transferability**: Meta-pattern - applies to any pattern that can be tracked over time

---

### 8.3 MULTI-SCALE ANALYSIS (Hierarchical Patterns)

**Computational Signature**: Detect patterns at multiple granularities simultaneously

**What it does**: Finds micro-patterns (individual notes) and macro-patterns (vault-wide)

**Examples**:
- `seasonal_patterns` operates at vault-wide scale
- `concept_drift` operates at note-level scale
- Could combine: "This note drifts, but the entire cluster it belongs to is stable"

**Key Algorithm**:
```python
# Micro-level
note_level_patterns = [analyze_note(n) for n in notes]

# Macro-level
cluster_level_patterns = [analyze_cluster(c) for c in clusters]
vault_level_patterns = analyze_vault(vault)

# Cross-scale insights
for note in notes:
    note_pattern = get_pattern(note, note_level_patterns)
    cluster = get_cluster(note)
    cluster_pattern = get_pattern(cluster, cluster_level_patterns)

    if note_pattern != cluster_pattern:
        yield CrossScaleAnomaly(note, note_pattern, cluster_pattern)
```

**Transferability**: Meta-pattern - applies hierarchical analysis to any domain

---

## 9. Multidimensional Movement Patterns

Patterns that analyze how entities move across **multiple dimensions simultaneously**. These patterns extend single-dimension primitives to handle complex multidimensional trajectories where different aspects of a note (semantic, temporal, graph, sentiment, cluster, etc.) can move in coupled or decoupled ways.

**Key insight**: Two notes can move closer in one dimension while moving farther in another. Traditional single-dimension patterns miss these nuanced relationships.

### 9.1 DECOUPLED_MOVEMENT (Independent Dimensional Movement)

**Computational Signature**: Measure correlation between directional movements in different dimensions

**What it does**: Identifies note pairs whose movement in one dimension is independent of movement in another

**Examples**:
- `sentiment_phantom_link` - Sentiment convergence + semantic divergence
- `sentiment_semantic_decoupling` - Sentiment divergence + semantic convergence
- Could apply to: graph distance vs embedding distance, cluster membership vs temporal drift

**Key Algorithm**:
```python
def detect_decoupled_movement(note_a, note_b, dim_x, dim_y, sessions):
    """Detect when movement in dim_x is uncorrelated with movement in dim_y."""
    directions_x = []
    directions_y = []

    for i in range(len(sessions) - 1):
        # Direction in dimension X
        sim_x_t0 = similarity(note_a, note_b, dimension=dim_x, session=sessions[i])
        sim_x_t1 = similarity(note_a, note_b, dimension=dim_x, session=sessions[i+1])
        directions_x.append(1 if sim_x_t1 > sim_x_t0 else -1)

        # Direction in dimension Y
        sim_y_t0 = similarity(note_a, note_b, dimension=dim_y, session=sessions[i])
        sim_y_t1 = similarity(note_a, note_b, dimension=dim_y, session=sessions[i+1])
        directions_y.append(1 if sim_y_t1 > sim_y_t0 else -1)

    correlation = pearsonr(directions_x, directions_y)

    if abs(correlation) < 0.3:  # Low correlation = decoupled
        return {
            'correlation': correlation,
            'dimensions': (dim_x, dim_y),
            'interpretation': 'Independent movement patterns'
        }
```

**Detection Formula**:
```
correlation(direction_X, direction_Y) < 0.3  # Uncorrelated movement
```

**Transferability**: Works with any pair of quantifiable dimensions (semantic, sentiment, graph, temporal, cluster, structural)

---

### 9.2 OPPOSING_MOVEMENT (Negatively Correlated Dimensions)

**Computational Signature**: Detect negative correlation between dimensional movements

**What it does**: Finds note pairs where closeness in one dimension predicts distance in another

**Examples**:
- `sentiment_phantom_link` - As sentiment converges, semantics diverge
- Graph distance decreasing while semantic distance increasing
- Could apply to: abstraction vs concreteness, formality vs casualness

**Key Algorithm**:
```python
def detect_opposing_movement(note_a, note_b, dim_x, dim_y, sessions):
    """Detect when movement in dim_x opposes movement in dim_y."""
    directions_x = []
    directions_y = []

    # Compute directional movements (same as DECOUPLED_MOVEMENT)
    # ... (see above) ...

    correlation = pearsonr(directions_x, directions_y)

    if correlation < -0.5:  # Strong negative correlation
        return {
            'correlation': correlation,
            'dimensions': (dim_x, dim_y),
            'interpretation': 'Opposing movement patterns'
        }
```

**Detection Formula**:
```
correlation(direction_X, direction_Y) < -0.5  # Opposing movement
```

**Transferability**: Works wherever DECOUPLED_MOVEMENT works, but stricter threshold

---

### 9.3 TRAJECTORY_REVERSAL (Current State vs Future Direction Mismatch)

**Computational Signature**: Compare current similarity with drift vector alignment

**What it does**: Identifies pairs that are currently close but drifting apart (or vice versa)

**Examples**:
- `sentiment_trajectory_reversal` - Similar emotions now, opposing drift vectors
- `convergent_evolution` (inverse) - Distant now but converging
- `divergent_evolution` - Close now but diverging

**Key Algorithm**:
```python
def detect_trajectory_reversal(note_a, note_b, dimension, sessions, min_sessions=3):
    """Detect when current similarity contradicts drift direction."""
    if len(sessions) < min_sessions:
        return None

    # Current similarity
    current_sim = similarity(note_a, note_b, dimension=dimension, session=sessions[-1])

    # Drift vectors (change from first to last session)
    emb_a_t0 = get_embedding(note_a, dimension=dimension, session=sessions[0])
    emb_a_t1 = get_embedding(note_a, dimension=dimension, session=sessions[-1])
    drift_a = emb_a_t1 - emb_a_t0

    emb_b_t0 = get_embedding(note_b, dimension=dimension, session=sessions[0])
    emb_b_t1 = get_embedding(note_b, dimension=dimension, session=sessions[-1])
    drift_b = emb_b_t1 - emb_b_t0

    # Drift alignment (cosine similarity of drift vectors)
    drift_alignment = cosine_similarity(drift_a, drift_b)

    # Reversal: high current similarity + opposing drifts
    if current_sim > 0.7 and drift_alignment < -0.5:
        # Predict future divergence
        predicted_future_sim = current_sim - abs(drift_alignment) * 0.2
        return {
            'current_similarity': current_sim,
            'drift_alignment': drift_alignment,
            'predicted_future_sim': predicted_future_sim,
            'interpretation': 'Currently similar but will diverge'
        }

    # Inverse: low current similarity + aligned drifts
    elif current_sim < 0.4 and drift_alignment > 0.7:
        predicted_future_sim = current_sim + drift_alignment * 0.2
        return {
            'current_similarity': current_sim,
            'drift_alignment': drift_alignment,
            'predicted_future_sim': predicted_future_sim,
            'interpretation': 'Currently distant but will converge'
        }
```

**Detection Formula**:
```
# Diverging reversal
current_similarity > 0.7 AND drift_alignment < -0.5

# Converging reversal (inverse)
current_similarity < 0.4 AND drift_alignment > 0.7
```

**Transferability**: Works with any vector embedding space that supports drift computation

---

### 9.4 MULTIDIMENSIONAL_CONVERGENCE (Mixed Convergence/Divergence)

**Computational Signature**: Categorize note pairs by convergence/divergence across multiple dimensions

**What it does**: Creates a multidimensional profile showing which dimensions are converging vs diverging

**Examples**:
- Note pair: Semantic ↑ (closer), Graph ↓ (farther), Sentiment ↑ (closer), Cluster = (stable)
- Could reveal: "Content drifting apart but emotional alignment increasing"

**Key Algorithm**:
```python
def detect_multidimensional_convergence(note_a, note_b, dimensions, sessions):
    """Profile convergence/divergence across all dimensions."""
    profile = {}

    for dim in dimensions:
        # Compute similarity change
        sim_initial = similarity(note_a, note_b, dimension=dim, session=sessions[0])
        sim_current = similarity(note_a, note_b, dimension=dim, session=sessions[-1])
        delta = sim_current - sim_initial

        if abs(delta) < 0.1:
            direction = "stable"
        elif delta > 0:
            direction = "converging"
        else:
            direction = "diverging"

        profile[dim] = {
            'direction': direction,
            'magnitude': abs(delta),
            'initial': sim_initial,
            'current': sim_current
        }

    # Count dimensions by direction
    converging = sum(1 for d in profile.values() if d['direction'] == 'converging')
    diverging = sum(1 for d in profile.values() if d['direction'] == 'diverging')
    stable = sum(1 for d in profile.values() if d['direction'] == 'stable')

    # Flag mixed patterns
    if converging > 0 and diverging > 0:
        return {
            'profile': profile,
            'converging_count': converging,
            'diverging_count': diverging,
            'stable_count': stable,
            'interpretation': 'Mixed multidimensional movement'
        }
```

**Detection Formula**:
```
∃ dim_i : direction(dim_i) = converging
∃ dim_j : direction(dim_j) = diverging
```

**Transferability**: Meta-pattern that works with any set of quantifiable dimensions

---

### 9.5 ORTHOGONAL_DRIFT (Uncorrelated Drift Directions)

**Computational Signature**: Compute angle between drift vectors in different embedding spaces

**What it does**: Identifies notes whose drift in one space is perpendicular to drift in another

**Examples**:
- Semantic drift orthogonal to sentiment drift (content changing independently of emotion)
- Topic drift orthogonal to complexity drift (subject shifting while sophistication stable)

**Key Algorithm**:
```python
def detect_orthogonal_drift(note, space_a, space_b, sessions):
    """Detect when drift in space_a is orthogonal to drift in space_b."""
    # Drift vector in space A
    emb_a_t0 = get_embedding(note, space=space_a, session=sessions[0])
    emb_a_t1 = get_embedding(note, space=space_a, session=sessions[-1])
    drift_a = emb_a_t1 - emb_a_t0

    # Drift vector in space B
    emb_b_t0 = get_embedding(note, space=space_b, session=sessions[0])
    emb_b_t1 = get_embedding(note, space=space_b, session=sessions[-1])
    drift_b = emb_b_t1 - emb_b_t0

    # Compute alignment (must project to common space or use canonical correlation)
    # For simplicity: compute correlation of magnitudes over time
    drift_correlation = canonical_correlation_analysis(drift_a, drift_b)

    if abs(drift_correlation) < 0.2:  # Near-zero correlation = orthogonal
        return {
            'drift_a_magnitude': norm(drift_a),
            'drift_b_magnitude': norm(drift_b),
            'correlation': drift_correlation,
            'interpretation': 'Independent drift trajectories'
        }
```

**Detection Formula**:
```
correlation(drift_vector_A, drift_vector_B) ≈ 0
```

**Transferability**: Works with any pair of embedding spaces

---

### 9.6 BOUNDARY_WALKER (Categorical Boundary Proximity)

**Computational Signature**: Identify entities near decision boundaries of categorical dimensions

**What it does**: Finds notes that are on the edge between categories (clusters, sentiment polarities, etc.)

**Examples**:
- `sentiment_cluster_boundary` - High sentiment similarity but different clusters
- Notes bridging topic clusters while maintaining coherence
- Could apply to: tag boundaries, abstraction level boundaries

**Key Algorithm**:
```python
def detect_boundary_walker(note_a, note_b, categorical_dim, continuous_dim):
    """Detect pairs near categorical boundaries."""
    # Check categorical mismatch
    category_a = get_category(note_a, dimension=categorical_dim)
    category_b = get_category(note_b, dimension=categorical_dim)

    if category_a == category_b:
        return None  # Same category, not boundary walker

    # Check continuous similarity
    continuous_sim = similarity(note_a, note_b, dimension=continuous_dim)

    # High continuous similarity despite categorical difference
    if continuous_sim > 0.7:
        # Measure distance to boundary
        boundary_score = estimate_boundary_proximity(note_a, note_b, categorical_dim)

        return {
            'category_a': category_a,
            'category_b': category_b,
            'continuous_similarity': continuous_sim,
            'boundary_score': boundary_score,
            'interpretation': 'Bridging categorical boundary'
        }
```

**Detection Formula**:
```
category(A) ≠ category(B) AND continuous_similarity(A, B) > 0.7
```

**Transferability**: Works with any combination of categorical + continuous dimensions

---

### 9.7 VELOCITY_MISMATCH (Aligned Direction, Different Speed)

**Computational Signature**: Compare drift magnitudes for pairs with aligned drift directions

**What it does**: Finds note pairs moving in the same direction but at different rates

**Examples**:
- `sentiment_velocity_mismatch` - Both becoming more positive, one faster
- Both increasing in complexity, different acceleration
- Could apply to: link growth rate, editing frequency

**Key Algorithm**:
```python
def detect_velocity_mismatch(note_a, note_b, dimension, sessions, min_sessions=4):
    """Detect aligned drift direction but different speeds."""
    if len(sessions) < min_sessions:
        return None

    # Compute drift vectors
    emb_a_t0 = get_embedding(note_a, dimension=dimension, session=sessions[0])
    emb_a_t1 = get_embedding(note_a, dimension=dimension, session=sessions[-1])
    drift_a = emb_a_t1 - emb_a_t0

    emb_b_t0 = get_embedding(note_b, dimension=dimension, session=sessions[0])
    emb_b_t1 = get_embedding(note_b, dimension=dimension, session=sessions[-1])
    drift_b = emb_b_t1 - emb_b_t0

    # Check direction alignment
    drift_alignment = cosine_similarity(drift_a, drift_b)

    if drift_alignment < 0.5:
        return None  # Not aligned

    # Compute velocities (magnitude per session)
    velocity_a = norm(drift_a) / len(sessions)
    velocity_b = norm(drift_b) / len(sessions)

    velocity_ratio = max(velocity_a, velocity_b) / min(velocity_a, velocity_b)

    if velocity_ratio > 2.0:  # One moving 2x faster
        return {
            'drift_alignment': drift_alignment,
            'velocity_a': velocity_a,
            'velocity_b': velocity_b,
            'velocity_ratio': velocity_ratio,
            'faster_note': note_a if velocity_a > velocity_b else note_b,
            'interpretation': 'Aligned direction, velocity mismatch'
        }
```

**Detection Formula**:
```
drift_alignment(A, B) > 0.5 AND velocity_ratio > 2.0
```

**Transferability**: Works with any vector space supporting drift computation

---

### 9.8 ACCELERATION_ASYMMETRY (Opposite Acceleration Signs)

**Computational Signature**: Compare second derivatives of trajectory curves

**What it does**: Finds pairs where one is accelerating while the other decelerates

**Examples**:
- Sentiment: One note's emotional velocity increasing, other's decreasing
- Complexity: One note simplifying (negative acceleration), other elaborating (positive)

**Key Algorithm**:
```python
def detect_acceleration_asymmetry(note_a, note_b, dimension, sessions, min_sessions=5):
    """Detect opposing acceleration patterns."""
    if len(sessions) < min_sessions:
        return None

    # Compute velocity over time windows
    velocities_a = []
    velocities_b = []

    for i in range(len(sessions) - 1):
        emb_a_t0 = get_embedding(note_a, dimension=dimension, session=sessions[i])
        emb_a_t1 = get_embedding(note_a, dimension=dimension, session=sessions[i+1])
        velocities_a.append(norm(emb_a_t1 - emb_a_t0))

        emb_b_t0 = get_embedding(note_b, dimension=dimension, session=sessions[i])
        emb_b_t1 = get_embedding(note_b, dimension=dimension, session=sessions[i+1])
        velocities_b.append(norm(emb_b_t1 - emb_b_t0))

    # Compute acceleration (change in velocity)
    accel_a = velocities_a[-1] - velocities_a[0]
    accel_b = velocities_b[-1] - velocities_b[0]

    # Opposite signs = asymmetric acceleration
    if (accel_a > 0 and accel_b < 0) or (accel_a < 0 and accel_b > 0):
        return {
            'acceleration_a': accel_a,
            'acceleration_b': accel_b,
            'velocity_trajectory_a': velocities_a,
            'velocity_trajectory_b': velocities_b,
            'interpretation': 'Opposing acceleration patterns'
        }
```

**Detection Formula**:
```
sign(acceleration_A) ≠ sign(acceleration_B)
```

**Transferability**: Works with any metric that supports second-order temporal derivatives

---

### 9.9 TEMPLATE_EMERGENCE (Structural Convergence, Semantic Divergence)

**Computational Signature**: Compare structural properties vs semantic embeddings

**What it does**: Identifies notes adopting similar templates/formats while content diverges

**Examples**:
- Both notes developing task lists but covering different topics
- Both adopting table structures but with unrelated data
- Could apply to: heading structures, citation patterns, code blocks

**Key Algorithm**:
```python
def detect_template_emergence(note_a, note_b, sessions):
    """Detect structural convergence + semantic divergence."""
    # Structural similarity change
    struct_sim_t0 = structural_similarity(note_a, note_b, session=sessions[0])
    struct_sim_t1 = structural_similarity(note_a, note_b, session=sessions[-1])
    struct_delta = struct_sim_t1 - struct_sim_t0

    # Semantic similarity change
    sem_sim_t0 = semantic_similarity(note_a, note_b, session=sessions[0])
    sem_sim_t1 = semantic_similarity(note_a, note_b, session=sessions[-1])
    sem_delta = sem_sim_t1 - sem_sim_t0

    # Structural convergence + semantic divergence
    if struct_delta > 0.3 and sem_delta < -0.15:
        shared_structure = identify_shared_structural_properties(note_a, note_b)
        return {
            'structural_convergence': struct_delta,
            'semantic_divergence': abs(sem_delta),
            'shared_structure': shared_structure,
            'interpretation': 'Template adoption with content divergence'
        }
```

**Detection Formula**:
```
Δ(structural_similarity) > 0.3 AND Δ(semantic_similarity) < -0.15
```

**Transferability**: Works with any dimensions that separate form from content

---

### 9.10 MAINTENANCE_DIVERGENCE (Content Similarity, Update Asymmetry)

**Computational Signature**: Compare semantic similarity with staleness/freshness metrics

**What it does**: Finds semantically similar note pairs where one is actively maintained and the other abandoned

**Examples**:
- `sentiment_maintenance_asymmetry` - Emotional twins, different update patterns
- Topic doppelgangers with asymmetric editing frequency
- Could apply to: linked notes, cluster members

**Key Algorithm**:
```python
def detect_maintenance_divergence(note_a, note_b):
    """Detect semantic twins with asymmetric update patterns."""
    # Current semantic similarity
    semantic_sim = semantic_similarity(note_a, note_b)

    if semantic_sim < 0.7:
        return None  # Not similar enough

    # Staleness metrics
    staleness_a = compute_staleness(note_a)
    staleness_b = compute_staleness(note_b)
    staleness_diff = abs(staleness_a - staleness_b)

    if staleness_diff > 0.4:  # Significant asymmetry
        days_a = days_since_modified(note_a)
        days_b = days_since_modified(note_b)

        maintained = note_a if days_a < days_b else note_b
        abandoned = note_b if days_a < days_b else note_a

        return {
            'semantic_similarity': semantic_sim,
            'staleness_diff': staleness_diff,
            'maintained_note': maintained,
            'abandoned_note': abandoned,
            'days_since_maintained': min(days_a, days_b),
            'days_since_abandoned': max(days_a, days_b),
            'interpretation': 'Semantic twins, maintenance asymmetry'
        }
```

**Detection Formula**:
```
semantic_similarity > 0.7 AND |staleness_A - staleness_B| > 0.4
```

**Transferability**: Works with any content similarity metric + temporal metadata

---

### 9.11 CORRELATED_MOVEMENT (Predictive Dimension Relationships)

**Computational Signature**: Identify dimensions whose movements reliably predict each other

**What it does**: Discovers which dimensional pairs have high positive correlation (moving together)

**Examples**:
- Sentiment and lexical complexity might correlate (positive mood → more complex language)
- Graph centrality and semantic breadth (hubs cover broader topics)
- Could apply to: any dimension pair with causal or correlative relationship

**Key Algorithm**:
```python
def detect_correlated_movement(notes, dim_a, dim_b, sessions, min_correlation=0.7):
    """Find notes where movement in dim_a predicts movement in dim_b."""
    correlations = []

    for note in notes:
        movements_a = []
        movements_b = []

        for i in range(len(sessions) - 1):
            # Movement in dimension A
            val_a_t0 = get_metric(note, dimension=dim_a, session=sessions[i])
            val_a_t1 = get_metric(note, dimension=dim_a, session=sessions[i+1])
            movements_a.append(val_a_t1 - val_a_t0)

            # Movement in dimension B
            val_b_t0 = get_metric(note, dimension=dim_b, session=sessions[i])
            val_b_t1 = get_metric(note, dimension=dim_b, session=sessions[i+1])
            movements_b.append(val_b_t1 - val_b_t0)

        if len(movements_a) >= 3:  # Need sufficient data
            correlation = pearsonr(movements_a, movements_b)
            correlations.append((note, correlation))

    # Find notes with high correlation
    correlated_notes = [
        (note, corr)
        for note, corr in correlations
        if corr > min_correlation
    ]

    if correlated_notes:
        return {
            'dimensions': (dim_a, dim_b),
            'correlated_notes': correlated_notes,
            'mean_correlation': mean([corr for _, corr in correlated_notes]),
            'interpretation': f'Movement in {dim_a} predicts movement in {dim_b}'
        }
```

**Detection Formula**:
```
correlation(movement_A, movement_B) > 0.7
```

**Transferability**: Meta-pattern applicable to any pair of quantifiable dimensions

---

### Summary: Multidimensional Pattern Architecture

**Key insight**: These 11 patterns extend the 7 single-dimension temporal patterns to handle **multidimensional spaces**.

**Relationship to single-dimension patterns**:

| Single-Dimension Pattern | Multidimensional Extension | What Changed |
|--------------------------|----------------------------|--------------|
| DRIFT | ORTHOGONAL_DRIFT | Drift in multiple spaces simultaneously |
| VELOCITY | VELOCITY_MISMATCH | Same direction, different speeds |
| CONVERGENCE/DIVERGENCE | DECOUPLED_MOVEMENT, OPPOSING_MOVEMENT | Mixed convergence/divergence |
| FLIP/REVERSAL | TRAJECTORY_REVERSAL | Current state vs future direction |
| CLUSTER | BOUNDARY_WALKER | Cluster boundaries in high-D space |
| MISMATCH | TEMPLATE_EMERGENCE | Form vs content divergence |
| ARCHAEOLOGY | MAINTENANCE_DIVERGENCE | Similar notes, different update patterns |

**Implementation strategy**:

1. **Choose dimensional pair**: (semantic, sentiment), (graph, temporal), etc.
2. **Choose multidimensional pattern**: DECOUPLED, OPPOSING, VELOCITY_MISMATCH, etc.
3. **Implement detection algorithm** using correlation, alignment, or delta metrics
4. **Generate provocation** based on discovered relationship

**Systematic geist creation**:
```python
# Template for multidimensional geist
def multidim_geist(vault, dim_a, dim_b, pattern):
    """
    Pattern: One of the 11 multidimensional patterns
    dim_a, dim_b: Dimensional spaces to compare
    """
    sessions = get_sessions(vault)
    note_pairs = sample_pairs(vault.notes(), k=50)

    for note_a, note_b in note_pairs:
        result = pattern.detect(note_a, note_b, dim_a, dim_b, sessions)
        if result:
            provocation = pattern.generate_question(result)
            yield Suggestion(
                text=provocation,
                notes=[note_a.title, note_b.title]
            )
```

**Transferability matrix**:

Each of the 11 patterns can be applied to any of the 8 dimensional spaces:
- Semantic embedding (384D)
- Temporal embedding (387D)
- Graph structure
- Sentiment
- Cluster membership
- Content properties (word count, complexity)
- Structural properties (headings, tasks)
- Staleness/freshness

This yields **88 potential geist variants** (11 patterns × 8 dimensions), though not all combinations are meaningful.

---

## 10. Pattern Combinations

How patterns can be combined to create more sophisticated geists.

### 10.1 Drift + Velocity

**Example**: `drift_velocity_anomaly` = DRIFT + VELOCITY

**What it creates**: Detects not just change, but accelerating change

**Other applications**:
- Emotional acceleration: sentiment changing faster over time
- Complexity acceleration: notes getting more complex faster
- Connection velocity: link growth rate increasing

---

### 10.2 Mirror + Temporal

**Example**: `temporal_mirror` = MIRROR + time periods

**What it creates**: Reflection across time rather than across space

**Other applications**:
- Emotional mirror: past vs present emotional states
- Topic mirror: different intellectual seasons
- Style mirror: writing style evolution

---

### 10.3 Cluster + Evolution

**Example**: `cluster_evolution_tracker` = CLUSTER + EVOLUTION TRACKING

**What it creates**: Tracks how cluster memberships change

**Other applications**:
- Emotional cluster migration: notes moving between mood groups
- Topic cluster fluidity: notes shifting between subject clusters
- Community evolution: how social networks reshape

---

### 10.4 Bridge + Contradiction

**Example**: Could create dialectic bridge finder

**What it creates**: Find notes that could reconcile opposing viewpoints

**Algorithm**:
```python
contradictions = find_contradictions(notes)
for thesis, antithesis in contradictions:
    bridges = find_bridge(thesis, antithesis, max_hops=2)
    if bridges:
        yield DialecticBridge(
            thesis=thesis,
            antithesis=antithesis,
            bridge=bridges,
            question="Could this bridge reconcile the contradiction?"
        )
```

---

### 10.5 Burst + Pattern

**Example**: Could create "burst theme detector"

**What it creates**: Finds recurring themes within creative bursts

**Algorithm**:
```python
bursts = find_bursts(notes)
for burst in bursts:
    themes = extract_themes(burst.notes)
    for theme in themes:
        other_bursts_with_theme = [
            b for b in bursts
            if b != burst and theme in extract_themes(b.notes)
        ]
        if other_bursts_with_theme:
            yield RecurringBurstTheme(theme=theme, bursts=[burst] + other_bursts_with_theme)
```

---

### 10.6 Archaeology + Emotion

**Example**: Proposed `joy_archaeology`

**What it creates**: Finds old notes with positive sentiment you've abandoned

**Algorithm**:
```python
for note in notes:
    sentiment = analyze_sentiment(note)
    days_old = (now - note.modified).days

    if sentiment > 0.7 and days_old > 90:  # Joyful but abandoned
        yield JoyArchaeology(
            note=note,
            sentiment=sentiment,
            days_abandoned=days_old,
            question="What made this joyful? Why did you stop?"
        )
```

---

## 11. Missing Patterns

Patterns that don't exist yet but should.

### 11.1 FEEDBACK LOOP Detection

**What it would do**: Identify notes that reference each other cyclically, forming feedback loops

**Why it's missing**: Current geists focus on pairwise or linear relationships, not cycles

**Algorithm**:
```python
def find_feedback_loops(notes, max_depth=4):
    for start_note in notes:
        visited = {start_note}
        queue = [(start_note, [start_note])]

        while queue:
            current, path = queue.pop(0)
            for neighbor in get_outgoing_links(current):
                if neighbor == start_note and len(path) >= 2:
                    yield FeedbackLoop(path=path + [neighbor])
                elif neighbor not in visited and len(path) < max_depth:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
```

**Applications**: Circular reasoning detection, conceptual dependencies, reinforcing beliefs

---

### 11.2 CASCADE/CONTAGION Detection

**What it would do**: Find ideas that spread through the vault like infections

**Why it's missing**: No geist tracks how concepts propagate through linked notes

**Algorithm**:
```python
def find_contagion(seed_note, feature):
    infected = {seed_note}
    wave_0 = {seed_note}
    waves = [wave_0]

    for generation in range(max_generations):
        wave_next = set()
        for note in waves[generation]:
            for neighbor in get_outgoing_links(note):
                if neighbor not in infected and has_feature(neighbor, feature):
                    wave_next.add(neighbor)
                    infected.add(neighbor)

        if not wave_next:
            break
        waves.append(wave_next)

    if len(waves) >= 3:  # Spread at least 3 hops
        yield Contagion(origin=seed_note, feature=feature, waves=waves)
```

**Applications**: Tag propagation, sentiment contagion, method adoption

---

### 11.3 EMERGENCE Detection

**What it would do**: Identify when vault-level properties emerge that aren't in individual notes

**Why it's missing**: All current geists are bottom-up (note → pattern), none detect true emergence

**Algorithm**:
```python
def detect_emergence():
    vault_embedding = compute_vault_centroid(all_notes)
    vault_themes = extract_themes(vault_embedding)

    for theme in vault_themes:
        # Check if this theme exists in individual notes
        notes_with_theme = [n for n in notes if theme in extract_themes(n)]

        if len(notes_with_theme) < len(notes) * 0.1:  # Less than 10% have it
            yield EmergentTheme(
                theme=theme,
                vault_strength=strength(theme, vault_embedding),
                note_coverage=len(notes_with_theme),
                question=f"This theme emerges at vault level but isn't in individual notes. How?"
            )
```

**Applications**: Implicit worldviews, unconscious assumptions, collective intelligence

---

### 11.4 RESONANCE Detection

**What it would do**: Find notes that amplify each other's signals

**Why it's missing**: Similar to bridge but focuses on reinforcement not connection

**Algorithm**:
```python
def find_resonance(note_a, note_b):
    # Check if they share reinforcing elements
    themes_a = extract_themes(note_a)
    themes_b = extract_themes(note_b)

    shared_themes = set(themes_a) & set(themes_b)
    if not shared_themes:
        return None

    # Check if strength is greater together than apart
    combined_strength = strength(shared_themes, [note_a, note_b])
    individual_strength = (
        strength(shared_themes, [note_a]) +
        strength(shared_themes, [note_b])
    ) / 2

    if combined_strength > individual_strength * 1.5:  # 50% amplification
        yield Resonance(
            notes=[note_a, note_b],
            shared_themes=shared_themes,
            amplification=combined_strength / individual_strength
        )
```

**Applications**: Mutually reinforcing beliefs, echo chambers, convergent validation

---

### 11.5 DECAY/ENTROPY Detection

**What it would do**: Identify notes or clusters losing coherence over time

**Why it's missing**: Focus on drift (directed change) but not decay (loss of structure)

**Algorithm**:
```python
def detect_decay(cluster, historical_sessions):
    coherence_over_time = []

    for session in historical_sessions:
        cluster_notes = get_cluster_members(cluster, session)
        coherence = measure_intra_cluster_similarity(cluster_notes)
        coherence_over_time.append(coherence)

    # Check for declining coherence
    trend = fit_line(coherence_over_time)
    if trend.slope < -0.05:  # Declining
        yield Decay(
            cluster=cluster,
            initial_coherence=coherence_over_time[0],
            current_coherence=coherence_over_time[-1],
            rate=trend.slope,
            question="This cluster is losing coherence. Natural evolution or fragmentation?"
        )
```

**Applications**: Abandoned projects, fragmenting topics, loss of focus

---

### 11.6 PHASE TRANSITION Detection

**What it would do**: Identify moments when the vault undergoes sudden structural change

**Why it's missing**: Current temporal geists track gradual change, not discontinuous shifts

**Algorithm**:
```python
def detect_phase_transitions(metric_over_time):
    # Compute first derivative (rate of change)
    derivatives = [
        metric_over_time[i+1] - metric_over_time[i]
        for i in range(len(metric_over_time)-1)
    ]

    # Find discontinuities
    mean_derivative = statistics.mean(derivatives)
    std_derivative = statistics.stdev(derivatives)

    transitions = []
    for i, derivative in enumerate(derivatives):
        if abs(derivative - mean_derivative) > 3 * std_derivative:
            transitions.append((i, derivative))

    for session_idx, magnitude in transitions:
        yield PhaseTransition(
            session=session_idx,
            magnitude=magnitude,
            before=metric_over_time[session_idx],
            after=metric_over_time[session_idx+1],
            question="What caused this sudden shift?"
        )
```

**Applications**: Conceptual breakthroughs, major life changes, paradigm shifts

---

### 11.7 ATTRACTOR Detection

**What it would do**: Find stable points that notes gravitate toward over time

**Why it's missing**: Drift patterns track movement but not destinations

**Algorithm**:
```python
def find_attractors(notes):
    # Group notes by their drift endpoints
    endpoints = [get_embedding_trajectory(n)[-1] for n in notes]

    # Cluster the endpoints
    attractor_clusters = cluster(endpoints, method="DBSCAN")

    for cluster_id, cluster in attractor_clusters.items():
        # Get notes that ended up in this cluster
        attracted_notes = [n for n in notes if get_trajectory(n)[-1] in cluster]

        # Check if they started from diverse positions
        starting_positions = [get_trajectory(n)[0] for n in attracted_notes]
        starting_diversity = measure_spread(starting_positions)

        if starting_diversity > threshold:
            centroid = compute_centroid(cluster)
            yield Attractor(
                position=centroid,
                attracted_notes=attracted_notes,
                diversity_of_origins=starting_diversity,
                question="Why are diverse notes converging on this point?"
            )
```

**Applications**: Fundamental concepts, core beliefs, intellectual gravity wells

---

## Summary: The Pattern Language

This taxonomy reveals GeistFabrik's true architecture: **a composable pattern language for thought**.

### Core Insight

Every geist is a **composition of primitive patterns**:
- `concept_drift` = DRIFT(embeddings, temporal)
- `convergent_evolution` = CONVERGENCE(DRIFT, DRIFT)
- `cluster_mirror` = MIRROR(CLUSTER)
- `bridge_hunter` = BRIDGE(semantic_space, unlinked_pairs)

### Pattern Transferability

Because patterns are computational primitives, they transfer across domains:

| Pattern | Applies to Concepts | Applies to Emotions | Applies to Topics | Applies to People |
|---------|---------------------|---------------------|-------------------|-------------------|
| DRIFT | concept_drift | sentiment_drift | topic_drift | belief_drift |
| VELOCITY | drift_velocity_anomaly | emotional_velocity | topic_velocity | learning_rate |
| BURST | creation_burst | emotional_burst | topic_burst | social_burst |
| BRIDGE | bridge_hunter | emotional_bridge | topic_bridge | social_bridge |
| HUB | hidden_hub | emotional_anchor | topic_hub | influencer |
| MIRROR | temporal_mirror | emotional_mirror | topic_mirror | role_mirror |
| PARADOX | columbo | mixed_feelings | topic_contradiction | value_conflict |

### Multidimensional Patterns

The 11 **multidimensional movement patterns** (section 9) extend single-dimension primitives to handle cases where notes move across multiple dimensions simultaneously:

| Multidimensional Pattern | What It Detects | Example Geist |
|--------------------------|-----------------|---------------|
| DECOUPLED_MOVEMENT | Independent movement in two dimensions | sentiment_phantom_link |
| OPPOSING_MOVEMENT | Negatively correlated dimensional movement | sentiment_semantic_decoupling |
| TRAJECTORY_REVERSAL | Current state contradicts drift direction | sentiment_trajectory_reversal |
| MULTIDIMENSIONAL_CONVERGENCE | Mixed convergence/divergence profile | (generic framework) |
| ORTHOGONAL_DRIFT | Perpendicular drift vectors | (single-note analysis) |
| BOUNDARY_WALKER | High similarity despite categorical mismatch | sentiment_cluster_boundary |
| VELOCITY_MISMATCH | Aligned direction, different speeds | sentiment_velocity_mismatch |
| ACCELERATION_ASYMMETRY | Opposite acceleration signs | (pairs with opposing trends) |
| TEMPLATE_EMERGENCE | Structural convergence, semantic divergence | (form vs content) |
| MAINTENANCE_DIVERGENCE | Content similarity, update asymmetry | sentiment_maintenance_asymmetry |
| CORRELATED_MOVEMENT | Predictive dimension relationships | (causal analysis) |

**Key insight**: Two notes can move **closer** in one dimension while moving **farther** in another. Traditional single-dimension patterns miss these nuanced relationships.

**Transferability**: Each of the 11 patterns can be applied to any dimensional pair from the 8 dimensional spaces (semantic, temporal, graph, sentiment, cluster, content, structural, staleness), yielding **88 potential geist variants**.

### Implementation Strategy

**For new geists, start with patterns not domains**:

1. Choose a pattern (e.g., DRIFT, BRIDGE, PARADOX)
2. Choose a domain (e.g., sentiment, complexity, topics)
3. Implement: `pattern(domain_data)`

**Example - Creating "emotional_velocity"**:
```python
def emotional_velocity(vault):
    # VELOCITY pattern applied to sentiment domain
    notes = vault.notes()

    for note in sample(notes):
        trajectory = get_sentiment_trajectory(note)  # Domain: sentiment
        velocity = compute_velocity(trajectory)       # Pattern: VELOCITY

        if is_accelerating(velocity):
            yield Suggestion(f"{note} shows accelerating emotional change")
```

### The Meta-Pattern

**GeistFabrik is a pattern engine, not a geist collection.**

Adding new geists isn't about writing custom code—it's about applying existing patterns to new dimensions:

- **Existing dimension + new pattern** → novel insight
- **Existing pattern + new dimension** → domain transfer
- **New pattern + new dimension** → genuine innovation

This taxonomy makes the implicit explicit, enabling systematic geist development rather than ad-hoc creativity.
