# Harvester Family - Specification

**Status**: ✅ Implemented
**Geist IDs**: `question_harvester`, `todo_harvester`, `quote_harvester`
**Type**: Code geists
**Tier**: A (Provocative discovery)
**Pattern Category**: Extraction-Based Geists

---

## Overview

The **Harvester Family** is a collection of geists that share a common pattern: pick a random note, extract specific content types, and surface them as provocations. Each harvester treats a different type of content as a valuable artifact worth isolating and revisiting.

### The Harvester Pattern

```
Random Note Selection → Content Extraction → Temporal Provocation
```

**Core Philosophy**: Your notes contain buried artifacts (questions, TODOs, quotes) that deserve attention. By stripping them from their original context and surfacing them randomly, harvesters create opportunities for temporal reflection and serendipitous rediscovery.

### Family Members

| Geist | Extracts | Provocation | Inspiration |
|-------|----------|-------------|-------------|
| **question_harvester** | Questions (`?`) | "What if you revisited this question now?" | Seeing only questions reveals inquiry structure |
| **todo_harvester** | TODO markers | "What if you tackled this now?" | Forgotten intentions deserve attention |
| **quote_harvester** | Blockquotes (`>`) | "What if you reflected on this again?" | Quotes show what resonated with you |

---

## Design Philosophy

### Shared Principles

1. **Random sampling** - Pure deterministic randomness (same session → same note)
2. **Silent abstention** - Return `[]` when target content not found
3. **Context preservation** - Always show source note: `From [[Note]]: ...`
4. **Temporal framing** - "What if you [action] now?" emphasizes time's passage
5. **No interpretation** - Present extracted content as-is
6. **Performance-conscious** - Single note read per session, fast regex extraction

### Why This Pattern Works

**Isolation creates perspective**: By stripping content from context, you see it differently. A question buried in paragraph 5 becomes provocative when isolated.

**Randomness creates serendipity**: You might find a question from 2 years ago that's suddenly relevant to today's thinking.

**Time creates relevance**: TODOs from last month might be more urgent now. Quotes that resonated before might mean something different today.

---

## Inspiration & Research Foundation

### Question Harvester Inspiration

**Sources**:
- [@pomeranian99 Tweet (2022)](https://x.com/pomeranian99/status/1497969902581272577) - Viewing only questions reveals thinking patterns
- ["The Power of Seeing Only the Questions"](https://uxdesign.cc/the-power-of-seeing-only-the-questions-in-a-piece-of-writing-8f486d2c6d7d) - Questions are the skeleton of inquiry

**Key Insight**: Questions reveal intent, process, and unresolved tensions invisible in full text.

### TODO Harvester Inspiration

**Insight**: Personal knowledge bases accumulate TODO markers (`TODO:`, `FIXME:`, `HACK:`) that represent:
- **Forgotten intentions** - "I meant to research this"
- **Deferred work** - "I'll fix this later" (but forgot)
- **Open loops** - Incomplete thoughts that deserve closure

Unlike `task_archaeology` (which finds checkbox tasks), `todo_harvester` surfaces inline prose markers—the casual "TODO: investigate this" notes scattered through writing.

### Quote Harvester Inspiration

**Insight**: Blockquotes in personal notes represent:
- **Resonance** - Text that moved you enough to preserve
- **External wisdom** - Voices beyond your own thinking
- **Reference points** - Ideas you return to repeatedly

Surfacing quotes randomly reveals what you valued at different times—a temporal map of intellectual influences.

---

## Shared Implementation Pattern

### Base Algorithm

All harvesters follow this template:

```python
def suggest(vault: VaultContext) -> list[Suggestion]:
    """Extract [content_type] from a randomly selected note."""

    # 1. Pick random note (deterministic by session seed)
    notes = vault.notes()
    if not notes:
        return []

    note = vault.random_notes(k=1)[0]
    content = vault.read(note)

    # 2. Extract target content using optimized regex
    extracted = extract_[content_type](content)

    # 3. Silent abstention if nothing found
    if not extracted:
        return []

    # 4. Create suggestions with temporal framing
    suggestions = []
    for item in extracted:
        text = f"From [[{note.title}]]: \"{item}\" [Provocation]"
        suggestions.append(Suggestion(
            text=text,
            notes=[note.title],
            geist_id="[harvester_id]",
        ))

    # 5. Sample 1-3 items to avoid overwhelming
    return vault.sample(suggestions, k=min(3, len(suggestions)))
```

### Performance Characteristics

**All harvesters are O(1) per session**:
- Read exactly **1 note** (randomly selected)
- Extract via **fast regex** (O(n) where n = note length)
- No cross-note analysis
- No embedding computations
- No database queries beyond note loading

**Expected execution**: <50ms per harvester

---

## Question Harvester

### What It Extracts

Questions ending with `?` character, including:
- Sentence-ending questions: "What is the meaning?"
- Multi-line questions: "What happens when\nwe do this?"
- List item questions: "- Why does it work?"
- Questions with embedded links: "[[How]] does [[this]] work?"

### Extraction Algorithm

```python
def extract_questions(content: str) -> list[str]:
    """Extract questions from markdown content."""

    # Remove code blocks (avoid false positives like "condition ? a : b")
    content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    content_no_code = re.sub(r'`[^`]+`', '', content_no_code)

    questions = []

    # Strategy 1: Sentence-ending questions
    sentence_questions = re.findall(
        r'([^.!?\n][^.!?]*\?)',
        content_no_code,
        re.MULTILINE
    )

    # Strategy 2: List item questions
    list_questions = re.findall(
        r'^\s*[-*+]\s+(.+\?)\s*$',
        content_no_code,
        re.MULTILINE
    )

    # Combine and filter
    all_questions = sentence_questions + list_questions
    seen = set()

    for q in all_questions:
        q_clean = q.strip()

        # Quality filtering
        if len(q_clean) < 10 or len(q_clean) > 500:
            continue

        # Deduplication (case-insensitive)
        q_normalized = q_clean.lower()
        if q_normalized not in seen:
            questions.append(q_clean)
            seen.add(q_normalized)

    return questions
```

### Output Example

**Input Note**: `[[Research Ideas]]`
```markdown
Working on neural networks. How do they learn from data?
What is backpropagation exactly?

Open questions:
- Can we visualize hidden layers?
- What determines optimal architecture?
```

**Geist Output**:
```markdown
From [[Research Ideas]]: "How do they learn from data?" What if you revisited this question now?

From [[Research Ideas]]: "Can we visualize hidden layers?" What if you revisited this question now?
```

---

## TODO Harvester

### What It Extracts

Inline TODO markers commonly used in prose and code comments:
- `TODO:` - General things to do
- `FIXME:` - Things that need fixing
- `HACK:` - Temporary solutions to revisit
- `NOTE:` - Important reminders
- `XXX:` - Warnings or urgent items

**Focus**: Prose TODOs, not checkbox tasks (`- [ ]`). Those are handled by `task_archaeology`.

### Extraction Algorithm

```python
def extract_todos(content: str) -> list[str]:
    """Extract TODO markers from content."""

    # Remove code blocks (those TODOs are for code, not notes)
    content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    content_no_code = re.sub(r'`[^`]+`', '', content_no_code)

    todos = []

    # Match TODO markers with their text
    # Captures: TODO: text until end of line or period
    pattern = r'(TODO|FIXME|HACK|NOTE|XXX):\s*([^.\n]+(?:\.[^\n]+)?)'
    matches = re.findall(pattern, content_no_code, re.IGNORECASE)

    seen = set()
    for marker, text in matches:
        todo_text = text.strip()

        # Quality filtering
        if len(todo_text) < 5 or len(todo_text) > 300:
            continue

        # Skip if it's just a placeholder
        if todo_text.lower() in ['add content', 'write this', 'fill in']:
            continue

        # Deduplication
        todo_normalized = todo_text.lower()
        if todo_normalized not in seen:
            # Format: "TODO: investigate this"
            formatted = f"{marker.upper()}: {todo_text}"
            todos.append(formatted)
            seen.add(todo_normalized)

    return todos
```

### Output Example

**Input Note**: `[[Project Planning]]`
```markdown
Phase 1 complete. Phase 2 blocked on API design.

TODO: Research GraphQL vs REST tradeoffs
FIXME: The authentication flow needs rethinking

NOTE: Check with Sarah about timeline constraints
```

**Geist Output**:
```markdown
From [[Project Planning]]: "TODO: Research GraphQL vs REST tradeoffs" What if you tackled this now?

From [[Project Planning]]: "FIXME: The authentication flow needs rethinking" What if you tackled this now?
```

---

## Quote Harvester

### What It Extracts

Blockquote content (markdown `>` prefix) representing:
- External quotes from books, articles, people
- Passages worth preserving
- Reference material
- Inspirational text

### Extraction Algorithm

```python
def extract_quotes(content: str) -> list[str]:
    """Extract blockquotes from markdown content."""

    quotes = []

    # Match blockquote blocks (may span multiple lines)
    # Blockquote: lines starting with ">", grouped together
    lines = content.split('\n')
    current_quote = []

    for line in lines:
        stripped = line.strip()

        # If line starts with ">", it's part of a quote
        if stripped.startswith('>'):
            # Remove the ">" prefix and leading whitespace
            quote_text = stripped[1:].strip()
            if quote_text:  # Skip empty quote lines
                current_quote.append(quote_text)
        else:
            # End of quote block
            if current_quote:
                # Join multi-line quotes
                full_quote = ' '.join(current_quote)
                quotes.append(full_quote)
                current_quote = []

    # Handle quote at end of file
    if current_quote:
        full_quote = ' '.join(current_quote)
        quotes.append(full_quote)

    # Filter and deduplicate
    filtered_quotes = []
    seen = set()

    for quote in quotes:
        quote_clean = quote.strip()

        # Quality filtering
        if len(quote_clean) < 10:  # Too short to be meaningful
            continue
        if len(quote_clean) > 500:  # Too long to surface
            quote_clean = quote_clean[:497] + "..."

        # Deduplication
        quote_normalized = quote_clean.lower()
        if quote_normalized not in seen:
            filtered_quotes.append(quote_clean)
            seen.add(quote_normalized)

    return filtered_quotes
```

### Output Example

**Input Note**: `[[Reading Notes - Deep Work]]`
```markdown
Cal Newport's book on focused work.

Key insights:

> The ability to perform deep work is becoming increasingly rare at exactly
> the same time it is becoming increasingly valuable in our economy.

> If you don't produce, you won't thrive—no matter how skilled or talented you are.

Need to think about how this applies to my workflow.
```

**Geist Output**:
```markdown
From [[Reading Notes - Deep Work]]: "The ability to perform deep work is becoming increasingly rare at exactly the same time it is becoming increasingly valuable in our economy." What if you reflected on this again?

From [[Reading Notes - Deep Work]]: "If you don't produce, you won't thrive—no matter how skilled or talented you are." What if you reflected on this again?
```

---

## Design Decisions

### Why Random Selection?

**Decision**: Pick exactly one random note per session (per harvester).

**Rationale**:
- Maximizes serendipity (any note could be chosen)
- Simple and fast (O(1) complexity)
- Deterministic by session date
- Treats all notes equally

**Alternative**: Target specific notes (recent, old, frequently accessed)
- **Rejected**: Reduces serendipity, adds complexity

### Why Silent Abstention?

**Decision**: Return `[]` when target content not found.

**Rationale**:
- GeistFabrik idiom: geists abstain when they have nothing valuable to say
- Clean failure mode (no forced output)
- Try again another day (different random note)

**Alternative**: Fallback to nearby notes
- **Rejected**: Violates determinism, unpredictable behavior

### Why 1-3 Items Max?

**Decision**: Sample maximum 3 items from selected note.

**Rationale**:
- Avoid overwhelming (a note might have 20 questions)
- Preserve surprise (partial sampling creates variety)
- Maintain focus (1-3 provocations are enough)
- Let filtering layer handle total volume

### Why Preserve Source Note?

**Decision**: Always include `From [[Note Title]]:` prefix.

**Rationale**:
- Provides context (where did this come from?)
- Enables navigation (click to jump to note)
- Temporal marker (note title might indicate date)
- Attribution (preserves provenance)

---

## Performance Optimization

### Shared Optimizations

All harvesters implement these performance strategies:

#### 1. Single Note Read
```python
# ✅ Good: Read one note
note = vault.random_notes(k=1)[0]
content = vault.read(note)

# ❌ Bad: Read multiple notes
for note in vault.sample(vault.notes(), k=10):
    content = vault.read(note)  # 10× slower
```

#### 2. Fast Regex (No Backtracking)
```python
# ✅ Good: Simple patterns, no catastrophic backtracking
pattern = r'([^.!?\n][^.!?]*\?)'

# ❌ Bad: Complex patterns with nested quantifiers
pattern = r'(.*\?.*)*'  # Exponential backtracking risk
```

#### 3. Early Termination
```python
# ✅ Good: Stop when enough items found
if len(extracted) >= 20:  # More than we'll sample anyway
    break

# ❌ Bad: Process entire note even if hundreds of matches
# (Not implemented yet, but could optimize further)
```

#### 4. Compiled Regex (If Needed)
```python
# For patterns used repeatedly, pre-compile
TODO_PATTERN = re.compile(r'(TODO|FIXME|HACK|NOTE|XXX):\s*([^.\n]+)', re.IGNORECASE)

def extract_todos(content: str) -> list[str]:
    matches = TODO_PATTERN.findall(content)
    # ... process matches
```

### Performance Profile

**Expected performance per harvester**:

| Vault Size | Note Length | Time | Bottleneck |
|------------|-------------|------|------------|
| 100 notes  | 1KB avg     | <10ms | Regex |
| 1000 notes | 1KB avg     | <10ms | Regex |
| 1000 notes | 100KB avg   | <50ms | Regex (large note) |

**Why vault size doesn't matter**: Only one note read per session.
**What matters**: Individual note length (linear scan for regex).

---

## Testing Strategy

### Unit Tests

Each harvester has parallel unit tests:

#### Question Harvester Tests
```python
def test_extract_simple_questions():
    content = "What is this? How does it work?"
    questions = extract_questions(content)
    assert len(questions) == 2

def test_extract_multiline_questions():
    content = "What happens\nwhen we do this?"
    questions = extract_questions(content)
    assert len(questions) == 1

def test_ignore_code_blocks():
    content = "Real: What? Code: ```condition ? a : b```"
    questions = extract_questions(content)
    assert len(questions) == 1
    assert "condition" not in questions[0]
```

#### TODO Harvester Tests
```python
def test_extract_todo_markers():
    content = "TODO: investigate this\nFIXME: broken behavior"
    todos = extract_todos(content)
    assert len(todos) == 2
    assert "TODO: investigate" in todos[0]

def test_ignore_code_block_todos():
    content = "TODO: fix this\n```\nTODO: code comment\n```"
    todos = extract_todos(content)
    assert len(todos) == 1
    assert "code comment" not in todos[0]
```

#### Quote Harvester Tests
```python
def test_extract_single_line_quote():
    content = "> This is a quote."
    quotes = extract_quotes(content)
    assert len(quotes) == 1
    assert "This is a quote" in quotes[0]

def test_extract_multiline_quote():
    content = "> Line one\n> Line two"
    quotes = extract_quotes(content)
    assert len(quotes) == 1
    assert "Line one Line two" in quotes[0]
```

### Integration Tests

Each harvester has parallel integration tests:

```python
def test_[harvester]_with_content(vault_context):
    """Test geist finds and returns content."""
    suggestions = suggest(vault_context)

    assert 0 <= len(suggestions) <= 3

    if suggestions:
        for s in suggestions:
            assert s.geist_id == "[harvester_id]"
            assert len(s.notes) == 1
            assert "From [[" in s.text

def test_[harvester]_deterministic(vault_context):
    """Test same session picks same note."""
    suggestions_1 = suggest(vault_context)
    suggestions_2 = suggest(vault_context)
    assert suggestions_1 == suggestions_2

def test_[harvester]_empty_vault(empty_vault_context):
    """Test graceful handling of empty vault."""
    suggestions = suggest(empty_vault_context)
    assert suggestions == []
```

---

## Implementation Checklist

### Phase 1: Question Harvester
- [x] Spec completed
- [ ] Create `src/geistfabrik/default_geists/code/question_harvester.py`
- [ ] Implement `extract_questions()` helper
- [ ] Add unit tests
- [ ] Add integration tests

### Phase 2: TODO Harvester
- [x] Spec completed
- [ ] Create `src/geistfabrik/default_geists/code/todo_harvester.py`
- [ ] Implement `extract_todos()` helper
- [ ] Add unit tests
- [ ] Add integration tests

### Phase 3: Quote Harvester
- [x] Spec completed
- [ ] Create `src/geistfabrik/default_geists/code/quote_harvester.py`
- [ ] Implement `extract_quotes()` helper
- [ ] Add unit tests
- [ ] Add integration tests

### Phase 4: Validation
- [ ] Run `./scripts/validate.sh`
- [ ] Fix any type errors or linting issues
- [ ] Ensure all tests pass

### Phase 5: Documentation
- [ ] Add to default geist configuration
- [ ] Update CHANGELOG
- [ ] Commit and push

---

## Future Enhancements

### More Harvesters

The pattern can be extended to other content types:

| Harvester | Extracts | Pattern | Provocation |
|-----------|----------|---------|-------------|
| **hypothesis_harvester** | "I wonder if..." | `r'I wonder if\s+([^.]+)'` | "What if you tested this?" |
| **claim_harvester** | Bold assertions | `r'\*\*(.+?)\*\*'` | "What if you questioned this?" |
| **definition_harvester** | "X is Y" / "X means Y" | `r'(\w+)\s+(?:is|means)\s+([^.]+)'` | "Does this still hold?" |
| **link_harvester** | `[[Unlinked]]` references | Check vault.resolve_link_target() | "What if you created this?" |

### Cross-Harvester Patterns

**Question-TODO Pairing**:
- Find questions near TODOs in same note
- Suggest: "This question has an actionable TODO"

**Quote-Question Resonance**:
- Find quotes that contain questions
- Suggest: "This quote asks: ..."

**Temporal Threading**:
- Track same TODO across multiple sessions
- Suggest: "You've been meaning to do this for 6 months"

---

## Comparison to Existing Geists

### vs question_generator
- **question_generator**: Generates NEW questions from declarative statements
- **question_harvester**: Extracts EXISTING questions from text
- **Relationship**: Complementary (create vs. surface)

### vs task_archaeology
- **task_archaeology**: Finds old checkbox tasks (`- [ ]` / `- [x]`)
- **todo_harvester**: Finds inline TODO markers in prose
- **Relationship**: Complementary (structured vs. unstructured tasks)

### vs No Direct Equivalent (quote_harvester)
- No existing geist extracts quotes
- Unique contribution to the ecosystem

---

## Design Principles Satisfied

### ✓ Muses, Not Oracles
- Surface content without interpretation
- Invite reflection, don't prescribe action
- "What if you [action] now?" not "You should [action]"

### ✓ Questions, Not Answers
- Provocations ask users to engage
- No solutions provided
- Open-ended temporal framing

### ✓ Sample, Don't Rank
- Random note selection (no ranking)
- Random item sampling (no prioritization)
- Treats all content equally

### ✓ Deterministic Randomness
- Same session date → same note → same items
- Reproducible for testing
- Consistent user experience

### ✓ Non-Destructive
- Read-only operations
- No note modifications
- Safe to run repeatedly

### ✓ Local-First
- Pure regex (no external dependencies)
- No API calls
- Fast execution

### ✓ Performance-Conscious
- O(1) notes read per session
- Fast regex extraction
- No cross-note analysis

---

## Conclusion

The Harvester Family introduces a new pattern to GeistFabrik: **extraction-based geists** that surface buried artifacts from random notes. By isolating specific content types (questions, TODOs, quotes) and presenting them with temporal framing, these geists create opportunities for reflection, rediscovery, and serendipitous insight.

All three harvesters share:
- Identical algorithmic structure
- Performance-conscious design
- Silent abstention when appropriate
- Deep respect for the "muses not oracles" philosophy

This pattern can be extended to many other content types, making the Harvester Family a foundational pattern for future geist development.

---

## References

### Inspiration Sources

1. **@pomeranian99 Tweet** (2022)
   - https://x.com/pomeranian99/status/1497969902581272577
   - Core observation about viewing only questions

2. **"The Power of Seeing Only the Questions"** (UX Design)
   - https://uxdesign.cc/the-power-of-seeing-only-the-questions-in-a-piece-of-writing-8f486d2c6d7d
   - Analysis of question extraction as thinking tool

### Technical References

3. **Python `re` Module Documentation**
   - https://docs.python.org/3/library/re.html
   - Regex patterns for text extraction

4. **Markdown Spec (CommonMark)**
   - https://commonmark.org/
   - Blockquote and list syntax

5. **TODO Comment Conventions**
   - Industry-standard markers: TODO, FIXME, HACK, NOTE, XXX
   - Used across programming languages and note-taking systems

---

**Version**: 2.0 (Expanded to Family)
**Date**: 2025-11-06
**Status**: ✅ Fully Implemented
