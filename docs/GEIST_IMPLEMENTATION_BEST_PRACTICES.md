# Geist Implementation Best Practices

**Purpose**: Technical implementation patterns and lessons learned from analyzing all 49 default geists (40 code, 9 Tracery).

This guide complements `WRITING_GOOD_GEISTS.md` (which covers philosophy and performance) by focusing on **how to implement geists correctly**.

---

## Table of Contents

- [Standard Code Geist Structure](#standard-code-geist-structure)
- [The 10 Essential Lessons](#the-10-essential-lessons)
- [Sampling Strategies](#sampling-strategies)
- [VaultContext API Patterns](#vaultcontext-api-patterns)
- [Performance Optimization Techniques](#performance-optimization-techniques)
- [Edge Case Handling](#edge-case-handling)
- [Suggestion Construction Patterns](#suggestion-construction-patterns)
- [Content Analysis Techniques](#content-analysis-techniques)
- [Tracery Geist Patterns](#tracery-geist-patterns)
- [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
- [Advanced Techniques](#advanced-techniques)
- [Testing and Validation](#testing-and-validation)

---

## Standard Code Geist Structure

Every code geist follows this battle-tested template:

```python
"""Clear docstring explaining what this geist does and why."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Generate suggestions for [specific purpose].

    Returns:
        List of 2-3 suggestions, or empty list if insufficient data.
    """
    from geistfabrik import Suggestion

    # 1. Early validation - exit before expensive operations
    notes = vault.notes()
    if len(notes) < MINIMUM_THRESHOLD:
        return []

    # 2. Core analysis logic
    suggestions = []

    # Sample or filter notes
    for note in vault.sample(notes, min(30, len(notes))):
        # Analyze note
        # Build suggestions
        if quality_check_passes:
            suggestions.append(
                Suggestion(
                    text=f"What if [[{note.title}]]...",
                    notes=[note.title],
                    geist_id="my_geist",
                )
            )

    # 3. Final sampling to limit output
    return vault.sample(suggestions, k=3)
```

### Why This Structure?

1. **TYPE_CHECKING guard** - Prevents circular imports while preserving type hints
2. **Runtime Suggestion import** - Keeps startup fast by importing only when needed
3. **Early exits** - Avoid wasted computation on edge cases
4. **Final sampling** - Limit output to prevent overwhelming users

**Observed in**: 100% of code geists use this exact pattern.

---

## The 10 Essential Lessons

These lessons represent the distilled wisdom from 49 geists and ~10,500 lines of production code:

### 1. **Sample Before Analyze**
Reduce search space before expensive operations.

```python
# ❌ BAD: Analyze all 10,000 notes
for note in notes:
    expensive_operation(note)

# ✅ GOOD: Sample to manageable size first
for note in vault.sample(notes, min(30, len(notes))):
    expensive_operation(note)
```

### 2. **Cache Before Reuse**
Get similarity scores once with `return_scores=True`.

```python
# ❌ BAD: Recompute similarity multiple times
neighbours = vault.neighbours(note, k=10)
for n in neighbours:
    sim = vault.similarity(note, n)  # Recomputed!
    if sim > 0.6:
        later_sim = vault.similarity(note, n)  # Recomputed again!

# ✅ GOOD: Get scores once, reuse
neighbours_with_scores = vault.neighbours(note, k=10, return_scores=True)
for n, sim in neighbours_with_scores:
    if sim > 0.6:
        # Reuse cached sim
```

### 3. **Build Sets, Not Loops**
Convert O(N) repeated searches into O(1) lookups.

```python
# ❌ BAD: O(N) lookup per iteration
for note_a in notes:
    for note_b in notes:
        if vault.links_between(note_a, note_b):  # O(N) per call!
            # ...

# ✅ GOOD: Build O(1) lookup set once
link_pairs = set()
for note in notes:
    for target in vault.outgoing_links(note):
        pair = tuple(sorted([note.path, target.path]))
        link_pairs.add(pair)

# Now O(1) lookups
for note_a in notes:
    for note_b in notes:
        pair = tuple(sorted([note_a.path, note_b.path]))
        if pair in link_pairs:
            # ...
```

**Real-world impact**: `pattern_finder.py` gained 30-50% speedup using this technique.

### 4. **Validate Before Return**
Quality gates prevent noise.

```python
# ❌ BAD: Return everything found
questions = extract_questions(content)
return questions

# ✅ GOOD: Validate quality first
questions = extract_questions(content)
valid_questions = [q for q in questions if is_valid_question(q)]
return valid_questions

def is_valid_question(q: str) -> bool:
    return 10 <= len(q) <= 500 and re.search(r'[a-zA-Z]', q)
```

### 5. **Abstain When Uncertain**
Empty list is better than low-quality suggestions.

```python
# Return empty list when:
if len(notes) < minimum_threshold:
    return []  # Insufficient data

if not quality_suggestions:
    return []  # Geist abstains

try:
    # Temporal operations
except Exception:
    return []  # Graceful degradation
```

### 6. **Respect Session Cache**
Use `similarity()` not `batch_similarity()` when cache might be warm.

```python
# ❌ BAD: Bypasses session cache
sim_matrix = vault.batch_similarity([note], candidates)

# ✅ GOOD: Benefits from session-scoped cache
for candidate in candidates:
    sim = vault.similarity(note, candidate)  # Cache hit if computed before
    if sim > threshold:
        # ...
```

**Context**: Other geists may have already computed these similarities in the same session. Individual calls leverage the cache; batch operations don't.

**Exception**: Use `batch_similarity()` for pairwise matrices where you need all N×M combinations.

### 7. **Match Threshold to Complexity**
Different operations need different minimum data.

```python
if len(notes) < 3: return []   # Basic comparisons
if len(notes) < 10: return []  # Graph operations
if len(notes) < 15: return []  # Pattern finding
if len(notes) < 50: return []  # Seasonal analysis
```

### 8. **Never Crash**
Wrap optional features in try/except.

```python
try:
    sessions = _get_session_history(vault, sessions_back=5)
    if len(sessions) < 3:
        return []
    # ... temporal analysis
except Exception:
    return []  # Graceful degradation
```

**Observed in**: All temporal geists (`concept_drift`, `session_drift`, `hermeneutic_instability`) use this pattern.

### 9. **Explain the Insight**
Construct suggestions that teach through "What if..." questions.

```python
# ❌ BAD: Just reference notes
text = f"[[{note_a.title}]] and [[{note_b.title}]]"

# ✅ GOOD: Explain why connection is interesting
text = (
    f"[[{note_a.title}]] and [[{note_b.title}]] are semantically "
    f"similar (0.87) despite no links. Same pattern, different scale?"
)
```

### 10. **Profile Before Optimize**
Measure bottlenecks, don't guess.

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your geist logic here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

**Lesson from Phase 3B**: Intuition often misleads about bottlenecks. Phrase extraction was 67.7% of time, not corpus iteration as assumed.

---

## Sampling Strategies

Three distinct approaches observed across geists:

### Strategy 1: Sample-Then-Analyze (Most Common)

Sample to manageable size before expensive operations.

```python
for note in vault.sample(notes, min(30, len(notes))):
    # Analyze sampled subset
    neighbours = vault.neighbours(note, k=5)
    # ... expensive analysis
```

**When to use**:
- Operations are expensive (O(N²) or worse)
- Sampling won't significantly reduce quality
- You need representative results, not exhaustive

**Used by**: `columbo`, `bridge_builder`, `temporal_mirror`

### Strategy 2: Analyze-All-Then-Sample (Quality-Focused)

Analyze everything to ensure quality, then sample final suggestions.

```python
candidates = []
for note in notes:  # Analyze all
    if meets_criteria(note):
        candidates.append(create_suggestion(note))

# Sample from quality candidates
return vault.sample(candidates, k=3)
```

**When to use**:
- Analysis per note is cheap (O(1) or O(log N))
- Quality requires examining all notes
- You're building a ranked list to sample from

**Used by**: `pattern_finder`, `question_harvester`

### Strategy 3: Early Termination (Performance-Focused)

Stop as soon as you have enough suggestions.

```python
max_suggestions = 5
count = 0

for note in vault.sample(notes, min(30, len(notes))):
    if count >= max_suggestions:
        break

    if generates_quality_suggestion(note):
        suggestions.append(...)
        count += 1

return suggestions
```

**When to use**:
- Finding first N quality suggestions is sufficient
- Continuing past N provides no additional value
- You want fastest possible runtime

**Used by**: `antithesis_generator`

### Adaptive Sampling

Scale sample size with vault size:

```python
# ❌ BAD: Fixed sample size
sample_size = 500  # Too many for small vaults, too few for large

# ✅ GOOD: Adaptive sampling
sample_size = min(1000, max(50, len(notes) // 10))
sampled = vault.sample(notes, k=sample_size)
```

**Formula**: `min(max_size, max(min_size, len(notes) // ratio))`
- `max_size`: Upper bound (e.g., 1000)
- `min_size`: Lower bound (e.g., 50)
- `ratio`: Scaling factor (e.g., 10 for 10% sample)

---

## VaultContext API Patterns

### High-Frequency Methods

#### 1. `vault.sample(items, k)` - Universal Randomization

Used by 100% of geists for deterministic sampling.

```python
# Random notes
random_notes = vault.sample(notes, k=3)

# Random from filtered set
stale_notes = [n for n in notes if vault.metadata(n)["staleness"] > 90]
random_stale = vault.sample(stale_notes, k=2)

# Random element from list
operation = vault.sample(scamper_operations, k=1)[0]
```

**Key property**: Respects session seed - same date + vault = same results.

#### 2. `vault.neighbours(note, k, return_scores=True)` - Semantic Similarity

Critical optimization: Use `return_scores=True` to avoid recomputation.

```python
# ❌ BAD: Scores not returned, must recompute if needed
neighbours = vault.neighbours(hub, k=10)
for n in neighbours:
    sim = vault.similarity(hub, n)  # Recomputed!

# ✅ GOOD: Scores returned, reuse them
neighbours_with_scores = vault.neighbours(hub, k=10, return_scores=True)
for neighbour, similarity in neighbours_with_scores:
    if similarity > 0.6:  # Use cached score
        # ...
```

**Real example** from `bridge_builder.py`:
```python
neighbours_with_scores = vault.neighbours(hub, k=10, return_scores=True)
high_sim_count = sum(1 for n, sim in neighbours_with_scores if sim > 0.6)
neighbour_notes = [n for n, sim in neighbours_with_scores[:5]]
```

#### 3. `vault.metadata(note)` - Computed Properties

Access rich metadata without reading file content.

```python
metadata = vault.metadata(note)

# Available properties
word_count = metadata.get("word_count", 0)
lexical_diversity = metadata.get("lexical_diversity", 0.0)
staleness = metadata.get("staleness", 0)
days_since_modified = metadata.get("days_since_modified", 0)
task_count = metadata.get("task_count", 0)
list_item_count = metadata.get("list_item_count", 0)
heading_count = metadata.get("heading_count", 0)

# Always use .get() with defaults for safety
if metadata.get("word_count", 0) < 50:
    # Short note
```

#### 4. `vault.similarity()` vs `vault.batch_similarity()`

**Use `similarity()` for individual comparisons** (cache-aware):
```python
for candidate in candidates:
    sim = vault.similarity(seed, candidate)  # Benefits from session cache
    if sim > threshold:
        # ...
```

**Use `batch_similarity()` for pairwise matrices** (when you need all N×M):
```python
# Computing full similarity matrix
candidates1 = vault.neighbours(start, k=10)
candidates2 = vault.neighbours(end, k=10)
sim_matrix = vault.batch_similarity(candidates1, candidates2)

for i, mid1 in enumerate(candidates1):
    for j, mid2 in enumerate(candidates2):
        similarity = sim_matrix[i, j]
        # ...
```

**Real example** from `bridge_hunter.py` (3-hop path finding):
```python
# Need full 10×10 matrix - batch is appropriate
sim_matrix = vault.batch_similarity(candidates1, candidates2)
for i, (mid1, sim1) in enumerate(candidates1_with_scores):
    for j, (mid2, sim3) in enumerate(candidates2_with_scores):
        sim2 = sim_matrix[i, j]  # Extract from pre-computed matrix
        total_sim = (sim1 + sim2 + sim3) / 3
```

---

## Performance Optimization Techniques

### Technique 1: Build Lookup Structures Once

From `pattern_finder.py`:

```python
# Build O(1) lookup set once instead of O(N) repeated calls
all_link_pairs = set()
for note in notes:
    for target in vault.outgoing_links(note):
        pair = tuple(sorted([note.path, target.path]))
        all_link_pairs.add(pair)

# Later: O(1) lookup instead of vault.links_between()
for note_a in cluster:
    for note_b in cluster:
        pair = tuple(sorted([note_a.path, note_b.path]))
        if pair in all_link_pairs:
            # Found connection - O(1) lookup
```

**Impact**: Transformed O(N³) algorithm to O(N), gaining 30-50% speedup on 10k vaults.

### Technique 2: Batch Similarity for Matrices

From `bridge_hunter.py`:

```python
# ❌ BAD: 100 individual calls for 10×10 matrix
candidates1 = vault.neighbours(start, k=10)
candidates2 = vault.neighbours(end, k=10)
for mid1 in candidates1:
    for mid2 in candidates2:
        sim = vault.similarity(mid1, mid2)  # 100 calls!

# ✅ GOOD: Single batch call for entire matrix
sim_matrix = vault.batch_similarity(candidates1, candidates2)
for i, mid1 in enumerate(candidates1):
    for j, mid2 in enumerate(candidates2):
        sim = sim_matrix[i, j]  # Extract from pre-computed matrix
```

### Technique 3: Cache Reuse with return_scores

From `hidden_hub.py`:

```python
# Get scores once, use multiple times
neighbors_with_scores = vault.neighbours(note, k=30, return_scores=True)

# Use 1: Count high-similarity neighbors
high_similarity_count = sum(1 for n, sim in neighbors_with_scores if sim > 0.6)

# Use 2: Extract top neighbors
neighbor_notes = [n for n, sim in neighbors_with_scores[:10]]

# Use 3: Filter by threshold
strong_connections = [(n, sim) for n, sim in neighbors_with_scores if sim > 0.7]
```

### Technique 4: Use Sets for Deduplication

From `method_scrambler.py`:

```python
# Combine and deduplicate in one operation
linked_notes = vault.outgoing_links(note)[:3]
similar_notes = vault.neighbours(note, k=5)

# ❌ BAD: Manual deduplication
candidates = linked_notes.copy()
for n in similar_notes:
    if n not in candidates:
        candidates.append(n)

# ✅ GOOD: Set handles deduplication
candidates = list(set(linked_notes + similar_notes))
```

### Technique 5: Early Termination

From `antithesis_generator.py`:

```python
max_suggestions = 5
suggestion_count = 0

for note in vault.sample(notes, min(30, len(notes))):
    if suggestion_count >= max_suggestions:
        break  # Stop early - we have enough

    # ... generate suggestion
    if suggestion_created:
        suggestion_count += 1
```

---

## Edge Case Handling

### Minimum Vault Size Checks

Different operations require different thresholds:

```python
# Basic comparisons - need at least 2 notes
if len(notes) < 3:
    return []

# Graph operations - need connected structure
if len(notes) < 10:
    return []

# Pattern finding - need statistical significance
if len(notes) < 15:
    return []

# Seasonal patterns - need temporal diversity
if len(notes) < 50:
    return []
```

**Observed thresholds**:
- `columbo.py`: 3 notes (basic comparison)
- `concept_cluster.py`: 5 notes (clustering)
- `antithesis_generator.py`: 10 notes (graph operations)
- `pattern_finder.py`: 15 notes (pattern detection)
- `scale_shifter.py`: 20 notes (classification)
- `seasonal_patterns.py`: 50 notes (temporal analysis)

### Session History Checks (Temporal Geists)

All temporal geists use this pattern:

```python
try:
    sessions = _get_session_history(vault, sessions_back=5)
    if len(sessions) < 3:
        return []  # Need multiple sessions for temporal analysis

    # ... temporal operations

except Exception:
    return []  # Graceful degradation when temporal data unavailable
```

**Used by**: `concept_drift`, `hermeneutic_instability`, `session_drift`

### Common Edge Cases Checklist

When writing a geist, handle these cases:

```python
# Empty vault
if len(notes) < minimum_threshold:
    return []

# No links
if len(vault.backlinks(note)) == 0 and len(note.links) == 0:
    # Note is isolated

# No tags
if len(note.tags) == 0:
    # Note has no tags

# Short notes
metadata = vault.metadata(note)
if metadata.get("word_count", 0) < 50:
    # Stub note

# Missing metadata (always use .get() with defaults)
word_count = metadata.get("word_count", 0)
staleness = metadata.get("staleness", 0)

# Temporal data unavailable
try:
    temporal_operation()
except Exception:
    return []

# No quality suggestions found
if not suggestions:
    return []  # Geist abstains
```

---

## Suggestion Construction Patterns

### Pattern 1: "What if..." Questions (Universal)

The most common and reliable pattern:

```python
text = f"What if [[{note.title}]] and [[{other.title}]] were connected?"
text = f"What if you zoomed in on [[{abstract_note.title}]]?"
text = f"What if [[{note.title}]]'s contradictions are revealing something?"
```

### Pattern 2: Structured Markdown

From `dialectic_triad.py`:

```python
text = (
    f"**Thesis**: [[{note.obsidian_link}]]\n"
    f"**Antithesis**: [[{antithesis.title}]]\n"
    f"\nWhat if you synthesized both?"
)
```

From `cluster_mirror.py`:

```python
cluster_descriptions = [f"- {label}" for label in cluster_labels]
text = "\n\n".join(cluster_descriptions) + "\n\nWhat do these clusters remind you of?"
```

### Pattern 3: Title Suggestions

Suggest new note titles for user consideration:

```python
suggestions.append(
    Suggestion(
        text=f"What if [[{note.title}]] had an opposite?",
        notes=[note.title],
        geist_id="antithesis_generator",
        title=f"Anti-{note.title}"  # Suggested new note title
    )
)
```

### Pattern 4: Vault-Level Insights (No Specific Notes)

From `vocabulary_expansion.py`:

```python
Suggestion(
    text="Your recent notes explore less semantic territory than older ones...",
    notes=[],  # No specific notes - vault-level observation
    geist_id="vocabulary_expansion",
)
```

### Pattern 5: Contextual Reasoning

Explain WHY the connection is interesting:

```python
# ❌ BAD: No explanation
text = f"[[{note_a.title}]] and [[{note_b.title}]]"

# ✅ GOOD: Explain the insight
text = (
    f"[[{note_a.title}]] and [[{note_b.title}]] are semantically "
    f"similar (0.87) despite having no links. Same pattern, different scale?"
)
```

### Pattern 6: Temporal Framing

From `session_drift.py`:

```python
text = (
    f"Your understanding of [[{note.title}]] shifted between sessions, "
    f"even though you haven't edited it in {days_unchanged} days. What changed?"
)
```

---

## Content Analysis Techniques

### Technique 1: Remove Code Blocks First

Avoid false positives from code examples:

```python
# From question_harvester.py
content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
content_no_code = re.sub(r'`[^`]+`', '', content_no_code)

# Now extract from prose only
questions = re.findall(r'([^.!?\n][^.!?]*\?)', content_no_code)
```

### Technique 2: Word Lists for Classification

From `scale_shifter.py`:

```python
abstract_words = [
    "theory", "principle", "concept", "framework", "approach",
    "perspective", "model", "paradigm", "methodology", "philosophy"
]

concrete_words = [
    "example", "case", "instance", "story", "specific",
    "particular", "actual", "real", "practice", "implementation"
]

content = vault.read(note).lower()
abstract_score = sum(1 for word in abstract_words if word in content)
concrete_score = sum(1 for word in concrete_words if word in content)

if abstract_score > concrete_score * 2:
    return "abstract"
elif concrete_score > abstract_score * 2:
    return "concrete"
else:
    return "mixed"
```

### Technique 3: Regex with Validation

Two-step process: extract broadly, then validate narrowly.

```python
def extract_questions(content: str) -> list[str]:
    """Extract questions from content."""
    # Step 1: Extract all question-like patterns
    candidates = re.findall(r'([^.!?\n][^.!?]*\?)', content)

    # Step 2: Validate quality
    return [q for q in candidates if is_valid_question(q)]

def is_valid_question(q: str) -> bool:
    """Validate question quality."""
    # Length check
    if not (10 <= len(q) <= 500):
        return False

    # Must contain letters (not just symbols)
    if not re.search(r'[a-zA-Z]', q):
        return False

    # Exclude code-like patterns
    if re.search(r'[{}()\[\]]', q):
        return False

    return True
```

### Technique 4: Structure Classification

From `structure_diversity_checker.py`:

```python
def _classify_structure(vault: "VaultContext", note: Note) -> str:
    """Classify note by writing structure."""
    metadata = vault.metadata(note)
    word_count = max(1, metadata.get("word_count", 1))

    list_density = metadata["list_item_count"] / max(1, word_count / 100)
    task_density = metadata["task_count"] / max(1, word_count / 100)
    heading_count = metadata["heading_count"]

    if task_density > 2:
        return "task-oriented"
    elif list_density > 5:
        return "list-heavy"
    elif heading_count < 2:
        return "prose-heavy"
    else:
        return "mixed"
```

---

## Tracery Geist Patterns

### Standard YAML Structure

```yaml
type: geist-tracery
id: geist_id
description: Human-readable description of what this geist does
count: 3  # Number of suggestions to generate

tracery:
  origin:
    - "Template with #symbols# that expand"
    - "Another template variant for variety"

  symbol_name:
    - "Expansion option 1"
    - "Expansion option 2"
    - "Expansion option 3"

  another_symbol:
    - "$vault.random_note_title()"  # Vault function call
    - "$vault.sample_notes(2)"
```

### The Five Modifiers

From `transformation_suggester.yaml`:

```yaml
# 1. .capitalize - First letter uppercase
"#action.capitalize# you viewed"  # "view" → "View"

# 2. .capitalizeAll - All words capitalized
"#concept.capitalizeAll#"  # "hidden pattern" → "Hidden Pattern"

# 3. .s - Pluralization
"#element.s#"  # "connection" → "connections"

# 4. .ed - Past tense
"#action.ed#"  # "view" → "viewed"

# 5. .a - Article (a/an)
"#metaphor.a#"  # "organism" → "an organism", "garden" → "a garden"
```

### Chaining Modifiers

```yaml
"#pattern.s.capitalize#"  # "assumption" → "Assumptions"
"#action.ed.capitalize#"  # "view" → "Viewed"
```

### Vault Function Integration

Three function call types:

```yaml
# 1. Simple note selection
note:
  - "$vault.random_note_title()"
  - "$vault.sample_notes(2)"

# 2. Graph queries
hub:
  - "$vault.hubs(2)"
orphan:
  - "$vault.orphans(1)"

# 3. Context-sensitive (references other symbols)
seed:
  - "$vault.sample_notes(2)"
neighbours:
  - "$vault.neighbours(#seed#, 3)"  # Uses seed from above
```

### Template Variation

From `contradictor.yaml` (20 variants for variety):

```yaml
origin:
  - "[[#note#]] exists. But what about the opposite?"
  - "You wrote [[#note#]]. What would the opposite look like?"
  - "[[#note#]] - have you considered the inverse perspective?"
  - "What contradicts [[#note#]]?"
  - "If [[#note#]] is true, what would be false?"
  - "[[#note#]] takes a stance. What's the counter-stance?"
  # ... 14 more variants
```

**Why multiple variants**: Prevents repetitive phrasing across sessions with same seed.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Fixed Sample Sizes

```python
# ❌ BAD: Breaks on small vaults, insufficient on large vaults
for note in notes[:500]:
    # ...

# ✅ GOOD: Adaptive sampling
for note in vault.sample(notes, min(500, len(notes))):
    # ...
```

### Anti-Pattern 2: Repeated Similarity Computation

```python
# ❌ BAD: Recomputes same similarity multiple times
similar = vault.neighbours(seed, k=10)
for note in similar:
    sim = vault.similarity(seed, note)  # Recomputed!
    if sim > 0.6:
        later_sim = vault.similarity(seed, note)  # Recomputed again!

# ✅ GOOD: Compute once with scores
similar_with_scores = vault.neighbours(seed, k=10, return_scores=True)
for note, sim in similar_with_scores:
    if sim > 0.6:
        # Reuse cached sim
```

### Anti-Pattern 3: No Quality Validation

```python
# ❌ BAD: Return all regex matches
questions = re.findall(pattern, content)
return [Suggestion(text=q, ...) for q in questions]

# ✅ GOOD: Validate quality first
questions = re.findall(pattern, content)
valid = [q for q in questions if is_valid_question(q)]
return [Suggestion(text=q, ...) for q in valid]
```

### Anti-Pattern 4: Ignoring Edge Cases

```python
# ❌ BAD: Crashes on empty vault
note = vault.sample(notes, k=1)[0]  # IndexError if notes is empty!

# ✅ GOOD: Early validation
if len(notes) < 1:
    return []
note = vault.sample(notes, k=1)[0]
```

### Anti-Pattern 5: Using batch_similarity When Cache is Warm

```python
# ❌ BAD: Bypasses session cache
candidates = vault.neighbours(note, k=10)
similarities = vault.batch_similarity([note], candidates)

# ✅ GOOD: Benefits from cache (if other geists computed these)
candidates_with_scores = vault.neighbours(note, k=10, return_scores=True)
for candidate, sim in candidates_with_scores:
    # Cache hit if another geist already computed this
```

**Context**: See Lesson #6 and `docs/POST_MORTEM_PHASE3B.md` for detailed analysis.

### Anti-Pattern 6: Hardcoded Thresholds Without Adaptation

```python
# ❌ BAD: Always sample 100 notes, regardless of vault size
for note in vault.sample(notes, k=100):  # Breaks on 50-note vault!

# ✅ GOOD: Adapt to vault size
sample_size = min(100, len(notes))
for note in vault.sample(notes, k=sample_size):
```

---

## Advanced Techniques

### Technique 1: Path Finding (from `bridge_hunter.py`)

Greedy best-first search for semantic bridges:

```python
def _find_semantic_path(
    vault: "VaultContext",
    start: Note,
    end: Note,
    max_hops: int = 3
) -> list[Note] | None:
    """Find semantic path from start to end note."""

    # 2-hop path: start -> intermediate -> end
    # Get candidates from start
    candidates1_with_scores = vault.neighbours(start, k=10, return_scores=True)
    candidates1 = [c for c, _ in candidates1_with_scores]

    # Batch compute all intermediate->end similarities
    sim_matrix = vault.batch_similarity(candidates1, [end])

    # Find best intermediate based on avg(start->mid, mid->end)
    best_path = None
    best_score = 0.0

    for i, (mid, sim_start_mid) in enumerate(candidates1_with_scores):
        sim_mid_end = sim_matrix[i, 0]
        avg_sim = (sim_start_mid + sim_mid_end) / 2

        if avg_sim > best_score:
            best_score = avg_sim
            best_path = [start, mid, end]

    return best_path if best_score > 0.5 else None
```

### Technique 2: Density Inversion (from `density_inversion.py`)

Compare graph density vs semantic density:

```python
def _analyze_density_mismatch(vault: "VaultContext", note: Note) -> dict[str, Any]:
    """Detect mismatch between link density and semantic density."""

    neighbors = vault.neighbours(note, k=10)
    if len(neighbors) < 3:
        return {}

    # Graph density: actual links / possible links
    edges = 0
    for n1 in neighbors:
        for n2 in neighbors:
            if vault.links_between(n1, n2):
                edges += 1

    max_edges = len(neighbors) * (len(neighbors) - 1) / 2
    graph_density = edges / max_edges if max_edges > 0 else 0.0

    # Semantic density: average pairwise similarity
    sim_matrix = vault.batch_similarity(neighbors, neighbors)
    semantic_density = np.mean(sim_matrix)

    # Detect mismatches
    if graph_density > 0.6 and semantic_density < 0.3:
        return {"type": "over-linked", "graph": graph_density, "semantic": semantic_density}
    elif graph_density < 0.2 and semantic_density > 0.7:
        return {"type": "under-linked", "graph": graph_density, "semantic": semantic_density}

    return {}
```

### Technique 3: Temporal Period Division (from `temporal_mirror.py`)

Divide vault history into equal periods:

```python
def _divide_into_periods(notes: list[Note], num_periods: int = 10) -> list[list[Note]]:
    """Divide notes into N temporal periods."""

    sorted_notes = sorted(notes, key=lambda n: n.created)
    period_size = max(1, len(sorted_notes) // num_periods)

    periods = []
    for i in range(num_periods):
        start_idx = i * period_size
        end_idx = (i + 1) * period_size if i < num_periods - 1 else len(sorted_notes)
        periods.append(sorted_notes[start_idx:end_idx])

    return [p for p in periods if len(p) > 0]
```

### Technique 4: Cluster Labeling (from `cluster_mirror.py`)

Use c-TF-IDF for automatic cluster labeling:

```python
def _get_labeled_clusters(vault: "VaultContext") -> dict[int, dict[str, Any]]:
    """Get clusters with automatic descriptive labels."""

    clusters = vault.get_clusters(min_size=5)
    labeled_clusters = {}

    for cluster_id, cluster in clusters.items():
        # Get auto-generated label from c-TF-IDF
        label = cluster["formatted_label"]

        # Get representative notes
        representatives = vault.get_cluster_representatives(cluster_id, k=3)

        labeled_clusters[cluster_id] = {
            "label": label,
            "representatives": representatives,
            "size": len(cluster["notes"]),
        }

    return labeled_clusters
```

---

## Testing and Validation

### Development Workflow

```bash
# 1. Test on small vault first
uv run geistfabrik test my_geist testdata/kepano-obsidian-main/

# 2. Test with specific date for reproducibility
uv run geistfabrik test my_geist testdata/kepano-obsidian-main/ --date 2025-01-15

# 3. Test on larger vault with higher timeout
uv run geistfabrik test my_geist /path/to/1000-note-vault --timeout 30

# 4. Test all geists to ensure no regressions
uv run geistfabrik test-all testdata/kepano-obsidian-main/
```

### Validation Checklist

Before committing your geist, verify:

**Functionality**:
- [ ] Returns `list[Suggestion]` type
- [ ] Handles empty vault (`len(notes) < threshold`)
- [ ] Handles small vaults (2-5 notes)
- [ ] Handles missing metadata (uses `.get()` with defaults)
- [ ] Returns empty list on errors (never crashes)
- [ ] Suggestions use "What if..." or question framing

**Performance**:
- [ ] Completes in <5s on 500-note vault
- [ ] Completes in <30s on 1000-note vault (if available)
- [ ] Uses `similarity()` not `batch_similarity()` when cache might be warm
- [ ] Builds lookup structures for O(1) repeated searches
- [ ] Uses adaptive sampling, not fixed sizes
- [ ] Early terminates when enough suggestions found

**Code Quality**:
- [ ] Uses TYPE_CHECKING guard for imports
- [ ] Imports Suggestion at runtime only
- [ ] Includes clear docstring
- [ ] Has descriptive variable names
- [ ] Validates extracted content before returning
- [ ] Final sampling limits output to 2-3 suggestions

**Testing**:
- [ ] Tested on `testdata/kepano-obsidian-main/`
- [ ] Tested with `--date` flag for reproducibility
- [ ] Verified deterministic (same date = same output)
- [ ] Checked suggestions are provocative, not prescriptive

---

## Performance Targets

From production experience:

- **Small vaults (10-100 notes)**: <1 second
- **Medium vaults (100-500 notes)**: <5 seconds
- **Large vaults (500-1000 notes)**: <10 seconds
- **Very large vaults (1000-10000 notes)**: <30 seconds

**If your geist exceeds these targets**:

1. Profile with `cProfile` to find bottleneck
2. Check for O(N²) or O(N³) operations
3. Consider adaptive sampling
4. Build lookup structures for repeated searches
5. Use batch operations for matrices only
6. Leverage session cache with individual `similarity()` calls

**Remember**: Quality > Speed. A 10-second geist that generates great suggestions beats a 2-second geist that generates mediocre ones.

---

## Resources

### Exemplary Geists to Study

**Best implementation patterns**:
- `pattern_finder.py` - Set-based lookups, quality gates
- `bridge_hunter.py` - Batch similarity for matrices
- `question_harvester.py` - Content extraction with validation
- `scale_shifter.py` - Word list classification
- `seasonal_patterns.py` - Temporal analysis patterns

**Best Tracery patterns**:
- `transformation_suggester.yaml` - Modifier chaining mastery
- `contradictor.yaml` - Template variation (20 variants)
- `hub_explorer.yaml` - Vault function integration

### Documentation

- `WRITING_GOOD_GEISTS.md` - Philosophy and performance guidance
- `POST_MORTEM_PHASE3B.md` - Optimization lessons learned
- `tests/integration/test_phase3b_regression.py` - Anti-regression tests
- `specs/geistfabrik_spec.md` - Complete technical specification

### Helper Functions

```python
# Get recent session history
def _get_session_history(vault: "VaultContext", sessions_back: int = 5) -> list[int]:
    cursor = vault.db.execute(
        "SELECT session_id FROM sessions ORDER BY session_date DESC LIMIT ?",
        (sessions_back,)
    )
    return [row[0] for row in cursor.fetchall()]

# Classify note structure
def _classify_structure(vault: "VaultContext", note: Note) -> str:
    metadata = vault.metadata(note)
    # ... see Content Analysis Techniques section

# Validate question quality
def is_valid_question(q: str) -> bool:
    return (
        10 <= len(q) <= 500 and
        re.search(r'[a-zA-Z]', q) and
        not re.search(r'[{}()\[\]]', q)
    )
```

---

## Quick Reference

### Common Patterns

```python
# Sample notes before analysis
for note in vault.sample(notes, min(30, len(notes))):
    # ...

# Get neighbors with scores
neighbours = vault.neighbours(note, k=10, return_scores=True)

# Build link lookup set
link_pairs = set()
for note in notes:
    for target in vault.outgoing_links(note):
        pair = tuple(sorted([note.path, target.path]))
        link_pairs.add(pair)

# Early validation
if len(notes) < threshold:
    return []

# Graceful error handling
try:
    # Optional feature
except Exception:
    return []

# Quality validation
suggestions = [s for s in candidates if is_valid(s)]

# Final sampling
return vault.sample(suggestions, k=3)
```

---

## Final Wisdom

These patterns and lessons represent production-tested code from 49 geists running on real vaults with 10-10,000 notes. They've been refined through:

- **Phase 3B rollback**: Learning that optimization without profiling reduces quality
- **Session cache architecture**: Understanding when to use batch vs individual operations
- **Timeout handling**: Balancing performance with suggestion quality
- **Edge case discovery**: Handling empty vaults, missing data, temporal operations

**Key principle**: Write correct code first, optimize only when profiling reveals bottlenecks.

**Remember the 10 Essential Lessons**:

1. Sample before analyze
2. Cache before reuse
3. Build sets, not loops
4. Validate before return
5. Abstain when uncertain
6. Respect session cache
7. Match threshold to complexity
8. Never crash
9. Explain the insight
10. Profile before optimize

Happy geist writing!
