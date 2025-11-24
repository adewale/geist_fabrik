# Missing Multidimensional Geists Analysis

**Date**: 2025-01-16
**Context**: Analysis of missing geists based on MULTIDIMENSIONAL_MOVEMENT_ANALYSIS.md
**Status**: Research document identifying implementation gaps

---

## Executive Summary

The multidimensional movement analysis identified **15 distinct multidimensional patterns** where notes move in different directions across different dimensional spaces. Currently, **ZERO of these patterns are implemented** in GeistFabrik.

**Current state**:
- 42 single-dimension code geists (implemented)
- 9 single-dimension Tracery geists (implemented)
- 37 sentiment geists (specified but NOT implemented)
  - Including 6 sentiment-specific multidimensional geists (specified only)
- **15 multidimensional patterns identified** → 0 implemented, 6 specified (sentiment only)

**Gap**: 15 multidimensional patterns × 8 dimensional spaces = **~88 potential geist variants**, with only 6 specified for sentiment domain.

---

## 1. Implemented Geists (Baseline)

### Single-Dimension Temporal Patterns (9 implemented)
1. `concept_drift` - DRIFT pattern on semantic embeddings
2. `session_drift` - DRIFT pattern on session-to-session interpretation
3. `temporal_drift` - DRIFT pattern on temporal embeddings
4. `drift_velocity_anomaly` - VELOCITY pattern (accelerating drift)
5. `convergent_evolution` - CONVERGENCE pattern
6. `divergent_evolution` - DIVERGENCE pattern
7. `cyclical_thinking` - CYCLE pattern
8. `creation_burst` - BURST pattern
9. `burst_evolution` - BURST + EVOLUTION pattern

### Single-Dimension Spatial Patterns (8 implemented)
10. `bridge_hunter` - BRIDGE pattern
11. `bridge_builder` - BRIDGE + suggestion pattern
12. `hidden_hub` - HUB pattern
13. `island_hopper` - ISLAND pattern
14. `cluster_mirror` - CLUSTER + MIRROR pattern
15. `cluster_evolution_tracker` - CLUSTER + EVOLUTION pattern
16. `temporal_clustering` - CLUSTER on temporal features
17. `concept_cluster` - CLUSTER on semantic features

### Single-Dimension Comparison Patterns (4 implemented)
18. `complexity_mismatch` - MISMATCH pattern
19. `density_inversion` - MISMATCH pattern (link density vs semantic density)
20. `columbo` - PARADOX pattern
21. `scale_shifter` - SCALE SHIFT pattern

### Other Single-Dimension Patterns (21 implemented)
22. `blind_spot_detector` - GAP DETECTION pattern
23. `pattern_finder` - PATTERN EXTRACTION
24. `metadata_outlier_detector` - OUTLIER DETECTION
25. `creative_collision` - COLLISION pattern
26. `method_scrambler` - SCAMPER pattern
27. `antithesis_generator` - ANTITHESIS pattern
28. `assumption_challenger` - SOCRATIC pattern
29. `task_archaeology` - ARCHAEOLOGY pattern
30. `temporal_mirror` - MIRROR + temporal
31. `seasonal_patterns` - CYCLICAL pattern (seasonal)
32. `seasonal_revisit` - CYCLICAL + archaeology
33. `seasonal_topic_analysis` - CYCLICAL + topics
34. `on_this_day` - TEMPORAL excavation
35. `anachronism_detector` - TEMPORAL mismatch
36. `hermeneutic_instability` - Interpretive drift
37. `question_harvester` - Content extraction
38. `quote_harvester` - Content extraction
39. `definition_harvester` - Content extraction
40. `todo_harvester` - Content extraction
41. `question_generator` - Generation pattern
42. `stub_expander` - GAP filling

**Total implemented**: 42 code geists + 9 Tracery geists = **51 geists**

---

## 2. Specified But Not Implemented

### Sentiment Geists (37 specified, 0 implemented)

Includes 6 sentiment-specific multidimensional geists:
- `sentiment_phantom_link` (geist 32) - OPPOSING_MOVEMENT pattern
- `sentiment_semantic_decoupling` (geist 33) - OPPOSING_MOVEMENT pattern (inverse)
- `sentiment_trajectory_reversal` (geist 34) - TRAJECTORY_REVERSAL pattern
- `sentiment_velocity_mismatch` (geist 35) - VELOCITY_MISMATCH pattern
- `sentiment_cluster_boundary` (geist 36) - BOUNDARY_WALKER pattern
- `sentiment_maintenance_asymmetry` (geist 37) - MAINTENANCE_DIVERGENCE pattern

**Status**: All 37 sentiment geists exist only as specifications in `specs/sentiment_geists_spec.md`

---

## 3. Missing Multidimensional Geists

### 3.1 Pattern Coverage Matrix

| Pattern Name | Dimensions | Sentiment Version | General Version | Priority |
|--------------|------------|-------------------|-----------------|----------|
| DECOUPLED_MOVEMENT | Any 2 dims, r<0.3 | ❌ Not specified | ❌ Missing | Medium |
| OPPOSING_MOVEMENT | Any 2 dims, r<-0.5 | ✅ Specified (32, 33) | ❌ Missing | **HIGH** |
| TRAJECTORY_REVERSAL | Current vs drift | ✅ Specified (34) | ❌ Missing | **HIGH** |
| MULTIDIMENSIONAL_CONVERGENCE | Mixed profile | ❌ Not specified | ❌ Missing | Medium |
| ORTHOGONAL_DRIFT | Perpendicular drifts | ❌ Not specified | ❌ Missing | Low |
| BOUNDARY_WALKER | Categorical boundary | ✅ Specified (36) | ❌ Missing | **HIGH** |
| VELOCITY_MISMATCH | Aligned, diff speed | ✅ Specified (35) | ❌ Missing | **HIGH** |
| ACCELERATION_ASYMMETRY | Opposite accel | ❌ Not specified | ❌ Missing | Medium |
| TEMPLATE_EMERGENCE | Form vs content | ❌ Not specified | ❌ Missing | **HIGH** |
| MAINTENANCE_DIVERGENCE | Content vs updates | ✅ Specified (37) | ❌ Missing | **HIGH** |
| CORRELATED_MOVEMENT | Predictive dims | ❌ Not specified | ❌ Missing | Low |

**Additional patterns from detailed analysis** (section 3.2 of MULTIDIMENSIONAL_MOVEMENT_ANALYSIS.md):

| Pattern Name | Dimensions | Specified? | Implemented? | Priority |
|--------------|------------|------------|--------------|----------|
| Phantom Link | Semantic ↑, Graph ↓ | ✅ Sentiment only | ❌ Missing | **CRITICAL** |
| Ghost Connection | Semantic ↓, Graph stable | ❌ No | ⚠️ Partial (`divergent_evolution`) | **HIGH** |
| Seasonal Drift | Semantic stable, Temporal Emb ↓ | ❌ No | ❌ Missing | Medium |
| Content Freeze | Semantic stable, Staleness ↑ | ❌ No | ⚠️ Partial (`temporal_drift`) | Medium |
| Style Convergence | Semantic ↓, Structural ↑ | ❌ No | ❌ Missing | **HIGH** |
| Cluster Boundary Walker | Semantic ↑, Cluster ↓ | ✅ Sentiment only | ❌ Missing | **HIGH** |
| Accelerating Divergence | Drift ↑, Acceleration ↑ | ❌ No | ❌ Missing | **HIGH** |
| Format Template Emergence | Content ↓, Structural ↑ | ❌ No | ❌ Missing | **CRITICAL** |
| Hub Migration | Graph ↑, Cluster stable | ❌ No | ❌ Missing | Medium |
| Temporal Decoupling | Semantic stable, Temporal ↓ | ❌ No | ❌ Missing | Medium |
| Cyclical Convergence | Semantic ↓ then ↑ | ❌ No | ✅ Implemented (`cyclical_thinking`) | ✅ Done |
| Bridge Collapse | Semantic ↑, Graph path ↑ | ❌ No | ❌ Missing | **HIGH** |

---

### 3.2 Detailed Missing Geist Specifications

#### CRITICAL Priority (4 geists)

##### 1. **phantom_link** (Semantic-Graph)

**Pattern**: OPPOSING_MOVEMENT (or DECOUPLED_MOVEMENT if weakly correlated)

**Dimensions**:
- Semantic embedding ↑ (closer, similarity increasing)
- Graph distance ↓ (farther, shortest path increasing)

**Detection Algorithm**:
```python
def detect_phantom_link(vault: VaultContext) -> list[Suggestion]:
    """Find semantically converging notes with weakening graph connections."""
    sessions = get_sessions(vault, min_count=3)
    note_pairs = sample_note_pairs(vault.notes(), k=100)

    results = []
    for note_a, note_b in note_pairs:
        # Semantic trajectory
        sem_t0 = semantic_similarity(note_a, note_b, session=sessions[0])
        sem_t1 = semantic_similarity(note_a, note_b, session=sessions[-1])
        sem_delta = sem_t1 - sem_t0

        # Graph trajectory
        graph_t0 = graph_distance(note_a, note_b, session=sessions[0])
        graph_t1 = graph_distance(note_a, note_b, session=sessions[-1])
        graph_delta = graph_t1 - graph_t0

        # Pattern: semantic converging + graph diverging
        if sem_delta > 0.15 and sem_t1 > 0.7 and graph_delta >= 2:
            results.append((note_a, note_b, sem_t1, sem_delta, graph_t1, graph_delta))

    # Return top 2-3
    results.sort(key=lambda x: x[3], reverse=True)  # Sort by semantic delta

    for note_a, note_b, sem_sim, sem_delta, graph_dist, graph_delta in results[:3]:
        yield Suggestion(
            text=f"[[{note_a.title}]] and [[{note_b.title}]] are semantically "
                 f"converging ({sem_sim:.2f} similarity, +{sem_delta:.2f}) but their "
                 f"graph distance increased (now {graph_dist} hops, +{graph_delta}). "
                 f"You're thinking similar thoughts but forgetting to connect them.",
            notes=[note_a.title, note_b.title]
        )
```

**Provocation Template**:
> "[[A]] and [[B]] are semantically converging (0.82 similarity, +0.21 from first session) but their graph distance increased from 2 to 5 hops. You're thinking similar thoughts but forgetting to connect them."

**Why CRITICAL**:
- Common UX issue (users don't remember to link semantically related notes)
- Directly actionable (suggests missing links)
- Leverages existing infrastructure (semantic similarity + graph queries)

**Estimated Implementation Effort**: 2-3 hours
- Session embedding queries: 30 min
- Graph distance tracking: 1 hour (may need new session_graph_distances table)
- Detector logic: 30 min
- Tests: 1 hour

---

##### 2. **format_template_emergence** (Content-Structural)

**Pattern**: TEMPLATE_EMERGENCE

**Dimensions**:
- Content properties ↓ (divergent: different topics, word counts, lexical diversity)
- Structural properties ↑ (convergent: similar heading counts, task counts, code blocks)

**Detection Algorithm**:
```python
def detect_format_template_emergence(vault: VaultContext) -> list[Suggestion]:
    """Find notes adopting similar structure despite different content."""
    sessions = get_sessions(vault, min_count=2)
    notes = vault.notes()

    # Group notes by structural signature
    structural_groups = defaultdict(list)

    for note in notes:
        # Structural fingerprint
        struct_sig = (
            get_heading_count(note),
            get_task_count(note) // 2,  # Bucketed (0-2, 3-5, 6-8, etc.)
            get_code_block_count(note),
            get_list_item_count(note) // 5,  # Bucketed
        )
        structural_groups[struct_sig].append(note)

    # Find groups with low semantic similarity but consistent structure
    for struct_sig, group in structural_groups.items():
        if len(group) < 3:
            continue

        # Compute average pairwise semantic similarity
        similarities = [
            semantic_similarity(a, b)
            for a, b in combinations(group, 2)
        ]
        avg_sim = mean(similarities)

        # Low semantic similarity + consistent structure = template
        if avg_sim < 0.4 and len(group) >= 3:
            heading_count, task_bucket, code_count, list_bucket = struct_sig
            task_count = task_bucket * 2 + 1  # Representative value
            list_count = list_bucket * 5 + 2

            yield Suggestion(
                text=f"{', '.join(['[[' + n.title + ']]' for n in group[:3]])} "
                     f"cover different topics (avg similarity: {avg_sim:.2f}) but all have "
                     f"{heading_count} headings, {task_count}-{task_count+2} tasks, "
                     f"{code_count} code blocks, and {list_count}-{list_count+5} list items. "
                     f"You've developed a template without documenting it—should this be formalized?",
                notes=[n.title for n in group[:5]],
                title=f"Implicit Template: {heading_count}H-{task_count}T-{code_count}C"
            )
```

**Provocation Template**:
> "[[A]], [[B]], and [[C]] cover different topics (avg similarity: 0.34) but all have 3 headings, 5-7 tasks, and 2 code blocks. You've developed a template without documenting it—should this be formalized?"

**Why CRITICAL**:
- Reveals unconscious patterns in note-taking
- Highly actionable (formalize template, create snippet)
- Unique insight (no other geist detects this)
- Low false positive rate (structural convergence is rare by chance)

**Estimated Implementation Effort**: 3-4 hours
- Structural property extraction: 1 hour (heading/task/code parsing)
- Similarity computation: 1 hour
- Grouping logic: 1 hour
- Tests: 1 hour

---

##### 3. **bridge_collapse** (Semantic-Graph Path)

**Pattern**: OPPOSING_MOVEMENT (semantic converging, graph path diverging)

**Dimensions**:
- Semantic similarity ↑ (closer)
- Graph shortest path ↑ (longer, intermediate links deleted)

**Detection Algorithm**:
```python
def detect_bridge_collapse(vault: VaultContext) -> list[Suggestion]:
    """Find semantically converging notes with weakening graph paths."""
    sessions = get_sessions(vault, min_count=3)
    note_pairs = sample_note_pairs(vault.notes(), k=100)

    results = []
    for note_a, note_b in note_pairs:
        # Semantic trajectory
        sem_t0 = semantic_similarity(note_a, note_b, session=sessions[0])
        sem_t1 = semantic_similarity(note_a, note_b, session=sessions[-1])
        sem_delta = sem_t1 - sem_t0

        # Graph path trajectory
        path_t0 = shortest_path_length(note_a, note_b, session=sessions[0])
        path_t1 = shortest_path_length(note_a, note_b, session=sessions[-1])
        path_delta = path_t1 - path_t0

        # Pattern: semantic converging + path lengthening
        if sem_delta > 0.15 and path_delta >= 2 and path_t0 <= 3:
            # Identify deleted intermediate notes (if possible)
            deleted_bridges = identify_deleted_bridges(note_a, note_b, sessions)

            results.append((
                note_a, note_b,
                sem_t0, sem_t1, sem_delta,
                path_t0, path_t1, path_delta,
                deleted_bridges
            ))

    # Return top 2-3
    results.sort(key=lambda x: x[4], reverse=True)  # Sort by semantic delta

    for note_a, note_b, sem_t0, sem_t1, sem_delta, path_t0, path_t1, path_delta, bridges in results[:3]:
        bridge_msg = ""
        if bridges:
            bridge_msg = f" (deleted intermediate notes: {', '.join(['[[' + b + ']]' for b in bridges])})"

        yield Suggestion(
            text=f"[[{note_a.title}]] and [[{note_b.title}]] are converging semantically "
                 f"({sem_t0:.2f} → {sem_t1:.2f}) but their graph distance increased from "
                 f"{path_t0} to {path_t1} hops{bridge_msg}. You deleted the bridges between "
                 f"similar ideas—should they be reconnected?",
            notes=[note_a.title, note_b.title]
        )
```

**Provocation Template**:
> "[[A]] and [[B]] are converging semantically (0.65 → 0.82) but their graph distance increased from 2 to 5 hops (deleted intermediate notes: [[C]], [[D]]). You deleted the bridges between similar ideas—should they be reconnected?"

**Why CRITICAL**:
- Detects information architecture degradation
- Actionable (restore deleted links or create new bridges)
- Combines graph topology + semantics (unique insight)

**Estimated Implementation Effort**: 4-5 hours
- Session graph path tracking: 2 hours (needs historical graph state)
- Deleted bridge identification: 1 hour (challenging without explicit deletion tracking)
- Detector logic: 1 hour
- Tests: 1 hour

---

##### 4. **ghost_connection** (Semantic-Graph) [Enhance existing]

**Pattern**: OPPOSING_MOVEMENT (semantic diverging, graph stable/linked)

**Dimensions**:
- Semantic similarity ↓ (farther)
- Graph distance stable (direct link exists) or 0 (directly linked)

**Current Status**: Partially implemented by `divergent_evolution.py`

**Gap Analysis**:
```python
# divergent_evolution.py (current implementation)
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Find linked notes that are semantically diverging."""
    # Only checks LINKED notes (backlinks)
    # Does NOT:
    #   1. Track multi-session semantic decline
    #   2. Generate "ghost connection" framing
    #   3. Suggest link removal vs content alignment
```

**Enhancement Needed**:
1. Add multi-session trajectory tracking (not just current similarity)
2. Compute rate of semantic decline
3. More provocative framing: "Does this connection still make sense?"
4. Suggest TWO actions: (a) remove link, or (b) align content

**Provocation Template** (enhanced):
> "[[A]] links to [[B]], but they've diverged from 0.78 to 0.41 similarity across 8 sessions (declining at -0.05/session). Does this connection still make sense, or should you update [[A]] to explain why it links to [[B]]?"

**Why CRITICAL**:
- Maintains graph quality (removes stale links)
- Already partially implemented (low effort to enhance)
- Directly actionable

**Estimated Implementation Effort**: 1-2 hours
- Add session trajectory tracking: 30 min
- Enhanced provocation: 30 min
- Tests: 30 min

---

#### HIGH Priority (6 geists)

##### 5. **style_convergence** (Semantic-Structural)

**Pattern**: OPPOSING_MOVEMENT (semantic diverging, structural converging)

**Similar to**: `format_template_emergence` but detects *temporal convergence* (notes becoming more similar structurally over time)

**Provocation**: "Are you developing a template without realizing it?"

**Estimated Effort**: 3 hours

---

##### 6. **cluster_boundary_walker** (Semantic-Cluster) [General version]

**Pattern**: BOUNDARY_WALKER

**Current**: Only sentiment version specified (`sentiment_cluster_boundary`)

**Need**: General version that works with semantic clusters, not emotional clusters

**Provocation**: "Are they bridging these domains—should they be linked?"

**Estimated Effort**: 2-3 hours (can reuse sentiment version logic)

---

##### 7. **velocity_mismatch** (Trajectory Direction-Velocity) [General version]

**Pattern**: VELOCITY_MISMATCH

**Current**: Only sentiment version specified (`sentiment_velocity_mismatch`)

**Need**: General version for semantic drift, not emotional drift

**Provocation**: "Why is one note accelerating while the other lags?"

**Estimated Effort**: 2-3 hours (can reuse sentiment version logic)

---

##### 8. **trajectory_reversal** (Semantic-Drift) [General version]

**Pattern**: TRAJECTORY_REVERSAL

**Current**: Only sentiment version specified (`sentiment_trajectory_reversal`)

**Need**: General version for semantic similarity vs drift vectors

**Provocation**: "They're converging now but will diverge soon"

**Estimated Effort**: 2-3 hours (can reuse sentiment version logic)

---

##### 9. **maintenance_asymmetry** (Semantic-Staleness) [General version]

**Pattern**: MAINTENANCE_DIVERGENCE

**Current**: Only sentiment version specified (`sentiment_maintenance_asymmetry`)

**Need**: General version for semantic similarity vs staleness

**Provocation**: "Why maintain one twin but abandon the other?"

**Estimated Effort**: 2 hours (can reuse sentiment version logic)

---

##### 10. **accelerating_divergence** (Drift-Acceleration)

**Pattern**: ACCELERATION_ASYMMETRY (or VELOCITY + ACCELERATION)

**Dimensions**:
- Total drift ↑ (notes diverging)
- Drift acceleration ↑ (rate of divergence increasing)

**Detection**: Positive second derivative of similarity trajectory

**Provocation**: "What inflection point occurred in session N?"

**Estimated Effort**: 2-3 hours (can leverage `drift_velocity_anomaly` methods)

---

#### MEDIUM Priority (4 geists)

##### 11. **seasonal_drift** (Semantic-Temporal Embedding)

**Pattern**: DECOUPLED_MOVEMENT

**Provocation**: "Does this note mean something different in winter vs summer?"

**Estimated Effort**: 2 hours

---

##### 12. **content_freeze** (Semantic-Staleness)

**Pattern**: MAINTENANCE_DIVERGENCE (single note version)

**Current**: Partially covered by `temporal_drift`

**Enhancement needed**: Focus on high-staleness + high-connectivity (frozen hubs)

**Provocation**: "A well-connected hub frozen in time—does it still represent your thinking?"

**Estimated Effort**: 1-2 hours (enhance `temporal_drift`)

---

##### 13. **hub_migration** (Graph-Cluster)

**Pattern**: DECOUPLED_MOVEMENT

**Provocation**: "Semantic twins with different social circles?"

**Estimated Effort**: 3 hours

---

##### 14. **temporal_decoupling** (Semantic-Temporal Embedding)

**Pattern**: DECOUPLED_MOVEMENT

**Provocation**: "How does time change meaning even without edits?"

**Estimated Effort**: 2 hours

---

#### LOW Priority (3 geists)

##### 15. **orthogonal_drift** (Space A - Space B)

**Pattern**: ORTHOGONAL_DRIFT

**Detection**: Drift in one embedding space perpendicular to drift in another

**Use case**: Research tool for understanding dimensional independence

**Estimated Effort**: 3-4 hours

---

##### 16. **correlated_movement** (Dimension A - Dimension B)

**Pattern**: CORRELATED_MOVEMENT

**Detection**: Movement in dimension A predicts movement in dimension B

**Use case**: Meta-analysis, understanding vault dynamics

**Estimated Effort**: 3-4 hours

---

##### 17. **multidimensional_convergence** (All Dimensions)

**Pattern**: MULTIDIMENSIONAL_CONVERGENCE

**Detection**: Profile of convergence/divergence across all 8 dimensions

**Use case**: Comprehensive note pair analysis

**Estimated Effort**: 4-5 hours (requires unified multidimensional framework)

---

## 4. Implementation Roadmap

### Phase 1: Critical Patterns (4 geists, ~12-15 hours)
**Goal**: Implement highest-impact multidimensional geists

1. **phantom_link** (2-3 hours)
   - Requires: Session graph distance tracking
   - Impact: High (common UX issue, actionable)

2. **format_template_emergence** (3-4 hours)
   - Requires: Structural property extraction
   - Impact: High (unique insight, reveals unconscious patterns)

3. **bridge_collapse** (4-5 hours)
   - Requires: Historical graph path tracking
   - Impact: High (graph quality maintenance)

4. **ghost_connection** enhancement (1-2 hours)
   - Requires: Minimal (enhance existing `divergent_evolution`)
   - Impact: High (low-effort, high-value)

**Deliverables**: 4 new multidimensional geists, 1 enhanced geist

---

### Phase 2: General Versions of Sentiment Patterns (5 geists, ~12-15 hours)
**Goal**: Implement general versions of sentiment-specific patterns

5. **cluster_boundary_walker** (2-3 hours)
6. **velocity_mismatch** (2-3 hours)
7. **trajectory_reversal** (2-3 hours)
8. **maintenance_asymmetry** (2 hours)
9. **accelerating_divergence** (2-3 hours)

**Deliverables**: 5 general multidimensional geists (can reuse sentiment logic)

---

### Phase 3: Medium Priority Patterns (4 geists, ~8-10 hours)
**Goal**: Fill remaining gaps in pattern coverage

10. **seasonal_drift** (2 hours)
11. **content_freeze** enhancement (1-2 hours)
12. **hub_migration** (3 hours)
13. **temporal_decoupling** (2 hours)

**Deliverables**: 4 additional multidimensional geists

---

### Phase 4: Research/Meta Patterns (3 geists, ~10-13 hours)
**Goal**: Meta-analysis and research tools

14. **orthogonal_drift** (3-4 hours)
15. **correlated_movement** (3-4 hours)
16. **multidimensional_convergence** (4-5 hours)

**Deliverables**: 3 meta-analysis geists

---

## 5. Infrastructure Requirements

### 5.1 Database Schema Extensions

**New table: `session_graph_distances`**
```sql
CREATE TABLE session_graph_distances (
    session_id INTEGER NOT NULL,
    note_a_path TEXT NOT NULL,
    note_b_path TEXT NOT NULL,
    distance INTEGER NOT NULL,  -- Shortest path length (-1 if no path)
    PRIMARY KEY (session_id, note_a_path, note_b_path),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_session_graph_pair ON session_graph_distances(session_id, note_a_path, note_b_path);
CREATE INDEX idx_graph_pair_session ON session_graph_distances(note_a_path, note_b_path, session_id);
```

**New table: `session_structural_properties`**
```sql
CREATE TABLE session_structural_properties (
    session_id INTEGER NOT NULL,
    note_path TEXT NOT NULL,
    heading_count INTEGER DEFAULT 0,
    task_count INTEGER DEFAULT 0,
    completed_task_count INTEGER DEFAULT 0,
    code_block_count INTEGER DEFAULT 0,
    list_item_count INTEGER DEFAULT 0,
    has_frontmatter BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (session_id, note_path),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_session_structural ON session_structural_properties(session_id, note_path);
```

**Enhancement: `session_embeddings` table**
```sql
-- Add cluster_id and cluster_label if not already present
ALTER TABLE session_embeddings ADD COLUMN cluster_id INTEGER DEFAULT -1;
ALTER TABLE session_embeddings ADD COLUMN cluster_label TEXT DEFAULT 'noise';
```

---

### 5.2 VaultContext API Extensions

**New methods needed**:
```python
class VaultContext:
    # Graph queries
    def graph_distance_trajectory(
        self, note_a: Note, note_b: Note
    ) -> list[tuple[datetime, int]]:
        """Returns [(session_date, shortest_path_length), ...] for note pair."""
        pass

    def shortest_path(
        self, note_a: Note, note_b: Note, session: datetime | None = None
    ) -> list[Note] | None:
        """Returns shortest path between notes at given session."""
        pass

    # Structural queries
    def structural_similarity(
        self, note_a: Note, note_b: Note, session: datetime | None = None
    ) -> float:
        """Returns structural similarity (0-1) based on heading/task/code counts."""
        pass

    def get_structural_properties(
        self, note: Note, session: datetime | None = None
    ) -> dict[str, int | bool]:
        """Returns structural fingerprint: heading_count, task_count, etc."""
        pass

    # Temporal embedding queries
    def temporal_embedding_similarity(
        self, note_a: Note, note_b: Note, session: datetime | None = None
    ) -> float:
        """Returns temporal embedding similarity (includes 3 temporal features)."""
        pass

    # Staleness queries
    def staleness_score(self, note: Note) -> float:
        """Returns staleness score (0-1) based on days since modified."""
        pass

    def staleness_difference(self, note_a: Note, note_b: Note) -> float:
        """Returns absolute staleness difference."""
        pass
```

---

### 5.3 Session Tracking Enhancements

**Graph distance tracking** (for `phantom_link`, `bridge_collapse`, `hub_migration`):
- Compute shortest path for sampled note pairs each session
- Store in `session_graph_distances` table
- Sample strategy:
  - All linked pairs (direct connections)
  - Top 100 semantically similar pairs (>0.6 similarity)
  - Random sample of 100 pairs

**Structural property tracking** (for `format_template_emergence`, `style_convergence`):
- Extract heading count, task count, code block count per note each session
- Store in `session_structural_properties` table

**Cluster membership tracking** (already partially implemented):
- Ensure `session_embeddings.cluster_id` and `cluster_label` are populated
- Verify HDBSCAN clustering runs each session

---

## 6. Testing Strategy

### 6.1 Known-Answer Tests

**Phantom Link**:
```python
def test_phantom_link_detection():
    """Test that semantically converging + graph diverging pairs are detected."""
    vault = create_test_vault()

    # Session 1: Notes A and B are 0.5 similar, 2 hops apart
    # Session 2: Notes A and B are 0.7 similar, 3 hops apart (bridge deleted)
    # Session 3: Notes A and B are 0.85 similar, 4 hops apart

    suggestions = phantom_link.suggest(vault)

    assert len(suggestions) >= 1
    assert any("[[A]]" in s.text and "[[B]]" in s.text for s in suggestions)
    assert any("converging" in s.text and "graph distance" in s.text for s in suggestions)
```

**Format Template Emergence**:
```python
def test_format_template_emergence():
    """Test that structurally similar but semantically different notes are detected."""
    vault = create_test_vault()

    # Notes A, B, C: Different topics (0.2 similarity) but all have:
    # - 3 headings
    # - 5-7 tasks
    # - 2 code blocks

    suggestions = format_template_emergence.suggest(vault)

    assert len(suggestions) >= 1
    assert any("3 headings" in s.text and "5-7 tasks" in s.text for s in suggestions)
    assert any("template" in s.text.lower() for s in suggestions)
```

---

### 6.2 Integration Tests

- Test with kepano vault (testdata/kepano-obsidian-main/)
- Verify no crashes on empty vaults
- Verify performance (< 30s timeout)
- Verify novelty filtering doesn't over-filter

---

### 6.3 Regression Tests

**Prevent Phase 3B-style regressions**:
- Document why sampling is/isn't used
- Profile before optimizing
- Verify cache benefits

---

## 7. Summary Statistics

### Current State
- **Implemented geists**: 51 (42 code + 9 Tracery)
- **Specified geists**: 37 (sentiment only, not implemented)
- **Multidimensional patterns identified**: 15
- **Multidimensional patterns specified**: 6 (sentiment only)
- **Multidimensional patterns implemented**: 0

### Gap Analysis
- **Missing general multidimensional geists**: 15
- **Missing sentiment implementations**: 37
- **Total missing multidimensional geists**: 52 (15 general + 37 sentiment)

### Implementation Effort Estimate
- **Phase 1 (Critical)**: 12-15 hours → 4 geists
- **Phase 2 (General versions)**: 12-15 hours → 5 geists
- **Phase 3 (Medium priority)**: 8-10 hours → 4 geists
- **Phase 4 (Research)**: 10-13 hours → 3 geists
- **Total**: 42-53 hours → 16 general multidimensional geists

### Potential Geist Count (Post-Implementation)
- **Current**: 51 geists
- **After sentiment implementation**: 88 geists (+37)
- **After multidimensional implementation**: 67 geists (+16 general)
- **Total potential**: 104 geists (51 current + 37 sentiment + 16 multidimensional)

---

## 8. Recommendations

### Immediate Actions

1. **Implement Phase 1 (Critical)** → 4 high-impact geists in ~15 hours
   - `phantom_link`: Most common UX issue (forgetting to link similar ideas)
   - `format_template_emergence`: Unique insight, reveals unconscious patterns
   - `bridge_collapse`: Graph quality maintenance
   - `ghost_connection` enhancement: Low effort, high value

2. **Add infrastructure** in parallel with Phase 1:
   - `session_graph_distances` table
   - `session_structural_properties` table
   - VaultContext API extensions

3. **Test on production vaults** (kepano, large vaults) to validate:
   - Performance (< 30s timeout)
   - Quality (novelty, diversity filtering)
   - Actionability (suggestions lead to vault improvements)

### Future Directions

4. **Phase 2: General versions** → Maximize ROI by reusing sentiment geist logic

5. **Phase 3: Medium priority** → Fill remaining pattern gaps

6. **Phase 4: Research patterns** → Meta-analysis tools for advanced users

---

## 9. Open Questions

1. **Session graph distance tracking**:
   - How to sample note pairs efficiently? (all linked + top-N semantic + random?)
   - Storage cost: 100 pairs × 100 sessions = 10K rows per vault

2. **Deleted bridge identification**:
   - How to track which notes were deleted between sessions?
   - Currently no deletion tracking in vault.db

3. **Structural property extraction**:
   - Should this be a metadata inference module?
   - Or inline during session sync?

4. **Multidimensional framework**:
   - Should there be a unified `MultiDimensionalAnalyzer` class?
   - Or individual geists with shared utility functions?

---

**End of Analysis**
