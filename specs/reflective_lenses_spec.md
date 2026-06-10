# Reflective Lenses Specification

*Version: 1.1*
*Date: June 2026*
*Supersedes: specs/sentiment_geists_spec.md (withdrawn)*
*v1.1: Added performance characteristics, vectorised algorithms for surprisal/attention-drift, and a comprehensive testing strategy based on adewale/testing-best-practices*

---

## Overview

This specification defines a **reflective lenses** framework for GeistFabrik — a set of geists that help users see their notes through dimensions they wouldn't naturally consider. Rather than classifying emotional content (which has ~50% accuracy and licensing barriers), this framework uses **observable linguistic and behavioral signals** to generate provocations.

The core insight: users don't need a system to tell them "this note is sad." They need a system to say "this note looks backward while that one looks forward — what if they met?"

---

## Why Not Sentiment Analysis?

An earlier specification (v2.0, November 2025) proposed sentiment analysis using NRC EmoLex, LIWC, and GoEmotions. That approach was withdrawn after audit revealed:

1. **Licensing barriers**: LIWC is proprietary (~$90+ academic, commercial requires Receptiviti); NRC EmoLex is research-only
2. **Accuracy limitations**: Best GoEmotions models achieve macro-F1 ~0.45–0.55 (coin flip); the cited "96.77%" figure was from a different, simpler dataset
3. **No temporal mechanism**: Sentiment is a pure function of text content — it cannot "drift" across sessions for unedited notes
4. **Arousal gap**: Neither proposed lexicon provides arousal scores
5. **False precision**: Outputs like "valence: +0.73" imply measurement where there's only noisy inference

This specification takes a different path: **observable signals that don't require classification**.

---

## Core Philosophy

### 1. Muses, Not Oracles

Reflective lenses pose questions rather than classifications:

**Avoid**: "This note is negative"
**Embrace**: "This note looks backward. What would it say about tomorrow?"

**Avoid**: "Anxiety detected (confidence: 0.67)"
**Embrace**: "You hedged 8 times in 200 words. What aren't you ready to commit to?"

### 2. Observable Over Inferred

Every signal in this framework is **syntactically observable** — verb tenses, pronouns, sentence structure, linking patterns — not semantically inferred. This trades depth for reliability.

### 3. Attention Over Emotion

Instead of "how do you feel about this note?" (unmeasurable from text), ask "how has your attention to this note changed?" (measurable from behavior).

### 4. Reflection Over Classification

The goal is not to label notes but to prompt reflection. A wrong provocation can still spark useful thinking; a wrong label just misleads.

---

## Three-Layer Architecture

### Layer 1: Metadata Inference Module

**File**: `src/geistfabrik/default_geists/metadata/voice.py`

Computes **linguistic voice** properties for each note using pure Python (no external lexicons):

#### Temporal Orientation
```python
{
    "past_tense_ratio": float,    # 0.0–1.0: fraction of verbs in past tense
    "future_tense_ratio": float,  # 0.0–1.0: fraction of verbs in future tense
    "present_tense_ratio": float, # 0.0–1.0: fraction of verbs in present tense
    "temporal_orientation": str,  # "past" | "present" | "future" | "mixed"
}
```

**Research basis**: Tausczik & Pennebaker (2010) found past-tense correlates with reflection/processing; future-tense with planning/optimism. This is syntactically detectable without sentiment classification.

#### Pronoun Patterns
```python
{
    "first_person_singular": float,  # "I", "me", "my" per 100 words
    "first_person_plural": float,    # "we", "us", "our" per 100 words  
    "second_person": float,          # "you", "your" per 100 words
    "self_focus_ratio": float,       # singular / (singular + plural)
}
```

**Research basis**: First-person singular increases in depression and self-focused processing; first-person plural indicates social connection and shared identity (Pennebaker et al., various).

#### Uncertainty Markers
```python
{
    "hedging_ratio": float,      # hedge words per sentence
    "question_density": float,   # questions per 100 words
    "modal_density": float,      # "might", "could", "may" per 100 words
}
```

**Hedge words** (no external lexicon needed):
```python
HEDGES = {
    "maybe", "perhaps", "possibly", "probably", "apparently",
    "seems", "appears", "suggests", "might", "could", "may",
    "somewhat", "rather", "fairly", "roughly", "approximately",
    "in a way", "sort of", "kind of", "I think", "I believe",
    "I guess", "I suppose", "it seems", "arguably", "presumably"
}
```

#### Structural Complexity
```python
{
    "mean_sentence_length": float,
    "sentence_length_variance": float,  # High variance = choppy/emotional
    "lexical_diversity": float,         # Unique words / total words (TTR)
    "paragraph_count": int,
}
```

**Research basis**: High sentence-length variance correlates with cognitive load and emotional processing (Pennebaker & King, 1999).

#### Implementation

```python
import re
from dataclasses import dataclass

@dataclass
class VoiceMetadata:
    # Temporal
    past_tense_ratio: float
    future_tense_ratio: float
    present_tense_ratio: float
    temporal_orientation: str
    
    # Pronouns
    first_person_singular: float
    first_person_plural: float
    second_person: float
    self_focus_ratio: float
    
    # Uncertainty
    hedging_ratio: float
    question_density: float
    modal_density: float
    
    # Structure
    mean_sentence_length: float
    sentence_length_variance: float
    lexical_diversity: float


def infer_voice(note: Note, vault: "VaultContext") -> dict[str, Any]:
    """Compute linguistic voice metadata for a note."""
    text = note.content
    words = tokenize(text)
    sentences = split_sentences(text)
    
    # Temporal orientation via verb patterns
    past = count_past_tense(words)
    future = count_future_tense(words)
    present = count_present_tense(words)
    total_verbs = past + future + present or 1
    
    past_ratio = past / total_verbs
    future_ratio = future / total_verbs
    present_ratio = present / total_verbs
    
    if past_ratio > 0.6:
        orientation = "past"
    elif future_ratio > 0.4:
        orientation = "future"
    elif present_ratio > 0.7:
        orientation = "present"
    else:
        orientation = "mixed"
    
    # Pronouns
    word_count = len(words) or 1
    fps = count_matches(words, {"i", "me", "my", "mine", "myself"})
    fpp = count_matches(words, {"we", "us", "our", "ours", "ourselves"})
    sp = count_matches(words, {"you", "your", "yours", "yourself"})
    
    # Uncertainty
    hedge_count = sum(1 for s in sentences for h in HEDGES if h in s.lower())
    question_count = text.count("?")
    modal_count = count_matches(words, {"might", "could", "may", "would", "should"})
    
    # Structure
    sent_lengths = [len(tokenize(s)) for s in sentences]
    mean_len = sum(sent_lengths) / len(sent_lengths) if sent_lengths else 0
    variance = sum((l - mean_len)**2 for l in sent_lengths) / len(sent_lengths) if sent_lengths else 0
    unique_words = len(set(w.lower() for w in words))
    
    return {
        "past_tense_ratio": past_ratio,
        "future_tense_ratio": future_ratio,
        "present_tense_ratio": present_ratio,
        "temporal_orientation": orientation,
        "first_person_singular": fps / word_count * 100,
        "first_person_plural": fpp / word_count * 100,
        "second_person": sp / word_count * 100,
        "self_focus_ratio": fps / (fps + fpp) if (fps + fpp) > 0 else 0.5,
        "hedging_ratio": hedge_count / len(sentences) if sentences else 0,
        "question_density": question_count / word_count * 100,
        "modal_density": modal_count / word_count * 100,
        "mean_sentence_length": mean_len,
        "sentence_length_variance": variance,
        "lexical_diversity": unique_words / word_count if word_count else 0,
    }
```

**No external dependencies. No licensing issues. Pure Python.**

---

### Layer 2: Vault Functions

**File**: `src/geistfabrik/function_registry.py` (additions)

#### Temporal Voice Queries

```python
@vault_function("past_focused_notes")
def past_focused_notes(vault: VaultContext, k: int = 5) -> list[str]:
    """Sample notes with past-tense orientation."""
    candidates = [
        n for n in vault.notes()
        if vault.metadata(n).get("temporal_orientation") == "past"
    ]
    return [f"[[{n.title}]]" for n in vault.sample(candidates, k)]


@vault_function("future_focused_notes")
def future_focused_notes(vault: VaultContext, k: int = 5) -> list[str]:
    """Sample notes with future-tense orientation."""
    candidates = [
        n for n in vault.notes()
        if vault.metadata(n).get("temporal_orientation") == "future"
    ]
    return [f"[[{n.title}]]" for n in vault.sample(candidates, k)]
```

#### Pronoun Pattern Queries

```python
@vault_function("self_focused_notes")
def self_focused_notes(vault: VaultContext, k: int = 5) -> list[str]:
    """Sample notes with high first-person singular usage."""
    candidates = [
        n for n in vault.notes()
        if vault.metadata(n).get("self_focus_ratio", 0.5) > 0.8
    ]
    return [f"[[{n.title}]]" for n in vault.sample(candidates, k)]


@vault_function("we_notes")
def we_notes(vault: VaultContext, k: int = 5) -> list[str]:
    """Sample notes with high first-person plural usage."""
    candidates = [
        n for n in vault.notes()
        if vault.metadata(n).get("first_person_plural", 0) > 2.0  # per 100 words
    ]
    return [f"[[{n.title}]]" for n in vault.sample(candidates, k)]
```

#### Uncertainty Queries

```python
@vault_function("uncertain_notes")
def uncertain_notes(vault: VaultContext, k: int = 5) -> list[str]:
    """Sample notes with high hedging density."""
    candidates = [
        n for n in vault.notes()
        if vault.metadata(n).get("hedging_ratio", 0) > 0.5  # >0.5 hedges per sentence
    ]
    return [f"[[{n.title}]]" for n in vault.sample(candidates, k)]


@vault_function("questioning_notes")
def questioning_notes(vault: VaultContext, k: int = 5) -> list[str]:
    """Sample notes with high question density."""
    candidates = [
        n for n in vault.notes()
        if vault.metadata(n).get("question_density", 0) > 1.0  # >1 question per 100 words
    ]
    return [f"[[{n.title}]]" for n in vault.sample(candidates, k)]
```

#### New VaultContext Methods (Required Infrastructure)

Per the architectural rule (geists use VaultContext, never raw loops over the
whole vault doing per-note similarity searches), the two expensive
computations live in VaultContext, are computed **once per session in a
single vectorised pass**, and are cached so every geist and vault function
shares the result.

```python
# vault_context.py additions

def surprisal_scores(self, k_neighbors: int = 10) -> dict[str, float]:
    """Surprisal = 1 - cosine(note, centroid of its k nearest neighbours).

    How unexpected is each note given its own semantic neighbourhood?
    Values lie in [0, 2] (cosine ∈ [-1, 1]); in practice [0, 1].

    Computed for ALL notes in one vectorised pass, session-cached.

    Algorithm (O(N²·d) flops, but as blocked BLAS matmuls, NOT a Python loop):
    1. E = row-normalised embedding matrix (N × d), already in memory
    2. For each 1024-row block B: S_B = E[B] @ E.T   (~40 MB per block at N=10k)
    3. Top-k neighbour indices per row via np.argpartition  (O(N) per row)
    4. centroid_i = mean(E[topk_i]); surprisal_i = 1 - E[i] · normalise(centroid_i)

    Notes with fewer than k_neighbors // 2 neighbours above noise
    threshold are excluded (surprisal is meaningless in a near-empty vault).
    """


@dataclass
class ChurnResult:
    churn: float                  # 1 - Jaccard(old neighbours, new neighbours), in [0, 1]
    departed: list[str]           # neighbour paths present then, absent now
    arrived: list[str]            # neighbour paths absent then, present now


def neighbor_churn(self, since_days: int = 180, k: int = 10) -> dict[str, ChurnResult]:
    """Jaccard churn between each note's current semantic neighbours and its
    neighbours as of the nearest session at or before (today - since_days).

    Graceful degradation:
    - No session that old → falls back to the OLDEST available session if it
      is at least 30 days old; otherwise returns {} (geists then return []).
    - Notes created after the historical session are skipped.

    Implementation:
    1. ONE bulk SELECT loads the historical session's embeddings
       (~15 MB for 10k notes × 387 dims × float32) — never per-note queries
    2. Two blocked top-k passes (as in surprisal_scores), one per epoch
    3. Set-based Jaccard per note (O(k) each)

    Session-cached per (since_days, k).
    """
```

#### Information-Theoretic Surprisal (Vault Function)

```python
@vault_function("surprising_notes")
def surprising_notes(vault: VaultContext, k: int = 5) -> list[str]:
    """Sample notes with high information-theoretic surprisal.

    Thin wrapper over the session-cached VaultContext.surprisal_scores().
    """
    scores = vault.surprisal_scores()
    top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
    return [f"[[{vault.note(path).title}]]" for path, _ in top]
```

#### Attention Drift Queries

```python
@vault_function("attention_shifted_notes")
def attention_shifted_notes(
    vault: VaultContext,
    months_ago: int = 6,
    min_churn: float = 0.7,
    k: int = 5
) -> list[str]:
    """Find notes whose semantic neighborhood has churned significantly.

    Thin wrapper over the session-cached VaultContext.neighbor_churn().
    """
    churn = vault.neighbor_churn(since_days=months_ago * 30)
    shifted = [(p, r) for p, r in churn.items() if r.churn >= min_churn]
    shifted.sort(key=lambda x: x[1].churn, reverse=True)
    return [f"[[{vault.note(p).title}]]" for p, _ in shifted[:k]]
```

---

### Layer 3: Geists

#### Code Geists

##### 1. temporal_voice
**File**: `src/geistfabrik/default_geists/code/temporal_voice.py`

Contrasts past-focused and future-focused notes.

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Find notes with contrasting temporal orientations."""
    past_notes = [
        n for n in vault.notes()
        if vault.metadata(n).get("temporal_orientation") == "past"
    ]
    future_notes = [
        n for n in vault.notes()
        if vault.metadata(n).get("temporal_orientation") == "future"
    ]
    
    if not past_notes or not future_notes:
        return []
    
    # Find a semantically related pair with opposite temporal voice.
    # Bounded search: 5 × 20 = at most 100 individual similarity() calls
    # (cache-aware, early-terminating — the right tool for loops with logic,
    # per the batch_similarity vs similarity() guidance in CLAUDE.md).
    future_candidates = vault.sample(future_notes, min(20, len(future_notes)))
    for past_note in vault.sample(past_notes, 5):
        for future_note in future_candidates:
            if vault.similarity(past_note, future_note) > 0.5:
                return [Suggestion(
                    text=f"[[{past_note.title}]] looks backward. "
                         f"[[{future_note.title}]] looks forward. "
                         f"They're semantically close — what bridges reflection and anticipation here?",
                    notes=[past_note.title, future_note.title],
                    geist_id="temporal_voice"
                )]
    
    # Fallback: any contrast
    past = vault.sample(past_notes, 1)[0]
    future = vault.sample(future_notes, 1)[0]
    return [Suggestion(
        text=f"[[{past.title}]] dwells in the past. "
             f"[[{future.title}]] reaches toward the future. "
             f"What would a present-tense note about these topics say?",
        notes=[past.title, future.title],
        geist_id="temporal_voice"
    )]
```

---

##### 2. self_and_other
**File**: `src/geistfabrik/default_geists/code/self_and_other.py`

Contrasts "I" notes with "we" notes.

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Find notes with contrasting pronoun patterns."""
    i_notes = [
        n for n in vault.notes()
        if vault.metadata(n).get("self_focus_ratio", 0.5) > 0.85
    ]
    we_notes = [
        n for n in vault.notes()
        if vault.metadata(n).get("first_person_plural", 0) > 2.0
    ]
    
    if len(i_notes) < 2:
        return []
    
    i_sample = vault.sample(i_notes, min(3, len(i_notes)))
    i_titles = ", ".join(f"[[{n.title}]]" for n in i_sample)
    
    if we_notes:
        we_sample = vault.sample(we_notes, min(2, len(we_notes)))
        we_titles = ", ".join(f"[[{n.title}]]" for n in we_sample)
        return [Suggestion(
            text=f"These notes say 'I': {i_titles}. "
                 f"These notes say 'we': {we_titles}. "
                 f"When do you think alone, and when do you think with others?",
            notes=[n.title for n in i_sample + we_sample],
            geist_id="self_and_other"
        )]
    else:
        return [Suggestion(
            text=f"These notes are all 'I': {i_titles}. "
                 f"You have no 'we' notes. Who could you be thinking with?",
            notes=[n.title for n in i_sample],
            geist_id="self_and_other"
        )]
```

---

##### 3. uncertainty_mapper
**File**: `src/geistfabrik/default_geists/code/uncertainty_mapper.py`

Surfaces notes with high hedging density.

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Find notes where you're hedging heavily."""
    hedgy_notes = []
    for note in vault.notes():
        meta = vault.metadata(note)
        hedging = meta.get("hedging_ratio", 0)
        if hedging > 0.3:  # More than 0.3 hedges per sentence
            hedgy_notes.append((note, hedging))
    
    if not hedgy_notes:
        return []
    
    hedgy_notes.sort(key=lambda x: x[1], reverse=True)
    top = hedgy_notes[0]
    note, ratio = top
    
    hedge_count = int(ratio * len(split_sentences(note.content)))
    word_count = len(note.content.split())
    
    return [Suggestion(
        text=f"[[{note.title}]] hedges {hedge_count} times in {word_count} words. "
             f"What are you not ready to commit to?",
        notes=[note.title],
        geist_id="uncertainty_mapper"
    )]
```

---

##### 4. surprisal
**File**: `src/geistfabrik/default_geists/code/surprisal.py`

Surfaces informationally unexpected notes using embedding distance.

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Find notes that don't fit their semantic neighborhood.

    Uses the session-cached, vectorised VaultContext.surprisal_scores() —
    NEVER a per-note semantic_neighbors() loop (O(N²) slow path, see
    Performance Characteristics).
    """
    scores = vault.surprisal_scores()
    if not scores:
        return []

    path = max(scores, key=scores.get)
    note = vault.note(path)
    neighbors = vault.semantic_neighbors(note, k=3)  # single cached query
    neighbor_titles = ", ".join(f"[[{n.title}]]" for n in neighbors)

    return [Suggestion(
        text=f"[[{note.title}]] doesn't quite fit. "
             f"Its neighbors are {neighbor_titles}, but it says something different. "
             f"Is it a seed of new thinking, or a stray thought?",
        notes=[note.title] + [n.title for n in neighbors],
        geist_id="surprisal"
    )]
```

---

##### 5. attention_shift
**File**: `src/geistfabrik/default_geists/code/attention_shift.py`

Detects notes whose semantic neighborhood has churned over time.

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Find notes whose semantic context has changed dramatically.

    Uses the session-cached, vectorised VaultContext.neighbor_churn() —
    one bulk historical-embedding load + two blocked top-k passes,
    NEVER per-note DB queries or similarity loops.
    """
    churn_map = vault.neighbor_churn(since_days=180)
    if not churn_map:
        return []  # No session history old enough — degrade gracefully

    candidates = [(p, r) for p, r in churn_map.items() if r.churn > 0.6]
    if not candidates:
        return []

    path, result = max(candidates, key=lambda x: x[1].churn)
    note = vault.note(path)
    departed = [vault.note(p).title for p in result.departed[:3]]
    arrived = [vault.note(p).title for p in result.arrived[:3]]

    old_titles = ", ".join(f"[[{t}]]" for t in departed)
    new_titles = ", ".join(f"[[{t}]]" for t in arrived)

    return [Suggestion(
        text=f"Your thinking around [[{note.title}]] has shifted. "
             f"Old neighbors: {old_titles}. "
             f"New neighbors: {new_titles}. "
             f"What changed in how you see this?",
        notes=[note.title] + departed + arrived,
        geist_id="attention_shift"
    )]
```

---

##### 6. this_time_last_year
**File**: `src/geistfabrik/default_geists/code/this_time_last_year.py`

Resurfaces notes from temporal anniversaries.

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Surface notes from around this date in previous years."""
    from datetime import timedelta
    
    today = vault.session_date
    candidates = []
    
    for years_ago in [1, 2, 3]:
        target_date = today.replace(year=today.year - years_ago)
        window_start = target_date - timedelta(days=7)
        window_end = target_date + timedelta(days=7)
        
        for note in vault.notes():
            if window_start <= note.created.date() <= window_end:
                candidates.append((note, years_ago))
    
    if not candidates:
        return []
    
    note, years = vault.sample(candidates, 1)[0]
    
    period = "a year" if years == 1 else f"{years} years"
    
    return [Suggestion(
        text=f"Around this time {period} ago, you wrote [[{note.title}]]. "
             f"What's different now? What's the same?",
        notes=[note.title],
        geist_id="this_time_last_year"
    )]
```

---

##### 7. sentence_variance
**File**: `src/geistfabrik/default_geists/code/sentence_variance.py`

Surfaces notes with choppy, high-variance sentence structure (cognitive load signal).

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Find notes with unusually choppy sentence structure."""
    variances = []
    
    for note in vault.notes():
        meta = vault.metadata(note)
        variance = meta.get("sentence_length_variance", 0)
        mean_len = meta.get("mean_sentence_length", 0)
        
        if mean_len > 5:  # Ignore very short notes
            variances.append((note, variance))
    
    if len(variances) < 10:
        return []
    
    # Find statistical outliers
    values = [v for _, v in variances]
    mean_var = sum(values) / len(values)
    std_var = (sum((v - mean_var)**2 for v in values) / len(values)) ** 0.5
    
    outliers = [
        (n, v) for n, v in variances
        if v > mean_var + 2 * std_var
    ]
    
    if not outliers:
        return []
    
    note, variance = max(outliers, key=lambda x: x[1])
    
    return [Suggestion(
        text=f"[[{note.title}]] has unusually choppy sentences — "
             f"short bursts mixed with long stretches. "
             f"Were you working something out when you wrote this?",
        notes=[note.title],
        geist_id="sentence_variance"
    )]
```

---

##### 8. voice_absence
**File**: `src/geistfabrik/default_geists/code/voice_absence.py`

Identifies missing voices in the vault (e.g., no future-focused notes, no "we" notes).

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Identify missing linguistic patterns in the vault."""
    orientations = {"past": 0, "present": 0, "future": 0, "mixed": 0}
    has_we = 0
    has_questions = 0
    total = 0
    
    for note in vault.notes():
        meta = vault.metadata(note)
        total += 1
        
        orientation = meta.get("temporal_orientation", "mixed")
        orientations[orientation] += 1
        
        if meta.get("first_person_plural", 0) > 1.0:
            has_we += 1
        
        if meta.get("question_density", 0) > 0.5:
            has_questions += 1
    
    if total < 20:
        return []
    
    suggestions = []
    
    # Check for missing temporal orientation
    if orientations["future"] < total * 0.05:
        suggestions.append(Suggestion(
            text=f"Only {orientations['future']} of your {total} notes look forward. "
                 f"What are you anticipating that you haven't written about?",
            notes=[],
            geist_id="voice_absence"
        ))
    
    if orientations["past"] < total * 0.05:
        suggestions.append(Suggestion(
            text=f"Only {orientations['past']} of your {total} notes look backward. "
                 f"What from your past haven't you processed on paper?",
            notes=[],
            geist_id="voice_absence"
        ))
    
    # Check for missing "we"
    if has_we < total * 0.05:
        suggestions.append(Suggestion(
            text=f"Only {has_we} of your {total} notes say 'we'. "
                 f"Who could you be thinking with?",
            notes=[],
            geist_id="voice_absence"
        ))
    
    # Check for missing questions
    if has_questions < total * 0.1:
        suggestions.append(Suggestion(
            text=f"Only {has_questions} of your {total} notes contain questions. "
                 f"What aren't you asking?",
            notes=[],
            geist_id="voice_absence"
        ))
    
    return suggestions[:1]  # Return at most one
```

---

#### Tracery Geists

##### 9. temporal_contrast (Tracery)
**File**: `src/geistfabrik/default_geists/tracery/temporal_contrast.yaml`

```yaml
type: geist-tracery
id: temporal_contrast
description: Contrasts past-focused and future-focused notes

tracery:
  origin: "#provocation#"
  
  provocation:
    - "#past_note# looks backward. #future_note# looks forward. What connects memory and anticipation here?"
    - "You reflected in #past_note# and planned in #future_note#. Are they about the same thing?"
    - "#past_note# is in past tense. What would it say if you rewrote it looking forward?"
  
  past_note: ["$vault.past_focused_notes(1)"]
  future_note: ["$vault.future_focused_notes(1)"]
```

---

##### 10. questioning_mind (Tracery)
**File**: `src/geistfabrik/default_geists/tracery/questioning_mind.yaml`

```yaml
type: geist-tracery
id: questioning_mind
description: Surfaces notes full of questions

tracery:
  origin: "#provocation#"
  
  provocation:
    - "#note# is full of questions. Which one keeps you up at night?"
    - "You asked a lot in #note#. Have any of those questions been answered?"
    - "#note# questions everything. What would it look like to answer just one?"
  
  note: ["$vault.questioning_notes(1)"]
```

---

##### 11. unexpected_neighbor (Tracery)
**File**: `src/geistfabrik/default_geists/tracery/unexpected_neighbor.yaml`

```yaml
type: geist-tracery
id: unexpected_neighbor
description: Surfaces surprising notes via information-theoretic surprisal

tracery:
  origin: "#provocation#"
  
  provocation:
    - "#note# doesn't fit anywhere obvious. Is it a seed or a stray?"
    - "#note# surprised me — it's unlike your typical thinking. What's it doing in your vault?"
    - "Your most unexpected note right now is #note#. What does it know that the others don't?"
  
  note: ["$vault.surprising_notes(1)"]
```

---

## Implementation Roadmap

### Phase 1: Core Metadata (1 week)
1. Implement `voice.py` metadata module
   - Single-pass tokenisation; precompiled patterns; irregular-verb set
   - Verb tense detection, pronoun counting, hedge detection, sentence stats
   - Strip code blocks and URLs before analysis
2. Wire into metadata loading system
3. Tests: known-answer units, sad paths, Hypothesis property/fuzz suite,
   `make_note`/`make_voice_vault` builders

### Phase 2: VaultContext Methods + Vault Functions (1 week)
1. Implement `surprisal_scores()` — naive reference first, then blocked
   vectorised version, with the **differential test written before the
   optimisation** (red-green-refactor)
2. Implement `neighbor_churn()` — bulk historical-embedding load, graceful
   degradation when session history is shallow
3. Implement 8 thin vault functions (bracket-conformance tests included)
4. Benchmarks on synthetic 10k vault (budget assertions, memory bound)

### Phase 3: Geists (1 week)
1. Implement 8 code geists + 3 Tracery geists
2. Parametrised conformance suite across all 11
3. Static architectural regression test (no similarity loops in geists)
4. Golden-file session tests on the voice fixture vault

### Phase 4: Validation (3 days)
1. Voice fixture vault (`tests/fixtures/voice_vault/`) with controlled
   tense/pronoun/hedging mixes
2. spaCy calibration test for tense detection (marked `slow`)
3. Characterization run against kepano testdata; e2e invoke test
4. Mutation-testing pass on `voice.py` (manual); documentation

**Total: ~3.5 weeks**

---

## Performance Characteristics

### Per-Component Cost Model

Estimates assume a 10k-note vault (~5M words), 384-dim embeddings already in
memory, warm session caches. The per-geist timeout is 30s.

| Component | Complexity | 1k notes | 10k notes | Memory | Notes |
|-----------|-----------|----------|-----------|--------|-------|
| `voice.py` metadata (all notes) | O(total words) | <0.5s | 1–3s | negligible | Single-pass tokenisation; runs once per session, shared by all geists via metadata cache |
| `surprisal_scores()` | O(N²·d) as blocked BLAS | <0.1s | 2–5s | ~40 MB/block | One-time per session, cached; argpartition top-k |
| `neighbor_churn()` | 2 × O(N²·d) + bulk DB read | <0.2s | 5–10s | ~15 MB hist. embeddings + blocks | One-time per session, cached |
| `temporal_voice` geist | ≤100 cached `similarity()` calls | <0.1s | <1s | — | Bounded search, early termination |
| `this_time_last_year` geist | O(N) date scan | <1ms | ~10ms | — | |
| All metadata-scan geists (`self_and_other`, `uncertainty_mapper`, `sentence_variance`, `voice_absence`) | O(N) dict reads | <5ms | ~50ms | — | Metadata already cached |

**Whole-session budget**: the 11 new geists together add roughly **10–20s on a
10k-note vault**, dominated by the two one-time vectorised passes
(`surprisal_scores`, `neighbor_churn`). Every individual geist stays well
under the 30s timeout because the heavy work is session-cached in
VaultContext, not repeated per geist.

### The Two Performance Cliffs (and how this spec avoids them)

1. **Per-note neighbour loops.** The naive implementation of surprisal —
   `for note in vault.notes(): vault.semantic_neighbors(note, k=10)` — is
   10k Python-level top-k searches ≈ 20–50s, at or over the timeout. This is
   exactly the Phase 3B failure mode documented in CLAUDE.md. The spec
   therefore mandates **one blocked matrix pass in VaultContext**
   (`E_block @ E.T`, `np.argpartition`), which is the same flop count but
   runs in multi-threaded BLAS: ~2–5s. A static regression test enforces
   that no reflective-lens geist calls `semantic_neighbors` inside a loop
   (precedent: `test_phase3b_regression.py`).

2. **Per-note DB queries for history.** `neighbor_churn` must load the
   historical session's embeddings with **one bulk SELECT** (~15 MB), never
   a query per note (10k round-trips).

### Optimisation Decisions

- **Single-pass tokenisation**: `voice.py` tokenises each note once and
  derives all features (tense counts, pronouns, hedges, sentence stats) from
  that one token stream — not 10+ separate regex scans (a ~5× constant-factor
  saving). Patterns are precompiled at module level; word lookups use
  `frozenset`s. Multi-word hedges ("sort of", "I think") are matched with a
  single compiled alternation over the raw text.
- **Session-scoped caching in VaultContext**: `surprisal_scores()` and
  `neighbor_churn()` are computed once and shared — if three geists or
  Tracery functions need them, the cost is paid once. This respects the
  "respect session-scoped caches" lesson from the Phase 3B rollback.
- **Blocked matmuls bound memory**: a full 10k×10k float32 similarity matrix
  is 400 MB; 1024-row blocks keep peak usage ≈ 40 MB.
- **No blind sampling**: per the Phase 3B lesson (pattern_finder lost 95%
  coverage), we keep full-vault coverage and win speed via vectorisation,
  not sampling. The only sampling is in cheap candidate selection
  (`temporal_voice`), where it bounds work without losing pattern coverage.
- **Graceful degradation gates**: geists return `[]` early when the vault is
  too small (<20 notes), session history is too shallow (`neighbor_churn`
  needs a session ≥30 days old), or no candidates pass thresholds. Early
  gates cost O(1)–O(N) and prevent wasted computation.
- **Known non-problem**: voice metadata is recomputed each session rather
  than persisted (metadata is in-memory by design, and there is no metadata
  table). At 1–3s per session for 10k notes this does not justify a breaking
  DB change pre-1.0. **Future work (post-1.0)**: content-hash keyed
  persistence alongside the planned migration framework.

### Known Quality Caveats (accepted trade-offs)

- Regex tense detection mislabels some irregular verbs; a ~180-entry
  irregular-past-form set is included (negligible cost). Accuracy is
  calibrated, not assumed — see Differential Testing below.
- Type-token ratio (lexical diversity) is length-biased: longer notes score
  lower. Acceptable for provocations; flagged so nobody treats it as a
  measurement.

---

## Testing Strategy

Mapped against the full technique catalogue in
[adewale/testing-best-practices](https://github.com/adewale/testing-best-practices)
(16 techniques in three tiers). Core principles applied throughout:
**3+ assertions per test, real objects over mocks, sad paths and boundary
values, test data builders.**

### Tier 1 — Always

#### Unit Testing
Per-feature tests for `voice.py` with known-answer inputs (the CLAUDE.md
"known-answer test" lesson — these catch wrong-algorithm bugs that fuzzy
tests miss):

```python
def test_past_tense_detection():
    note = make_note("I walked to the store. I bought milk. I returned home.")
    meta = infer_voice(note, vault)
    assert meta["past_tense_ratio"] > 0.8
    assert meta["temporal_orientation"] == "past"
    assert meta["future_tense_ratio"] < 0.1

def test_irregular_past_tense():
    """Irregular verbs (no -ed suffix) must still register as past."""
    note = make_note("I went home. I saw the error. I thought about it.")
    meta = infer_voice(note, vault)
    assert meta["temporal_orientation"] == "past"

def test_hedging_detection():
    note = make_note("Maybe this works. Perhaps it doesn't. I think it might be okay.")
    meta = infer_voice(note, vault)
    assert meta["hedging_ratio"] > 0.5
    assert meta["modal_density"] > 0

def test_pronoun_patterns():
    note = make_note("We built this together. Our team succeeded. We celebrated.")
    meta = infer_voice(note, vault)
    assert meta["first_person_plural"] > 3.0
    assert meta["self_focus_ratio"] < 0.3
    assert meta["first_person_singular"] == 0.0
```

Sad paths and boundary values: empty note, whitespace-only note, single
word, no verbs at all (ratios must not divide by zero), a note that is one
giant sentence, a note of only questions.

Test data builder (`tests/fixtures/voice_notes.py`):

```python
def make_note(content: str, *, title: str = "Test", created: datetime = ...) -> Note: ...
def make_voice_vault(past: int = 5, future: int = 5, hedgy: int = 3, ...) -> Vault:
    """Builds a vault with a controlled mix of linguistic voices."""
```

#### Smoke Testing
`geistfabrik test <geist_id> <fixture-vault>` for each of the 11 geists in
CI — each must execute without error and return a list (possibly empty).

#### Regression Testing
- Every bug found gets a pinned test with the reproducing input.
- **Static architectural regression** (precedent: `test_phase3b_regression.py`):
  assert via AST/source inspection that no reflective-lens geist calls
  `semantic_neighbors` or `similarity` inside a `for note in vault.notes()`
  loop, and that `surprisal`/`attention_shift` geists use the cached
  VaultContext methods.

### Tier 2 — Triggered (and which triggers fire here)

#### Property-Based Testing (Hypothesis — already a dev dependency)
Triggered: the voice features have genuine mathematical properties.

```python
@given(st.text(max_size=5000))
def test_voice_metadata_total_function(content):
    """Never crashes, all ranges hold, on ARBITRARY text."""
    meta = infer_voice(make_note(content), vault)
    assert 0.0 <= meta["past_tense_ratio"] <= 1.0
    assert 0.0 <= meta["self_focus_ratio"] <= 1.0
    assert meta["hedging_ratio"] >= 0.0
    assert abs(meta["past_tense_ratio"] + meta["present_tense_ratio"]
               + meta["future_tense_ratio"] - 1.0) < 1e-9 or no_verbs(content)

@given(st.text(max_size=2000))
def test_case_invariance(content):
    """Voice features are invariant under case changes."""
    assert infer_voice(make_note(content.lower()), vault) == \
           infer_voice(make_note(content.upper().lower()), vault)

@given(st.text(max_size=2000), st.text(max_size=2000))
def test_pronoun_counts_additive(a, b):
    """Metamorphic: raw counts are additive under concatenation."""
    combined = raw_counts(a + "\n\n" + b)
    assert combined == add_counts(raw_counts(a), raw_counts(b))

@given(st.text(max_size=2000))
def test_appending_hedge_never_decreases_hedging(content):
    """Metamorphic: adding 'Maybe.' can only increase hedge count."""
    before = raw_hedge_count(content)
    after = raw_hedge_count(content + " Maybe it is.")
    assert after >= before + 1

@given(embedding_matrices())  # strategy generating small random (N, d) arrays
def test_surprisal_properties(E):
    scores = compute_surprisal(E, k=3)
    assert all(0.0 <= s <= 2.0 for s in scores.values())
    # A note identical to its neighbours has ~zero surprisal
    # (constructed case appended to E)

@given(neighbour_sets())
def test_churn_properties(old, new):
    assert 0.0 <= jaccard_churn(old, new) <= 1.0
    assert jaccard_churn(old, old) == 0.0
    assert jaccard_churn(old, new) == jaccard_churn(new, old)  # symmetry
```

#### Differential Testing
Triggered twice — this is the highest-value technique for this feature:

1. **Vectorised vs. reference implementation.** The blocked-BLAS
   `surprisal_scores()` must agree with a 20-line naive reference
   implementation to within 1e-5 on Hypothesis-generated random embedding
   matrices. Same for `neighbor_churn` top-k sets. This is the classic
   guard when optimising: the fast path is only trusted because the slow
   path defines correctness.

   ```python
   @given(embedding_matrices(min_n=10, max_n=200))
   def test_vectorised_surprisal_matches_naive(E):
       fast = compute_surprisal_blocked(E, k=5)
       slow = compute_surprisal_naive(E, k=5)   # readable reference
       assert fast.keys() == slow.keys()
       assert all(abs(fast[p] - slow[p]) < 1e-5 for p in fast)
   ```

2. **Regex tense detector vs. spaCy POS tagging** (calibration, marked
   `slow`, dev-only dependency): on a 200-sentence fixture corpus, regex
   orientation must agree with spaCy-derived orientation on ≥85% of
   sentences. This converts "regex is probably fine" into a measured,
   regression-guarded number.

#### Golden File Testing
Triggered: deterministic randomness (same date + vault = same output) is a
core GeistFabrik design principle, which makes session output a perfect
golden-file candidate.

- Fixture vault `tests/fixtures/voice_vault/` (notes with controlled tense /
  pronoun / hedging mixes) + pinned date `--date 2025-01-15` → golden
  journal markdown checked into `tests/goldens/`.
- Promotion workflow: `UPDATE_GOLDENS=1 pytest tests/integration/test_reflective_goldens.py`
  regenerates; diffs are reviewed in PR like any code change.
- Catches: template wording regressions, bracket-formatting bugs, ordering
  instability, accidental nondeterminism.

#### Pirate/Conformance Testing
Triggered: 11 new geists must all satisfy the same contracts. One
parametrised suite runs the full GEIST_TESTING_TEMPLATE battery against
every reflective-lens geist:

```python
@pytest.mark.parametrize("geist_id", REFLECTIVE_LENS_GEISTS)
class TestReflectiveLensConformance:
    def test_returns_list_of_suggestions(self, geist_id, voice_vault): ...
    def test_handles_empty_vault(self, geist_id, empty_vault): ...
    def test_handles_tiny_vault(self, geist_id, three_note_vault): ...
    def test_all_note_references_bracketed(self, geist_id, voice_vault): ...
    def test_referenced_notes_exist(self, geist_id, voice_vault): ...
    def test_deterministic_for_same_date(self, geist_id, voice_vault): ...
```

Plus the existing vault-function contract: all new vault functions return
`[[bracketed]]` links (the consistent-API rule from CLAUDE.md) — added to
the existing bracket-conformance tests.

#### Documentation-Code Sync Testing
Triggered: adding geists changes counts. The existing
`test_geist_count_consistency.py` will fail automatically if README/CLAUDE.md
drift — no action needed beyond running it. Additionally: a test asserting
every geist ID listed in this spec's config example exists on disk, and
every `$vault.*` function named in the Tracery YAML is registered.

#### End-to-End Testing
One e2e test: full `geistfabrik invoke` on the voice fixture vault produces
a journal note containing at least one reflective-lens suggestion with a
valid block ID (`^gYYYYMMDD-NNN`), exercising metadata inference → vault
functions → geists → filtering → journal writing as one pipeline.

#### Characterization Testing
Light use: run all 11 geists against the existing kepano testdata vault and
pin which ones produce suggestions vs. return `[]` (the kepano vault is
factual/technical — most voice geists *should* still fire since technical
notes have tenses and pronouns; surprisal always fires). This pins behaviour
on realistic-but-unfavourable data before any refactor.

#### Contract / VCR Cassette Testing
**Not applicable** — no external APIs, no network, no multi-language SDK.
Local-first design removes these trust boundaries entirely. (This is worth
stating so nobody adds them ritually.)

### Tier 3 — With Caution

#### Performance Testing
Uses the existing `benchmark` pytest marker (not run by default):

```python
@pytest.mark.benchmark
def test_voice_inference_10k_budget(synthetic_10k_vault):
    elapsed = timed(lambda: infer_all_voice(synthetic_10k_vault))
    assert elapsed < 5.0   # budget from Performance Characteristics table

@pytest.mark.benchmark
def test_surprisal_scores_10k_budget(synthetic_10k_vault): ...   # < 8s

@pytest.mark.benchmark
def test_neighbor_churn_memory_bounded(synthetic_10k_vault):
    """Peak RSS delta < 150 MB — blocked matmul, not full N×N matrix."""
```

Synthetic vault generator: N notes of Markov-ish text with random embeddings
(no model needed — works with the `SentenceTransformerStub`). Budgets have
~2× headroom over the estimates so CI noise doesn't flake.

#### Mutation Testing
Targeted, not blanket: run `mutmut` (or `cosmic-ray`) on `voice.py` only —
it is pure, fast, and threshold-dense (`>` vs `>=`, ratio denominators,
orientation cut-points are exactly what mutation testing catches and what
Hypothesis range checks may survive). Run manually / nightly, not in PR CI.
Goal: >85% mutants killed on `voice.py`.

#### Fuzz Testing
Folded into Hypothesis with hostile-input strategies rather than a separate
harness: emoji, CJK text (no whitespace tokenisation!), RTL text, zero-width
joiners, 100k-character single lines, markdown edge cases (nested code
blocks, frontmatter-in-body). Assertions: no exceptions, all range
invariants hold, runtime per note stays bounded. Code blocks and URLs should
be stripped before voice analysis — fuzz cases pin that behaviour.

#### Visual/Screenshot Testing
**Not applicable** — output is markdown text; golden files cover it.

### What This Catches That the Old Plan Missed

| Risk | Technique that catches it |
|------|--------------------------|
| Vectorised surprisal silently wrong (the L2-vs-cosine class of bug) | Differential vs. naive reference + known-answer tests |
| Regex tense detection quietly inaccurate | Differential calibration vs. spaCy (measured ≥85%) |
| Division by zero on verb-free/empty notes | Property-based total-function test + sad-path units |
| O(N²) Python-loop regression reintroduced | Static architectural regression test + benchmarks |
| Template/format drift in suggestions | Golden files with promotion workflow |
| A geist crashing on tiny/empty vaults | Conformance suite (parametrised across all 11) |
| Docs drifting from geist counts | Existing doc-sync test fires automatically |
| Threshold off-by-one (`>` vs `>=`) surviving the suite | Mutation testing on voice.py |
| Unicode/CJK input crashing tokeniser | Hypothesis fuzz strategies |

---

## Comparison: Sentiment Spec vs. Reflective Lenses

| Aspect | Sentiment Spec (withdrawn) | Reflective Lenses |
|--------|---------------------------|-------------------|
| Core signal | Valence/arousal classification | Verb tense, pronouns, hedging |
| Accuracy | ~50% on fine-grained emotions | 100% (syntactic, not semantic) |
| Licensing | LIWC proprietary, NRC research-only | No external lexicons needed |
| Dependencies | External lexicons or 125MB model | Pure Python regex |
| Temporal tracking | Claimed but no mechanism | Attention drift via neighbors |
| Precision | False ("valence: +0.73") | Honest ("looks backward") |
| Philosophy alignment | Says "muses" but measures | Actually provokes without labeling |

---

## Success Metrics

Reflective lenses succeed when they:

1. **Surface patterns users didn't notice** — "I didn't realize all my notes are past-focused"
2. **Ask questions users wouldn't ask themselves** — "Who could you be thinking with?"
3. **Generate useful reflection even when "wrong"** — A note miscategorized as "uncertain" still prompts reflection
4. **Never mislead with false precision** — No decimal scores, no confidence percentages
5. **Work on any vault** — Technical notes have verb tenses and pronouns too

---

## Future Extensions (Post-1.0)

### Behavioral Signals (Requires Obsidian Plugin)
- Edit velocity (revisions per session)
- Deletion ratio (self-censorship signal)
- Revisitation without editing (attention without action)

### User-Supplied Annotations
- Emoji reactions per session
- Simple mood tags (`#feeling/uncertain`)
- End-of-session reflection prompts

### Empath Integration (Optional)
- 200+ categories, MIT licensed
- Categories beyond sentiment: cognition, perception, social processes
- `pip install empath`

---

## Research Basis

This specification draws on:

- **Pennebaker & colleagues** on linguistic markers of psychological states (LIWC validation studies, 1999–2022)
- **Fast et al. (2016)** on Empath as open-source LIWC alternative
- **Palm (2012)** on information-theoretic novelty/surprisal
- **CHI reminiscence research** (2015) on temporal cues for reflection
- **Expressive writing literature** (Pennebaker, 1986–present) on reflection prompts

Unlike the sentiment spec, this specification does not depend on:
- Plutchik's wheel (heuristic taxonomy, not empirically validated structure)
- GoEmotions transformer accuracy (misattributed in prior spec)
- Appraisal theory dimensions (not inferrable from text without knowing author goals)
- Facebook contagion study (effect sizes near zero, ethics controversy)

---

*End of Reflective Lenses Specification v1.0*
