# Writing Good Geists: A Complete Guide

**Purpose**: This guide helps you write geists that embody GeistFabrik's philosophy of "muses, not oracles" with practical implementation patterns learned from production use.

---

## Part 1: Philosophy & Craft

> "GeistFabrik is not an answer machine—it's a **question factory**."

### Core Principles

Your geist should:
- ✅ **Ask questions**, not give answers
- ✅ **Provoke**, not prescribe
- ✅ **Surprise**, not predict
- ✅ **Diverge**, not converge
- ✅ Ask **different questions** than users would ask themselves

---

## The Golden Rules

### Rule 1: Questions, Not Commands

**❌ Bad** (prescriptive):
```python
"You should expand [[{note}]]. It's underdeveloped."
"Consider linking [[{note_a}]] to [[{note_b}]]."
"This note needs more connections."
```

**✅ Good** (provocative):
```python
"What if [[{note}]]'s brevity is intentional—a hinge concept that gains power from compression?"
"What if [[{note_a}]] and [[{note_b}]] were connected? What would emerge?"
"[[{note}]] has few links. Self-contained island or overlooked hub?"
```

**Key difference**: Good geists raise possibilities; bad geists give instructions.

---

### Rule 2: Speculative, Not Certain

**❌ Bad** (judgmental):
```python
"[[{note}]] is wrong."
"This connection doesn't make sense."
"You've made an error in [[{note}]]."
```

**✅ Good** (speculative):
```python
"What if [[{note}]] is only half the story?"
"[[{note_a}]] and [[{note_b}]] seem to contradict each other—what gives?"
"I think you're lying about your claim in [[{note}]]..." (playful provocation)
```

**Key words**: Use "might", "could", "what if", "perhaps" - never "must", "should", "needs to".

---

### Rule 3: Vault-Specific, Not Generic

**❌ Bad** (could apply to any vault):
```python
f"Why is {title}?"  # Generic question anyone would ask
f"How does {title} work?"  # Too obvious
"What if you thought about creativity?"  # Not grounded in vault
```

**✅ Good** (uses actual vault relationships):
```python
"[[{note_a}]] and [[{note_b}]] are semantically similar (0.87) despite no links. Same pattern, different scale?"
"[[{note}]] has been interpreted differently across your last 5 sessions—meaning unsettled?"
"Your Q2 notes cluster around [[Flow]], but Q4 notes cluster around [[Structure]]. Different seasons?"
```

**Key difference**: Reference specific notes, relationships, and patterns in the user's actual vault.

---

### Rule 4: Multiple Interpretations

**❌ Bad** (only one answer):
```python
"[[{note}]] is too short. You should expand it."  # One obvious action
```

**✅ Good** (many possible responses):
```python
"[[{note}]] has only 47 words but 8 backlinks. What if its brevity is intentional? Or is it waiting to emerge?"
# Could interpret as: 1) intentionally minimal, 2) needs expansion, 3) serves as connector, etc.
```

**Key difference**: Good questions open up thinking; bad questions narrow it down.

---

## Writing Patterns That Work

### Pattern 1: "What if" Questions
The most reliable pattern for provocative suggestions.

```python
"What if [[{note_a}]] and [[{note_b}]] were connected?"
"What if you zoomed in on [[{abstract_note}]]?"
"What if [[{note}]]'s contradictions are actually revealing something?"
```

### Pattern 2: Contrasting Observations
Point out patterns and let users interpret them.

```python
"[[{note}]] has high link density (0.15), while [[{other}]] has low density (0.02).
Connector vs. island?"
```

### Pattern 3: Temporal Awareness
Track changes over time without prescribing action.

```python
"Your understanding of [[{note}]] shifted between sessions,
even though you haven't edited it in 127 days. What changed?"
```

### Pattern 4: Provocative Framing
Use playful or challenging framing to spark engagement.

```python
"I think you're lying about your claim in [[{note}]] because..." (Columbo-style)
"What would the opposite of [[{note}]] look like?"
"Who would disagree with [[{note}]]?"
```

### Pattern 5: Either/Or Questions
Offer contrasting interpretations.

```python
"[[{note}]] is brief but referenced often. Hinge concept or placeholder?"
"Current preoccupation or emerging theme?"
"Deep focus or narrowing perspective?"
```

---

## Philosophical Anti-Patterns

### Anti-Pattern 1: The Todo List
```python
# ❌ Don't turn geists into task managers
"You should expand [[{note}]]."
"Consider adding more links."
"This needs revision."
```

**Fix**: Ask what the current state reveals, don't prescribe changes.

---

### Anti-Pattern 2: The Linter
```python
# ❌ Don't give code-review style feedback
"[[{note}]] has too many links. Consider focusing on key connections."
"This note is too short for its importance."
"Poor link density detected."
```

**Fix**: Describe patterns and ask what they mean, don't judge them.

---

### Anti-Pattern 3: The Generic Template
```python
# ❌ Don't ask questions anyone would ask
f"Why is {title}?"  # Too obvious
f"How does {title} work?"  # Too generic
f"What is {title} about?"  # Not provocative
```

**Fix**: Use vault relationships to generate unexpected questions.

---

### Anti-Pattern 4: The Instruction Manual
```python
# ❌ Don't explain or educate
"Questions invite exploration where statements invite acceptance."
"Linking notes helps create connections."
"Writing regularly improves thinking."
```

**Fix**: Show, don't tell. Let the suggestion itself embody the principle.

---

## The "Would You Ask This Yourself?" Test

Before finalizing a geist, ask:

1. **Would I naturally think to ask this question?**
   - If yes → too generic, make it more specific/unexpected
   - If no → good, it's divergent

2. **Does this tell me what to do, or make me think?**
   - If "what to do" → too prescriptive, reframe as question
   - If "make me think" → good, it's provocative

3. **Could this apply to any vault, or is it specific to mine?**
   - If "any vault" → add specific note references
   - If "specific" → good, it's grounded

4. **Does this have one obvious answer, or multiple interpretations?**
   - If "one answer" → open it up with alternatives
   - If "multiple" → good, it's divergent

---

## Gold Standard Examples

Study these geists for excellent patterns:

### Columbo (Provocative Challenger)
```python
"I think you're lying about your claim in [[{note.title}]]
because [[{other.title}]] argues something that seems to contradict it"
```
**Why it's gold**: Playful, specific, catches user in contradictions they wouldn't notice.

---

### Session Drift (Metacognitive Mirror)
```python
"Your understanding of [[{note}]] shifted significantly between sessions.
What changed in how you're reading it?"
```
**Why it's gold**: Questions interpretation, not content. Reveals temporal evolution.

---

### Scale Shifter (Perspective Transformer)
```python
"[[{note}]] operates at high abstraction. What if you zoomed in?
[[{example}]] might be a more concrete instance."
```
**Why it's gold**: Suggests perspective shift, uses "might", connects specific notes.

---

### Assumption Challenger (Socratic Questioner)
```python
"[[{note}]] makes claims that seem certain,
but [[{other}]] expresses uncertainty.
What assumptions underlie the certainty?"
```
**Why it's gold**: Points out pattern, asks "what" not "you should".

---

## Language Reference

### ✅ Use These
- "What if..."
- "might", "could", "perhaps"
- "seems", "appears"
- "?" (questions)
- "or" (alternatives)
- Specific note titles: [[{note}]]
- Concrete numbers: "5 links", "127 days"

### ❌ Avoid These
- "you should", "consider"
- "must", "need to", "have to"
- "too much", "not enough"
- "worth", "important", "critical"
- "." (declarative statements)
- Generic abstractions: "creativity", "learning"
- Commands: "expand", "link", "revise"

---

## Examples: Before & After

### Example 1: Stub Expander

**❌ Before** (prescriptive):
```python
"What if you expanded [[{note}]]? It's only {words} words but has {links} connections.
This stub might be worth developing."
```

**✅ After** (provocative):
```python
"[[{note}]] has only {words} words but {links} notes reference it.
What if its brevity is intentional—a hinge gaining power from compression?
Or is it a placeholder waiting to emerge?"
```

---

### Example 2: Link Density

**❌ Before** (linter-style):
```python
"[[{note}]] has too many links ({count} in {words} words).
Consider focusing on key connections."
```

**✅ After** (observational):
```python
"[[{note}]] has high link density ({density:.2f} per 100 words).
Is this a rhizome concept spreading through your vault?
Or is the density obscuring which connections actually matter?"
```

---

### Example 3: Question Generator

**❌ Before** (generic template):
```python
f"What if you reframed [[{title}]] as a question: 'Why is {title}?'"
```

**✅ After** (vault-specific):
```python
"[[{question_note}]] has been sitting as a question for {days} days.
What if [[{similar[0]}]], [[{similar[1]}]], and [[{similar[2]}]]
are actually partial answers you already have?"
```

---

## Part 2: Implementation Patterns

This section covers technical implementation patterns learned from production geists.

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

---

## The 10 Essential Lessons

These lessons represent distilled wisdom from production geists:

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

### 10. **Profile Before Optimise**
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

Three distinct approaches observed:

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

---

## VaultContext API Patterns

### 1. `vault.sample(items, k)` - Universal Randomization

Used universally for deterministic sampling.

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

### 2. `vault.neighbours(note, k, return_scores=True)` - Semantic Similarity

Critical optimisation: Use `return_scores=True` to avoid recomputation.

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

### 3. `vault.metadata(note)` - Computed Properties

Access rich metadata without reading file content.

```python
metadata = vault.metadata(note)

# Available properties
word_count = metadata.get("word_count", 0)
lexical_diversity = metadata.get("lexical_diversity", 0.0)
staleness = metadata.get("staleness", 0)
days_since_modified = metadata.get("days_since_modified", 0)
task_count = metadata.get("task_count", 0)

# Always use .get() with defaults for safety
if metadata.get("word_count", 0) < 50:
    # Short note
```

### 4. `vault.similarity()` vs `vault.batch_similarity()`

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

---

## Performance Optimisation Techniques

### Technique 1: Build Lookup Structures Once

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

### Technique 2: Cache Reuse with return_scores

```python
# Get scores once, use multiple times
neighbors_with_scores = vault.neighbours(note, k=30, return_scores=True)

# Use 1: Count high-similarity neighbours
high_similarity_count = sum(1 for n, sim in neighbors_with_scores if sim > 0.6)

# Use 2: Extract top neighbours
neighbor_notes = [n for n, sim in neighbors_with_scores[:10]]

# Use 3: Filter by threshold
strong_connections = [(n, sim) for n, sim in neighbors_with_scores if sim > 0.7]
```

### Technique 3: Use Sets for Deduplication

```python
# Combine and deduplicate in one operation
linked_notes = vault.outgoing_links(note)[:3]
similar_notes = vault.neighbours(note, k=5)
candidates = list(set(linked_notes + similar_notes))
```

### Technique 4: Early Termination

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

### Session History Checks (Temporal Geists)

```python
try:
    sessions = _get_session_history(vault, sessions_back=5)
    if len(sessions) < 3:
        return []  # Need multiple sessions for temporal analysis

    # ... temporal operations

except Exception:
    return []  # Graceful degradation when temporal data unavailable
```

### Common Edge Cases Checklist

```python
# Empty vault
if len(notes) < minimum_threshold:
    return []

# No links
if len(vault.backlinks(note)) == 0 and len(note.links) == 0:
    # Note is isolated

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

```python
text = f"What if [[{note.title}]] and [[{other.title}]] were connected?"
text = f"What if you zoomed in on [[{abstract_note.title}]]?"
text = f"What if [[{note.title}]]'s contradictions are revealing something?"
```

### Pattern 2: Structured Markdown

```python
text = (
    f"**Thesis**: [[{note.obsidian_link}]]\n"
    f"**Antithesis**: [[{antithesis.title}]]\n"
    f"\nWhat if you synthesized both?"
)
```

### Pattern 3: Title Suggestions

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

### Pattern 4: Vault-Level Insights

```python
Suggestion(
    text="Your recent notes explore less semantic territory than older ones...",
    notes=[],  # No specific notes - vault-level observation
    geist_id="vocabulary_expansion",
)
```

### Pattern 5: Contextual Reasoning

```python
# Explain WHY the connection is interesting
text = (
    f"[[{note_a.title}]] and [[{note_b.title}]] are semantically "
    f"similar (0.87) despite having no links. Same pattern, different scale?"
)
```

---

## Content Analysis Techniques

### Technique 1: Remove Code Blocks First

```python
# Avoid false positives from code examples
content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
content_no_code = re.sub(r'`[^`]+`', '', content_no_code)

# Now extract from prose only
questions = re.findall(r'([^.!?\n][^.!?]*\?)', content_no_code)
```

### Technique 2: Word Lists for Classification

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
```

### Technique 3: Regex with Validation

```python
def extract_questions(content: str) -> list[str]:
    """Extract questions from content."""
    # Step 1: Extract all question-like patterns
    candidates = re.findall(r'([^.!?\n][^.!?]*\?)', content)

    # Step 2: Validate quality
    return [q for q in candidates if is_valid_question(q)]

def is_valid_question(q: str) -> bool:
    """Validate question quality."""
    return (
        10 <= len(q) <= 500 and
        re.search(r'[a-zA-Z]', q) and
        not re.search(r'[{}()\[\]]', q)
    )
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

  another_symbol:
    - "$vault.random_note_title()"  # Vault function call
```

### The Five Modifiers

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
"#metaphor.a#"  # "organism" → "an organism"
```

### Chaining Modifiers

```yaml
"#pattern.s.capitalize#"  # "assumption" → "Assumptions"
```

### Vault Function Integration

```yaml
# Simple note selection
note:
  - "$vault.random_note_title()"
  - "$vault.sample_notes(2)"

# Graph queries
hub:
  - "$vault.hubs(2)"
orphan:
  - "$vault.orphans(1)"

# Context-sensitive (references other symbols)
seed:
  - "$vault.sample_notes(2)"
neighbours:
  - "$vault.neighbours(#seed#, 3)"
```

### Template Variation

Multiple variants prevent repetitive phrasing:

```yaml
origin:
  - "[[#note#]] exists. But what about the opposite?"
  - "You wrote [[#note#]]. What would the opposite look like?"
  - "[[#note#]] - have you considered the inverse perspective?"
  - "What contradicts [[#note#]]?"
  # ... more variants
```

---

## Implementation Anti-Patterns

### Anti-Pattern 1: Fixed Sample Sizes

```python
# ❌ BAD: Breaks on small vaults
for note in notes[:500]:
    # ...

# ✅ GOOD: Adaptive sampling
for note in vault.sample(notes, min(500, len(notes))):
    # ...
```

### Anti-Pattern 2: Repeated Similarity Computation

```python
# ❌ BAD: Recomputes same similarity
similar = vault.neighbours(seed, k=10)
for note in similar:
    sim = vault.similarity(seed, note)  # Recomputed!

# ✅ GOOD: Compute once with scores
similar_with_scores = vault.neighbours(seed, k=10, return_scores=True)
for note, sim in similar_with_scores:
    # Reuse cached sim
```

### Anti-Pattern 3: No Quality Validation

```python
# ❌ BAD: Return all matches
questions = re.findall(pattern, content)
return [Suggestion(text=q, ...) for q in questions]

# ✅ GOOD: Validate quality
questions = re.findall(pattern, content)
valid = [q for q in questions if is_valid_question(q)]
return [Suggestion(text=q, ...) for q in valid]
```

### Anti-Pattern 4: Ignoring Edge Cases

```python
# ❌ BAD: Crashes on empty vault
note = vault.sample(notes, k=1)[0]  # IndexError!

# ✅ GOOD: Early validation
if len(notes) < 1:
    return []
note = vault.sample(notes, k=1)[0]
```

### Anti-Pattern 5: Using batch_similarity When Cache is Warm

```python
# ❌ BAD: Bypasses session cache
similarities = vault.batch_similarity([note], candidates)

# ✅ GOOD: Benefits from cache
for candidate in candidates:
    sim = vault.similarity(note, candidate)
```

---

## Performance Guidance

Geists run within a 30-second timeout (default) and must complete efficiently.

### Understanding the Timeout

**Default timeout**: 30 seconds per geist
- Configurable via `--timeout` flag during testing/development
- After 3 consecutive timeouts, geist is automatically disabled
- Timeout logged with test command for reproduction

**What happens on timeout**:
```
⚠ scale_shifter timed out (30.0s)
→ Test: geistfabrik test scale_shifter /path/to/vault --date YYYY-MM-DD
```

### Phase 3B Lessons Learned

**Three key lessons from the Phase 3B rollback** (see `docs/POST_MORTEM_PHASE3B.md`):

1. **Profile first, optimise second**
   - Sampling introduced to "improve performance" without profiling
   - Reality: Phrase extraction was the bottleneck, not corpus iteration
   - Lesson: Measure before optimising; intuition misleads

2. **Respect the session cache**
   - `batch_similarity()` bypassed session-scoped similarity cache
   - Other geists had already computed those similarities
   - Lesson: Individual `similarity()` calls > batch calls when cache is warm

3. **Quality > Speed**
   - pattern_finder sampling saved ~20s but lost 95% pattern coverage
   - Suggestions quality dropped, users got worse experience
   - Lesson: A slightly slower geist that works > fast geist that doesn't

### Development Workflow

1. **Start with correctness**
   ```bash
   uv run geistfabrik test my_geist testdata/kepano-obsidian-main/
   ```

2. **Test on large vaults**
   ```bash
   uv run geistfabrik test my_geist /path/to/1000-note-vault --timeout 30
   ```

3. **Profile if needed**
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

4. **Optimise bottlenecks only**
   - Don't optimise until you've identified the actual bottleneck
   - Focus on algorithmic improvements (O(N³) → O(N))

### When NOT to Optimise

**Don't optimise if**:
- Your geist completes in <2 seconds on 1000-note vaults
- You haven't profiled to find the bottleneck
- Optimisation would reduce suggestion quality
- The geist only runs on small sample sizes anyway

**Remember**: GeistFabrik's filtering pipeline runs AFTER your geist. Quality matters more than speed.

---

## Testing and Validation

### Development Workflow

```bash
# 1. Test on small vault first
uv run geistfabrik test my_geist testdata/kepano-obsidian-main/

# 2. Test with specific date for reproducibility
uv run geistfabrik test my_geist testdata/kepano-obsidian-main/ --date 2025-01-15

# 3. Test on larger vault
uv run geistfabrik test my_geist /path/to/1000-note-vault --timeout 30

# 4. Test all geists to ensure no regressions
uv run geistfabrik test-all testdata/kepano-obsidian-main/
```

### Complete Checklist

Before committing your geist, verify:

**Philosophy**:
- [ ] Uses "what if" or question framing (not directives)
- [ ] Employs speculative language: "might", "could", "perhaps"
- [ ] References specific vault notes (not abstract concepts)
- [ ] Asks questions with multiple possible interpretations
- [ ] Provokes thinking rather than prescribing action
- [ ] Would surprise the user (not obvious questions)
- [ ] No directive verbs: "should", "consider", "must"
- [ ] No value judgments: "too many", "not enough", "wrong"
- [ ] Tone is playful or curious (not authoritative)

**Functionality**:
- [ ] Returns `list[Suggestion]` type
- [ ] Handles empty vault (`len(notes) < threshold`)
- [ ] Handles small vaults (2-5 notes)
- [ ] Handles missing metadata (uses `.get()` with defaults)
- [ ] Returns empty list on errors (never crashes)

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

## Advanced Techniques

### Technique 1: Path Finding

Greedy best-first search for semantic bridges:

```python
def _find_semantic_path(vault, start, end, max_hops=3):
    """Find semantic path from start to end note."""
    # Get candidates from start
    candidates1_with_scores = vault.neighbours(start, k=10, return_scores=True)
    candidates1 = [c for c, _ in candidates1_with_scores]

    # Batch compute all intermediate->end similarities
    sim_matrix = vault.batch_similarity(candidates1, [end])

    # Find best intermediate
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

### Technique 2: Density Inversion

Compare graph density vs semantic density:

```python
def _analyze_density_mismatch(vault, note):
    """Detect mismatch between link density and semantic density."""
    neighbours = vault.neighbours(note, k=10)

    # Graph density: actual links / possible links
    edges = sum(1 for n1 in neighbours for n2 in neighbours
                if vault.links_between(n1, n2))
    max_edges = len(neighbours) * (len(neighbours) - 1) / 2
    graph_density = edges / max_edges if max_edges > 0 else 0.0

    # Semantic density: average similarity
    sim_matrix = vault.batch_similarity(neighbours, neighbours)
    semantic_density = np.mean(sim_matrix)

    # Detect mismatches
    if graph_density > 0.6 and semantic_density < 0.3:
        return "over-linked"
    elif graph_density < 0.2 and semantic_density > 0.7:
        return "under-linked"
```

### Technique 3: Temporal Period Division

```python
def _divide_into_periods(notes, num_periods=10):
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

---

## Reuse Abstractions (GeistFabrik 0.9+)

**New in v0.9**: GeistFabrik now provides 6 core abstraction modules that eliminate 70% of boilerplate code and enable rapid geist development through composition.

### Overview

Instead of manually implementing recurring patterns (similarity thresholds, temporal analysis, content extraction), use the provided abstractions:

1. **`similarity_analysis`** - Named thresholds and declarative filtering
2. **`content_extraction`** - Generalizable extraction pipeline
3. **`temporal_analysis`** - Embedding trajectory and drift patterns
4. **`cluster_labeling`** - Shared labeling with MMR
5. **`clustering_analysis`** - Session-scoped clustering
6. **`graph_analysis`** - Unified graph pattern detection

**Metadata extensions**:
- **`TemporalSemanticQuery`** (in `temporal_analysis`) - Fuse time + semantics
- **`MetadataAnalyser`** (in `metadata_system`) - Statistical metadata operations

### Abstraction 1: Similarity Analysis

**Before** (manual threshold handling):
```python
def suggest(vault):
    for note_a in notes:
        for note_b in notes:
            sim = vault.similarity(note_a, note_b)
            if sim >= 0.65 and sim < 0.80:  # Magic numbers!
                # ... bridge detection logic ...
```

**After** (named thresholds):
```python
from geistfabrik.similarity_analysis import SimilarityLevel, SimilarityFilter

def suggest(vault):
    filter = SimilarityFilter(vault)
    # Find notes similar to topic anchors
    candidates = filter.filter_similar_to_all(
        anchors=[topic_a, topic_b],
        candidates=vault.notes(),
        threshold=SimilarityLevel.HIGH  # Clear, semantic naming!
    )
```

**Available Classes**:
- `SimilarityLevel`: Named constants (VERY_HIGH=0.80, HIGH=0.65, MODERATE=0.50, etc.)
- `SimilarityProfile`: Analyze note's similarity distribution (hub detection, percentiles)
- `SimilarityFilter`: Declarative operations (filter_similar_to_any, filter_dissimilar_to_all)

### Abstraction 2: Content Extraction

**Before** (bespoke extraction logic):
```python
def suggest(vault):
    # 80 lines of regex patterns, validation, deduplication...
    questions = []
    for pattern in patterns:
        matches = re.findall(pattern, content)
        # ... validation ...
        # ... deduplication ...
```

**After** (reusable pipeline):
```python
from geistfabrik.content_extraction import (
    ExtractionPipeline,
    DefinitionExtractor,
    LengthFilter,
    AlphaFilter
)

def suggest(vault):
    pipeline = ExtractionPipeline(
        strategies=[DefinitionExtractor()],
        filters=[LengthFilter(min_len=15, max_len=300), AlphaFilter()]
    )
    definitions = pipeline.extract(note.content)
```

**Built-in Extractors**:
- `QuestionExtractor` - Sentence and list questions
- `DefinitionExtractor` - "X is Y", "X: Y", "X means Y" patterns
- `ClaimExtractor` - Assertive statements ("shows", "proves", "demonstrates")
- `HypothesisExtractor` - If/then, may/might, conditionals

**Example Geist**: See `definition_harvester.py` for full example (~75 lines → ~25 lines)

### Abstraction 3: Temporal Analysis

**Before** (manual session queries):
```python
def suggest(vault):
    # Get session history (8 lines)
    cursor = vault.db.execute("SELECT session_id, session_date FROM sessions...")
    sessions = cursor.fetchall()

    # For each note (40+ lines)
    for note in notes:
        trajectory = []
        for session_id, session_date in sessions:
            cursor = vault.db.execute(
                "SELECT embedding FROM session_embeddings WHERE..."
            )
            # ... manual drift computation ...
```

**After** (trajectory calculator):
```python
from geistfabrik.temporal_analysis import (
    EmbeddingTrajectoryCalculator,
    TemporalPatternFinder
)

def suggest(vault):
    finder = TemporalPatternFinder(vault)
    drifting = finder.find_high_drift_notes(vault.notes(), min_drift=0.2)

    for note, drift_vector in drifting:
        calc = EmbeddingTrajectoryCalculator(vault, note)
        if calc.is_accelerating(threshold=0.1):
            # Found accelerating drift!
```

**Available Classes**:
- `EmbeddingTrajectoryCalculator`: Track note evolution (drift, alignment, convergence)
- `TemporalPatternFinder`: Find patterns (converging pairs, cycling notes, aligned drift)
- `TemporalSemanticQuery`: Fuse time + semantics (seasonal patterns, time-bounded similarity)

**Example Geists**:
- `drift_velocity_anomaly.py` - Detects accelerating drift (~30 lines vs 60+)
- `cyclical_thinking.py` - Finds cyclical patterns (~25 lines)

### Abstraction 4: Graph Analysis

**Before** (manual graph traversal):
```python
def suggest(vault):
    # Hub detection (20 lines)
    for note in notes:
        backlinks = vault.backlinks(note)
        if len(backlinks) >= 10:
            hubs.append(note)

    # Bridge detection (30+ lines)
    for bridge in candidates:
        connected = set(vault.outgoing_links(bridge))
        connected.update(vault.backlinks(bridge))
        # ... unlinked pair checking ...
```

**After** (unified pattern finder):
```python
from geistfabrik.graph_analysis import GraphPatternFinder

def suggest(vault):
    finder = GraphPatternFinder(vault)
    hubs = finder.find_hubs(min_backlinks=10)
    bridges = finder.find_bridges(min_similarity=0.6)
    structural_holes = finder.detect_structural_holes(min_similarity=0.6)
```

**Available Methods**:
- `find_hubs()`, `find_orphans()`, `find_bridges()`
- `shortest_path()`, `k_hop_neighborhood()`
- `find_connected_components()`, `detect_structural_holes()`

### Abstraction 5: Clustering Analysis

**Before** (duplicate HDBSCAN calls):
```python
def suggest(vault):
    # Every geist runs HDBSCAN independently (expensive!)
    clusterer = HDBSCAN(min_cluster_size=5)
    labels = clusterer.fit_predict(embeddings)
    # ... labelling ...
```

**After** (session-scoped caching):
```python
from geistfabrik.clustering_analysis import ClusterAnalyser

def suggest(vault):
    # Clustering computed once per session, cached for all geists
    analyser = ClusterAnalyser(vault, strategy="hdbscan", min_size=5)
    clusters = analyser.get_clusters()

    for cluster_id, cluster in clusters.items():
        reps = analyser.get_representatives(cluster_id, k=3)
        # cluster.formatted_label already available!
```

### Abstraction 6: Metadata Analysis

**Before** (manual aggregation):
```python
def suggest(vault):
    # Manual percentile computation
    values = [vault.metadata(n).get("word_count", 0) for n in notes]
    p75 = np.percentile(values, 75)
    outliers = [n for n in notes if vault.metadata(n).get("word_count") > p75 * 2]
```

**After** (statistical operations):
```python
from geistfabrik.metadata_system import MetadataAnalyser

def suggest(vault):
    analyser = MetadataAnalyser(vault)
    outliers = analyser.outliers("word_count", threshold=2.0)  # Z-score based
    profile = analyser.profile(note)  # {'word_count': 'high', 'link_density': 'low'}
```

### Best Practices for Using Abstractions

1. **Import at function level** (not module level) to avoid circular dependencies
2. **Combine abstractions** for complex patterns:
   ```python
   # Temporal + Similarity + Graph
   from geistfabrik.temporal_analysis import TemporalPatternFinder
   from geistfabrik.similarity_analysis import SimilarityLevel
   from geistfabrik.graph_analysis import GraphPatternFinder
   ```

3. **Use named constants** over magic numbers:
   ```python
   # ✅ Good
   filter.filter_by_range(note, candidates,
                          SimilarityLevel.MODERATE, SimilarityLevel.HIGH)

   # ❌ Bad
   filter.filter_by_range(note, candidates, 0.5, 0.65)
   ```

4. **Leverage caching** - ClusterAnalyser caches per session for all geists
5. **Compose abstractions** - Power comes from combining primitives

### Migration Guide

To refactor existing geists:

1. **Identify patterns**: Look for similarity thresholds, session queries, graph traversal
2. **Import abstractions**: Add imports at function level
3. **Replace logic**: Swap manual implementation for abstraction calls
4. **Test equivalence**: Ensure output matches original behavior
5. **Simplify**: Remove now-redundant helper functions

**Example**: See how `concept_drift.py` could be refactored from 65 lines to 15 lines using `TemporalPatternFinder`.

### Reference Documentation

- **Specification**: `specs/reuse_abstractions_spec.md` - Complete API reference
- **Example Geists**:
  - `definition_harvester.py` - Content extraction
  - `drift_velocity_anomaly.py` - Temporal analysis
  - `cyclical_thinking.py` - Pattern finding
- **Source Modules**: `src/geistfabrik/{similarity,temporal,clustering,graph}_analysis.py`

---

## Common Questions

### Q: Can I ever use directive language?
**A**: Rarely. If you do, it should be playful/provocative, not authoritative:
- ✅ "I think you're lying about..." (playful challenge)
- ❌ "You should link these notes" (authoritative command)

### Q: What if my geist genuinely finds an error?
**A**: Frame it as a question, not a correction:
- ❌ "[[note]] has an error"
- ✅ "[[note_a]] and [[note_b]] seem to contradict—what gives?"

### Q: Can I suggest creating a new note?
**A**: Yes, but make it speculative:
- ❌ "You should create a synthesis note"
- ✅ "What would a synthesis between X and Y look like?"

### Q: How specific should I be?
**A**: Very. Reference actual note titles, specific numbers, concrete relationships.

### Q: What about Tracery geists?
**A**: Same principles apply. Use vault functions to ground abstract templates in specific vault content.

---

## Resources

### Exemplary Geists to Study

**Philosophy & craft**:
- `columbo.py` - Gold standard for provocative questioning
- `session_drift.py` - Excellent temporal framing
- `assumption_challenger.py` - Great Socratic style
- `scale_shifter.py` - Superb perspective shifting

**Implementation patterns**:
- `pattern_finder.py` - Set-based lookups, quality gates
- `bridge_hunter.py` - Batch similarity for matrices
- `question_harvester.py` - Content extraction with validation

**Tracery patterns**:
- `transformation_suggester.yaml` - Modifier chaining
- `contradictor.yaml` - Template variation

### Documentation

- `docs/POST_MORTEM_PHASE3B.md` - Optimisation lessons learned
- `tests/integration/test_phase3b_regression.py` - Anti-regression tests
- `specs/geistfabrik_spec.md` - Complete technical specification
- `specs/geistfabrik_vision.md` - Core principles

---

## Final Wisdom

> "The owl of Minerva spreads its wings only with the falling of the dusk." — Hegel

Like Hegel's owl, geists work retrospectively—finding patterns and questions in knowledge already accumulated. They are **spirits in a factory of thought**, not managers of a to-do list.

Your geist should ask: **"What if?"** not **"You should."**

It should be a **muse**, not an **oracle**.

Most importantly, it should ask **different questions than users would ask themselves**—because that's the whole point of a divergence engine.

### Remember the 10 Essential Lessons:

1. Sample before analyze
2. Cache before reuse
3. Build sets, not loops
4. Validate before return
5. Abstain when uncertain
6. Respect session cache
7. Match threshold to complexity
8. Never crash
9. Explain the insight
10. Profile before optimise

---

**Happy geist writing!**
