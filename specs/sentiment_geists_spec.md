# Sentiment Geists Specification

**Version**: 0.1.0 (Draft)
**Status**: Proposal
**Target**: Post-1.0 Feature
**Author**: Claude Code
**Date**: 2025-11-12

## Overview

This specification describes a sentiment analysis framework for GeistFabrik and a collection of geists built upon it. The framework follows GeistFabrik's three-dimensional extensibility model:

1. **Metadata Layer**: Sentiment inference module that analyzes emotional qualities of notes
2. **Function Layer**: Vault functions exposing sentiment-based queries
3. **Geist Layer**: Creative geists generating suggestions from emotional patterns

## Design Philosophy

### Muses, Not Therapists

Sentiment-based geists should be **provocative, not prescriptive**. They ask questions about emotional patterns rather than diagnosing or prescribing emotional states.

**Good**: "What if [[Burnout]] and [[Creative Flow]] are closer than they appear?"
**Bad**: "You seem stressed. Consider meditation."

### Emotional Cartography, Not Psychology

The system maps emotional terrain in your vault, revealing patterns and connections. It does NOT:
- Diagnose mental health conditions
- Prescribe emotional responses
- Judge emotional states as "good" or "bad"
- Provide therapeutic advice

### Questions Over Answers

Like all GeistFabrik suggestions, sentiment geists generate **"What if...?"** questions:
- "What if your most joyful notes share something with your most melancholic?"
- "What if [[2024-03-15]] and [[2024-09-20]] are emotional mirrors?"
- "What if notes about [[Work]] cluster into three distinct emotional spaces?"

## Architecture

### Layer 1: Metadata Inference Module

**Location**: `_geistfabrik/metadata_inference/sentiment.py`

**Exported Function**: `infer(note: Note, vault: VaultContext) -> dict[str, Any]`

**Inferred Properties**:

```python
{
    "sentiment_valence": float,      # -1.0 (negative) to +1.0 (positive)
    "sentiment_intensity": float,    # 0.0 (neutral) to 1.0 (intense)
    "sentiment_dominant": str,       # "joy" | "sadness" | "anger" | "fear" | "surprise" | "neutral"
    "sentiment_mixed": bool,         # True if multiple emotions present
    "sentiment_confidence": float,   # 0.0 to 1.0 confidence in classification
}
```

**Implementation Approach**:

Two possible implementations (choose based on dependencies):

1. **Lightweight** (no external dependencies):
   - Lexicon-based sentiment using word lists
   - Fast but less nuanced
   - Suitable for offline-first requirement

2. **Enhanced** (with transformers):
   - Use pre-trained sentiment model (e.g., `cardiffnlp/twitter-roberta-base-sentiment`)
   - More accurate but requires model download
   - Falls back to lightweight if model unavailable

**Design Decisions**:

- **Cache sentiment in database**: Store computed sentiment to avoid recomputation
- **Recompute on content change**: Only reanalyze when note content modified
- **Handle short notes gracefully**: Notes < 50 words get lower confidence scores
- **Ignore code blocks**: Strip code fences before analysis to avoid false signals

### Layer 2: Vault Functions

**Location**: `_geistfabrik/vault_functions/sentiment.py`

**Functions**:

```python
@vault_function("notes_by_sentiment")
def notes_by_sentiment(dominant: str, limit: int = 10) -> list[str]:
    """
    Return notes with specified dominant sentiment.

    Args:
        dominant: One of "joy", "sadness", "anger", "fear", "surprise", "neutral"
        limit: Maximum number of notes to return

    Returns:
        List of note titles as wikilinks: ["[[Note A]]", "[[Note B]]"]
    """
    pass


@vault_function("emotional_spectrum")
def emotional_spectrum(valence_min: float, valence_max: float, limit: int = 10) -> list[str]:
    """
    Return notes within a valence range.

    Args:
        valence_min: Minimum valence (-1.0 to +1.0)
        valence_max: Maximum valence (-1.0 to +1.0)
        limit: Maximum number of notes to return

    Returns:
        List of note titles as wikilinks
    """
    pass


@vault_function("emotional_outliers")
def emotional_outliers(count: int = 5) -> list[str]:
    """
    Return notes with unusual emotional intensity.

    Args:
        count: Number of outliers to return

    Returns:
        List of note titles as wikilinks, sorted by intensity
    """
    pass


@vault_function("sentiment_drift")
def sentiment_drift(note_title: str, k: int = 5) -> list[str]:
    """
    Find notes semantically similar but emotionally different.

    Args:
        note_title: Reference note title (without brackets)
        k: Number of results to return

    Returns:
        List of note titles as wikilinks, sorted by sentiment distance
    """
    pass


@vault_function("emotional_bridges")
def emotional_bridges(valence_min: float, valence_max: float) -> str:
    """
    Find notes that bridge two emotional regions.

    Returns cluster format: "[[Bridge]]|||[[End A]], [[End B]]"
    Uses delimiter pattern for Tracery compatibility.

    Args:
        valence_min: Valence of first region
        valence_max: Valence of second region

    Returns:
        Cluster string with delimiter for split modifiers
    """
    pass


@vault_function("mixed_emotion_notes")
def mixed_emotion_notes(limit: int = 10) -> list[str]:
    """
    Return notes with mixed/complex emotional content.

    Args:
        limit: Maximum number of notes to return

    Returns:
        List of note titles as wikilinks
    """
    pass
```

**Design Note**: All functions return wikilinks with brackets (`[[...]]`) following the Consistent API principle established in v0.9.1. Cluster functions like `emotional_bridges()` use delimiter patterns for Tracery compatibility.

### Layer 3: Geists

Six proposed geists, each exploring different aspects of emotional patterns:

---

#### 1. **emotional_mirror** (Code Geist)

**Purpose**: Find pairs of notes with opposite emotional valence but similar semantic content.

**Concept**: Sometimes we write about the same topic from drastically different emotional states. What can these mirrors teach us?

**Algorithm**:
1. Sample 20 random notes
2. For each note, find semantically similar notes (cosine > 0.6)
3. Filter for opposite valence (difference > 1.0)
4. Sample one pair with highest semantic similarity
5. Generate suggestion asking about the contrast

**Example Output**:
```
What if [[Burnout - March 2024]] and [[Flow State Discovery]] are describing
the same territory from opposite shores? What changed between these two maps?
```

**Implementation**:
```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    notes = vault.sample_notes(20)
    pairs = []

    for note in notes:
        similar = vault.semantic_search(note.title, k=10, min_similarity=0.6)
        valence_a = vault.metadata(note.title).get("sentiment_valence", 0.0)

        for other_title in similar:
            valence_b = vault.metadata(other_title).get("sentiment_valence", 0.0)
            if abs(valence_a - valence_b) > 1.0:
                similarity = vault.similarity(note.title, other_title)
                pairs.append((note.title, other_title, similarity))

    if not pairs:
        return []

    # Select pair with highest similarity
    pairs.sort(key=lambda x: x[2], reverse=True)
    note_a, note_b, _ = pairs[0]

    return [Suggestion(
        text=f"What if [[{note_a}]] and [[{note_b}]] are describing the same "
             f"territory from opposite shores? What changed between these two maps?",
        notes=[note_a, note_b],
        geist_id="emotional_mirror"
    )]
```

---

#### 2. **mood_constellation** (Code Geist)

**Purpose**: Identify clusters of notes sharing similar emotional valence but spanning different topics.

**Concept**: Emotional states create their own semantic spaces. What patterns emerge when you view your vault through the lens of feeling rather than topic?

**Algorithm**:
1. Group notes into 3 valence bands: negative (-1.0 to -0.3), neutral (-0.3 to 0.3), positive (0.3 to 1.0)
2. Within each band, sample 5 notes spanning different topics (low semantic similarity)
3. Pick the band with most interesting diversity
4. Generate suggestion about the emotional constellation

**Example Output**:
```
These notes share a melancholic undertone despite spanning different worlds:
[[Database Design]], [[Rainy Tuesday]], [[Sourdough Failure]]. What if this
mood is a lens, not a theme?
```

---

#### 3. **intensity_spike** (Code Geist)

**Purpose**: Highlight notes with unusually high emotional intensity.

**Concept**: Intensity often signals importance, revelation, or crisis. These spikes deserve attention.

**Algorithm**:
1. Query for top 10 notes by `sentiment_intensity`
2. Filter for intensity > 0.7
3. Sample 2-3 notes randomly
4. Generate suggestion asking what made these moments so charged

**Example Output**:
```
[[Breaking Point - Q4 2023]] registers seismic intensity. What was it about
that moment that demanded to be written with such force?
```

---

#### 4. **emotional_drift** (Tracery Geist)

**Purpose**: Find semantically similar notes with different emotional valences.

**Concept**: When we return to similar topics over time, our emotional relationship often changes. This drift reveals growth, change, or cycles.

**Implementation**:
```yaml
type: geist-tracery
id: emotional_drift
description: Finds semantically similar notes with contrasting emotional tones

tracery:
  origin: "What if #seed# has drifted emotionally from #drifted#? What shifted in the space between?"

  # Get cluster of seed + emotionally drifted neighbors
  cluster: ["$vault.sentiment_drift(#random_note#, 3)"]

  # Extract parts using split modifiers
  seed: ["#cluster.split_seed#"]
  drifted: ["#cluster.split_neighbours#"]

  # Sample a random note as starting point
  random_note: ["$vault.random_note_title()"]
```

**Notes**:
- Uses cluster pattern with delimiter for Tracery compatibility
- Requires `sentiment_drift()` vault function
- Requires `split_seed` and `split_neighbours` custom modifiers

---

#### 5. **mixed_feelings** (Tracery Geist)

**Purpose**: Highlight notes with complex, mixed emotional content.

**Concept**: Ambivalence and emotional complexity often signal rich, nuanced thinking. These notes resist simple categorization.

**Implementation**:
```yaml
type: geist-tracery
id: mixed_feelings
description: Surfaces notes with mixed emotional valence

tracery:
  origin: "#note# resists emotional simplicity. What if this complexity is the point?"
  note: ["$vault.mixed_emotion_notes(5)"]
```

---

#### 6. **joy_archaeology** (Tracery Geist)

**Purpose**: Resurface joyful notes that might be buried in the vault.

**Concept**: We often forget what delighted us. Joy deserves rediscovery.

**Implementation**:
```yaml
type: geist-tracery
id: joy_archaeology
description: Resurfaces notes with high positive valence

tracery:
  origin: "What if #joyful_note# holds a spark worth revisiting? What made this moment luminous?"
  joyful_note: ["$vault.notes_by_sentiment('joy', 10)"]
```

---

## Configuration

Users can enable/disable the sentiment framework in `config.yaml`:

```yaml
# Sentiment analysis framework
enabled_modules:
  metadata_inference:
    - sentiment

  vault_functions:
    - sentiment

  geists:
    # Code geists
    - emotional_mirror
    - mood_constellation
    - intensity_spike

    # Tracery geists
    - emotional_drift
    - mixed_feelings
    - joy_archaeology
```

## Implementation Plan

### Phase 1: Foundation (Metadata + Functions)
1. Implement `sentiment.py` metadata module
   - Start with lightweight lexicon-based approach
   - Add tests using known-answer examples
   - Validate against testdata vault
2. Implement vault functions in `sentiment.py`
   - Add regression tests for each function
   - Verify Tracery compatibility
3. Update database schema to cache sentiment properties
4. Add configuration validation

### Phase 2: Code Geists
1. Implement `emotional_mirror.py`
2. Implement `mood_constellation.py`
3. Implement `intensity_spike.py`
4. Add integration tests using testdata vault

### Phase 3: Tracery Geists
1. Implement custom modifiers for sentiment clusters (if needed)
2. Create `emotional_drift.yaml`
3. Create `mixed_feelings.yaml`
4. Create `joy_archaeology.yaml`
5. Validate Tracery grammar with `_validate_grammar()`

### Phase 4: Enhancement (Optional)
1. Add transformer-based sentiment model
2. Implement fallback logic (transformer → lexicon)
3. Add model download to setup
4. Benchmark accuracy improvement

## Testing Strategy

### Unit Tests

**Metadata Module** (`tests/unit/test_sentiment_metadata.py`):
- Test known-answer examples (joyful text → positive valence)
- Test edge cases (empty notes, very short notes, code-heavy notes)
- Test confidence scoring
- Test mixed emotion detection

**Vault Functions** (`tests/unit/test_sentiment_functions.py`):
- Test each function returns bracketed wikilinks
- Test filtering logic (valence ranges, dominant emotions)
- Test sampling behavior
- Test cluster format for `emotional_bridges()`

### Integration Tests

**Geists** (`tests/integration/test_sentiment_geists.py`):
- Test each geist against testdata vault
- Verify suggestions follow "muses not oracles" principle
- Test timeout behavior (30 seconds)
- Test graceful failure when insufficient emotional diversity

### Regression Tests

**API Consistency** (`tests/unit/test_sentiment_api.py`):
- Verify all vault functions return bracketed links
- Verify cluster functions use delimiter pattern
- Prevent future API inconsistencies

## Performance Considerations

**Sentiment Computation**:
- Cache sentiment in database (recompute only on content change)
- Lightweight lexicon approach: ~10ms per note
- Transformer approach: ~50-100ms per note
- Target: < 5 seconds to compute sentiment for 1000 notes

**Query Performance**:
- Index `sentiment_valence` and `sentiment_intensity` columns
- Use SQLite queries for filtering before Python processing
- Sample randomly to avoid scanning full vault

**Memory**:
- Sentiment properties: ~40 bytes per note
- 10,000 notes × 40 bytes = 400KB overhead

## Limitations & Future Work

### Current Limitations

1. **English-only**: Lexicon and transformer models trained on English
2. **Context-blind**: Analyzes notes in isolation, not in graph context
3. **Static sentiment**: Doesn't track how emotional reading changes over time
4. **No temporal patterns**: Doesn't detect seasonal or cyclical emotional patterns

### Future Extensions (Post-1.0)

1. **Temporal Sentiment Tracking**:
   - Store sentiment embeddings per session
   - Track how emotional interpretation evolves
   - Detect seasonal patterns (winter melancholy, summer joy)

2. **Graph-Aware Sentiment**:
   - Emotional influence propagation (do linked notes share sentiment?)
   - Emotional bridges in knowledge graph
   - Sentiment gradients across paths

3. **Multi-Language Support**:
   - Language detection per note
   - Language-specific lexicons
   - Multilingual transformer models

4. **Additional Geists**:
   - `emotional_path`: Trace sentiment along link paths
   - `seasonal_moods`: Detect temporal emotional patterns
   - `sentiment_forecast`: Predict emotional tone of future notes based on current patterns (provocative, not prescriptive!)

## Open Questions

1. **Privacy & Ethics**: Should sentiment analysis be opt-in? How do we communicate that this is cartography, not diagnosis?

2. **Accuracy vs. Speed**: Should default be lexicon (fast) or transformer (accurate)?

3. **Confidence Thresholds**: What minimum confidence should geists require before generating suggestions?

4. **Emotional Vocabulary**: Are 6 emotion categories sufficient, or do we need more nuance?

## References

- Gordon Brander's work on divergence engines and muses
- GeistFabrik core specification (`specs/geistfabrik_spec.md`)
- Tracery grammar system (`specs/tracery_research.md`)
- Writing Good Geists guide (`docs/WRITING_GOOD_GEISTS.md`)

---

**End of Specification**
