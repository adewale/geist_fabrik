# Reflective Lenses Specification

*Version: 1.0*
*Date: June 2026*
*Supersedes: specs/sentiment_geists_spec.md (withdrawn)*

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

#### Information-Theoretic Surprisal

```python
@vault_function("surprising_notes")
def surprising_notes(vault: VaultContext, k: int = 5) -> list[str]:
    """Sample notes with high information-theoretic surprisal.
    
    Surprisal = how unexpected a note is given its semantic neighborhood.
    Computed as: 1 - similarity to centroid of nearest neighbors.
    """
    surprisals = []
    for note in vault.notes():
        neighbors = vault.semantic_neighbors(note, k=10)
        if len(neighbors) < 3:
            continue
        neighbor_embeddings = [vault.embedding(n) for n in neighbors]
        centroid = np.mean(neighbor_embeddings, axis=0)
        surprisal = 1 - cosine_similarity(vault.embedding(note), centroid)
        surprisals.append((note, surprisal))
    
    surprisals.sort(key=lambda x: x[1], reverse=True)
    top_k = surprisals[:k]
    return [f"[[{n.title}]]" for n, _ in top_k]
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
    
    Compares neighbors from `months_ago` to current neighbors.
    High churn = the notes you associate with this topic have changed.
    """
    shifted = []
    cutoff = vault.session_date - timedelta(days=months_ago * 30)
    
    for note in vault.notes():
        old_neighbors = vault.neighbors_at_date(note, cutoff, k=10)
        new_neighbors = vault.semantic_neighbors(note, k=10)
        
        if not old_neighbors:
            continue
            
        old_set = {n.path for n in old_neighbors}
        new_set = {n.path for n in new_neighbors}
        
        jaccard = len(old_set & new_set) / len(old_set | new_set) if old_set | new_set else 1
        churn = 1 - jaccard
        
        if churn >= min_churn:
            shifted.append((note, churn, old_neighbors, new_neighbors))
    
    shifted.sort(key=lambda x: x[1], reverse=True)
    return [f"[[{n.title}]]" for n, _, _, _ in shifted[:k]]
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
    
    # Find a semantically related pair with opposite temporal voice
    for past_note in vault.sample(past_notes, 5):
        for future_note in future_notes:
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
    """Find notes that don't fit their semantic neighborhood."""
    surprisals = []
    
    for note in vault.notes():
        neighbors = vault.semantic_neighbors(note, k=10)
        if len(neighbors) < 5:
            continue
        
        neighbor_embeddings = [vault.embedding(n) for n in neighbors]
        centroid = np.mean(neighbor_embeddings, axis=0)
        note_embedding = vault.embedding(note)
        
        similarity_to_centroid = cosine_similarity(
            note_embedding.reshape(1, -1),
            centroid.reshape(1, -1)
        )[0][0]
        
        surprisal = 1 - similarity_to_centroid
        surprisals.append((note, surprisal, neighbors[:3]))
    
    if not surprisals:
        return []
    
    surprisals.sort(key=lambda x: x[1], reverse=True)
    note, score, neighbors = surprisals[0]
    
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
    """Find notes whose context has changed dramatically."""
    from datetime import timedelta
    
    shifts = []
    cutoff = vault.session_date - timedelta(days=180)  # 6 months ago
    
    for note in vault.notes():
        if note.created > cutoff:
            continue  # Note didn't exist 6 months ago
            
        old_neighbors = vault.neighbors_at_date(note, cutoff, k=10)
        new_neighbors = vault.semantic_neighbors(note, k=10)
        
        if not old_neighbors or not new_neighbors:
            continue
        
        old_set = {n.path for n in old_neighbors}
        new_set = {n.path for n in new_neighbors}
        
        overlap = len(old_set & new_set)
        union = len(old_set | new_set)
        churn = 1 - (overlap / union) if union else 0
        
        if churn > 0.6:  # >60% of neighbors changed
            departed = [n for n in old_neighbors if n.path not in new_set][:3]
            arrived = [n for n in new_neighbors if n.path not in old_set][:3]
            shifts.append((note, churn, departed, arrived))
    
    if not shifts:
        return []
    
    shifts.sort(key=lambda x: x[1], reverse=True)
    note, churn, departed, arrived = shifts[0]
    
    old_titles = ", ".join(f"[[{n.title}]]" for n in departed)
    new_titles = ", ".join(f"[[{n.title}]]" for n in arrived)
    
    return [Suggestion(
        text=f"Your thinking around [[{note.title}]] has shifted. "
             f"Old neighbors: {old_titles}. "
             f"New neighbors: {new_titles}. "
             f"What changed in how you see this?",
        notes=[note.title] + [n.title for n in departed + arrived],
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
   - Verb tense detection (regex-based)
   - Pronoun counting
   - Hedge word detection
   - Sentence structure analysis
2. Wire into metadata loading system
3. Unit tests for each feature

### Phase 2: Vault Functions (3 days)
1. Implement 8 vault functions
2. Add `neighbors_at_date()` to VaultContext (may require temporal infrastructure)
3. Integration tests

### Phase 3: Geists (1 week)
1. Implement 8 code geists
2. Implement 3 Tracery geists
3. Per-geist unit tests following GEIST_TESTING_TEMPLATE.md

### Phase 4: Validation (3 days)
1. Create test fixtures with varied linguistic patterns
2. Validate geist output quality
3. Documentation

**Total: ~3 weeks**

---

## Testing Strategy

### Metadata Module Tests
```python
def test_past_tense_detection():
    note = Note(content="I walked to the store. I bought milk. I returned home.")
    meta = infer_voice(note, vault)
    assert meta["past_tense_ratio"] > 0.8
    assert meta["temporal_orientation"] == "past"

def test_hedging_detection():
    note = Note(content="Maybe this works. Perhaps it doesn't. I think it might be okay.")
    meta = infer_voice(note, vault)
    assert meta["hedging_ratio"] > 0.5

def test_pronoun_patterns():
    note = Note(content="We built this together. Our team succeeded. We celebrated.")
    meta = infer_voice(note, vault)
    assert meta["first_person_plural"] > 3.0  # per 100 words
    assert meta["self_focus_ratio"] < 0.3
```

### Geist Tests
Follow existing GEIST_TESTING_TEMPLATE.md:
- `test_returns_suggestions` — non-empty on suitable vault
- `test_suggestion_structure` — valid Suggestion objects
- `test_obsidian_link` — proper `[[...]]` formatting
- `test_empty_vault` — graceful handling
- `test_insufficient_data` — graceful handling

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
