# Multidimensional Movement Analysis: GeistFabrik Note Trajectories

## Executive Summary

This document catalogues all the ways notes can move closer together or farther apart in GeistFabrik's multidimensional space, identifying **non-obvious combinations** where notes move in different directions across different dimensions, and proposing extensions to the primitive pattern taxonomy.

**Key Finding**: Notes exist in at least **8 distinct dimensional spaces**, and movement in one dimension is often **independent** or even **inversely correlated** with movement in others. This creates a rich landscape of multidimensional movement patterns that current geists only partially exploit.

---

## 1. Dimension Catalog

GeistFabrik tracks notes across eight primary dimensional spaces:

### 1.1 Semantic Embedding Space
- **Dimensionality**: 384 (all-MiniLM-L6-v2 model)
- **Nature**: Dense vector representation of note content meaning
- **Metric**: Cosine similarity (0-1)
- **Change drivers**: Content edits, semantic shifts
- **Stability**: Only changes when note content is modified

### 1.2 Temporal Embedding Space
- **Dimensionality**: 387 (384 semantic + 3 temporal features)
- **Temporal features**:
  - Note age (days since creation / 365)
  - Creation season (sin encoding of day-of-year)
  - Session season (sin encoding of current date)
- **Metric**: Cosine similarity (0-1)
- **Change drivers**: Content edits + time passage
- **Stability**: Changes EVERY session even if content is unchanged (due to temporal drift)

### 1.3 Graph Structure Space
- **Dimensions**:
  - Link distance (shortest path length)
  - Backlink count
  - Outgoing link count
  - Degree centrality
  - Hub/orphan status
- **Metric**: Graph distance (discrete), link counts (integer)
- **Change drivers**: Creating/deleting links between notes
- **Stability**: Changes only when graph topology changes

### 1.4 Temporal Trajectory Space
- **Dimensions**:
  - Total drift (1 - similarity between first and last embeddings)
  - Drift direction vector (unit vector in embedding space)
  - Drift velocity (drift per session window)
  - Drift acceleration (change in velocity)
- **Metric**: Vector alignment (-1 to 1), magnitude (0-2)
- **Change drivers**: Accumulation of semantic changes across sessions
- **Stability**: Requires multiple sessions to compute; monotonically accumulates

### 1.5 Cluster Membership Space
- **Dimensions**:
  - Cluster ID (categorical)
  - Cluster label (semantic description)
  - Distance to cluster centroid (continuous)
  - Cluster size (integer)
- **Metric**: Cluster overlap (Jaccard), centroid distance
- **Change drivers**: Semantic shifts + HDBSCAN reclustering
- **Stability**: Changes when note crosses cluster boundaries

### 1.6 Content Property Space
- **Dimensions**:
  - Word count
  - Lexical diversity (unique words / total words)
  - Average word length
  - Sentence count
  - Phrase overlap with other notes
- **Metric**: Euclidean distance, ratio differences
- **Change drivers**: Content edits (length, style, vocabulary)
- **Stability**: Changes only with content modifications

### 1.7 Structural Property Space
- **Dimensions**:
  - Heading count
  - Task count / completion rate
  - Code block count
  - List item count
  - Has frontmatter (boolean)
- **Metric**: Count differences, structural similarity
- **Change drivers**: Formatting changes, reorganization
- **Stability**: Changes with structural edits

### 1.8 Staleness/Freshness Space
- **Dimensions**:
  - Days since modified
  - Days since created
  - Staleness score (0-1, asymptotic)
  - Recency flags (is_recent, is_old)
- **Metric**: Time delta (days), staleness ratio
- **Change drivers**: Time passage + modification events
- **Stability**: Monotonically increases until modification resets it

---

## 2. Movement Patterns by Dimension

### 2.1 Semantic Embedding Space

#### Ways to Move Closer
1. **Content alignment**: Adding similar topics, concepts, or vocabulary
2. **Semantic refinement**: Clarifying ideas in similar directions
3. **Topic merging**: Converging on same subject matter
4. **Style harmonization**: Adopting similar writing style/terminology
5. **Quote/citation overlap**: Referencing same sources

#### Ways to Move Farther Apart
1. **Topic divergence**: Exploring different subject matter
2. **Conceptual refactoring**: Splitting merged concepts
3. **Perspective shift**: Changing viewpoint on same topic
4. **Specialization**: One note becoming more technical/specific
5. **Generalization**: One note becoming more abstract/broad

### 2.2 Temporal Embedding Space

#### Ways to Move Closer
1. **Synchronized temporal features**: Notes created in same season, viewed in same session
2. **Age convergence**: Notes aging toward similar maturity
3. **Seasonal alignment**: Both notes associated with same seasonal context
4. **Content + time alignment**: Both semantic similarity + temporal proximity

#### Ways to Move Farther Apart
1. **Temporal drift**: Time passage increasing temporal distance
2. **Seasonal divergence**: Creation seasons becoming more distinct relative to current season
3. **Age gap widening**: One note aging faster (unmodified) vs recently updated note
4. **Content + time divergence**: Semantic divergence amplified by temporal features

### 2.3 Graph Structure Space

#### Ways to Move Closer
1. **Direct linking**: Creating link from A to B or B to A
2. **Bridge creation**: Adding intermediate notes that connect A and B
3. **Mutual neighbor increase**: Both notes linking to more common notes
4. **Cluster densification**: Adding links within same neighborhood
5. **Hub convergence**: Both notes linking to same hub

#### Ways to Move Farther Apart
1. **Link deletion**: Removing direct or indirect connections
2. **Bridge removal**: Deleting intermediate notes on shortest path
3. **Cluster separation**: Notes moving to different graph communities
4. **Orphan drift**: One note losing all connections
5. **Hub divergence**: Linking to different hubs

### 2.4 Temporal Trajectory Space

#### Ways to Move Closer (Aligned Drift)
1. **Parallel evolution**: Both drift in same semantic direction
2. **Convergent trajectories**: Drift directions pointing toward each other
3. **Synchronized velocity**: Both changing at similar rate
4. **Coordinated acceleration**: Both speeding up or slowing down together

#### Ways to Move Farther Apart (Divergent Drift)
1. **Opposite drift directions**: Moving in anti-parallel directions
2. **Divergent trajectories**: Drift vectors pointing away from each other
3. **Velocity mismatch**: One drifting rapidly, other stable
4. **Acceleration asymmetry**: One accelerating, other decelerating

### 2.5 Cluster Membership Space

#### Ways to Move Closer
1. **Same cluster membership**: Both notes assigned to same cluster
2. **Neighboring clusters**: In adjacent clusters with overlapping boundaries
3. **Centroid convergence**: Both moving toward same cluster centroid
4. **Co-migration**: Both migrating to same new cluster together

#### Ways to Move Farther Apart
1. **Cluster divergence**: Moving to different clusters
2. **Noise transition**: One note becoming noise (unclustered)
3. **Centroid divergence**: Moving toward different cluster centroids
4. **Split migration**: Previously same cluster, now separate clusters

### 2.6 Content Property Space

#### Ways to Move Closer
1. **Length convergence**: Word counts becoming similar
2. **Lexical diversity alignment**: Similar vocabulary richness
3. **Style matching**: Similar sentence structure, word length
4. **Phrase overlap increase**: Using same multi-word phrases

#### Ways to Move Farther Apart
1. **Length divergence**: One note expanding, other staying concise
2. **Complexity mismatch**: One becoming technical, other simple
3. **Style drift**: Different writing styles emerging
4. **Phrase overlap decrease**: Using different terminology

### 2.7 Structural Property Space

#### Ways to Move Closer
1. **Format harmonization**: Similar heading hierarchy
2. **Task alignment**: Both becoming task-heavy or task-free
3. **Code block matching**: Similar technical content
4. **List structure similarity**: Similar organization patterns

#### Ways to Move Farther Apart
1. **Format divergence**: Different structural patterns
2. **Task asymmetry**: One task-heavy, one narrative
3. **Technical/narrative split**: Code-heavy vs prose-heavy
4. **Organization mismatch**: Different hierarchical depth

### 2.8 Staleness/Freshness Space

#### Ways to Move Closer
1. **Synchronized updates**: Modified at similar times
2. **Age convergence**: Created at similar times
3. **Staleness alignment**: Both aging at similar rate
4. **Maintenance pattern matching**: Both updated or neglected together

#### Ways to Move Farther Apart
1. **Update asymmetry**: One frequently updated, other abandoned
2. **Age gap**: One old, one new
3. **Staleness divergence**: One fresh, one stale
4. **Maintenance pattern mismatch**: One actively maintained, other static

---

## 3. Multidimensional Movement Patterns

### 3.1 Pattern Matrix

This matrix shows **interesting combinations** where notes move in different directions across different dimensions:

| Pattern Name | Dimension A | Direction A | Dimension B | Direction B | Interpretation |
|--------------|-------------|-------------|-------------|-------------|----------------|
| **Phantom Link** | Semantic | Closer | Graph | Farther | Semantically similar but losing connection |
| **Ghost Connection** | Semantic | Farther | Graph | Closer | Linked but meaning diverging |
| **Seasonal Drift** | Semantic | Stable | Temporal Emb. | Farther | Same content, different temporal context |
| **Content Freeze** | Semantic | Stable | Staleness | Farther | Unchanged but aging |
| **Style Convergence** | Semantic | Farther | Structural | Closer | Different topics, similar organization |
| **Velocity Mismatch** | Trajectory Dir. | Aligned | Trajectory Vel. | Divergent | Same direction, different speed |
| **Cluster Boundary** | Semantic | Closer | Cluster | Farther | Semantically similar, different clusters |
| **Trajectory Reversal** | Semantic | Closer | Drift Vector | Opposite | Currently similar but drifting apart |
| **Accelerating Divergence** | Trajectory Drift | Farther | Drift Accel. | Increasing | Diverging faster over time |
| **Format Alignment** | Content Props | Divergent | Structural | Convergent | Different content, similar structure |
| **Maintenance Asymmetry** | Semantic | Closer | Staleness | Divergent | Similar content, different update patterns |
| **Hub Migration** | Graph Distance | Farther | Cluster | Closer | Different graph neighborhoods, same cluster |
| **Temporal Decoupling** | Semantic | Unchanged | Temporal Emb. | Farther | Content stable, temporal features changing |
| **Cyclical Convergence** | Semantic (early) | Farther | Semantic (late) | Closer | Returning to previous similarity |
| **Bridge Collapse** | Semantic | Closer | Graph | Farther (path) | Similar but losing intermediate links |

### 3.2 Detailed Pattern Analysis

#### Pattern: **Phantom Link**
- **Dimensions**: Semantic ↑ (closer), Graph ↓ (farther)
- **Detection**: High semantic similarity (>0.7) but decreasing graph distance (e.g., 2 hops → 4 hops)
- **Interpretation**: Notes are about similar topics but connection through graph is weakening
- **Provocative framing**: "[[A]] and [[B]] are semantically converging (0.82 similarity) but their graph distance is increasing (now 4 hops apart). You're thinking similar thoughts but forgetting to connect them."

#### Pattern: **Ghost Connection**
- **Dimensions**: Semantic ↓ (farther), Graph ↑ (closer) or stable
- **Detection**: Direct link exists but semantic similarity declining over sessions
- **Interpretation**: Old link that no longer reflects current understanding
- **Provocative framing**: "[[A]] links to [[B]], but they've diverged semantically from 0.78 to 0.41 similarity across 8 sessions. Does this connection still make sense?"
- **Implementation**: Already detected by `divergent_evolution` geist

#### Pattern: **Seasonal Drift**
- **Dimensions**: Semantic stable, Temporal Embedding ↓ (farther)
- **Detection**: Content unchanged (semantic similarity ≈1.0) but temporal embedding similarity decreasing
- **Interpretation**: Same content, different temporal context (season, age)
- **Provocative framing**: "[[A]]'s content hasn't changed, but its temporal embedding drifted from 0.91 to 0.73. Same words, different season—does this note mean something different in winter vs summer?"

#### Pattern: **Content Freeze**
- **Dimensions**: Semantic stable, Staleness ↑ (higher)
- **Detection**: No content changes but staleness score increasing (>0.7)
- **Interpretation**: Static note aging without revision
- **Provocative framing**: "[[A]] hasn't changed in 247 days (staleness: 0.89) but has 12 backlinks. A well-connected hub that's frozen in time—does it still represent your thinking?"
- **Implementation**: Partially detected by `temporal_drift` geist

#### Pattern: **Style Convergence**
- **Dimensions**: Semantic ↓ (farther), Structural ↑ (closer)
- **Detection**: Decreasing semantic similarity but increasing structural similarity
- **Interpretation**: Different topics adopting similar organizational patterns
- **Provocative framing**: "[[A]] and [[B]] are semantically unrelated (0.32 similarity) but structurally converging: both now have 4 headings, 8 tasks, 2 code blocks. Are you developing a template without realizing it?"

#### Pattern: **Velocity Mismatch**
- **Dimensions**: Drift direction aligned (>0.5), Drift velocity divergent
- **Detection**: Similar drift vectors but different drift rates per session
- **Interpretation**: Moving in same direction but at different speeds
- **Provocative framing**: "[[A]] and [[B]] are both drifting toward 'system design' (alignment: 0.73) but [[A]] is moving 3x faster. Why is one note accelerating while the other lags?"

#### Pattern: **Cluster Boundary Walker**
- **Dimensions**: Semantic ↑ (closer), Cluster membership ↓ (different clusters)
- **Detection**: High pairwise similarity but assigned to different clusters
- **Interpretation**: Similar notes separated by clustering algorithm (near cluster boundary)
- **Provocative framing**: "[[A]] (cluster: 'productivity') and [[B]] (cluster: 'creativity') are 0.79 similar but in different conceptual neighborhoods. Are they bridging these domains?"

#### Pattern: **Trajectory Reversal**
- **Dimensions**: Current semantic ↑ (closer), Historical drift direction opposite
- **Detection**: Currently similar but drift vectors pointing away from each other
- **Interpretation**: Temporarily aligned but underlying trajectories diverging
- **Provocative framing**: "[[A]] and [[B]] are currently 0.81 similar, but their drift vectors are anti-aligned (-0.62). They're converging now but their trajectories suggest they'll diverge soon."

#### Pattern: **Accelerating Divergence**
- **Dimensions**: Total drift ↑ (farther), Drift acceleration ↑ (increasing rate)
- **Detection**: Drift increasing AND rate of drift increasing (positive second derivative)
- **Interpretation**: Divergence speeding up over time
- **Provocative framing**: "[[A]] and [[B]] were 0.89 similar 6 sessions ago, now 0.52, and the divergence is accelerating. What inflection point occurred in session 4?"
- **Implementation**: Can be detected with `drift_velocity_anomaly` geist methods

#### Pattern: **Format Template Emergence**
- **Dimensions**: Content properties divergent, Structural properties convergent
- **Detection**: Different word counts/lexical diversity but similar heading/task/list counts
- **Interpretation**: Unconscious template development
- **Provocative framing**: "[[A]], [[B]], and [[C]] cover different topics (avg similarity: 0.34) but all have 3 headings, 5-7 tasks, and 2 code blocks. You've developed a template without documenting it."

#### Pattern: **Maintenance Asymmetry**
- **Dimensions**: Semantic ↑ (closer), Staleness ↓ (divergent)
- **Detection**: Similar content but very different staleness scores (>0.4 difference)
- **Interpretation**: One note actively maintained, other neglected
- **Provocative framing**: "[[A]] (staleness: 0.12, updated 5 days ago) and [[B]] (staleness: 0.87, updated 231 days ago) are 0.76 similar. Why maintain one twin but abandon the other?"

#### Pattern: **Hub Migration**
- **Dimensions**: Graph distance ↑ (farther), Cluster membership ↑ (closer/same)
- **Detection**: Increasing graph distance but same cluster
- **Interpretation**: Semantically grouped but graph neighborhoods diverging
- **Provocative framing**: "[[A]] and [[B]] are in the same cluster ('PKM tools') but their graph distance increased from 2 to 5 hops. Semantic twins with different social circles?"

#### Pattern: **Temporal Decoupling**
- **Dimensions**: Semantic embedding stable, Temporal embedding ↓ (farther)
- **Detection**: Semantic similarity ≈1.0 but temporal embedding similarity decreasing across sessions
- **Interpretation**: Content unchanged but temporal features shifting
- **Provocative framing**: "[[A]]'s semantic embedding is unchanged (similarity: 0.99) but its temporal embedding drifted 0.18 over 4 sessions. How does the passage of time change meaning even without edits?"

#### Pattern: **Cyclical Convergence**
- **Dimensions**: Early semantic ↓ (farther), Late semantic ↑ (closer)
- **Detection**: Similarity decreases then increases across session history
- **Interpretation**: Cyclical thinking—returning to previous understanding
- **Provocative framing**: "[[A]] and [[B]] were 0.82 similar, diverged to 0.51, and are converging again to 0.78. You're circling back to an old connection—what changed to make it relevant again?"
- **Implementation**: Detected by `cyclical_thinking` geist's `find_cycling_notes`

#### Pattern: **Bridge Collapse**
- **Dimensions**: Semantic ↑ (closer), Graph path length ↑ (farther)
- **Detection**: Increasing semantic similarity but increasing shortest path length
- **Interpretation**: Notes becoming more similar but intermediate links being removed
- **Provocative framing**: "[[A]] and [[B]] are converging semantically (0.65 → 0.82) but their graph distance increased from 2 hops to 5 hops. You deleted the bridges between similar ideas."

---

## 4. Mathematical Characterization

### 4.1 Movement Metrics

For any note pair (A, B) and dimension D:

**Direction**:
```
direction_D(A, B) = sign(similarity_D(A, B, t+1) - similarity_D(A, B, t))
  = +1 (closer), -1 (farther), 0 (stable)
```

**Magnitude**:
```
magnitude_D(A, B) = |similarity_D(A, B, t+1) - similarity_D(A, B, t)|
```

**Velocity**:
```
velocity_D(A, B) = Δsimilarity_D(A, B) / Δt
  (change in similarity per session)
```

**Acceleration**:
```
acceleration_D(A, B) = Δvelocity_D(A, B) / Δt
  (change in velocity per session)
```

**Correlation across dimensions**:
```
correlation(D1, D2) = pearsonr(
  [similarity_D1(A, B, t) for t in sessions],
  [similarity_D2(A, B, t) for t in sessions]
)
```

### 4.2 Multidimensional Movement Signature

Each note pair can be characterized by a **movement signature vector**:

```python
signature(A, B) = [
  direction_semantic(A, B),
  direction_temporal_emb(A, B),
  direction_graph(A, B),
  direction_drift_alignment(A, B),
  direction_cluster(A, B),
  direction_content(A, B),
  direction_structural(A, B),
  direction_staleness(A, B),
]
```

**Example signatures**:
- Phantom Link: `[+1, +1, -1, 0, 0, 0, 0, -1]` (semantic closer, graph farther, staleness diverging)
- Ghost Connection: `[-1, -1, 0, -1, 0, 0, 0, 0]` (semantic farther, temporal farther, graph stable)
- Style Convergence: `[-1, -1, 0, 0, 0, -1, +1, 0]` (semantic farther, structural closer)

### 4.3 Orthogonality of Dimensions

Key insight: Many dimensions are **mathematically orthogonal** (independent):

1. **Semantic vs Graph**: r ≈ 0.3 (weak correlation)
   - Many linked notes are not semantically similar
   - Many similar notes are not linked

2. **Semantic vs Staleness**: r ≈ 0.1 (nearly independent)
   - Similar notes can have very different staleness
   - Stale notes can be similar or dissimilar to fresh notes

3. **Semantic vs Structural**: r ≈ 0.2 (weak correlation)
   - Similar content can have different structures
   - Different content can have similar structures

4. **Temporal Embedding vs Semantic**: r ≈ 0.7 (strong but not perfect)
   - Temporal features add independent variance
   - Same semantic content, different temporal context

5. **Drift Direction vs Current Similarity**: r ≈ 0.0 (orthogonal)
   - Currently similar notes can drift in opposite directions
   - Dissimilar notes can drift in same direction

This orthogonality creates a **high-dimensional movement space** with many non-obvious patterns.

---

## 5. Primitive Pattern Extensions

### 5.1 Current Primitive Patterns

From the existing geists and `temporal_analysis.py`, we have these primitives:

1. **DRIFT**: Single-note trajectory in one dimension (semantic, temporal)
2. **VELOCITY**: Rate of drift (change per session)
3. **ACCELERATION**: Change in velocity
4. **CONVERGENCE**: Two entities moving closer in one dimension
5. **DIVERGENCE**: Two entities moving farther in one dimension
6. **FLIP/REVERSAL**: Polarity change (high ↔ low similarity)
7. **CYCLE**: Periodic return to previous state

### 5.2 Proposed New Primitives

#### **DECOUPLED_MOVEMENT**
- **Definition**: Movement in dimension A independent of movement in dimension B
- **Detection**: Low correlation (r < 0.3) between two dimensional movements
- **Example**: Semantic similarity increasing while graph distance increases
- **Implementation signature**:
  ```python
  def detect_decoupled_movement(
      note_a: Note, note_b: Note,
      dim_a: str, dim_b: str,
      min_sessions: int = 3
  ) -> tuple[float, float]:
      """Returns (direction_A, direction_B, correlation)"""
  ```

#### **OPPOSING_MOVEMENT**
- **Definition**: Movement in dimension A negatively correlated with dimension B
- **Detection**: Negative correlation (r < -0.5) between dimensional movements
- **Example**: Notes converging semantically but diverging in graph distance
- **Implementation signature**:
  ```python
  def detect_opposing_movement(
      note_a: Note, note_b: Note,
      dim_a: str, dim_b: str,
      threshold: float = -0.5
  ) -> bool
  ```

#### **TRAJECTORY_REVERSAL**
- **Definition**: Current state vs future trajectory pointing opposite directions
- **Detection**: High current similarity but drift vectors anti-aligned
- **Example**: Currently similar (0.8) but drift vectors opposite (-0.6 alignment)
- **Implementation signature**:
  ```python
  def detect_trajectory_reversal(
      note_a: Note, note_b: Note,
      current_sim_threshold: float = 0.7,
      alignment_threshold: float = -0.5
  ) -> tuple[float, float]:
      """Returns (current_similarity, drift_alignment)"""
  ```

#### **MULTIDIMENSIONAL_CONVERGENCE**
- **Definition**: Convergence in subset of dimensions, divergence in others
- **Detection**: Mixed directional signature across dimensions
- **Example**: Semantic + structural convergence, graph + staleness divergence
- **Implementation signature**:
  ```python
  def detect_multidim_convergence(
      note_a: Note, note_b: Note,
      converging_dims: list[str],
      diverging_dims: list[str],
      threshold: float = 0.1
  ) -> dict[str, float]:
      """Returns dimension -> direction map"""
  ```

#### **ORTHOGONAL_DRIFT**
- **Definition**: Independent drift in multiple uncorrelated dimensions
- **Detection**: Notes drifting in dimensions with r ≈ 0
- **Example**: Semantic drift toward 'productivity', structural drift toward 'narrative'
- **Implementation signature**:
  ```python
  def detect_orthogonal_drift(
      note: Note,
      dimensions: list[str],
      max_correlation: float = 0.3
  ) -> dict[str, np.ndarray]:
      """Returns dimension -> drift_vector map"""
  ```

#### **CORRELATED_MOVEMENT**
- **Definition**: Movement in dimension A predicts movement in dimension B
- **Detection**: High correlation (r > 0.7) between dimensional changes
- **Example**: Semantic convergence always accompanied by cluster membership change
- **Implementation signature**:
  ```python
  def detect_correlated_movement(
      note_a: Note, note_b: Note,
      dim_a: str, dim_b: str,
      min_correlation: float = 0.7
  ) -> float:
      """Returns correlation coefficient"""
  ```

#### **BOUNDARY_WALKER**
- **Definition**: Note near decision boundary between categorical states
- **Detection**: High similarity to notes in different clusters/categories
- **Example**: 0.79 similar to note in different cluster (cluster boundary)
- **Implementation signature**:
  ```python
  def detect_boundary_walkers(
      notes: list[Note],
      boundary_type: str,  # 'cluster', 'hub_orphan', etc.
      similarity_threshold: float = 0.7
  ) -> list[Note]:
      """Returns notes near categorical boundaries"""
  ```

#### **VELOCITY_MISMATCH**
- **Definition**: Aligned direction but different rates of change
- **Detection**: Similar drift direction (>0.5 alignment) but different magnitudes
- **Example**: Both drifting toward same concept but one 3x faster
- **Implementation signature**:
  ```python
  def detect_velocity_mismatch(
      note_a: Note, note_b: Note,
      direction_threshold: float = 0.5,
      velocity_ratio_threshold: float = 2.0
  ) -> tuple[float, float, float]:
      """Returns (alignment, velocity_a, velocity_b)"""
  ```

#### **ACCELERATION_ASYMMETRY**
- **Definition**: One note accelerating while another decelerating
- **Detection**: Opposite signs of acceleration in same direction
- **Example**: Both drifting toward 'systems', but one speeding up, other slowing
- **Implementation signature**:
  ```python
  def detect_acceleration_asymmetry(
      note_a: Note, note_b: Note,
      min_accel_diff: float = 0.1
  ) -> tuple[float, float]:
      """Returns (acceleration_a, acceleration_b)"""
  ```

#### **TEMPLATE_EMERGENCE**
- **Definition**: Multiple notes converging on structural pattern
- **Detection**: Low semantic similarity but high structural similarity
- **Example**: 3+ notes with different content but same heading/task structure
- **Implementation signature**:
  ```python
  def detect_template_emergence(
      notes: list[Note],
      min_structural_similarity: float = 0.8,
      max_semantic_similarity: float = 0.4,
      min_cluster_size: int = 3
  ) -> list[list[Note]]:
      """Returns clusters of structurally similar, semantically different notes"""
  ```

#### **MAINTENANCE_DIVERGENCE**
- **Definition**: Similar notes with asymmetric update patterns
- **Detection**: High semantic similarity but large staleness difference
- **Example**: Twin notes, one updated 5 days ago, other 231 days ago
- **Implementation signature**:
  ```python
  def detect_maintenance_divergence(
      note_a: Note, note_b: Note,
      min_semantic_sim: float = 0.7,
      min_staleness_diff: float = 0.4
  ) -> tuple[float, float]:
      """Returns (semantic_similarity, staleness_difference)"""
  ```

### 5.3 Primitive Pattern Hierarchy

```
Movement Patterns
├── Single-Dimension
│   ├── DRIFT (position change in one dimension)
│   ├── VELOCITY (rate of drift)
│   └── ACCELERATION (rate of velocity change)
│
├── Pairwise Single-Dimension
│   ├── CONVERGENCE (two notes moving closer)
│   ├── DIVERGENCE (two notes moving farther)
│   ├── FLIP (similarity polarity reversal)
│   └── CYCLE (periodic convergence/divergence)
│
└── Multidimensional
    ├── DECOUPLED_MOVEMENT (independent movement in dimensions)
    ├── OPPOSING_MOVEMENT (negatively correlated dimensions)
    ├── CORRELATED_MOVEMENT (positively correlated dimensions)
    ├── TRAJECTORY_REVERSAL (current state vs future direction mismatch)
    ├── MULTIDIMENSIONAL_CONVERGENCE (mixed convergence/divergence)
    ├── ORTHOGONAL_DRIFT (uncorrelated dimensional drifts)
    ├── BOUNDARY_WALKER (near categorical decision boundary)
    ├── VELOCITY_MISMATCH (aligned direction, different speed)
    ├── ACCELERATION_ASYMMETRY (opposite acceleration signs)
    ├── TEMPLATE_EMERGENCE (structural convergence, semantic divergence)
    └── MAINTENANCE_DIVERGENCE (content similarity, update asymmetry)
```

---

## 6. Provocative Question Templates

For each pattern, GeistFabrik can generate "What if...?" questions following the "muses not oracles" philosophy:

### Template: **Phantom Link**
```
"[[{A}]] and [[{B}]] are {semantic_direction} ({similarity:.2f} similarity,
{direction_text} from {prev_similarity:.2f}) but their graph distance is
{graph_direction} (now {current_hops} hops, {hop_direction_text} from {prev_hops}).
What if you're thinking similar thoughts but forgetting to connect them?"
```

### Template: **Ghost Connection**
```
"[[{A}]] links to [[{B}]], but they've {semantic_direction} from {prev_similarity:.2f}
to {current_similarity:.2f} similarity across {session_count} sessions.
What if this connection no longer reflects your current understanding?"
```

### Template: **Seasonal Drift**
```
"[[{A}]]'s content hasn't changed (semantic similarity: {semantic_sim:.2f}),
but its temporal embedding drifted from {prev_temporal_sim:.2f} to {current_temporal_sim:.2f}.
What if the passage from {prev_season} to {current_season} changes meaning even without edits?"
```

### Template: **Style Convergence**
```
"[[{A}]] and [[{B}]] are semantically unrelated ({semantic_sim:.2f} similarity)
but structurally converging: both now have {heading_count} headings, {task_count} tasks,
{code_count} code blocks. What if you're developing a template without realizing it?"
```

### Template: **Velocity Mismatch**
```
"[[{A}]] and [[{B}]] are both drifting toward '{common_direction}'
(alignment: {alignment:.2f}) but [[{A}]] is moving {velocity_ratio:.1f}x faster.
What if one note is accelerating while the other lags—what's blocking [[{B}]]?"
```

### Template: **Cluster Boundary Walker**
```
"[[{A}]] (cluster: '{cluster_a}') and [[{B}]] (cluster: '{cluster_b}')
are {similarity:.2f} similar but in different conceptual neighborhoods.
What if they're bridging these domains—should they be linked?"
```

### Template: **Trajectory Reversal**
```
"[[{A}]] and [[{B}]] are currently {current_sim:.2f} similar, but their
drift vectors are anti-aligned ({alignment:.2f}). What if they're converging now
but their trajectories suggest they'll diverge soon?"
```

### Template: **Accelerating Divergence**
```
"[[{A}]] and [[{B}]] were {initial_sim:.2f} similar {session_count} sessions ago,
now {current_sim:.2f}, and the divergence is accelerating ({acceleration:.3f} per session).
What inflection point occurred around session {inflection_session}?"
```

### Template: **Maintenance Asymmetry**
```
"[[{A}]] (staleness: {staleness_a:.2f}, updated {days_a} days ago) and
[[{B}]] (staleness: {staleness_b:.2f}, updated {days_b} days ago) are {semantic_sim:.2f} similar.
What if you're maintaining one twin but abandoning the other—why?"
```

### Template: **Hub Migration**
```
"[[{A}]] and [[{B}]] are in the same cluster ('{cluster_label}') but their
graph distance increased from {prev_hops} to {current_hops} hops.
What if they're semantic twins with different social circles?"
```

### Template: **Template Emergence**
```
"[[{A}]], [[{B}]], and [[{C}]] cover different topics (avg similarity: {avg_sim:.2f})
but all have {heading_count} headings, {task_count} tasks, and {code_count} code blocks.
What if you've developed a template without documenting it?"
```

### Template: **Bridge Collapse**
```
"[[{A}]] and [[{B}]] are converging semantically ({prev_sim:.2f} → {current_sim:.2f})
but their graph distance increased from {prev_hops} hops to {current_hops} hops.
What if you deleted the bridges between similar ideas?"
```

### Template: **Cyclical Convergence**
```
"[[{A}]] and [[{B}]] were {initial_sim:.2f} similar, diverged to {min_sim:.2f},
and are converging again to {current_sim:.2f}. What if you're circling back to
an old connection—what changed in session {return_session} to make it relevant again?"
```

---

## 7. Implementation Signatures

### 7.1 Core Detection Functions

```python
from typing import Protocol, Literal
from datetime import datetime
import numpy as np

class MultiDimensionalAnalyzer:
    """Analyzes note movement across multiple dimensions."""

    def __init__(self, vault: VaultContext):
        self.vault = vault

    # Dimension-specific similarity functions

    def semantic_similarity_trajectory(
        self, note_a: Note, note_b: Note
    ) -> list[tuple[datetime, float]]:
        """Returns [(session_date, similarity), ...] for semantic dimension."""
        pass

    def temporal_embedding_trajectory(
        self, note_a: Note, note_b: Note
    ) -> list[tuple[datetime, float]]:
        """Returns [(session_date, similarity), ...] for temporal dimension."""
        pass

    def graph_distance_trajectory(
        self, note_a: Note, note_b: Note
    ) -> list[tuple[datetime, int]]:
        """Returns [(session_date, shortest_path_length), ...] for graph."""
        pass

    def cluster_overlap_trajectory(
        self, note_a: Note, note_b: Note
    ) -> list[tuple[datetime, float]]:
        """Returns [(session_date, cluster_overlap), ...] for clustering."""
        pass

    def staleness_difference_trajectory(
        self, note_a: Note, note_b: Note
    ) -> list[tuple[datetime, float]]:
        """Returns [(session_date, staleness_diff), ...] for freshness."""
        pass

    # Movement pattern detectors

    def detect_phantom_link(
        self,
        min_semantic_sim: float = 0.7,
        min_graph_distance_increase: int = 2,
        min_sessions: int = 3
    ) -> list[tuple[Note, Note, dict[str, float]]]:
        """Find note pairs with semantic convergence + graph divergence.

        Returns:
            List of (note_a, note_b, metrics) where metrics contains:
            - semantic_similarity: current similarity
            - semantic_delta: change in similarity
            - graph_distance: current graph distance
            - graph_delta: change in graph distance
        """
        pass

    def detect_ghost_connection(
        self,
        max_semantic_sim: float = 0.5,
        min_semantic_decline: float = 0.2,
        min_sessions: int = 3
    ) -> list[tuple[Note, Note, dict[str, float]]]:
        """Find linked pairs with semantic divergence.

        Returns:
            List of (note_a, note_b, metrics) where metrics contains:
            - initial_similarity: similarity at first session
            - current_similarity: similarity at latest session
            - total_decline: initial - current
            - session_count: number of sessions tracked
        """
        pass

    def detect_seasonal_drift(
        self,
        min_semantic_stability: float = 0.95,
        min_temporal_drift: float = 0.15,
        min_sessions: int = 4
    ) -> list[tuple[Note, dict[str, float]]]:
        """Find notes with stable content but temporal embedding drift.

        Returns:
            List of (note, metrics) where metrics contains:
            - semantic_stability: variance in semantic embedding
            - temporal_drift: total temporal embedding drift
            - prev_season: season of first session
            - current_season: season of latest session
        """
        pass

    def detect_style_convergence(
        self,
        max_semantic_sim: float = 0.4,
        min_structural_sim: float = 0.8,
        min_sessions: int = 2
    ) -> list[tuple[Note, Note, dict[str, Any]]]:
        """Find pairs with semantic divergence + structural convergence.

        Returns:
            List of (note_a, note_b, metrics) where metrics contains:
            - semantic_similarity: current semantic similarity
            - structural_similarity: current structural similarity
            - shared_structure: dict of matching structural properties
        """
        pass

    def detect_velocity_mismatch(
        self,
        min_direction_alignment: float = 0.5,
        min_velocity_ratio: float = 2.0,
        min_sessions: int = 4
    ) -> list[tuple[Note, Note, dict[str, float]]]:
        """Find pairs drifting in same direction but different speeds.

        Returns:
            List of (note_a, note_b, metrics) where metrics contains:
            - drift_alignment: dot product of drift vectors
            - velocity_a: drift magnitude per session for note_a
            - velocity_b: drift magnitude per session for note_b
            - velocity_ratio: velocity_a / velocity_b
        """
        pass

    def detect_trajectory_reversal(
        self,
        min_current_sim: float = 0.7,
        max_drift_alignment: float = -0.5,
        min_sessions: int = 3
    ) -> list[tuple[Note, Note, dict[str, float]]]:
        """Find pairs currently similar but drift vectors opposing.

        Returns:
            List of (note_a, note_b, metrics) where metrics contains:
            - current_similarity: current semantic similarity
            - drift_alignment: alignment of drift direction vectors
            - predicted_future_sim: estimated similarity N sessions ahead
        """
        pass

    def detect_maintenance_asymmetry(
        self,
        min_semantic_sim: float = 0.7,
        min_staleness_diff: float = 0.4,
    ) -> list[tuple[Note, Note, dict[str, float]]]:
        """Find semantically similar pairs with asymmetric update patterns.

        Returns:
            List of (note_a, note_b, metrics) where metrics contains:
            - semantic_similarity: current similarity
            - staleness_a: staleness score for note_a
            - staleness_b: staleness score for note_b
            - staleness_diff: absolute difference
            - days_since_modified_a: days since note_a modified
            - days_since_modified_b: days since note_b modified
        """
        pass

    def detect_cluster_boundary_walker(
        self,
        min_cross_cluster_sim: float = 0.7,
        min_within_cluster_sim: float = 0.5,
    ) -> list[tuple[Note, dict[str, Any]]]:
        """Find notes near cluster boundaries.

        Returns:
            List of (note, metrics) where metrics contains:
            - cluster_id: assigned cluster
            - cluster_label: cluster semantic label
            - max_cross_cluster_sim: highest similarity to note in different cluster
            - cross_cluster_note: Note object of most similar cross-cluster note
            - boundary_score: how close to cluster boundary (0-1)
        """
        pass
```

### 7.2 Data Requirements

To implement these detectors, we need:

**Per Session Storage**:
```sql
-- Already exists in session_embeddings table
CREATE TABLE session_embeddings (
    session_id INTEGER,
    note_path TEXT,
    embedding BLOB,
    cluster_id INTEGER,        -- Already exists
    cluster_label TEXT,        -- Already exists
    PRIMARY KEY (session_id, note_path)
);

-- Need to add: graph distance cache
CREATE TABLE session_graph_distances (
    session_id INTEGER,
    note_a_path TEXT,
    note_b_path TEXT,
    distance INTEGER,          -- Shortest path length (-1 if no path)
    PRIMARY KEY (session_id, note_a_path, note_b_path)
);

-- Need to add: structural property cache
CREATE TABLE session_structural_properties (
    session_id INTEGER,
    note_path TEXT,
    heading_count INTEGER,
    task_count INTEGER,
    code_block_count INTEGER,
    list_item_count INTEGER,
    -- ... other structural properties
    PRIMARY KEY (session_id, note_path)
);
```

**Derived Metrics** (computed on-demand, session-scoped cache):
- Semantic similarity trajectories
- Temporal embedding trajectories
- Graph distance trajectories
- Cluster overlap trajectories
- Staleness difference trajectories
- Drift direction vectors
- Velocity vectors
- Acceleration vectors

---

## 8. Geist Implementation Opportunities

### 8.1 High-Priority Geists (Novel Patterns)

#### **phantom_link** geist
- **Pattern**: Semantic convergence + graph divergence
- **Detection**: `detect_phantom_link()`
- **Output**: "You're thinking similar thoughts but forgetting to connect them"
- **Priority**: HIGH (common pattern, actionable)

#### **seasonal_drift** geist
- **Pattern**: Semantic stability + temporal drift
- **Detection**: `detect_seasonal_drift()`
- **Output**: "Same words, different season—does this note mean something different now?"
- **Priority**: MEDIUM (interesting but subtle)

#### **velocity_mismatch** geist
- **Pattern**: Aligned drift direction + different speeds
- **Detection**: `detect_velocity_mismatch()`
- **Output**: "Both drifting toward same concept but one 3x faster—what's blocking the other?"
- **Priority**: HIGH (reveals bottlenecks in thinking)

#### **trajectory_reversal** geist
- **Pattern**: Current similarity + opposing drift vectors
- **Detection**: `detect_trajectory_reversal()`
- **Output**: "Currently similar but trajectories suggest they'll diverge soon"
- **Priority**: HIGH (predictive, actionable)

#### **maintenance_asymmetry** geist
- **Pattern**: Semantic similarity + staleness divergence
- **Detection**: `detect_maintenance_asymmetry()`
- **Output**: "Why maintain one twin but abandon the other?"
- **Priority**: MEDIUM (prompts reflection on note maintenance)

#### **cluster_boundary_walker** geist
- **Pattern**: High cross-cluster similarity
- **Detection**: `detect_cluster_boundary_walker()`
- **Output**: "Are they bridging these domains—should they be linked?"
- **Priority**: HIGH (discovers cross-domain connections)

#### **template_emergence** geist
- **Pattern**: Structural convergence + semantic divergence
- **Detection**: `detect_template_emergence()`
- **Output**: "You've developed a template without documenting it"
- **Priority**: MEDIUM (meta-observation about note-taking patterns)

#### **bridge_collapse** geist
- **Pattern**: Semantic convergence + graph path lengthening
- **Detection**: Semantic trajectory + graph distance trajectory analysis
- **Output**: "You deleted the bridges between similar ideas"
- **Priority**: MEDIUM (identifies lost connections)

### 8.2 Existing Geist Enhancements

#### **concept_drift** enhancement
- **Add**: Velocity and acceleration metrics
- **New output**: "Drifting toward X at 0.15/session (accelerating)"
- **Implementation**: Use `drift_velocity` and `acceleration` from trajectory calculator

#### **convergent_evolution** enhancement
- **Add**: Velocity mismatch detection
- **New output**: "Converging but [[A]] moving 3x faster than [[B]]"
- **Implementation**: Add velocity comparison in existing logic

#### **divergent_evolution** enhancement
- **Add**: Acceleration metrics
- **New output**: "Divergence accelerating—inflection point in session X"
- **Implementation**: Detect increasing divergence rate

#### **temporal_drift** enhancement
- **Add**: Maintenance asymmetry detection
- **New output**: Include staleness comparison for similar notes
- **Implementation**: Combine with staleness metadata

---

## 9. Research Questions

### 9.1 Correlation Studies

**Q1**: What is the empirical correlation between semantic similarity and graph distance?
- **Hypothesis**: r ≈ 0.3 (weak positive correlation)
- **Method**: Sample 1000 note pairs, compute both metrics, measure Pearson r
- **Implication**: If r < 0.4, semantic and graph are largely independent dimensions

**Q2**: Do notes in the same cluster have different graph neighborhoods?
- **Hypothesis**: Yes, cluster membership is more semantic than structural
- **Method**: For each cluster, compute average intra-cluster graph distance
- **Implication**: If avg distance > 3 hops, "Hub Migration" pattern is common

**Q3**: How often do notes exhibit cyclical drift patterns?
- **Hypothesis**: 5-10% of notes with 6+ sessions show cycles
- **Method**: Run `find_cycling_notes()` on production vaults
- **Implication**: If >10%, cyclical thinking is significant cognitive pattern

**Q4**: What is the distribution of multidimensional movement signatures?
- **Hypothesis**: Most pairs have mixed signatures (not all convergent or divergent)
- **Method**: Compute signature vectors for 1000 pairs, cluster by signature
- **Implication**: If signatures are diverse, multidimensional patterns are common

### 9.2 Predictive Modeling

**Q5**: Can drift direction vectors predict future similarity?
- **Hypothesis**: Yes, with r > 0.6 correlation
- **Method**: Train linear regression on drift vectors to predict similarity N sessions ahead
- **Implication**: If accurate, can warn about impending divergence/convergence

**Q6**: Do velocity mismatches predict eventual divergence?
- **Hypothesis**: Yes, notes with velocity ratio > 3 diverge within 5 sessions
- **Method**: Track velocity mismatch pairs, measure divergence rate
- **Implication**: If true, velocity is early warning signal

**Q7**: Can cluster boundary walkers predict future cluster migrations?
- **Hypothesis**: Yes, high boundary score → 70% migration probability
- **Method**: Track boundary walkers, measure cluster change rate
- **Implication**: If predictive, boundary walking is precursor to conceptual shift

### 9.3 Interaction Effects

**Q8**: Does graph distance moderate semantic drift?
- **Hypothesis**: Linked notes drift slower than unlinked notes
- **Method**: Compare drift rates for linked vs unlinked pairs with similar initial similarity
- **Implication**: If true, links stabilize semantic similarity

**Q9**: Does staleness predict drift acceleration?
- **Hypothesis**: Stale notes drift faster when finally updated
- **Method**: Compare drift acceleration before/after updates for stale notes
- **Implication**: If true, stale notes undergo conceptual "bursts"

**Q10**: Do structural templates constrain semantic drift?
- **Hypothesis**: Notes with similar structure drift less
- **Method**: Measure drift for structurally similar vs dissimilar pairs
- **Implication**: If true, format shapes content evolution

---

## 10. Conclusion

### 10.1 Key Insights

1. **Notes exist in 8+ dimensional spaces**, each with independent movement dynamics
2. **Multidimensional patterns** (e.g., semantic convergence + graph divergence) are common but unexploited
3. **Orthogonality** between dimensions creates rich space of non-obvious combinations
4. **Predictive signals** exist: drift vectors, velocity mismatches, boundary walking
5. **Primitive patterns** can be extended from single-dimension to multidimensional

### 10.2 Implementation Priority

**Phase 1: High-value, low-complexity**
1. `phantom_link` geist (semantic ↑, graph ↓)
2. `trajectory_reversal` geist (current similarity ↑, drift alignment ↓)
3. `velocity_mismatch` geist (direction aligned, velocity divergent)
4. `cluster_boundary_walker` geist (high cross-cluster similarity)

**Phase 2: Medium-value, medium-complexity**
5. `maintenance_asymmetry` geist (semantic ↑, staleness ↓)
6. `seasonal_drift` geist (semantic stable, temporal ↓)
7. `bridge_collapse` geist (semantic ↑, graph path ↓)
8. `template_emergence` geist (semantic ↓, structural ↑)

**Phase 3: Research and validation**
9. Correlation studies (Q1-Q4)
10. Predictive modeling (Q5-Q7)
11. Interaction effects (Q8-Q10)

### 10.3 Architectural Implications

**Storage requirements**:
- Add `session_graph_distances` table for graph trajectory tracking
- Add `session_structural_properties` table for structural trajectory tracking
- Current `session_embeddings` table is sufficient for semantic/temporal/cluster tracking

**Computation requirements**:
- Most patterns require 3+ sessions for meaningful detection
- Trajectory calculations are session-scoped cacheable
- Multidimensional analysis is O(N²) for pairwise patterns, O(N) for single-note patterns

**API extensions**:
- Add `MultiDimensionalAnalyzer` class to `temporal_analysis.py`
- Extend `EmbeddingTrajectoryCalculator` with dimension parameter
- Add dimension-specific trajectory methods to `VaultContext`

### 10.4 Philosophical Implications

**Muses, not oracles**: Multidimensional patterns generate richer "What if...?" questions by revealing **contradictions** and **tensions** in the vault's evolution.

**Examples**:
- "What if you're connecting ideas in your mind (semantic) but not in your graph?"
- "What if time changes meaning even when words stay the same?"
- "What if you've built a template without naming it?"
- "What if these notes are converging now but trajectories suggest future divergence?"

These questions arise from **dimensional tensions**—when different spaces tell different stories about the same notes. This is where GeistFabrik's "divergence engine" philosophy truly shines: not by smoothing over contradictions, but by **surfacing them as provocations**.

---

**Document version**: 1.0
**Date**: 2025-01-16
**Author**: GeistFabrik Multidimensional Movement Analysis
