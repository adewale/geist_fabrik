# Question Harvester Geist - Specification

**Status**: Proposed (Not Yet Implemented)
**Geist ID**: `question_harvester`
**Type**: Code geist
**Tier**: A (Provocative discovery)

---

## Overview

`question_harvester` picks a random note and extracts all questions found within it, surfacing them as provocations to revisit. By isolating questions from their surrounding context, the geist reveals the shape of your curiosity—the implicit inquiry structure that may be buried in longer writing.

### Philosophy

**"Muse, not oracle"**: This geist presents your own questions back to you, stripped of their original context. It doesn't answer them or suggest solutions—it simply asks: "What if you revisited this question now?"

**Core Insight**: When you extract only the questions from a piece of writing, you get:
1. **A map of curiosity** - What the author wondered about
2. **Unanswered tensions** - Unresolved threads of inquiry
3. **The shape of thinking** - The implicit structure of exploration
4. **Temporal resonance** - Questions that may have new relevance today

---

## Inspiration & Research Foundation

### The Power of Seeing Only Questions

This geist is inspired by two key observations about questions in writing:

#### Source 1: @pomeranian99 Tweet (2022)
**Reference**: https://x.com/pomeranian99/status/1497969902581272577

The observation that viewing only the questions from a piece of writing reveals something profound about the thinking process—questions are the skeleton of inquiry, and when isolated, they show patterns invisible in full context.

#### Source 2: "The Power of Seeing Only the Questions"
**Reference**: https://uxdesign.cc/the-power-of-seeing-only-the-questions-in-a-piece-of-writing-8f486d2c6d7d

Key insights about question extraction:
- **Questions reveal intent** - They show what the author is trying to understand
- **Questions show process** - The sequence of questions maps the thinking journey
- **Questions persist** - They may outlive their original answers as contexts change
- **Questions invite participation** - They're inherently open-ended and provocative

### Why This Matters for Personal Knowledge Management

In an Obsidian vault:
- **Questions get buried** in longer notes
- **Questions evolve relevance** over time—a question from 6 months ago may be answerable today
- **Questions connect** across notes in non-obvious ways
- **Questions are underutilized** as a navigation mechanism

By surfacing random questions, this geist:
1. **Reveals forgotten curiosity** - What you wondered about but may have dropped
2. **Invites temporal reflection** - Does this question still matter? Has it been answered?
3. **Creates serendipity** - A random question may resonate with current thinking
4. **Values inquiry over answers** - Questions are treated as artifacts worth revisiting

---

## Design Philosophy

### Muse Principles

**Questions over Answers**
- This geist never attempts to answer the questions it finds
- It surfaces them as-is, preserving the original phrasing
- The provocation is: "What if you thought about this now?"

**Sample, Don't Rank**
- Picks one random note (deterministic by session date)
- Doesn't prioritize "important" or "recent" notes
- Any note's questions deserve attention

**Temporal Serendipity**
- Questions from old notes may have new relevance
- The randomness creates surprising connections
- Same session date always picks the same note (determinism)

### Edge Case: Notes Without Questions

**Design Decision**: Return empty list `[]`

**Rationale**:
- GeistFabrik's idiom: Geists that find nothing abstain silently
- The filtering system expects and handles empty results gracefully
- No value in forcing a suggestion when there are no questions
- Trying again another day (different random note) is appropriate

**Alternative Approaches Considered**:

1. **Fallback to nearby notes**
   - Could check semantic neighbors if selected note has no questions
   - **Rejected**: Violates deterministic sampling principle (makes behavior unpredictable)

2. **Generate questions about the note**
   - Could use templates: "What does [[Note Title]] mean?"
   - **Rejected**: Violates "muse not oracle" (we don't invent questions for the user)

3. **Sample multiple notes until one has questions**
   - Could try 5-10 random notes
   - **Rejected**: Changes execution semantics (some sessions would process 10× more notes)

**Conclusion**: Silence is appropriate—this geist only speaks when it has something to say.

---

## Technical Specification

### Core Algorithm

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Extract questions from a randomly selected note."""

    # 1. Pick one random note (deterministic by session seed)
    notes = vault.notes()
    if not notes:
        return []

    note = vault.random_notes(k=1)[0]

    # 2. Read note content
    content = vault.read(note)

    # 3. Extract questions
    questions = extract_questions(content)

    # 4. If no questions found, return empty (geist abstains)
    if not questions:
        return []

    # 5. Create suggestions from questions
    suggestions = []
    for question in questions:
        text = (
            f"From [[{note.title}]]: \"{question}\" "
            f"What if you revisited this question now?"
        )
        suggestions.append(Suggestion(
            text=text,
            notes=[note.title],
            geist_id="question_harvester",
        ))

    # 6. Sample 1-3 questions to avoid overwhelming
    return vault.sample(suggestions, k=min(3, len(suggestions)))
```

### Question Extraction Algorithm

**Challenge**: Detecting questions in Markdown text with high precision and recall.

**Strategies**:

#### Strategy 1: Sentence-Ending Questions
```python
# Match text ending with '?'
pattern = r'([^.!?\n][^.!?]*\?)'
questions = re.findall(pattern, content, re.MULTILINE)
```

**Handles**:
- Simple sentences: "What is the meaning of life?"
- Multi-line questions: "What happens when\nwe try this?"
- Questions in paragraphs

**Misses**:
- Questions split across paragraphs (rare)
- Rhetorical questions in quotes (acceptable)

#### Strategy 2: List Item Questions
```python
# Match Markdown list items ending with '?'
pattern = r'^\s*[-*]\s+(.+\?)\s*$'
questions = re.findall(pattern, content, re.MULTILINE)
```

**Handles**:
- Bullet lists: "- Why does this happen?"
- Numbered lists: "1. What is the cause?"
- Nested lists (with proper indentation)

**Misses**:
- Multi-line list items (could extend pattern)

#### Strategy 3: Code Block Exclusion
```python
# Remove code blocks to avoid false positives
content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
content_no_code = re.sub(r'`[^`]+`', '', content_no_code)
```

**Why needed**:
- Code comments often contain `?` characters
- Inline code like `` `condition ? a : b` `` would be false positives
- SQL queries: `SELECT * FROM users WHERE active = ?`

#### Strategy 4: Length and Quality Filtering
```python
def is_valid_question(q: str) -> bool:
    """Filter out false positives."""
    q_clean = q.strip()

    # Too short: likely false positive
    if len(q_clean) < 10:
        return False

    # Too long: likely multiple sentences
    if len(q_clean) > 500:
        return False

    # Must contain at least one letter (not just punctuation)
    if not re.search(r'[a-zA-Z]', q_clean):
        return False

    return True
```

**Filters**:
- Very short matches: "Why?" (could be rhetorical or fragment)
- Very long matches: Likely parsing error
- Non-textual matches: "???"

#### Strategy 5: Deduplication
```python
seen = set()
for q in all_questions:
    q_normalized = q.strip().lower()
    if q_normalized not in seen:
        questions.append(q)
        seen.add(q_normalized)
```

**Why needed**:
- Same question might appear multiple times
- Case variations should be deduplicated
- Preserves first occurrence (maintains reading order)

### Complete Implementation

**File**: `src/geistfabrik/default_geists/code/question_harvester.py`

```python
"""Question Harvester geist - extracts questions from random notes.

Inspired by:
- https://x.com/pomeranian99/status/1497969902581272577
- https://uxdesign.cc/the-power-of-seeing-only-the-questions-in-a-piece-of-writing-8f486d2c6d7d

The power of seeing only the questions: when you strip away everything except
the questions from a piece of writing, you reveal the shape of curiosity and
the implicit structure of inquiry.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Extract questions from a randomly selected note.

    Returns:
        List of 1-3 suggestions containing questions found (or empty if none)
    """
    from geistfabrik import Suggestion

    # Pick one random note (deterministic by session seed)
    notes = vault.notes()
    if not notes:
        return []

    note = vault.random_notes(k=1)[0]
    content = vault.read(note)

    # Extract questions
    questions = extract_questions(content)

    # If no questions found, return empty (geist abstains)
    if not questions:
        return []

    # Create suggestions from questions
    suggestions = []
    for question in questions:
        # Clean up whitespace
        question_clean = " ".join(question.split())

        text = (
            f"From [[{note.title}]]: \"{question_clean}\" "
            f"What if you revisited this question now?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.title],
                geist_id="question_harvester",
            )
        )

    # Sample 1-3 questions to avoid overwhelming
    return vault.sample(suggestions, k=min(3, len(suggestions)))


def extract_questions(content: str) -> list[str]:
    """Extract questions from markdown content.

    Uses multiple strategies:
    1. Remove code blocks (avoid false positives)
    2. Find sentence-ending questions
    3. Find list item questions
    4. Filter and deduplicate

    Args:
        content: Markdown content

    Returns:
        List of question strings (deduplicated, filtered)
    """
    # Strategy 1: Remove code blocks to avoid false positives
    content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    content_no_code = re.sub(r'`[^`]+`', '', content_no_code)

    questions = []

    # Strategy 2: Sentence-ending questions
    # Match text ending with '?' (handles multi-line)
    sentence_questions = re.findall(
        r'([^.!?\n][^.!?]*\?)',
        content_no_code,
        re.MULTILINE
    )

    # Strategy 3: List item questions
    # Match Markdown list items ending with '?'
    list_questions = re.findall(
        r'^\s*[-*+]\s+(.+\?)\s*$',
        content_no_code,
        re.MULTILINE
    )

    # Combine and deduplicate
    all_questions = sentence_questions + list_questions
    seen = set()

    for q in all_questions:
        q_clean = q.strip()
        q_normalized = q_clean.lower()

        # Strategy 4: Quality filtering
        if not is_valid_question(q_clean):
            continue

        # Strategy 5: Deduplication (case-insensitive)
        if q_normalized not in seen:
            questions.append(q_clean)
            seen.add(q_normalized)

    return questions


def is_valid_question(q: str) -> bool:
    """Filter out false positives and low-quality matches.

    Args:
        q: Question string

    Returns:
        True if valid question, False otherwise
    """
    # Too short: likely false positive
    if len(q) < 10:
        return False

    # Too long: likely parsing error
    if len(q) > 500:
        return False

    # Must contain at least one letter
    if not re.search(r'[a-zA-Z]', q):
        return False

    # Common false positives to exclude
    false_positive_patterns = [
        r'^#+\s*\?',  # Markdown headings that are just "?"
        r'^\s*\?\s*$',  # Just a question mark
    ]

    for pattern in false_positive_patterns:
        if re.match(pattern, q):
            return False

    return True
```

---

## Output Examples

### Example 1: Research Note with Multiple Questions

**Source Note**: `[[Understanding Neural Networks]]`

**Content Snippet**:
```markdown
Neural networks learn by adjusting weights. But how do they
know which direction to adjust? And why does backpropagation
work so well in practice even though it's just gradient descent?

Open questions:
- Can we visualize what each layer is learning?
- What is the relationship between network depth and expressiveness?
- How do transformers differ from CNNs in their inductive biases?
```

**Geist Output**:
```markdown
From [[Understanding Neural Networks]]: "But how do they know which direction to adjust?" What if you revisited this question now?

From [[Understanding Neural Networks]]: "What is the relationship between network depth and expressiveness?" What if you revisited this question now?

From [[Understanding Neural Networks]]: "How do transformers differ from CNNs in their inductive biases?" What if you revisited this question now?
```

---

### Example 2: Personal Reflection with Single Question

**Source Note**: `[[2024-03-15 Daily Note]]`

**Content**:
```markdown
Spent the day thinking about career direction. Feeling stuck
between staying technical vs moving into management.

The real question is: what kind of impact do I want to have
in 10 years?

Made progress on the authentication refactor.
```

**Geist Output**:
```markdown
From [[2024-03-15 Daily Note]]: "The real question is: what kind of impact do I want to have in 10 years?" What if you revisited this question now?
```

---

### Example 3: Meeting Notes with Action Items

**Source Note**: `[[Team Meeting 2024-11-05]]`

**Content**:
```markdown
## Agenda
1. Q4 roadmap discussion
2. Performance issues in production

## Notes
Sarah raised concerns about database scaling. Need to investigate
whether we should shard now or later.

Questions for follow-up:
- What's our current query latency at p99?
- How much headroom do we have on the current infrastructure?
- Should we consider moving to a distributed database?

Action items:
- Mike to profile the slow queries
- Sarah to estimate future growth
```

**Geist Output**:
```markdown
From [[Team Meeting 2024-11-05]]: "What's our current query latency at p99?" What if you revisited this question now?

From [[Team Meeting 2024-11-05]]: "Should we consider moving to a distributed database?" What if you revisited this question now?
```

---

### Example 4: Note Without Questions (Silent Abstention)

**Source Note**: `[[Installing Docker]]`

**Content**:
```markdown
# Docker Installation Guide

Steps:
1. Download Docker Desktop
2. Run installer
3. Restart computer
4. Verify with `docker --version`

The installation process was straightforward. Everything works now.
```

**Geist Output**: *(none - returns empty list)*

The geist silently abstains because there are no questions to harvest. Next session (different random note) might find questions.

---

## Design Decisions

### Why Random Selection?

**Decision**: Pick exactly one random note per session.

**Alternatives Considered**:

1. **Most recent notes**
   - Pro: Questions from active thinking
   - Con: Misses buried questions from older notes
   - Con: Biases toward recent work

2. **Notes with most questions**
   - Pro: Maximizes chance of finding questions
   - Con: Requires full vault scan (performance)
   - Con: Always samples same notes

3. **Semantic similarity to recent notes**
   - Pro: Questions related to current focus
   - Con: Reduces serendipity
   - Con: More complex

**Chosen**: Pure random sampling
- Maximizes serendipity
- Simple and fast (O(1) after note loading)
- Treats all notes equally (no bias)
- Deterministic by session date

### Why 1-3 Questions Max?

**Decision**: Sample maximum 3 questions from the selected note.

**Rationale**:
- **Avoid overwhelming**: A note might have 10+ questions
- **Preserve surprise**: Seeing too many at once dilutes impact
- **Maintain focus**: 1-3 provocations are enough per session
- **Filtering layer**: Other geists also contribute; total suggestions will be filtered

**Edge Cases**:
- 0 questions: Return empty list (silent abstention)
- 1-2 questions: Return all
- 3+ questions: Sample 3 randomly (deterministic)

### Why Include Note Title in Suggestion?

**Decision**: Always include `From [[Note Title]]:` prefix.

**Rationale**:
- **Context**: User needs to know where the question came from
- **Navigation**: Clicking the link jumps to the note
- **Temporal marker**: Note title might indicate when the question was asked
- **Attribution**: Preserves the question's origin

**Alternative**: Strip context entirely, present bare question
- **Rejected**: Too disorienting without context
- User wouldn't know where to look for related thinking

### Question Extraction Precision vs Recall

**Trade-off**: False positives vs false negatives

**Current Bias**: Optimize for precision (avoid false positives)
- Length filter (>10 chars) reduces noise
- Code block exclusion prevents technical false positives
- Quality checks filter out fragment matches

**Acceptable False Negatives**:
- Multi-paragraph questions (rare)
- Questions without `?` (rhetorical, implicit)
- Questions in images or embedded content

**Rationale**: Better to miss some questions than to surface garbage
- User trust eroded by false positives
- Silence (empty result) is acceptable outcome

---

## Implementation Checklist

- [ ] Create `src/geistfabrik/default_geists/code/question_harvester.py`
- [ ] Implement `suggest()` function
- [ ] Implement `extract_questions()` helper
- [ ] Implement `is_valid_question()` filter
- [ ] Add unit tests for question extraction
- [ ] Add integration test with test vault
- [ ] Add to default geist configuration
- [ ] Document in CHANGELOG
- [ ] Add to geist catalog documentation

---

## Testing Strategy

### Unit Tests

**File**: `tests/unit/test_question_harvester.py`

#### Test 1: Basic Question Extraction
```python
def test_extract_simple_questions():
    content = "What is the meaning? How does it work?"
    questions = extract_questions(content)
    assert len(questions) == 2
    assert "What is the meaning?" in questions
    assert "How does it work?" in questions
```

#### Test 2: Multi-line Questions
```python
def test_extract_multiline_questions():
    content = """
    What happens when
    we do this?
    """
    questions = extract_questions(content)
    assert len(questions) == 1
    assert "What happens when we do this?" in questions[0]
```

#### Test 3: List Item Questions
```python
def test_extract_list_questions():
    content = """
    - What is A?
    - What is B?
    * What is C?
    """
    questions = extract_questions(content)
    assert len(questions) == 3
```

#### Test 4: Code Block Exclusion
```python
def test_ignore_code_blocks():
    content = """
    Real question: What is this?

    ```python
    # What is this? (comment)
    result = condition ? a : b
    ```

    Another question: How does it work?
    """
    questions = extract_questions(content)
    assert len(questions) == 2
    assert "What is this?" in questions
    assert "How does it work?" in questions
    # Code block questions should not appear
    assert "comment" not in " ".join(questions).lower()
```

#### Test 5: Deduplication
```python
def test_deduplication():
    content = """
    What is this?
    What is this?
    WHAT IS THIS?
    """
    questions = extract_questions(content)
    assert len(questions) == 1
```

#### Test 6: Length Filtering
```python
def test_length_filtering():
    content = "Why? What is the meaning of life, the universe, and everything?"
    questions = extract_questions(content)
    assert len(questions) == 1
    assert "meaning of life" in questions[0]
```

#### Test 7: Empty Content
```python
def test_empty_content():
    questions = extract_questions("")
    assert questions == []
```

#### Test 8: No Questions
```python
def test_no_questions():
    content = "This is a statement. Another statement."
    questions = extract_questions(content)
    assert questions == []
```

### Integration Tests

**File**: `tests/integration/test_question_harvester_geist.py`

#### Test 1: Full Geist Execution
```python
def test_question_harvester_with_questions(vault_context):
    """Test geist finds and returns questions."""
    suggestions = suggest(vault_context)

    # Should return 1-3 suggestions
    assert 0 <= len(suggestions) <= 3

    if len(suggestions) > 0:
        for s in suggestions:
            # Check structure
            assert s.geist_id == "question_harvester"
            assert len(s.notes) == 1
            assert "From [[" in s.text
            assert "What if you revisited this question now?" in s.text

            # Check question is quoted
            assert '"' in s.text
```

#### Test 2: Deterministic Behavior
```python
def test_deterministic_selection(vault_context):
    """Test same session date picks same note."""
    suggestions_1 = suggest(vault_context)
    suggestions_2 = suggest(vault_context)

    # Should return identical results
    assert len(suggestions_1) == len(suggestions_2)

    for s1, s2 in zip(suggestions_1, suggestions_2):
        assert s1.text == s2.text
        assert s1.notes == s2.notes
```

#### Test 3: Empty Vault
```python
def test_empty_vault(empty_vault_context):
    """Test graceful handling of empty vault."""
    suggestions = suggest(empty_vault_context)
    assert suggestions == []
```

#### Test 4: Note Without Questions
```python
def test_note_without_questions(vault_context_no_questions):
    """Test silent abstention when note has no questions."""
    # Create vault where random note has no questions
    suggestions = suggest(vault_context_no_questions)

    # Should return empty (silent abstention)
    assert suggestions == []
```

### Quality Metrics

**Manual Evaluation** (sample 20 sessions):
- **Precision**: % of surfaced questions that are valid questions
  - Target: >95% (very few false positives)
- **Recall**: % of actual questions that were extracted
  - Target: >80% (most questions found)
- **Relevance**: % of questions that user finds interesting/worth revisiting
  - Target: >50% (subjective but important)

**Performance**:
- Question extraction: <0.1s per note (regex is fast)
- Total geist execution: <0.5s (dominated by note loading)

---

## Future Enhancements (Post-1.0)

### Enhancement 1: Question Threading

**Idea**: Connect questions across notes that are semantically similar.

**Example Output**:
```markdown
These questions seem related:
- From [[Note A]]: "How does backpropagation work?"
- From [[Note B]]: "Why is gradient descent effective?"

What connects them?
```

**Requirements**:
- Compute embeddings for each question
- Find similar questions across vault
- Present as a separate geist: `question_threads`

### Enhancement 2: Unanswered Question Detector

**Idea**: Find questions followed by no answer attempt.

**Heuristic**:
- Question followed immediately by new heading → likely unanswered
- Question at end of note → likely unanswered
- Question in list with no follow-up items → likely unanswered

**Example Output**:
```markdown
[[Note Title]] asks "What is the solution?" but doesn't answer it.
Do you know now?
```

### Enhancement 3: Question Evolution

**Idea**: Track how questions change over time in evolving notes.

**Requires**:
- Session history tracking
- Diff detection for question content
- Temporal comparison

**Example Output**:
```markdown
[[Note Title]] changed its question from "How?" to "Why?"
What shifted?
```

### Enhancement 4: Question Density Analysis

**Idea**: Identify notes with unusually high question density.

**Metric**: Questions per 100 words

**Example Output**:
```markdown
[[Brainstorm Session Notes]] has 15 questions in 200 words.
What were you exploring?
```

### Enhancement 5: Question-Answer Pairing

**Idea**: Detect when a question is followed by what looks like an answer.

**Heuristic**:
- Question followed by "Because", "Answer:", or indented text
- Could annotate: "✓ Answered" or "? Unanswered"

**Trade-off**:
- Complex heuristics may have low accuracy
- Better to keep simple: just surface questions

### Enhancement 6: Temporal Targeting

**Idea**: Bias toward old questions (instead of pure random).

**Variation**: `question_archaeology` geist
- Samples from notes >6 months old
- Surfaces forgotten questions

**Example Output**:
```markdown
From [[2023-05-12]]: "Should we refactor the API?"
You asked this 18 months ago. Did you?
```

---

## Comparison to Related Geists

### vs `question_generator`

**question_generator**:
- Generates *new* questions about existing notes
- Transforms declarative statements into questions
- Prescriptive: "What if you reframed X as Y?"

**question_harvester**:
- Extracts *existing* questions from notes
- Surfaces your own past curiosity
- Reflective: "What if you revisited this?"

**Relationship**: Complementary
- One creates questions (generator)
- One surfaces questions (harvester)

### vs `columbo`

**columbo**:
- Detects contradictions between notes
- Generates *investigative* questions
- Focus: Consistency checking

**question_harvester**:
- Extracts questions as-written
- No interpretation or analysis
- Focus: Curiosity mapping

**Relationship**: Different domains
- Columbo creates questions *about* your notes
- Harvester shows questions *within* your notes

### vs `temporal_mirror`

**temporal_mirror**:
- Shows how note interpretations change over time
- Uses embeddings to detect drift
- Focus: Semantic evolution

**question_harvester**:
- Shows explicit questions from the past
- No semantic analysis
- Focus: Explicit inquiry

**Relationship**: Different time scales
- Mirror tracks unconscious drift
- Harvester surfaces conscious questions

---

## Design Principles Satisfied

### ✓ Muses, Not Oracles
- Surfaces questions without answering them
- Invites reflection: "What if you revisited this?"
- No prescription or instruction

### ✓ Questions, Not Answers
- Literally surfaces questions
- The geist's entire purpose is to highlight inquiry
- Embodies the principle perfectly

### ✓ Sample, Don't Rank
- Random selection (no ranking)
- Treats all notes equally
- Avoids creating hierarchies

### ✓ Deterministic Randomness
- Same session date → same note → same questions
- Reproducible for testing
- Consistent user experience

### ✓ Non-Destructive
- Read-only operation
- No modifications to notes
- Safe to run repeatedly

### ✓ Local-First
- No external dependencies (pure regex)
- No API calls
- Fast execution

---

## Known Limitations

### 1. Rhetorical Questions

**Issue**: Extracts all questions, including rhetorical ones.

**Example**: "Who knows? Maybe it'll work."
- This might be rhetorical, not a genuine inquiry
- Hard to distinguish without semantic analysis

**Mitigation**: Acceptable limitation
- Context preserved (note title shown)
- User can judge relevance

### 2. Implicit Questions

**Issue**: Doesn't detect questions without `?`.

**Example**: "I wonder if this will work"
- Clearly a question, but no `?`

**Mitigation**: Acceptable trade-off
- Optimizing for precision over recall
- Could extend with "I wonder if" pattern matching

### 3. Questions in Embedded Content

**Issue**: Doesn't process embedded notes or images.

**Example**: `![[Other Note#Question Section]]`
- Questions in transcluded content not extracted

**Mitigation**: Acceptable scope limitation
- Processing transclusions adds complexity
- User can navigate to source if needed

### 4. Language-Specific

**Issue**: Assumes English-language questions.

**Example**: "¿Por qué?" (Spanish) won't be detected
- Different languages use different question patterns

**Mitigation**: Could extend with multi-language support
- Would need language detection
- Post-1.0 enhancement

### 5. Question Quality Variance

**Issue**: No semantic filtering for "interesting" questions.

**Example**: "What?" vs "What is the relationship between quantum entanglement and consciousness?"
- Both are questions, but very different value
- Length filter helps but isn't perfect

**Mitigation**: Acceptable design choice
- Let user judge quality
- All questions are potentially valuable

---

## User Experience Goals

### Surprise
Surfaces questions you forgot you asked—"Oh, I wondered about that!"

### Reflection
Invites temporal comparison—"Do I still care about this? Have I answered it?"

### Rediscovery
Reveals buried curiosity—questions hidden in longer notes

### Serendipity
Random selection creates unexpected relevance—"This question is perfect for what I'm thinking about now"

### Validation
Treats questions as valuable artifacts—inquiry is worth preserving and revisiting

---

## Implementation Complexity

**Estimated Effort**: 4-6 hours

**Breakdown**:
- Core extraction logic: 2 hours
- Unit tests: 1 hour
- Integration tests: 1 hour
- Documentation: 1-2 hours

**Dependencies**:
- None (pure Python + regex)
- No external libraries needed
- Minimal VaultContext usage

**Risk Level**: Low
- Simple algorithm
- Well-defined scope
- No performance concerns
- No external dependencies

---

## Conclusion

`question_harvester` embodies the "muses not oracles" philosophy by treating questions as valuable artifacts worth revisiting. By isolating questions from their original context and surfacing them randomly, it creates opportunities for temporal reflection and serendipitous rediscovery.

The geist is simple in implementation but profound in effect—it reveals the shape of your curiosity and invites you to revisit inquiry that may have been buried or forgotten.

---

## References

### Inspiration

1. **@pomeranian99 Tweet** (2022)
   - https://x.com/pomeranian99/status/1497969902581272577
   - Core observation about the power of viewing only questions

2. **"The Power of Seeing Only the Questions in a Piece of Writing"** (UX Design)
   - https://uxdesign.cc/the-power-of-seeing-only-the-questions-in-a-piece-of-writing-8f486d2c6d7d
   - Analysis of question extraction as a thinking tool

### Related Concepts

3. **Question-Driven Learning** (Educational Psychology)
   - Self-generated questions improve learning (Rosenshine et al., 1996)
   - Questions as metacognitive tools

4. **Zettelkasten "Question Notes"** (Niklas Luhmann)
   - Some practitioners maintain separate question notes
   - Questions as first-class knowledge objects

5. **Socratic Method**
   - Learning through inquiry
   - Questions as tools for discovery

### Technical References

6. **Python `re` Module Documentation**
   - https://docs.python.org/3/library/re.html
   - Regex patterns for text extraction

7. **Markdown Spec (CommonMark)**
   - https://commonmark.org/
   - List syntax and formatting rules

---

**Version**: 1.0
**Date**: 2025-11-06
**Status**: Specification Complete (Ready for Implementation)
**Author**: Specification created for GeistFabrik project
