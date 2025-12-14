# Sentiment Geists Specification

*Version: 2.0 (Research-Informed)*
*Updated: November 2025*
*Research basis: specs/research/SENTIMENT_ANALYSIS_RESEARCH.md*

---

## Overview

This specification defines a sentiment analysis framework for GeistFabrik that transforms emotional patterns in notes into provocative suggestions. Drawing on academic research in emotion psychology, temporal dynamics, and NLP, this framework uses multiple emotion models simultaneously to create rich, generative provocations.

## Core Philosophy

### 1. Muses, Not Therapists

Sentiment geists pose provocative questions rather than diagnoses:

**Avoid**: "Your notes show signs of depression"
**Embrace**: "What if your most anxious note is your most alive note?"

**Avoid**: "This emotional pattern is unhealthy"
**Embrace**: "Your vault oscillates between anger and fear, never resting in calm - why?"

### 2. Emotional Cartography

Map emotional patterns without judgment. The system observes emotional terrain, identifies patterns, and poses questions - but never prescribes responses or diagnoses conditions.

### 3. Complexity as Creative Opportunity

Research shows emotional complexity increases cognitive flexibility. Mixed emotions, emotional dialecticism, and high granularity are signs of rich thinking, not confusion.

**Embrace**: "Find the note where joy and sadness coexist - that's where the insight lives"

### 4. Multiple Lenses Simultaneously

Use dimensional (valence/arousal), categorical (Plutchik, GoEmotions), appraisal-based (goal relevance), and temporal (dynamics, arcs) models together, not exclusively.

---

## Three-Layer Architecture

### Layer 1: Metadata Inference Module

**File**: `<vault>/_geistfabrik/metadata_inference/sentiment.py`

Computes emotional properties for each note using multiple models:

#### Dimensional Properties:
- **valence**: Float [-1.0, +1.0] (pleasure ↔ displeasure)
- **arousal**: Float [0.0, 1.0] (calm ↔ excited)
- **positive_activation**: Float [0.0, 1.0] (PANAS model - independent of negative)
- **negative_activation**: Float [0.0, 1.0] (PANAS model - independent of positive)

#### Categorical Properties:
- **plutchik_primary**: One of 8 basic emotions (joy, sadness, trust, disgust, fear, anger, surprise, anticipation)
- **plutchik_intensity**: One of 3 levels (low, medium, high)
- **goemotions_labels**: List of 0-27 fine-grained emotions from GoEmotions taxonomy

#### Appraisal Properties:
- **novelty_score**: Float [0.0, 1.0] (how surprising/unexpected)
- **goal_relevance**: Float [0.0, 1.0] (how relevant to implicit goals)
- **coping_potential**: Float [0.0, 1.0] (how much control/agency expressed)

#### Complexity Metrics:
- **emotional_granularity**: Float [0.0, 1.0] (fine-grained vs. coarse emotional vocabulary)
- **emotional_dialecticism**: Boolean (simultaneous positive AND negative)
- **mixed_emotions**: Boolean (conflicting emotions present)
- **dominant_emotion_confidence**: Float [0.0, 1.0]

#### Implementation Details:

**Local-first approach**:
1. **Lexicon-based** (primary): Use NRC Emotion Lexicon + LIWC together
   - Fast, interpretable, works offline
   - Research shows using 2+ lexicons prevents unreliable conclusions
   - NRC covers 8 Plutchik emotions + positive/negative sentiment
   - LIWC provides 73 linguistic categories

2. **Transformer-based** (optional enhancement):
   - For vaults with GPU acceleration available
   - Use GoEmotions-fine-tuned RoBERTa for 27 fine-grained emotions
   - Achieves 96.77% accuracy (2025 research)
   - Falls back to lexicon if unavailable

**Output format**:
```python
{
    "valence": 0.3,
    "arousal": 0.7,
    "positive_activation": 0.6,
    "negative_activation": 0.2,
    "plutchik_primary": "anticipation",
    "plutchik_intensity": "medium",
    "goemotions_labels": ["curiosity", "excitement", "nervousness"],
    "novelty_score": 0.8,
    "goal_relevance": 0.6,
    "coping_potential": 0.7,
    "emotional_granularity": 0.8,
    "emotional_dialecticism": False,
    "mixed_emotions": True,
    "dominant_emotion_confidence": 0.7
}
```

---

### Layer 2: Vault Functions

**File**: `<vault>/_geistfabrik/vault_functions/sentiment.py`

Functions for querying notes by emotional properties:

#### Basic Queries:

```python
@vault_function("notes_by_emotion")
def notes_by_emotion(vault: VaultContext, emotion: str, min_confidence: float = 0.5) -> List[str]:
    """Sample notes with specific Plutchik or GoEmotions emotion.

    Args:
        emotion: One of Plutchik's 8 or GoEmotions' 27 emotions
        min_confidence: Minimum confidence threshold

    Returns:
        List of note titles with [[...]] brackets
    """
```

```python
@vault_function("emotional_quadrant")
def emotional_quadrant(vault: VaultContext, valence: str, arousal: str, k: int = 5) -> List[str]:
    """Sample notes from specific emotional quadrant.

    Args:
        valence: "positive" or "negative"
        arousal: "high" or "low"
        k: Number to sample

    Returns:
        List of note titles in that quadrant

    Example quadrants:
        - positive/high: excited, elated, energized
        - positive/low: calm, content, peaceful
        - negative/high: angry, anxious, stressed
        - negative/low: sad, depressed, bored
    """
```

#### Dimensional Queries:

```python
@vault_function("emotional_spectrum")
def emotional_spectrum(vault: VaultContext, start_emotion: str, end_emotion: str, k: int = 5) -> List[str]:
    """Sample notes along emotional spectrum between two emotions.

    Uses circumplex model to find notes between two emotional poles.
    """
```

```python
@vault_function("emotional_outliers")
def emotional_outliers(vault: VaultContext, dimension: str = "intensity", k: int = 5) -> List[str]:
    """Find notes with extreme emotional characteristics.

    Args:
        dimension: "intensity", "granularity", "complexity", "volatility"
    """
```

#### Temporal Queries:

```python
@vault_function("sentiment_drift")
def sentiment_drift(vault: VaultContext, min_semantic_similarity: float = 0.7,
                    min_emotional_distance: float = 0.5, k: int = 5) -> List[str]:
    """Find note pairs with similar content but different emotions.

    Identifies notes about same topic but experienced with different affect.
    """
```

```python
@vault_function("emotional_trajectory")
def emotional_trajectory(vault: VaultContext, note_path: str, sessions: int = 5) -> Dict[str, Any]:
    """Track how emotions about a note changed across sessions.

    Returns emotional arc data for visualization/analysis.
    """
```

#### Complex Queries:

```python
@vault_function("emotional_bridges")
def emotional_bridges(vault: VaultContext, k: int = 3) -> List[str]:
    """Find notes that bridge different emotional regions of the vault.

    Identifies notes with mixed/dialectic emotions that connect otherwise
    emotionally distant clusters.
    """
```

```python
@vault_function("emotional_opposites")
def emotional_opposites(vault: VaultContext, k: int = 5) -> List[str]:
    """Find note pairs with opposite Plutchik emotions.

    Examples: joy ↔ sadness, fear ↔ anger, trust ↔ disgust
    """
```

```python
@vault_function("high_granularity_notes")
def high_granularity_notes(vault: VaultContext, k: int = 5) -> List[str]:
    """Find notes with most emotionally nuanced vocabulary.

    High granularity = fine-grained emotional distinctions.
    Research shows this correlates with better coping and cognitive flexibility.
    """
```

---

### Layer 3: Geists (Expanded & Research-Informed)

## Original Geists (from v1.0 spec)

### Code Geists

#### 1. emotional_mirror
**File**: `src/geistfabrik/default_geists/code/emotional_mirror.py`

Pairs notes with opposite valence but similar semantics.

**Provocation**: "What if the things that make you sad and happy are two sides of the same coin?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find semantically similar notes with opposite emotional valence.

    Implementation:
    1. Filter notes with strong positive valence (> 0.5)
    2. Filter notes with strong negative valence (< -0.5)
    3. For each positive note, find most semantically similar negative note
    4. Return pairs with similarity > 0.7 and valence delta > 1.0

    Returns 2-3 suggestions maximum.
    """
```

**Example output**:
> "[[Vacation Planning]] (joy, positive) mirrors [[Burnout Recovery]] (sadness, negative) with 82% semantic similarity. What if rest and escape are the same yearning wearing different faces?"

---

#### 2. mood_constellation
**File**: `src/geistfabrik/default_geists/code/mood_constellation.py`

Clusters emotionally similar notes across different topics.

**Provocation**: "Your vault has emotional neighborhoods - which one are you living in?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find clusters of notes with similar emotional profiles.

    Implementation:
    1. Compute emotional distance matrix (valence + arousal + 8 Plutchik emotions)
    2. Use HDBSCAN clustering on emotional features (NOT semantic)
    3. Find clusters of 5+ notes
    4. Sample 1 cluster with highest within-cluster emotional coherence
    5. Return representative notes from cluster

    Returns 1 suggestion showing 3-5 notes in constellation.
    """
```

**Example output**:
> "Emotional constellation 'anxious anticipation': [[Job Interview Prep]], [[First Date]], [[Launching Project]], [[Medical Test Results]], [[Moving Day]]. Five unrelated topics, one emotional signature. What are you really preparing for?"

---

#### 3. intensity_spike
**File**: `src/geistfabrik/default_geists/code/intensity_spike.py`

Highlights unusually emotionally charged notes.

**Provocation**: "Your calmest vault note still has 10x the emotional intensity of your baseline - why?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find notes with anomalous emotional intensity.

    Implementation:
    1. Compute vault-wide emotional intensity distribution
        intensity = sqrt(valence^2 + arousal^2)
    2. Identify notes > 2 standard deviations from mean
    3. For each spike, determine dominant emotion
    4. Return 2-3 highest spikes

    Returns notes with intensity > mean + 2*stddev.
    """
```

**Example output**:
> "[[Technical Documentation for Auth System]] registers emotional intensity 3.2σ above your vault baseline (surprise + fear). What happened while writing this?"

---

### Tracery Geists

#### 4. emotional_drift (Tracery)
**File**: `src/geistfabrik/default_geists/tracery/emotional_drift.yaml`

Questions changes in emotional relationship with recurring topics.

```yaml
type: geist-tracery
id: emotional_drift
description: Surfaces notes where emotions about same topic changed over time

tracery:
  origin: "#setup# #question#"

  setup:
    - "[[#old_note#]] (#old_emotion#) became [[#new_note#]] (#new_emotion#)"
    - "Your feeling about #topic# shifted from #old_emotion# to #new_emotion#"

  question:
    - "What changed between then and now?"
    - "What happened to flip your emotional relationship?"
    - "What if the old feeling is still there, just hidden?"
    - "Which emotion was the real one?"

  # Uses sentiment_drift() function
  drift_pair: ["$vault.sentiment_drift(0.7, 0.5, 1)"]
  old_note: ["#drift_pair.split('|||')[0]#"]
  new_note: ["#drift_pair.split('|||')[1]#"]
  old_emotion: ["#drift_pair.split('|||')[2]#"]
  new_emotion: ["#drift_pair.split('|||')[3]#"]
  topic: ["#old_note.split('[[')[1].split(']]')[0]#"]
```

---

#### 5. mixed_feelings (Tracery)
**File**: `src/geistfabrik/default_geists/tracery/mixed_feelings.yaml`

Surfaces notes resisting emotional simplification.

```yaml
type: geist-tracery
id: mixed_feelings
description: Highlights notes with mixed/dialectic emotions

tracery:
  origin: "#provocation#"

  provocation:
    - "[[#note#]] feels both #emotion1# and #emotion2# simultaneously. What if that contradiction is the point?"
    - "You can't decide if [[#note#]] is #emotion1# or #emotion2#. What if it's both?"
    - "[[#note#]] resists emotional categorization (#emotions_list#). What's it protecting?"

  note: ["$vault.emotional_bridges(1)"]
  emotion1: ["#note.extract_first_emotion#"]
  emotion2: ["#note.extract_second_emotion#"]
  emotions_list: ["#note.all_emotions#"]
```

---

#### 6. joy_archaeology (Tracery)
**File**: `src/geistfabrik/default_geists/tracery/joy_archaeology.yaml`

Resurfaces buried positive notes.

```yaml
type: geist-tracery
id: joy_archaeology
description: Unearths forgotten positive notes from vault history

tracery:
  origin: "#provocation#"

  provocation:
    - "[[#old_joy#]] from #timeframe# radiated joy (plutchik intensity: high). What happened to that feeling?"
    - "You wrote [[#old_joy#]] #timeframe# ago in a state of #specific_emotion#. Where did it go?"
    - "Excavating [[#old_joy#]] - a note from #timeframe# that you haven't revisited. What if you need it now?"

  old_joy: ["$vault.notes_by_emotion('joy', 0.7)"]
  timeframe: ["more than 6 months", "over a year", "long ago"]
  specific_emotion: ["delight", "excitement", "contentment", "gratitude"]
```

---

## NEW Geists (Research-Informed, v2.0)

These geists are inspired by academic research in emotional dynamics, complexity, and temporal patterns. They reuse architectural patterns from existing drift/velocity/burst geists.

### Temporal Dynamics Geists (Reuse drift/velocity/burst patterns)

#### 7. valence_flip
**File**: `src/geistfabrik/default_geists/code/valence_flip.py`

**Research basis**: Affective instability, brain-state transitions (SENTIMENT_ANALYSIS_RESEARCH.md §2)

**Architecture pattern**: Reuses `concept_drift.py` temporal tracking pattern

**Provocation**: "These notes flipped emotional polarity - what event caused the reversal?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect notes that flipped from positive to negative valence (or vice versa).

    REUSES pattern from: concept_drift.py (temporal embeddings + session tracking)

    Implementation:
    1. Query session_embeddings table for notes with 3+ sessions
    2. For each note, compute valence across sessions using sentiment metadata
    3. Detect polarity flips: valence crosses zero threshold (±0.3 buffer)
    4. Calculate flip magnitude: |valence_before - valence_after|
    5. Filter for flips with magnitude > 0.6 (strong reversal)
    6. Return top 3 flips ranked by magnitude

    Temporal SQL query similar to concept_drift.py:
    ```sql
    SELECT n.path, n.title,
           se1.session_id as old_session,
           se2.session_id as new_session,
           m1.valence as old_valence,
           m2.valence as new_valence
    FROM notes n
    JOIN session_embeddings se1 ON n.path = se1.note_path
    JOIN session_embeddings se2 ON n.path = se2.note_path
    WHERE se2.session_id > se1.session_id
      AND (m1.valence > 0.3 AND m2.valence < -0.3)  -- positive to negative
       OR (m1.valence < -0.3 AND m2.valence > 0.3)  -- negative to positive
    ```

    Returns 2-3 suggestions.
    """
```

**Example output**:
> "[[Career Planning]] flipped from joy (+0.7) to sadness (-0.6) across 4 sessions. Session 2024-09-15 marks the reversal. What happened that day to invert your emotional relationship with this idea?"

**Code reuse**:
- Temporal analysis infrastructure from `concept_drift.py`
- Session-based comparison logic
- Embedding retrieval from `session_embeddings` table

---

#### 8. emotional_velocity
**File**: `src/geistfabrik/default_geists/code/emotional_velocity.py`

**Research basis**: Temporal dynamics, affective instability as predictor (SENTIMENT_ANALYSIS_RESEARCH.md §2.3)

**Architecture pattern**: Reuses `drift_velocity_anomaly.py` pattern

**Provocation**: "This note's emotional state changed faster than anything else in your vault - why the sudden shift?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect notes with unusually rapid emotional change.

    REUSES pattern from: drift_velocity_anomaly.py

    Implementation:
    1. Compute emotional velocity for each note with 2+ sessions
        velocity = emotional_distance / time_delta
        emotional_distance = sqrt((v2-v1)^2 + (a2-a1)^2)  # valence + arousal
    2. Compute vault-wide velocity distribution
    3. Identify notes with velocity > mean + 2*stddev
    4. Return top 3 ranked by velocity

    Research insight: "It's not how negative you feel, but how unstably you feel it"

    Returns 2-3 notes with highest emotional velocity.
    """
```

**Example output**:
> "[[Project Retrospective]] velocity: 0.87 emotional units/day (3.1σ above baseline). From contentment to anxiety in 48 hours. What accelerated this shift?"

**Code reuse**:
- Velocity calculation from `drift_velocity_anomaly.py`
- Statistical anomaly detection
- Temporal distance normalization

---

#### 9. emotional_burst
**File**: `src/geistfabrik/default_geists/code/emotional_burst.py`

**Research basis**: Affective oscillations, relaxation oscillator models (SENTIMENT_ANALYSIS_RESEARCH.md §2.4)

**Architecture pattern**: Reuses `burst_evolution.py` pattern

**Provocation**: "5 notes created in 24 hours, all sharing the same emotional signature - what burst triggered this?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect temporal bursts of notes with similar emotional signatures.

    REUSES pattern from: burst_evolution.py (creation bursts + drift tracking)

    Implementation:
    1. Identify creation bursts (5+ notes within 48-hour window)
    2. For each burst, compute emotional centroid in valence/arousal space
    3. Calculate within-burst emotional coherence (avg pairwise similarity)
    4. Filter for bursts with coherence > 0.7 (tight emotional clustering)
    5. Return 1-2 bursts with highest coherence

    Research basis: Bipolar oscillations modeled as relaxation oscillators

    Returns 1-2 suggestions showing emotionally coherent bursts.
    """
```

**Example output**:
> "November 3rd burst: 7 notes created in 18 hours, all clustering in 'anxious anticipation' region (fear + anticipation, high arousal). [[Interview Prep]], [[Budget Planning]], [[Deadline Tasks]], [[Conflict Resolution]], [[Health Checkup]], [[Performance Review]], [[Travel Planning]]. What made that day feel like a countdown?"

**Code reuse**:
- Burst detection from `burst_evolution.py`
- Temporal windowing
- Drift metrics repurposed for emotional coherence

---

#### 10. emotional_inertia
**File**: `src/geistfabrik/default_geists/code/emotional_inertia.py`

**Research basis**: Emotional persistence, temporal dependency (SENTIMENT_ANALYSIS_RESEARCH.md §2.3)

**Architecture pattern**: Reuses `convergent_evolution.py` tracking pattern

**Provocation**: "This emotion persisted across 12 notes spanning 3 months - what's keeping it alive?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect emotions that persist across many notes/sessions.

    REUSES pattern from: convergent_evolution.py (tracking semantic persistence)

    Implementation:
    1. For each note sequence (temporal ordering), track dominant emotion
    2. Identify runs of 5+ consecutive notes with same Plutchik primary emotion
    3. Calculate persistence span (time from first to last note in run)
    4. Filter for runs spanning 30+ days
    5. Return top 2-3 longest runs

    Research: High emotional inertia = emotion persists even when context changes

    Returns 2-3 notes showing emotional persistence.
    """
```

**Example output**:
> "Sadness inertia: [[Loss]], [[Transition]], [[Letting Go]], [[Closure]], [[Moving On]], [[New Beginnings]], [[Fresh Start]] - 7 notes over 87 days, all tagged 'sadness' despite progression narrative. What if sadness is protecting you from something?"

**Code reuse**:
- Temporal sequence tracking from `convergent_evolution.py`
- Run-length encoding
- Session-based analysis

---

### Complexity & Granularity Geists

#### 11. emotional_granularity
**File**: `src/geistfabrik/default_geists/code/emotional_granularity.py`

**Research basis**: Emotional differentiation, adaptive benefits (SENTIMENT_ANALYSIS_RESEARCH.md §3.3)

**Provocation**: "These notes all say 'I feel bad' - can you find the 7 different types of bad hiding there?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Contrast high-granularity notes with low-granularity notes.

    Implementation:
    1. Compute granularity score for each note:
        - Count unique GoEmotions labels used
        - Weight by emotional vocabulary diversity in text
        - Score = unique_emotions / total_emotional_words
    2. Find highest granularity note (many distinct emotions)
    3. Find lowest granularity note (generic "positive/negative" only)
    4. Return pair for contrast

    Research: High granularity → better coping, more adaptive behaviors

    Provocation: Invite user to revisit low-granularity notes and add nuance

    Returns 1-2 suggestions pairing high vs. low granularity.
    """
```

**Example output**:
> "[[Reflections on 2024]] uses 9 distinct emotions (disappointment, relief, gratitude, regret, pride, hope, nostalgia, anxiety, contentment) with high granularity (0.82). Meanwhile, [[Bad Day]] just says 'negative' (granularity: 0.12). What emotional distinctions are you missing?"

---

#### 12. dialectic_tension
**File**: `src/geistfabrik/default_geists/code/dialectic_tension.py`

**Research basis**: Emotional dialecticism, East Asian vs. Western tolerance (SENTIMENT_ANALYSIS_RESEARCH.md §3.1)

**Provocation**: "This note holds two opposite truths at once - what if that's wisdom, not confusion?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find notes experiencing positive AND negative emotions simultaneously.

    Implementation:
    1. Query notes with emotional_dialecticism = True
    2. Filter for high confidence (> 0.6) on both positive and negative activation
    3. Calculate dialectic strength: min(pos_activation, neg_activation)
    4. Return top 3 by dialectic strength

    Research: Dialecticism ≠ mixed emotions. It's holding opposites together, not
    alternating between them. More common in collectivist cultures.

    Returns 2-3 notes with strongest dialectic tension.
    """
```

**Example output**:
> "[[Goodbye Letter to Old Job]] scores high on BOTH positive activation (0.78) and negative activation (0.81). Gratitude and grief occupy the same space. What if leaving and staying are equally true?"

---

### Appraisal-Based Geists

#### 13. novelty_blindness
**File**: `src/geistfabrik/default_geists/code/novelty_blindness.py`

**Research basis**: Appraisal theory, novelty detection (SENTIMENT_ANALYSIS_RESEARCH.md §1.1)

**Provocation**: "These notes surprised you with radical novelty, but you wrote them calmly - what are you avoiding?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find notes with high novelty but low arousal (muted response to surprise).

    Implementation:
    1. Query notes with high novelty_score (> 0.7)
    2. Filter for low arousal (< 0.3)
    3. Rank by novelty/arousal ratio
    4. Return top 3

    Appraisal theory: Novelty should trigger arousal (surprise, fear, or excitement).
    Low arousal + high novelty = suppressed emotional response to unexpected events.

    Provocation: What new ideas are you intellectualizing instead of feeling?

    Returns 2-3 notes showing novelty/arousal mismatch.
    """
```

**Example output**:
> "[[Revolutionary Product Idea]] novelty: 0.89, arousal: 0.21. This note describes something completely unprecedented, yet you wrote it like a grocery list. What if you're too scared to get excited?"

---

#### 14. goal_conflict
**File**: `src/geistfabrik/default_geists/code/goal_conflict.py`

**Research basis**: Appraisal theory, goal relevance (SENTIMENT_ANALYSIS_RESEARCH.md §1.1)

**Provocation**: "These three notes serve the same hidden goal from opposite angles - what are you really trying to do?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find notes with high goal relevance but opposite emotional valence.

    Implementation:
    1. Cluster notes by semantic similarity (same topic/goal)
    2. Within each cluster, identify notes with:
        - High goal_relevance (> 0.7)
        - Opposite valence signs (some positive, some negative)
    3. Return 1 cluster showing 3-4 notes with goal conflict

    Appraisal theory: Same goal, different emotions = conflicting appraisals

    Provocation: Your goals might be contradictory

    Returns 1 suggestion showing goal-conflicted cluster.
    """
```

**Example output**:
> "Goal conflict cluster: [[Work-Life Balance]] (+0.6), [[Career Ambition]] (+0.8), [[Family Time]] (-0.3), [[Saying No to Projects]] (-0.5). All four notes score high on goal relevance (avg: 0.81), but pull in opposite emotional directions. What if balance isn't the goal - choosing is?"

---

### Network & Contagion Geists

#### 15. emotional_contagion
**File**: `src/geistfabrik/default_geists/code/emotional_contagion.py`

**Research basis**: Emotional contagion, network effects (SENTIMENT_ANALYSIS_RESEARCH.md §4.4)

**Architecture pattern**: Reuses `hidden_hub.py` network centrality pattern

**Provocation**: "This note infected 8 others with its emotional signature - it's a super-spreader"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find emotionally influential notes (super-spreaders).

    REUSES pattern from: hidden_hub.py (semantic centrality → emotional centrality)

    Implementation:
    1. Build vault graph (notes as nodes, links as edges)
    2. For each note, compute emotional influence:
        - Find all neighbors (linked notes)
        - Calculate emotional similarity to neighbors
        - influence_score = avg_similarity * neighbor_count
    3. Identify notes with influence > 0.7 and 5+ neighbors
    4. Return top 3 super-spreaders

    Research: Emotions spread through networks without awareness or direct contact

    Returns 2-3 emotionally influential hub notes.
    """
```

**Example output**:
> "[[Burnout Reflection]] is an emotional super-spreader: 9 linked notes share its 'exhaustion + resignation' signature (avg similarity: 0.79). Network includes [[Sprint Retrospective]], [[Weekend Plans]], [[Energy Management]], [[Saying No]], [[Boundaries]]. What if burnout is contagious in your vault?"

**Code reuse**:
- Network analysis from `hidden_hub.py`
- Centrality metrics
- Graph traversal

---

### Narrative Arc Geists

#### 16. emotional_arc
**File**: `src/geistfabrik/default_geists/code/emotional_arc.py`

**Research basis**: Six basic emotional arcs (SENTIMENT_ANALYSIS_RESEARCH.md §4.2)

**Provocation**: "Your vault follows a 'man in a hole' pattern - what's the hole, and when do you climb out?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Identify emotional narrative arcs across note sequences.

    Implementation:
    1. Order notes by creation time
    2. Compute valence trajectory (valence over time)
    3. Pattern match against 6 basic shapes using DTW (Dynamic Time Warping):
        - Rags to riches (rise)
        - Tragedy (fall)
        - Man in a hole (fall → rise)
        - Icarus (rise → fall)
        - Cinderella (rise → fall → rise)
        - Oedipus (fall → rise → fall)
    4. Return best-fitting arc with confidence > 0.6

    Research: All stories reduce to 6 emotional arcs

    Provocation: Name your vault's narrative shape

    Returns 1 suggestion identifying arc.
    """
```

**Example output**:
> "Your past 3 months follow an 'Icarus arc' (rise then fall): Started at valence -0.2 in August, peaked at +0.7 in October ([[Launch Success]], [[Team Recognition]], [[Milestone Achieved]]), crashed to -0.5 in November ([[Burnout]], [[Scope Creep]], [[Conflict]]). What happened at the peak to trigger the fall?"

---

### Provocative Meta-Geists

#### 17. affect_labeling_trap
**File**: `src/geistfabrik/default_geists/code/affect_labeling_trap.py`

**Research basis**: Affect labeling paradox (SENTIMENT_ANALYSIS_RESEARCH.md §4.3)

**Provocation**: "You've named this feeling 5 different ways - what if the naming is the problem?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Identify notes with excessive emotional labeling (crystallized affect).

    Implementation:
    1. Count explicit emotion words in each note
    2. Calculate labeling density = emotion_words / total_words
    3. Find notes with density > 0.05 (high labeling)
    4. Return top 3

    Research: Naming emotions can help OR harm. It "crystallizes" affect, limiting
    reinterpretation. Over-labeling may trap you in one emotional interpretation.

    Provocation: Try feeling this note without naming it

    Returns 2-3 over-labeled notes.
    """
```

**Example output**:
> "[[Breakup Processing]] contains 47 emotion words in 320 words (14.7% density): 'sad', 'heartbroken', 'devastated', 'numb', 'angry', 'betrayed', 'lost', 'hopeless'. Research shows naming can trap you in one interpretation. What if you felt this note without the labels?"

---

#### 18. emotional_absence
**File**: `src/geistfabrik/default_geists/code/emotional_absence.py`

**Research basis**: GoEmotions taxonomy, emotional quadrants (SENTIMENT_ANALYSIS_RESEARCH.md §5.3)

**Provocation**: "Your vault has zero notes in the 'calm contentment' quadrant - what are you avoiding?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Identify missing emotional regions in vault.

    Implementation:
    1. Map vault notes to 4 quadrants (valence × arousal)
    2. Identify empty/sparse quadrants (< 5% of notes)
    3. For GoEmotions taxonomy, check which of 27 emotions are absent
    4. Return 1-2 suggestions about emotional blind spots

    Provocation: What emotions are you not allowing yourself to write about?

    Returns 1-2 suggestions about emotional absences.
    """
```

**Example output**:
> "Emotional blind spot: Your vault has 0 notes in low-arousal positive space (calm, content, peaceful, serene). 78% cluster in high-arousal regions (excited, anxious, energized, stressed). GoEmotions analysis shows zero instances of: 'relief', 'approval', 'caring', 'gratitude'. What if calm feels dangerous?"

---

#### 19. plutchik_dyads
**File**: `src/geistfabrik/default_geists/code/plutchik_dyads.py`

**Research basis**: Plutchik's wheel, emotional combinations (SENTIMENT_ANALYSIS_RESEARCH.md §1.1)

**Provocation**: "Joy + trust creates love. Which notes in your vault are accidentally creating tertiary emotions?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Identify notes forming Plutchik emotional dyads (combinations).

    Implementation:
    1. For notes with multiple Plutchik emotions, check for dyad patterns:
        - Primary dyads (adjacent): joy + trust = love
        - Secondary dyads: anticipation + joy = optimism
        - Tertiary dyads: joy + fear = guilt
        - Opposite dyads: joy + sadness = conflict
    2. Find notes matching dyad patterns
    3. Return 2-3 with strongest dyad signals

    Provocation: Complex emotions emerge from combinations

    Returns 2-3 notes forming dyads.
    """
```

**Example output**:
> "[[Wedding Planning]] combines anticipation + joy (optimism dyad, secondary). [[Difficult Conversation]] combines fear + surprise (awe dyad). [[Farewell Party]] combines joy + sadness (opposite dyad = bittersweet conflict). What tertiary emotions are you creating without realizing?"

---

## Implementation Roadmap

### Phase 1: Foundation (Metadata + Functions)
**Timeline**: 2-3 weeks

1. Implement `sentiment.py` metadata module
   - NRC + LIWC lexicon integration
   - Dimensional scores (valence, arousal, PANAS)
   - Plutchik primary emotion detection
   - Complexity metrics (granularity, dialecticism)
   - Appraisal scores (novelty, goal relevance, coping)

2. Implement 12 vault functions
   - Basic queries: `notes_by_emotion()`, `emotional_quadrant()`
   - Temporal queries: `sentiment_drift()`, `emotional_trajectory()`
   - Complex queries: `emotional_bridges()`, `emotional_opposites()`

3. Testing
   - Unit tests for metadata inference
   - Vault function tests with known emotion examples
   - Validate against GoEmotions dataset samples

**Deliverable**: Metadata layer + functions ready for geist development

---

### Phase 2: Core Code Geists (Original 6 + Temporal Dynamics)
**Timeline**: 2-3 weeks

Implement in priority order:

1. **valence_flip** (NEW, priority)
2. emotional_mirror (original)
3. mood_constellation (original)
4. intensity_spike (original)
5. **emotional_velocity** (NEW)
6. **emotional_burst** (NEW)
7. **emotional_inertia** (NEW)

**Testing**:
- Dedicated unit tests per geist
- Integration tests with test vault
- Validate provocations align with philosophy

**Deliverable**: 7 code geists generating research-informed provocations

---

### Phase 3: Complexity & Appraisal Geists
**Timeline**: 2 weeks

1. **emotional_granularity** (NEW)
2. **dialectic_tension** (NEW)
3. **novelty_blindness** (NEW)
4. **goal_conflict** (NEW)

**Testing**:
- Complex emotional scenarios
- Appraisal theory validation

**Deliverable**: 4 geists exploring emotional complexity

---

### Phase 4: Network & Arc Geists
**Timeline**: 2 weeks

1. **emotional_contagion** (NEW)
2. **emotional_arc** (NEW)
3. **affect_labeling_trap** (NEW)
4. **emotional_absence** (NEW)
5. **plutchik_dyads** (NEW)

**Testing**:
- Network analysis validation
- Arc pattern matching
- Meta-analysis accuracy

**Deliverable**: 5 geists using network/narrative patterns

---

### Phase 5: Tracery Geists
**Timeline**: 1 week

1. emotional_drift (original)
2. mixed_feelings (original)
3. joy_archaeology (original)

**Testing**:
- Tracery grammar validation
- Vault function integration
- Output quality review

**Deliverable**: 3 Tracery geists

---

### Phase 6: Optional Enhancement (Transformer Models)
**Timeline**: 1-2 weeks (optional)

1. Integrate GoEmotions-fine-tuned RoBERTa
2. Add GPU acceleration detection
3. Implement transformer fallback logic
4. Performance benchmarking

**Deliverable**: Enhanced 27-emotion detection (optional)

---

## Testing Strategy

### Unit Tests

**Metadata Inference** (`tests/unit/test_sentiment_metadata.py`):
- Lexicon agreement (NRC + LIWC)
- Dimensional score ranges (valence, arousal, PANAS)
- Plutchik emotion detection accuracy
- Complexity metric calculation
- Known examples: "I am very happy" → joy, high valence, high positive activation

**Vault Functions** (`tests/unit/test_sentiment_functions.py`):
- Correct filtering by emotion
- Quadrant boundaries
- Drift detection sensitivity
- Trajectory calculation
- Empty vault handling

**Geists** (individual files per geist):
- Follows existing template (GEIST_TESTING_TEMPLATE.md)
- Core tests: returns_suggestions, structure, obsidian_link
- Edge cases: empty_vault, insufficient_data
- Geist-specific tests (e.g., valence_flip tests polarity reversal)

### Integration Tests

**End-to-End** (`tests/integration/test_sentiment_geists.py`):
- Full pipeline: metadata → functions → geists
- Test vault with known emotional patterns:
  - Positive→negative flip example
  - Emotional burst example
  - Mixed emotion example
- Validate provocations are non-diagnostic

### Regression Tests

**GoEmotions Dataset** (`tests/integration/test_goemotions_regression.py`):
- Sample 100 GoEmotions examples
- Validate emotion detection accuracy > 70% (lexicon baseline)
- Ensure no crashes on edge cases

**Philosophy Compliance** (`tests/integration/test_sentiment_philosophy.py`):
- Scan all geist outputs for diagnostic language ("you have", "you should")
- Validate all suggestions follow "What if...?" pattern
- Check no therapeutic framing

---

## Configuration

**File**: `<vault>/_geistfabrik/config.yaml`

```yaml
sentiment:
  # Metadata inference
  lexicons:
    - nrc_emotion
    - liwc

  # Optional transformer
  use_transformer: false  # Set to true for GoEmotions-RoBERTa
  transformer_model: "google/goemotions-roberta"

  # Thresholds
  emotion_confidence_threshold: 0.5
  valence_neutral_range: [-0.3, 0.3]
  arousal_neutral_range: [0.0, 0.4]

  # Granularity
  high_granularity_threshold: 0.6
  dialectic_minimum_activation: 0.5

  # Temporal
  drift_min_sessions: 3
  velocity_stddev_threshold: 2.0
  burst_window_hours: 48

  # Enabled geists
  enabled_geists:
    - valence_flip
    - emotional_mirror
    - mood_constellation
    - intensity_spike
    - emotional_velocity
    - emotional_burst
    - emotional_inertia
    - emotional_granularity
    - dialectic_tension
    - novelty_blindness
    - goal_conflict
    - emotional_contagion
    - emotional_arc
    - affect_labeling_trap
    - emotional_absence
    - plutchik_dyads
    - emotional_drift
    - mixed_feelings
    - joy_archaeology
```

---

## Code Reuse Summary

These new geists reuse proven patterns from existing geists:

| New Geist | Reuses Pattern From | Shared Code |
|-----------|-------------------|-------------|
| valence_flip | concept_drift.py | Temporal embeddings, session tracking, SQL queries |
| emotional_velocity | drift_velocity_anomaly.py | Velocity calculation, statistical anomaly detection |
| emotional_burst | burst_evolution.py | Burst detection, temporal windowing, coherence metrics |
| emotional_inertia | convergent_evolution.py | Sequence tracking, run-length encoding |
| emotional_contagion | hidden_hub.py | Network analysis, centrality metrics, graph traversal |

**Code abstraction opportunities**:
- Extract `temporal_analysis.py` module for shared session/embedding queries
- Extract `graph_analysis.py` for network centrality calculations
- Extract `similarity_analysis.py` for distance/coherence metrics

These abstractions already exist in main (per CLAUDE.md):
- `src/geistfabrik/temporal_analysis.py` ✅
- `src/geistfabrik/graph_analysis.py` ✅
- `src/geistfabrik/similarity_analysis.py` ✅

**Therefore**: New sentiment geists can import from these modules directly.

---

## Research Alignment

All geists align with research findings from `specs/research/SENTIMENT_ANALYSIS_RESEARCH.md`:

- **Multiple models**: Dimensional, categorical, appraisal, temporal (§1)
- **Temporal dynamics**: Velocity, bursts, inertia, arcs (§2)
- **Complexity as richness**: Granularity, dialecticism, mixed emotions (§3)
- **Provocative framing**: Muses not therapists, questions not diagnoses (§4)
- **Fine-grained detection**: GoEmotions 27 emotions, Plutchik dyads (§5)

---

## Success Metrics

Sentiment geists succeed when they:

1. **Generate surprise**: "I never thought about my notes this way"
2. **Provoke questions**: "What if my sadness is actually grief?" vs. "You are depressed"
3. **Avoid diagnosis**: Zero therapeutic/clinical language in output
4. **Reveal patterns**: "I didn't realize my vault oscillates between fear and anger"
5. **Inspire action**: User revisits old notes, adds emotional nuance, questions labels

**Anti-patterns to avoid**:
- ❌ "Your notes show signs of depression" (diagnostic)
- ❌ "You should regulate this emotion" (prescriptive)
- ❌ "This pattern is unhealthy" (judgmental)

**Embrace instead**:
- ✅ "What if your most anxious note is your most alive note?" (provocative)
- ✅ "These notes form an emotional oscillator - what's the frequency?" (generative)
- ✅ "Your vault has zero calm notes - what are you avoiding?" (curious)

---

## Alternative Geist Candidates

These additional geist concepts emerged from research but were not included in the core v2.0 spec. They represent future directions and alternative approaches.

### From Emotion Research

#### 20. emotional_weather
**File**: `src/geistfabrik/default_geists/code/emotional_weather.py`

**Research basis**: Vault-wide emotional climate analysis

**Provocation**: "Your vault's emotional weather is 'anxious fog with occasional bursts of optimism' - what climate are you creating?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Analyze vault-wide emotional climate over time windows.

    Implementation:
    1. Divide vault into temporal windows (weekly, monthly)
    2. Compute aggregate emotional metrics per window:
        - Dominant emotion (mode)
        - Emotional diversity (entropy)
        - Valence/arousal distribution
    3. Classify climate using weather metaphors:
        - "Sunny" (high positive, low variance)
        - "Stormy" (high negative, high variance)
        - "Foggy" (low arousal, high uncertainty)
        - "Electric" (high arousal, mixed valence)
    4. Return 1-2 climate descriptions with trend analysis

    Provocation: Name your vault's emotional ecosystem

    Returns 1-2 climate observations.
    """
```

**Example output**:
> "Your vault's emotional weather shifted from 'calm overcast' (September: low arousal, neutral valence) to 'electric storm' (November: high arousal, volatile valence). The climate destabilized around October 15th. What front moved in?"

---

#### 21. emotion_prediction
**File**: `src/geistfabrik/default_geists/code/emotion_prediction.py`

**Research basis**: Temporal dynamics, affective forecasting

**Provocation**: "Based on your patterns, your next note will feel like disappointment mixed with determination - write it and see"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Predict next note's emotional signature based on vault patterns.

    Implementation:
    1. Build emotional time series from recent notes (last 30 days)
    2. Fit simple predictive model (ARIMA, moving average, or pattern matching)
    3. Forecast next emotional state
    4. Include confidence interval
    5. Return prediction as invitation to test it

    WARNING: Frame as playful experiment, not deterministic prediction

    Provocation: Test your emotional predictability

    Returns 1 prediction.
    """
```

**Example output**:
> "Your emotional trajectory predicts tomorrow's note will land in the 'frustrated but curious' quadrant (negative valence +0.3, high arousal 0.7). Your vault follows a 7-day emotional cycle. What if you deliberately write something joyful to break the pattern?"

---

#### 22. emotional_contrarian
**File**: `src/geistfabrik/default_geists/code/emotional_contrarian.py`

**Research basis**: Emotional absence, counterbalance

**Provocation**: "Every note in your vault is high arousal - what would a calm note say?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Identify and challenge vault's dominant emotional stance.

    Implementation:
    1. Compute vault-wide emotional distribution
    2. Identify dominant quadrant (e.g., 70% in high-arousal negative)
    3. Find opposite quadrant with minimal representation
    4. Generate provocation inviting exploration of underrepresented emotions

    Provocation: Balance your emotional portfolio

    Returns 1 suggestion.
    """
```

**Example output**:
> "91% of your vault lives in high-arousal space (anxious, excited, angry, enthusiastic). Only 4 notes occupy low-arousal positive (calm, content, peaceful). Your vault doesn't know how to rest. What if you wrote one note from a place of quiet contentment?"

---

#### 23. emotion_archaeology
**File**: `src/geistfabrik/default_geists/code/emotion_archaeology.py`

**Research basis**: Emotional memory, mood-congruent recall

**Provocation**: "You buried 6 notes full of hope in early 2023 - your current mood would never find them"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Excavate old notes with emotions opposite to recent dominant mood.

    Implementation:
    1. Compute recent emotional trend (last 30 days)
    2. Identify dominant recent emotion (e.g., sadness)
    3. Find old notes (180+ days) with opposite emotion (joy)
    4. Filter for notes not revisited recently
    5. Return 2-3 excavated notes

    Research basis: Mood-congruent recall means you won't naturally find these

    Provocation: Dig up emotional counterexamples to your current state

    Returns 2-3 buried notes.
    """
```

**Example output**:
> "Emotional archaeology: While you've been writing anxious notes for 6 weeks, [[Summer Breakthrough]] (joy, 2023-07-12), [[Teaching Success]] (pride, 2023-08-03), [[Garden Project]] (contentment, 2023-06-22) gathered dust. You won't think to read them now - but you should."

---

### From Extended Mind Research

These geists explicitly frame the vault as part of your extended mind, not just a tool.

#### 24. extended_memory_conflict
**File**: `src/geistfabrik/default_geists/code/extended_memory_conflict.py`

**Research basis**: Extended mind thesis, transactive memory

**Provocation**: "Your vault remembers this differently than you do - which memory is real?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Identify notes that contradict your current biological memory.

    Implementation:
    1. Use sentiment drift + semantic drift to find notes that changed
    2. Highlight notes with OLD interpretation contradicting CURRENT interpretation
    3. Frame as extended mind vs. biological mind conflict
    4. Return 2-3 memory conflicts

    Extended mind angle: Your extended mind has different memories

    Returns 2-3 conflicting memory pairs.
    """
```

**Example output**:
> "[[Leaving Academia]] in session 2024-03-15 felt like 'relief and liberation.' In session 2024-11-10, same note feels like 'regret and loss.' Your biological memory rewrote history. Your extended mind (the vault) preserves the original. Which version is true?"

---

#### 25. transactive_boundaries
**File**: `src/geistfabrik/default_geists/code/transactive_boundaries.py`

**Research basis**: Extended mind, distributed cognition

**Provocation**: "Your vault knows 37 things you've forgotten - what else lives in your extended mind?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Identify knowledge stored in vault but not in biological memory.

    Implementation:
    1. Find notes not accessed in 180+ days
    2. With high information density (many outgoing links, rich content)
    3. On topics you still write about (semantic overlap with recent notes)
    4. Return 2-3 notes representing "vault-only knowledge"

    Extended mind angle: Map the boundary between brain and vault

    Returns 2-3 vault-resident knowledge nodes.
    """
```

**Example output**:
> "Your extended mind knows: [[Byzantine Consensus Algorithms]] (47 links, last accessed 2023-04-12), [[Category Theory Basics]] (63 links, last accessed 2023-06-03), [[Computational Topology]] (29 links, last accessed 2023-05-21). You're still writing about distributed systems, but this foundational knowledge lives only in your vault. Your biological brain delegated it."

---

#### 26. cognitive_scaffolding_audit
**File**: `src/geistfabrik/default_geists/code/cognitive_scaffolding_audit.py`

**Research basis**: Extended mind, load-bearing ideas

**Provocation**: "[[Systems Thinking]] supports 23 other notes - it's a load-bearing wall in your extended mind"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Identify notes serving critical scaffolding functions.

    Implementation:
    1. Compute centrality metrics (PageRank, betweenness, hub score)
    2. Identify notes with many incoming links (referenced frequently)
    3. Cross-reference with semantic similarity (conceptually foundational)
    4. Return top 3 scaffolding notes

    Extended mind angle: Some ideas hold up the whole structure

    Provocation: What happens if you remove a load-bearing note?

    Returns 2-3 scaffolding notes.
    """
```

**Example output**:
> "[[First Principles Thinking]] is a load-bearing idea: 34 notes link to it, 89 notes are semantically downstream. Your extended mind built an entire wing on this foundation. What if you challenged the first principles themselves?"

---

#### 27. mind_drift_detector
**File**: `src/geistfabrik/default_geists/code/mind_drift_detector.py`

**Research basis**: Extended mind, temporal dynamics

**Provocation**: "Your extended mind drifted 12% away from your biological mind over 6 months - you're thinking past each other"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Track divergence between recent thinking and vault structure.

    Implementation:
    1. Compute recent note centroids (last 30 days)
    2. Compute vault-wide historical centroid (all notes, weighted by age)
    3. Measure semantic distance between recent and historical
    4. If distance > threshold, flag as "mind drift"
    5. Return suggestion about divergence

    Extended mind angle: Your biological and extended minds are separating

    Returns 1 drift observation.
    """
```

**Example output**:
> "Your vault's semantic center is 'knowledge management, productivity, systems thinking' (historical centroid). Your recent notes cluster around 'uncertainty, creativity, emergence' (30-day centroid). Cosine distance: 0.74. Your biological mind is drifting away from your extended mind. Are you abandoning old ideas or evolving past them?"

---

#### 28. affective_scaffolding_map
**File**: `src/geistfabrik/default_geists/code/affective_scaffolding_map.py`

**Research basis**: Extended mind, emotion regulation

**Provocation**: "You visit [[Stoic Meditations]] every Sunday evening - your extended mind uses it for emotional regulation"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Identify notes serving emotional regulation functions.

    Implementation:
    1. Track note access patterns over time
    2. Correlate with emotional metadata (sentiment of notes created around same time)
    3. Identify notes visited during specific emotional states
    4. Return 2-3 notes with clear affective scaffolding roles

    Extended mind angle: Your vault regulates your emotions

    Returns 2-3 affective scaffolding notes.
    """
```

**Example output**:
> "[[Rumi Poems]] accessed 8 times in last 6 months, always within 24 hours of writing high-sadness notes. Your extended mind uses poetry for grief processing. [[Running Log]] accessed 12 times after high-anxiety notes. Your vault scaffolds emotional regulation through ritualized note retrieval."

---

#### 29. cognitive_niche_health
**File**: `src/geistfabrik/default_geists/code/cognitive_niche_health.py`

**Research basis**: Extended mind, cognitive ecology

**Provocation**: "82% of your notes cluster around 'productivity' - your cognitive niche lacks biodiversity"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Assess diversity and redundancy of cognitive niche.

    Implementation:
    1. Topic modeling across vault (LDA or semantic clustering)
    2. Compute topic distribution entropy
    3. Identify over-represented topics (> 30%)
    4. Identify under-represented regions (semantic voids)
    5. Return 1-2 niche health observations

    Extended mind angle: Evaluate extended mind's ecosystem

    Returns 1-2 niche assessments.
    """
```

**Example output**:
> "Topic entropy: 0.42 (low diversity). 78% of vault: 'productivity', 'systems', 'efficiency'. Under-represented: 'play', 'art', 'mysticism', 'relationships'. Your cognitive niche is a monoculture. Monocultures are fragile. What if you explored [[Art]] or [[Spirituality]]?"

---

#### 30. distributed_creativity_probe
**File**: `src/geistfabrik/default_geists/code/distributed_creativity_probe.py`

**Research basis**: Extended mind, emergent combinations

**Provocation**: "[[Quantum Entanglement]] and [[Jazz Improvisation]] have no overlap - what if non-locality and spontaneity share a pattern?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Generate suggestions by combining never-connected distant ideas.

    Implementation:
    1. Find note pairs with:
        - Low semantic similarity (< 0.3)
        - No graph path between them
        - Both in distant clusters
    2. For each pair, generate speculative connection question
    3. Return 2-3 creative collisions

    Extended mind angle: Your extended system creates emergent ideas

    Returns 2-3 creative collision questions.
    """
```

**Example output**:
> "[[Topological Data Analysis]] (math cluster, no links) and [[Grief Processing]] (personal cluster, no links) have 0.18 similarity. Distributed creativity probe: What if emotional grief has a topological structure? What if persistent homology could model psychological hole-filling?"

---

#### 31. extended_subconscious_dreams
**File**: `src/geistfabrik/default_geists/code/extended_subconscious_dreams.py`

**Research basis**: Extended mind, dream logic

**Provocation**: "In the liminal space between [[Topology]] and [[Grief]], your extended mind whispers about continuous deformations of loss..."

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Generate surreal, dream-like combinations mimicking subconscious processing.

    Implementation:
    1. Use Markov chains across note content
    2. Tracery grammars with aggressive randomness
    3. Allow semantic drift (intentionally break coherence)
    4. Mix metaphors from distant domains
    5. Return 1-2 "dream suggestions"

    Extended mind angle: Vault as extended subconscious

    WARNING: Intentionally surreal, not logical

    Returns 1-2 dream-logic suggestions.
    """
```

**Example output**:
> "Your extended subconscious dreams: In the space where [[Market Dynamics]] meets [[Ocean Tides]], liquidity becomes literal. Supply and demand are just gravity by another name. What if economics is just fluid dynamics wearing a suit?"

---

## Multidimensional Sentiment Movement Geists

These geists analyze note pairs that move in **different directions across multiple dimensions** simultaneously. Research shows notes can converge emotionally while diverging semantically, or move closer in sentiment but farther apart in the graph.

**Research basis**: `specs/research/MULTIDIMENSIONAL_MOVEMENT_ANALYSIS.md`

### Key Insight

Notes exist in multiple independent dimensional spaces:
- **Sentiment space** (valence, arousal, emotions)
- **Semantic space** (384D embeddings)
- **Graph space** (links, paths, clusters)
- **Temporal space** (drift vectors, velocity)
- **Maintenance space** (staleness, update patterns)

Movement in one dimension is often **decoupled** or even **opposing** movement in another, creating non-obvious patterns worth highlighting.

---

#### 32. sentiment_phantom_link
**File**: `src/geistfabrik/default_geists/code/sentiment_phantom_link.py`

**Pattern**: OPPOSING_MOVEMENT (sentiment ↑ closer, semantic ↓ farther)

**Research basis**: Multidimensional movement analysis, emotional convergence without conceptual alignment

**Provocation**: "You're feeling the same about different things"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect note pairs with sentiment convergence but semantic divergence.

    Implementation:
    1. Sample random note pairs from recent notes (last 60 days)
    2. Query session_embeddings for temporal trajectory (2+ sessions)
    3. Compute sentiment distance change: |valence_A(t) - valence_B(t)|
    4. Compute semantic similarity change: cosine(emb_A(t), emb_B(t))
    5. Identify pairs where:
        - Sentiment distance DECREASING (converging emotions)
        - Semantic similarity DECREASING (diverging content)
    6. Return top 2-3 pairs ranked by opposition strength

    Detection formula:
        sentiment_convergence = sentiment_distance(t0) - sentiment_distance(t1) > 0.3
        semantic_divergence = semantic_similarity(t0) - semantic_similarity(t1) > 0.15

    Returns 2-3 suggestions.
    """
```

**Example output**:
> "[[Career Planning]] and [[Weekend Hobbies]] are converging emotionally (valence distance: 0.6 → 0.2, both becoming more positive) but semantically diverging (similarity: 0.78 → 0.52). You're feeling the same about increasingly different things—what common emotion bridges work and play?"

---

#### 33. sentiment_semantic_decoupling
**File**: `src/geistfabrik/default_geists/code/sentiment_semantic_decoupling.py`

**Pattern**: OPPOSING_MOVEMENT (sentiment ↓ farther, semantic ↑ closer)

**Research basis**: Emotional divergence on same topic

**Provocation**: "Same idea, opposite feelings—what shifted?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect note pairs with semantic convergence but sentiment divergence.

    Implementation:
    1. Sample random note pairs with high current semantic similarity (> 0.7)
    2. Track sentiment across sessions (2+ sessions required)
    3. Identify pairs where:
        - Semantic similarity INCREASING or stable (> 0.7)
        - Sentiment distance INCREASING (diverging emotions)
    4. Calculate sentiment flip potential: opposite valence signs
    5. Return top 2-3 pairs ranked by decoupling strength

    Detection formula:
        semantic_stability = semantic_similarity > 0.7
        sentiment_divergence = |valence_A(t1) - valence_B(t1)| >
                               |valence_A(t0) - valence_B(t0)| + 0.4

    Returns 2-3 suggestions.
    """
```

**Example output**:
> "[[Project Retrospective]] and [[Project Planning]] are about the same topic (0.86 similarity, up from 0.81) but your emotional relationship is diverging dramatically. Planning feels optimistic (valence: +0.7), retrospective feels disappointed (valence: -0.5). Same project, opposite emotional arcs—what happened between planning and execution?"

---

#### 34. sentiment_trajectory_reversal
**File**: `src/geistfabrik/default_geists/code/sentiment_trajectory_reversal.py`

**Pattern**: TRAJECTORY_REVERSAL (current sentiment similar, drift vectors opposing)

**Research basis**: Predictive divergence, future emotional separation

**Provocation**: "They feel similar now but will diverge soon"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect note pairs with similar current sentiment but opposing emotional trajectories.

    Implementation:
    1. Sample note pairs with similar current sentiment (valence distance < 0.3)
    2. Compute sentiment drift vectors (rate of valence change per session)
    3. Calculate drift alignment: dot product of drift vectors
    4. Identify pairs where:
        - Current sentiment similar (low valence distance)
        - Drift vectors anti-aligned (dot product < -0.5)
    5. Return top 2-3 pairs by alignment negativity

    Detection formula:
        current_similarity = |valence_A - valence_B| < 0.3
        trajectory_opposition = dot(drift_vec_A, drift_vec_B) < -0.5

    Provocation: You're temporarily aligned but trajectories predict split

    Returns 2-3 suggestions.
    """
```

**Example output**:
> "[[Morning Meditation]] (valence: +0.6) and [[Evening Reflection]] (valence: +0.7) currently share similar positive sentiment. But their emotional drift vectors are anti-aligned (-0.68 correlation): meditation trending more positive (+0.12/session), reflection trending negative (-0.09/session). They feel similar now but their trajectories suggest emotional divergence within 3 sessions."

---

#### 35. sentiment_velocity_mismatch
**File**: `src/geistfabrik/default_geists/code/sentiment_velocity_mismatch.py`

**Pattern**: VELOCITY_MISMATCH (same direction, different rates)

**Research basis**: Asymmetric emotional evolution

**Provocation**: "Why is one note's emotional evolution outpacing the other?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect note pairs drifting in same emotional direction but at different speeds.

    Implementation:
    1. Sample note pairs with aligned sentiment drift direction
    2. Compute sentiment velocity (valence change per session)
    3. Calculate velocity ratio
    4. Identify pairs where:
        - Drift direction aligned (both increasing OR both decreasing valence)
        - Velocity ratio > 2.5 (one moving 2.5x+ faster)
    5. Return top 2-3 pairs by velocity ratio

    Detection formula:
        direction_aligned = sign(drift_A) == sign(drift_B)
        velocity_ratio = max(|drift_A|, |drift_B|) / min(|drift_A|, |drift_B|) > 2.5

    Returns 2-3 suggestions.
    """
```

**Example output**:
> "[[Team Dynamics]] and [[Personal Growth]] are both becoming more negative (valence: +0.4 → -0.2 and +0.6 → +0.3 respectively). But [[Team Dynamics]] is plummeting 3.2x faster (-0.15/session vs -0.047/session). Same negative direction, wildly asymmetric velocity—what's accelerating one note's emotional decline while the other drifts slowly?"

---

#### 36. sentiment_cluster_boundary
**File**: `src/geistfabrik/default_geists/code/sentiment_cluster_boundary.py`

**Pattern**: BOUNDARY_WALKER (similar sentiment, different emotional clusters)

**Research basis**: Categorical boundary proximity, cluster bridging

**Provocation**: "Are they bridging these emotional domains?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect note pairs with similar sentiment but different emotional cluster labels.

    Implementation:
    1. Get emotional clusters from vault (using Plutchik or GoEmotions)
    2. Sample note pairs from different clusters
    3. Calculate sentiment similarity (valence + arousal distance)
    4. Identify pairs where:
        - Different cluster labels (e.g., 'joy' vs 'anticipation')
        - High sentiment similarity (valence distance < 0.2, arousal distance < 0.2)
    5. Return top 2-3 pairs by sentiment proximity

    Detection formula:
        different_clusters = cluster_label_A != cluster_label_B
        high_similarity = distance(valence_A, valence_B) < 0.2 AND
                          distance(arousal_A, arousal_B) < 0.2

    Provocation: You're near an emotional category boundary

    Returns 2-3 cluster boundary pairs.
    """
```

**Example output**:
> "[[Product Launch]] (cluster: 'excitement', valence: +0.7, arousal: 0.8) and [[Wedding Planning]] (cluster: 'joy', valence: +0.8, arousal: 0.7) have nearly identical sentiment profiles but belong to different emotional clusters. Excitement and joy sit on opposite sides of a categorical boundary—are these notes bridging anticipatory vs. accomplished positive emotions?"

---

#### 37. sentiment_maintenance_asymmetry
**File**: `src/geistfabrik/default_geists/code/sentiment_maintenance_asymmetry.py`

**Pattern**: MAINTENANCE_DIVERGENCE (similar sentiment, different staleness)

**Research basis**: Asymmetric note attention, maintenance patterns

**Provocation**: "Why maintain one emotional twin but abandon the other?"

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Detect note pairs with similar sentiment but asymmetric maintenance.

    Implementation:
    1. Sample note pairs with similar current sentiment (valence distance < 0.25)
    2. Compute staleness score for each note:
        staleness = 1 - exp(-days_since_modified / 180)
    3. Calculate staleness asymmetry (difference)
    4. Identify pairs where:
        - Similar sentiment (low valence distance)
        - High staleness asymmetry (> 0.5 difference)
    5. Return top 2-3 pairs by staleness gap

    Detection formula:
        sentiment_similarity = |valence_A - valence_B| < 0.25
        staleness_asymmetry = |staleness_A - staleness_B| > 0.5

    Provocation: Why neglect one but maintain the other?

    Returns 2-3 asymmetric maintenance pairs.
    """
```

**Example output**:
> "[[Burnout Recovery]] (valence: -0.3, staleness: 0.08, modified 4 days ago) and [[Stress Management]] (valence: -0.4, staleness: 0.91, modified 287 days ago) share similar negative sentiment about overwhelm. But you're actively maintaining the recovery note while abandoning stress management. Why keep one emotional twin fresh but let the other fossilize? What changed in your relationship with these parallel struggles?"

---

## Pattern-Based Geist Design

See `specs/research/GEIST_PATTERN_TAXONOMY.md` for comprehensive pattern analysis.

### Reusable Pattern Types

The geist pattern taxonomy identifies **8 major pattern categories** with **30+ primitive patterns** that can be combined and applied to different dimensions:

#### Temporal Patterns (9)
- DRIFT, VELOCITY, FLIP/REVERSAL, BURST, INERTIA, CONVERGENCE/DIVERGENCE, MIRROR, CYCLICAL, ARC

#### Spatial/Topological (5)
- BRIDGE, HUB, ISLAND, CLUSTER, BOUNDARY

#### Comparison/Contrast (4)
- MISMATCH, PARADOX, SCALE SHIFT, INVERSION

#### Discovery/Pattern Recognition (3)
- PATTERN EXTRACTION, OUTLIER DETECTION, GAP DETECTION

#### Generation/Transformation (3)
- COLLISION, SCAMPER, ANTITHESIS

#### Dialectic/Questioning (2)
- SOCRATIC QUESTIONING, SYNTHESIS

#### Archaeology/Excavation (2)
- TEMPORAL EXCAVATION, CRYSTALLIZATION/TRAP

#### Meta-Patterns (3)
- MIRRORING, EVOLUTION TRACKING, MULTI-SCALE ANALYSIS

### Pattern Transferability

**Key insight**: Patterns transfer across dimensions. For example, the **DRIFT pattern** applies to:
- Concepts → `concept_drift`
- Emotions → `sentiment_drift`, `valence_flip` (drift + reversal)
- Topics → `topic_drift` (potential)
- Complexity → `complexity_evolution` (potential)

### Systematic Geist Creation

Instead of ad-hoc creativity, you can systematically generate new geists by:

1. **Applying existing pattern to new dimension**:
   - DRIFT + emotions → `emotional_drift` ✅
   - BURST + emotions → `emotional_burst` ✅
   - HUB + emotions → `emotional_contagion` ✅

2. **Combining multiple patterns**:
   - DRIFT + VELOCITY → `drift_velocity_anomaly` ✅
   - MIRROR + TEMPORAL → `temporal_mirror` ✅
   - CLUSTER + EVOLUTION → `cluster_evolution_tracker` ✅

3. **Applying new patterns to existing dimensions**:
   - FEEDBACK LOOP + concepts → `conceptual_feedback_detector` (potential)
   - CASCADE + emotions → `emotional_cascade` (potential)
   - PHASE TRANSITION + topics → `topic_phase_shift` (potential)

### Missing Patterns to Explore

Seven patterns identified in the taxonomy but not yet implemented:

1. **FEEDBACK LOOP** - Circular reference detection
2. **CASCADE/CONTAGION** - Already implemented as `emotional_contagion`
3. **EMERGENCE** - Vault-level properties not in individual notes
4. **RESONANCE** - Mutual amplification detection
5. **DECAY/ENTROPY** - Loss of coherence over time
6. **PHASE TRANSITION** - Discontinuous structural changes
7. **ATTRACTOR** - Stable convergence points

These patterns could inspire entirely new geist categories.

---

## Future Enhancements (Post-v2.0)

### Cultural Emotion Models
- Integrate affect valuation theory (ideal vs. actual affect)
- Cross-cultural emotion taxonomies beyond Western models
- Dialecticism as cultural lens (East Asian emotional patterns)

### Advanced Temporal Analysis
- Emotion prediction: "Based on your patterns, tomorrow will be..."
- Seasonal affective patterns across years
- Circadian emotional rhythms (morning vs. evening notes)

### Emotion-Driven Discovery
- Semantic search weighted by emotion: "Find notes like X but happier"
- Emotional bridges between clusters
- Emotion-guided reading order

### Multimodal Emotion
- Image sentiment (if vault contains images)
- Audio tone analysis (if vault contains recordings)
- Combined text+image emotion detection

---

## Appendix: Emotion Taxonomies

### Plutchik's 8 Primary Emotions
1. Joy ↔ Sadness
2. Trust ↔ Disgust
3. Fear ↔ Anger
4. Surprise ↔ Anticipation

### GoEmotions 27 Categories

**Positive (12)**:
admiration, amusement, approval, caring, desire, excitement, gratitude, joy, love, optimism, pride, relief

**Negative (11)**:
anger, annoyance, disappointment, disapproval, disgust, embarrassment, fear, grief, nervousness, remorse, sadness

**Ambiguous (4)**:
confusion, curiosity, realization, surprise

**Neutral (1)**:
neutral

### Emotional Quadrants (Circumplex)

| Valence | Arousal | Emotions |
|---------|---------|----------|
| Positive | High | excited, elated, energized, enthusiastic |
| Positive | Low | calm, content, peaceful, serene |
| Negative | High | angry, anxious, stressed, fearful |
| Negative | Low | sad, depressed, bored, lethargic |

---

*End of Sentiment Geists Specification v2.0*
