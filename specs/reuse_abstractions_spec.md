# GeistFabrik Reuse Abstractions Specification

**Status**: Proposed
**Version**: 1.0
**Date**: 2025-11-10

---

## Executive Summary

Analysis of the GeistFabrik codebase reveals **seven core conceptual abstractions** that recur across geists but are currently implemented ad-hoc. These abstractions represent 60-70% of geist implementation logic. Elevating them into first-class, composable operations would unlock significant capability expansion while dramatically simplifying geist authorship.

**Current State**: 51 geists (42 code, 9 Tracery) spanning ~4,450 lines. ~70% of code deals with recurring patterns.

**Key Finding**: GeistFabrik's power isn't in individual geists—it's in **combinations of primitives**. Formalizing these primitives enables exponential capability expansion through composition.

**Impact Projections**:
- Average geist size: 50-65 lines → 10-20 lines (70% reduction)
- Enabled geists: 51 → 100+ (96% increase)
- Code dealing with patterns: 70% → 20% (71% reduction)

---

## I. The Seven Core Abstractions

| # | Abstraction | Recurs In | Current Pain | Unlocked Capability |
|---|-------------|-----------|--------------|---------------------|
| 1 | **Embedding Trajectory Calculator** | 4 geists | Session queries duplicated | Temporal analysis as first-class |
| 2 | **Similarity Threshold Profiles** | 8+ geists | Magic numbers (0.6, 0.5, 0.7) | Semantic naming, systematic tuning |
| 3 | **Clustering Service** | 4+ geists | HDBSCAN + labeling 4× | Strategy swapping, session caching |
| 4 | **Graph Pattern Queries** | 5+ geists | Hub/orphan/bridge duplicated | Unified interface, node roles |
| 5 | **Content Extraction Pipeline** | 1 geist | Baked into question_harvester | 8+ new extractor types |
| 6 | **Temporal-Semantic Fusion** | 3 geists | Ad-hoc time+semantics | Cyclical thinking, seasonal patterns |
| 7 | **Metadata Analysis Profiles** | 3+ geists | Manual ratio calculations | Profiles, comparisons, audits |

---

## II. Detailed Abstraction Specifications

### 1. Embedding Trajectory Calculator

**Conceptual Pattern**

Notes' semantic interpretations evolve across sessions. Understanding this evolution requires:
- Tracking embeddings across session history
- Computing drift metrics (distance, direction, velocity)
- Comparing trajectories between notes (convergence, divergence)
- Detecting temporal patterns (cycling, acceleration, reversal)

**Current Implementation (4 geists)**

Each of `concept_drift.py`, `convergent_evolution.py`, `divergent_evolution.py`, `burst_evolution.py` independently:
1. Queries `session_embeddings` table for historical data
2. Reconstructs numpy arrays from BLOBs
3. Computes pairwise similarities across time
4. Interprets trajectory (first-last comparison, session halves, alignment)

**Pain Points**
- Session query logic duplicated 4×
- Embedding retrieval/reconstruction repeated
- Drift computation manually reimplemented
- No unified vocabulary for temporal queries
- Adding new patterns (cycling, acceleration) requires reimplementing everything
- Hard to express "show me notes that drifted >0.2 toward topic X"

**Proposed API**

```python
# New module: src/geistfabrik/temporal_analysis.py

class EmbeddingTrajectoryCalculator:
    """Calculates how a note's embedding evolves across sessions.

    Provides uniform API for temporal analysis patterns.
    """

    def __init__(self, vault: VaultContext, note: Note, sessions: Optional[List[int]] = None):
        """Initialize trajectory calculator for a note.

        Args:
            vault: VaultContext with session history
            note: Note to track
            sessions: Optional specific session IDs (default: all available)
        """
        self.vault = vault
        self.note = note
        self.sessions = sessions or self._get_available_sessions()
        self._snapshots_cache: Optional[List[Tuple[datetime, np.ndarray]]] = None

    # Core data access
    def snapshots(self) -> List[Tuple[datetime, np.ndarray]]:
        """Get (date, embedding) for all sessions containing this note."""
        if self._snapshots_cache is None:
            self._snapshots_cache = self._load_snapshots()
        return self._snapshots_cache

    # Drift metrics
    def total_drift(self) -> float:
        """Compute total drift (1 - cosine_sim(first, last))."""

    def drift_direction_vector(self) -> np.ndarray:
        """Compute unit vector of drift direction (last - first, normalized)."""

    def drift_alignment(self, direction: np.ndarray) -> float:
        """Compute how aligned trajectory is with a given direction (dot product)."""

    def windowed_drift_rates(self, window_size: int = 3) -> List[float]:
        """Compute drift rates in sliding windows of consecutive sessions."""

    # Temporal segmentation
    def early_late_split(self) -> Tuple[float, float]:
        """Return (early_avg_sim, late_avg_sim) for convergence detection."""

    def is_accelerating(self, threshold: float = 0.1) -> bool:
        """Check if drift rate is increasing over time."""

    # Comparative analysis
    def similarity_with_trajectory(self, other: "EmbeddingTrajectoryCalculator") -> List[float]:
        """Compute similarity between this note and another note at each session."""

    def is_converging_with(self, other: "EmbeddingTrajectoryCalculator",
                          threshold: float = 0.15) -> bool:
        """Check if trajectories are converging (recent sim > early sim + threshold)."""

    def is_diverging_from(self, other: "EmbeddingTrajectoryCalculator",
                         threshold: float = 0.15) -> bool:
        """Check if trajectories are diverging (early sim > recent sim + threshold)."""


class TemporalPatternFinder:
    """Finds patterns across multiple trajectories."""

    @staticmethod
    def find_converging_pairs(
        vault: VaultContext,
        candidate_pairs: List[Tuple[Note, Note]],
        threshold: float = 0.15
    ) -> List[Tuple[Note, Note]]:
        """Find pairs whose embeddings are converging across sessions."""

    @staticmethod
    def find_high_drift_notes(
        vault: VaultContext,
        notes: List[Note],
        min_drift: float = 0.2
    ) -> List[Tuple[Note, np.ndarray]]:
        """Find notes with significant drift and their drift direction vectors."""

    @staticmethod
    def find_aligned_with_direction(
        vault: VaultContext,
        notes: List[Note],
        direction: np.ndarray,
        min_alignment: float = 0.5
    ) -> List[Note]:
        """Find notes drifting in a specific semantic direction."""

    @staticmethod
    def find_cycling_notes(
        vault: VaultContext,
        notes: List[Note],
        min_cycles: int = 2
    ) -> List[Note]:
        """Find notes that return to previous semantic states (cyclical thinking)."""
```

**Architectural Placement**

New module: `src/geistfabrik/temporal_analysis.py`

Why not in VaultContext:
- VaultContext provides *primitives* (embeddings, similarity)
- This provides *analysis* (trajectories, patterns)
- Keeps VaultContext focused, prevents bloat
- Allows temporal analysis to import VaultContext without circular deps

**What It Unlocks**

New geist patterns become trivial:
- **Semantic Reversal Detector**: Notes that drift then reverse direction
- **Convergence Cluster**: Groups of notes all converging toward same area
- **Drift Velocity Anomaly**: Notes whose drift suddenly accelerates
- **Cyclical Thinking Patterns**: Notes that cycle through distinct states
- **Directional Drift Groups**: Notes drifting in same semantic direction
- **Temporal Stability Score**: How much a note's interpretation varies over time

**Before/After Example**

```python
# BEFORE (concept_drift.py - ~65 lines)
def suggest(vault: VaultContext) -> list[Suggestion]:
    # Get session history (8 lines)
    cursor = vault.db.execute("SELECT session_id, session_date FROM sessions...")
    sessions = cursor.fetchall()

    # For each note (40+ lines)
    for note in vault.sample(notes, min(30, len(notes))):
        trajectory = []
        for session_id, session_date in sessions:
            cursor = vault.db.execute(
                "SELECT embedding FROM session_embeddings WHERE session_id = ? AND note_path = ?",
                (session_id, note.path)
            )
            row = cursor.fetchone()
            if row:
                emb = np.frombuffer(row[0], dtype=np.float32)
                trajectory.append((session_date, emb))

        if len(trajectory) < 3:
            continue

        # Calculate drift manually
        first_emb = trajectory[0][1]
        last_emb = trajectory[-1][1]
        from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
        similarity = sklearn_cosine(first_emb.reshape(1, -1), last_emb.reshape(1, -1))
        drift = 1.0 - float(similarity[0, 0])

        # ... more drift direction calculations ...

# AFTER (concept_drift.py - ~15 lines)
def suggest(vault: VaultContext) -> list[Suggestion]:
    from geistfabrik.temporal_analysis import TemporalPatternFinder

    notes = vault.notes()

    # Find notes with high drift and their directions
    drifting_notes = TemporalPatternFinder.find_high_drift_notes(
        vault, notes, min_drift=0.2
    )

    for note, drift_vector in drifting_notes:
        # Find what note is drifting toward
        neighbors = vault.neighbours(note, k=5)
        aligned = max(neighbors, key=lambda n:
            EmbeddingTrajectoryCalculator(vault, note).drift_alignment(
                vault.embedding(n)
            ))

        yield Suggestion(f"[[{note.title}]] drifting toward [[{aligned.title}]]", ...)
```

---

### 2. Similarity Threshold Profiles

**Conceptual Pattern**

Semantic similarity is a spectrum from "completely unrelated" (0.0) to "nearly identical" (1.0). Different geists need to reason about different regions of this spectrum:
- Bridge builder: High similarity but unlinked (>0.6)
- Creative collision: Low similarity collision (0.2-0.5)
- Pattern finder: Very high similarity cluster (>0.7)

**Current Implementation (8+ geists)**

Magic numbers scattered throughout:
- `0.6` appears in: bridge_builder, hidden_hub, concept_cluster
- `0.5` appears in: unlinked_pairs, island_hopper
- `0.7` appears in: pattern_finder
- Relative thresholds: `avg + 0.15`, `max > avg + delta`

**Pain Points**
- No shared vocabulary ("what does 0.6 mean?")
- Impossible to systematically tune across geists
- Hard to express "similar to A but dissimilar to B"
- No way to reason about similarity distributions

**Proposed API**

```python
# New module: src/geistfabrik/similarity_analysis.py

class SimilarityLevel:
    """Semantic names for similarity thresholds."""
    VERY_HIGH = 0.80  # Almost identical semantically
    HIGH = 0.65       # Clearly related concepts
    MODERATE = 0.50   # Meaningfully connected
    WEAK = 0.35       # Tangentially related
    NOISE = 0.15      # Mostly unrelated


class SimilarityProfile:
    """Analyzes a note's similarity distribution."""

    def __init__(self, vault: VaultContext, note: Note, candidates: Optional[List[Note]] = None):
        """Create similarity profile for a note against candidates."""
        self.vault = vault
        self.note = note
        self.candidates = candidates or vault.notes()

    def count_above(self, threshold: float) -> int:
        """Count candidates with similarity >= threshold."""

    def count_in_range(self, min_sim: float, max_sim: float) -> int:
        """Count candidates with similarity in [min_sim, max_sim]."""

    def percentile(self, p: float) -> float:
        """Get pth percentile of similarity distribution."""

    def is_hub(self, threshold: float = SimilarityLevel.HIGH, min_count: int = 10) -> bool:
        """Check if note has many high-similarity neighbors (hub pattern)."""

    def is_bridge(self, threshold: float = SimilarityLevel.HIGH, unlinked_only: bool = True) -> bool:
        """Check if note connects unlinked high-similarity notes."""


class SimilarityFilter:
    """Declarative filtering on similarity."""

    @staticmethod
    def filter_by_range(
        vault: VaultContext,
        source: Note,
        candidates: List[Note],
        min_sim: float,
        max_sim: float
    ) -> List[Note]:
        """Filter candidates by similarity range."""

    @staticmethod
    def filter_similar_to_any(
        vault: VaultContext,
        anchors: List[Note],
        candidates: List[Note],
        threshold: float = SimilarityLevel.MODERATE
    ) -> List[Note]:
        """Find candidates similar to ANY anchor (union)."""

    @staticmethod
    def filter_similar_to_all(
        vault: VaultContext,
        anchors: List[Note],
        candidates: List[Note],
        threshold: float = SimilarityLevel.MODERATE
    ) -> List[Note]:
        """Find candidates similar to ALL anchors (intersection)."""
```

**What It Unlocks**
- Systematic threshold tuning: Change `SimilarityLevel.HIGH` once, affects all geists
- Clear reasoning: "We want HIGH similarity" vs "we want 0.65"
- Complex filters: "Similar to A and B but dissimilar to C"
- Profile-based detection: "Is this note a hub?" vs manual counting

---

### 3. Clustering Service

**Conceptual Pattern**

Group notes into semantic clusters, label them, find representatives. Used by:
- `concept_cluster.py`: Main clustering geist
- `cluster_mirror.py`: Cluster-based mirroring
- `temporal_clustering.py`: Session-based cluster evolution
- `VaultContext.get_clusters()`: Core clustering method

**Current Implementation**

HDBSCAN + c-TF-IDF/KeyBERT labeling implemented 4+ times. Each run is expensive (minutes on large vaults).

**Pain Points**
- Clustering computed per-geist (expensive, redundant)
- No session-scoped caching (one clustering per session vs per geist)
- Strategy baked in (can't swap HDBSCAN for K-means)
- Labeling reimplemented independently

**Proposed API**

```python
# New module: src/geistfabrik/clustering_analysis.py

class ClusteringService:
    """Session-scoped clustering with strategy swapping."""

    def __init__(self, vault: VaultContext, strategy: str = "hdbscan", min_size: int = 5):
        """Initialize clustering service.

        Args:
            vault: VaultContext
            strategy: "hdbscan", "kmeans", "agglomerative"
            min_size: Minimum cluster size
        """

    def get_clusters(self) -> Dict[int, Cluster]:
        """Get clusters (cached per session)."""

    def get_cluster_for_note(self, note: Note) -> Optional[int]:
        """Get cluster ID for a note."""

    def get_representatives(self, cluster_id: int, k: int = 3) -> List[Note]:
        """Get k most representative notes for cluster."""

    def compare_with_session(self, other_session_id: int) -> ClusterComparison:
        """Compare current clustering with another session."""


class Cluster:
    """Represents a semantic cluster."""
    cluster_id: int
    label: str                    # "keyword, list, here"
    formatted_label: str          # "Notes about keyword, list, and here"
    notes: List[Note]
    size: int
    centroid: np.ndarray

    def contains(self, note: Note) -> bool:
        """Check if note is in cluster."""

    def similarity_to_note(self, note: Note) -> float:
        """Compute note's similarity to cluster centroid."""
```

**What It Unlocks**
- One clustering per session (shared across all geists)
- Strategy experimentation (HDBSCAN vs K-means)
- Temporal cluster tracking (births, deaths, merges, splits)
- Cross-geist cluster consistency

---

### 4. Graph Pattern Queries

**Conceptual Pattern**

Structural queries on the note graph:
- Hubs: Notes with many incoming links
- Orphans: Notes with no links
- Bridges: Notes connecting otherwise unlinked clusters
- Paths: Shortest paths between notes

**Current Implementation (5+ geists)**

Each reimplements graph traversal:
- `bridge_builder.py`: Hub detection + outgoing link analysis
- `island_hopper.py`: Orphan/isolated cluster detection
- `hidden_hub.py`: Hub detection with semantic similarity
- `VaultContext`: `hubs()`, `orphans()`, `backlinks()`, `outgoing_links()`

**Pain Points**
- Hub/orphan queries duplicated
- No unified "bridge" detection
- Path-finding not available
- No structural pattern vocabulary

**Proposed API**

```python
# New module: src/geistfabrik/graph_analysis.py

class GraphPatternFinder:
    """Unified graph pattern detection."""

    def __init__(self, vault: VaultContext):
        self.vault = vault

    # Structural roles
    def find_hubs(self, min_backlinks: int = 10) -> List[Note]:
        """Find notes with many incoming links."""

    def find_orphans(self) -> List[Note]:
        """Find notes with no incoming or outgoing links."""

    def find_bridges(self, min_similarity: float = 0.6) -> List[Tuple[Note, Note, Note]]:
        """Find (note_a, bridge, note_b) where bridge connects high-sim unlinked notes."""

    # Paths
    def shortest_path(self, source: Note, target: Note) -> Optional[List[Note]]:
        """Find shortest path from source to target via links."""

    def k_hop_neighborhood(self, note: Note, k: int) -> List[Note]:
        """Get all notes within k link hops."""

    # Clusters
    def find_connected_components(self) -> List[List[Note]]:
        """Find disconnected subgraphs."""

    def detect_structural_holes(self, min_similarity: float = 0.6) -> List[Tuple[Note, Note]]:
        """Find high-similarity pairs in different connected components."""
```

---

### 5. Content Extraction Pipeline

**Conceptual Pattern**

Extract structured content from markdown:
1. Remove code blocks (avoid false positives)
2. Apply extraction strategies (regex, patterns)
3. Filter (quality checks)
4. Deduplicate

Currently only `question_harvester.py` uses this pattern.

**Pain Points**
- Pipeline baked into single geist
- Not generalizable to other content types
- Hard to add new extractors (definitions, claims, hypotheses)

**Proposed API**

```python
# New module: src/geistfabrik/content_extraction.py

class ExtractionPipeline:
    """Generalizable content extraction pipeline."""

    def __init__(self, strategies: List[ExtractionStrategy],
                 filters: Optional[List[ContentFilter]] = None):
        """Initialize pipeline with strategies and filters."""

    def extract(self, content: str) -> List[str]:
        """Run full pipeline: strategies → filters → deduplicate."""


class ExtractionStrategy(Protocol):
    """Protocol for extraction strategies."""
    def extract(self, content: str) -> List[str]:
        """Extract content items from markdown."""


class ContentFilter(Protocol):
    """Protocol for content filters."""
    def is_valid(self, item: str) -> bool:
        """Check if extracted item is valid."""


# Built-in strategies
class QuestionExtractor(ExtractionStrategy):
    """Extract questions (sentences ending with ?)."""

class DefinitionExtractor(ExtractionStrategy):
    """Extract definitions (X is Y, X: Y patterns)."""

class ClaimExtractor(ExtractionStrategy):
    """Extract claims (assertive statements)."""

class HypothesisExtractor(ExtractionStrategy):
    """Extract hypotheses (if/then, may/might patterns)."""
```

**What It Unlocks**

New geist types:
- **Definition Harvester**: Surface terminology definitions
- **Claim Harvester**: Extract assertions/claims
- **Hypothesis Harvester**: Surface testable hypotheses
- **Assumption Detector**: Find embedded assumptions
- **Terminology Extractor**: Build glossary
- **Citation Extractor**: Extract referenced sources
- **Example Harvester**: Find concrete examples
- **Counter-Example Finder**: Find exceptions/counter-cases

---

### 6. Temporal-Semantic Fusion

**Conceptual Pattern**

Combine temporal and semantic queries:
- "Notes about X created in season Y"
- "What was I thinking about Z last winter?"
- "Concepts that emerged in burst periods"

**Current Implementation**

Ad-hoc combinations in individual geists.

**Proposed API**

```python
# Extends temporal_analysis.py

class TemporalSemanticQuery:
    """Combine time and semantics."""

    def notes_created_similar_to(
        self,
        vault: VaultContext,
        anchor: Note,
        start_date: datetime,
        end_date: datetime,
        min_similarity: float = 0.6
    ) -> List[Note]:
        """Find notes created in time range similar to anchor."""

    def seasonal_pattern_for_topic(
        self,
        vault: VaultContext,
        topic_keywords: List[str]
    ) -> Dict[str, int]:
        """Count notes about topic by season (spring/summer/fall/winter)."""

    def drift_direction_by_period(
        self,
        vault: VaultContext,
        note: Note
    ) -> Dict[str, np.ndarray]:
        """Get drift direction vectors by time period (month, season)."""
```

**What It Unlocks**
- Cyclical thinking patterns
- Seasonal topic analysis
- Time-bounded semantic queries

---

### 7. Metadata Analysis Profiles

**Conceptual Pattern**

Analyze metadata distributions and outliers:
- Complexity distribution across vault
- Link density profiles
- Tag usage patterns

**Current Implementation**

Manual ratio calculations in individual geists.

**Proposed API**

```python
# Extends src/geistfabrik/metadata_system.py

class MetadataAnalyzer:
    """Analyze metadata distributions."""

    def __init__(self, vault: VaultContext):
        self.vault = vault

    def distribution(self, metadata_key: str) -> Dict[str, float]:
        """Get percentiles (p10, p25, p50, p75, p90) for metadata."""

    def outliers(self, metadata_key: str, threshold: float = 2.0) -> List[Note]:
        """Find notes with metadata > threshold standard deviations from mean."""

    def compare_notes(self, note_a: Note, note_b: Note, keys: List[str]) -> Dict[str, float]:
        """Compare metadata between two notes (ratios)."""

    def profile(self, note: Note) -> Dict[str, str]:
        """Get metadata profile: {key: 'high'|'moderate'|'low'} based on percentiles."""
```

---

## III. Architectural Placement

### New Modules (5)

```
src/geistfabrik/
├── temporal_analysis.py         (EmbeddingTrajectoryCalculator, TemporalPatternFinder)
├── similarity_analysis.py       (SimilarityLevel, SimilarityProfile, SimilarityFilter)
├── clustering_analysis.py       (ClusteringService, Cluster)
├── graph_analysis.py           (GraphPatternFinder)
└── content_extraction.py       (ExtractionPipeline, strategies, filters)
```

### Enhanced Modules (2)

```
src/geistfabrik/vault_context.py   (May add convenience methods calling new modules)
src/geistfabrik/metadata_system.py (+ MetadataAnalyzer)
```

### Why Not in VaultContext?

**VaultContext provides primitives**:
- `notes()`, `similarity()`, `neighbours()`, `backlinks()`
- Raw data access and basic operations

**New modules provide analysis**:
- Patterns, trajectories, profiles
- Complex queries and comparisons
- Keep VaultContext focused, prevent bloat
- Avoid circular dependencies

---

## IV. Implementation Roadmap

**8-Week Incremental Plan**

### Phase 1 (Weeks 1-2): Similarity Analysis + Content Extraction
- Implement `SimilarityLevel`, `SimilarityProfile`, `SimilarityFilter`
- Implement `ExtractionPipeline` and 2-3 extractors
- Refactor 1-2 geists to use new APIs
- **Deliverable**: Similarity analysis module + 2 new extractor geists

### Phase 2 (Weeks 2-3): Temporal Analysis
- Implement `EmbeddingTrajectoryCalculator`
- Implement `TemporalPatternFinder`
- Refactor concept_drift, convergent_evolution, divergent_evolution
- **Deliverable**: Temporal analysis module + 3 refactored geists

### Phase 3 (Weeks 3-4): Clustering Service
- Implement `ClusteringService` with session caching
- Implement strategy swapping (HDBSCAN, K-means)
- Refactor concept_cluster, cluster_mirror
- **Deliverable**: Clustering service + 2 refactored geists

### Phase 4 (Weeks 4-5): Graph Analysis
- Implement `GraphPatternFinder`
- Add path-finding, bridge detection
- Refactor bridge_builder, island_hopper
- **Deliverable**: Graph analysis module + 2 refactored geists

### Phase 5 (Weeks 5-6): Temporal-Semantic + Metadata
- Implement `TemporalSemanticQuery`
- Implement `MetadataAnalyzer`
- **Deliverable**: Fusion queries + metadata profiles

### Phase 6 (Weeks 6-7): New Geists (Proof of Concept)
- Write 2-3 new geists using abstractions
- Examples: Drift Velocity Anomaly, Definition Harvester, Cyclical Thinking
- **Deliverable**: 3 new geists demonstrating power of composition

### Phase 7 (Weeks 7-8): Documentation + Stabilization
- Update WRITING_GOOD_GEISTS.md with abstraction patterns
- Add examples to each module
- Performance optimization
- **Deliverable**: Complete documentation + stable APIs

---

## V. Questions for Architectural Review

### Question 1: Relationship to stats.py

**How do these proposed abstractions differ from existing `stats.py` functionality?**

`stats.py` already provides:
- `get_temporal_drift()`: Vault-wide drift using Procrustes alignment
- `EmbeddingMetricsComputer`: Clustering, diversity, intrinsic dimensionality
- `_label_clusters_tfidf()` / `_label_clusters_keybert()`: Cluster labeling

**Key differences**:
- **Purpose**: `stats.py` = diagnostic metrics (vault health reports), Abstractions = operational primitives (geist execution)
- **Granularity**: `stats.py` = vault-wide aggregates, Abstractions = per-note operations
- **Usage**: `stats.py` = called by CLI for reports, Abstractions = called by geists during suggestion generation
- **Temporal**: `stats.py` = two-session comparison, Abstractions = multi-session trajectories per note
- **Clustering**: `stats.py` = compute once for report, Abstractions = session-scoped cache for all geists

**Is there overlap?**
- Both use HDBSCAN for clustering → Could refactor stats.py to use `ClusteringService`
- Both compute drift → `stats.py` for vault-wide, abstractions for per-note
- Cluster labeling → Shared implementation possible

**Should they be unified?**
- No. Different purposes, different usage patterns
- `stats.py` remains diagnostic/reporting layer
- Abstractions remain operational/execution layer
- Could share underlying implementations (e.g., both call same clustering code)

### Question 2: What New Geists Are Unlocked?

**What specific new geist types become possible with these abstractions?**

#### Enabled by EmbeddingTrajectoryCalculator:
1. **Semantic Reversal Detector**: Notes that drift >0.3 then reverse direction (U-turn thinking)
2. **Convergence Cluster**: Groups of 3+ notes all converging toward same semantic area
3. **Drift Velocity Anomaly**: Notes whose drift suddenly accelerates (conceptual breakthrough?)
4. **Cyclical Thinking Patterns**: Notes that cycle through 2-3 distinct semantic states
5. **Directional Drift Groups**: Notes drifting in same semantic direction (collective evolution)
6. **Temporal Stability Score**: Rank notes by interpretive variance (stable vs shifting)
7. **Drift Forecast**: Predict future drift direction based on trajectory
8. **Concept Fusion**: Detect when two initially distinct notes merge semantically
9. **Concept Fission**: Detect when single note splits into multiple interpretations
10. **Seasonal Drift Patterns**: Notes that drift differently by season/time of year

#### Enabled by ExtractionPipeline:
11. **Definition Harvester**: Extract and surface terminology definitions
12. **Claim Harvester**: Extract assertions/claims for review
13. **Hypothesis Harvester**: Surface testable hypotheses
14. **Assumption Detector**: Find embedded assumptions
15. **Terminology Extractor**: Build vault glossary automatically
16. **Citation Harvester**: Extract referenced sources
17. **Example Harvester**: Find concrete examples
18. **Counter-Example Finder**: Find exceptions/counter-cases

#### Enabled by SimilarityProfile:
19. **Hub Type Classifier**: Distinguish hub types (connector, expert, synthesizer)
20. **Similarity Distribution Anomaly**: Notes with unusual similarity patterns
21. **Bridge Quality Ranker**: Rank bridges by connection strength

#### Enabled by TemporalSemanticQuery:
22. **Seasonal Topic Analysis**: "What do I think about in winter vs summer?"
23. **Burst Topic Detector**: Topics that emerge during creation bursts
24. **Time-Bounded Similarity**: "Notes similar to X created in 2024"

#### Enabled by GraphPatternFinder:
25. **Structural Hole Detector**: High-similarity pairs in disconnected components
26. **Path Length Anomaly**: Semantically close but link-distant notes
27. **Bridge Redundancy**: Multiple bridges between same clusters

#### Enabled by Composition:
28. **Temporal Cluster Evolution**: Track cluster births/deaths/merges over sessions
29. **Drifting Cluster Members**: Notes that drift out of their original cluster
30. **Converging Definitions**: Definitions that become more aligned over time

**Total**: 30+ new geist types become trivial to implement with these abstractions.

---

## VI. Design Principles

### Principle 1: Composition Over Components
Power comes from combining abstractions, not individual abstractions.

### Principle 2: Backward Compatibility
All existing geists continue to work unchanged. Refactoring is optional.

### Principle 3: Incremental Adoption
Geists can adopt abstractions one at a time. No "big bang" migration.

### Principle 4: Caching at the Right Layer
Session-scoped caching (clustering, session history) happens in abstractions, not geists.

### Principle 5: Semantic Over Numeric
`SimilarityLevel.HIGH` is clearer than `0.65`. Names over magic numbers.

### Principle 6: Protocols Over Classes
Use Protocol for extensibility (ExtractionStrategy, ContentFilter).

### Principle 7: Stateless Where Possible
Most abstractions are stateless utilities. State only when caching is valuable.

---

## VII. Success Metrics

### Code Reduction
- Average geist size: 50-65 lines → 10-20 lines (70% reduction)
- Temporal geists: Current 4 geists × 60 lines = 240 lines → 4 geists × 15 lines = 60 lines
- Extractors: Current 1 × 80 lines → 8 × 10 lines = 80 lines (7× more geists, same code)

### Capability Expansion
- New geist types enabled: 30+
- Temporal geists: 4 → 10+ (150% increase)
- Content extractors: 1 → 8+ (700% increase)
- Graph geists: 5 → 15+ (200% increase)

### Performance
- Clustering: N geists × M seconds → 1 × M seconds (N× speedup via caching)
- Session queries: Duplicated → Cached at trajectory level

### Developer Experience
- Time to write new temporal geist: 2-3 hours → 30 minutes
- Lines of code to understand: 60 → 15
- Bugs from copy-paste: Reduced (shared implementation)

---

## VIII. Next Steps

1. **Team Review**: Evaluate specification, ask questions, provide feedback
2. **Prioritization**: Which abstractions provide most immediate value?
3. **Proof of Concept**: Implement one abstraction (e.g., SimilarityLevel) to validate approach
4. **Refinement**: Adjust APIs based on proof of concept learnings
5. **Incremental Implementation**: Follow 8-week roadmap
6. **Validation**: Write 2-3 new geists using abstractions to prove composition power

---

## IX. Appendix: Code Examples

### Example A: Before/After Comparison (concept_drift)

**Before** (65 lines):
```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    cursor = vault.db.execute("SELECT session_id, session_date FROM sessions ORDER BY session_date ASC")
    sessions = cursor.fetchall()
    if len(sessions) < 3:
        return []

    notes = vault.notes()
    for note in vault.sample(notes, min(30, len(notes))):
        trajectory = []
        for session_id, session_date in sessions:
            cursor = vault.db.execute(
                "SELECT embedding FROM session_embeddings WHERE session_id = ? AND note_path = ?",
                (session_id, note.path)
            )
            row = cursor.fetchone()
            if row:
                emb = np.frombuffer(row[0], dtype=np.float32)
                trajectory.append((session_date, emb))

        if len(trajectory) < 3:
            continue

        first_emb = trajectory[0][1]
        last_emb = trajectory[-1][1]

        from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
        similarity = sklearn_cosine(first_emb.reshape(1, -1), last_emb.reshape(1, -1))
        drift = 1.0 - float(similarity[0, 0])

        if drift > 0.2:
            # ... 30 more lines computing drift direction and finding aligned neighbors ...
```

**After** (15 lines):
```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    from geistfabrik.temporal_analysis import TemporalPatternFinder, EmbeddingTrajectoryCalculator

    notes = vault.notes()
    drifting = TemporalPatternFinder.find_high_drift_notes(vault, notes, min_drift=0.2)

    suggestions = []
    for note, drift_vector in drifting[:10]:
        neighbors = vault.neighbours(note, k=5)
        calc = EmbeddingTrajectoryCalculator(vault, note)
        aligned = max(neighbors, key=lambda n: calc.drift_alignment(vault.embedding(n)))

        suggestions.append(Suggestion(
            text=f"[[{note.title}]] drifting toward [[{aligned.title}]]",
            notes=[note.title, aligned.title],
            geist_id="concept_drift"
        ))

    return vault.sample(suggestions, k=2)
```

---

**End of Specification**
