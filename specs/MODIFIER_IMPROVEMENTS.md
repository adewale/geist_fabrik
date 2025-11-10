# Tracery Modifier Improvements

## Overview

This document shows how the implementation of Tracery modifiers (`.s`, `.ed`, `.a`, `.capitalize`, `.capitalizeAll`) improves existing geists by enabling grammatically correct, natural-sounding suggestions.

## Implemented Modifiers

Based on `specs/tracery_research.md` (lines 640-676), we've implemented:

- **`.capitalize`** - Capitalize first letter ("hello" → "Hello")
- **`.capitalizeAll`** - Capitalize all words ("hello world" → "Hello World")
- **`.s`** - Pluralization ("cat" → "cats", "city" → "cities", "person" → "people")
- **`.ed`** - Past tense ("walk" → "walked", "try" → "tried", "go" → "went")
- **`.a`** - Article selection ("owl" → "an owl", "cat" → "a cat")

## Before/After Examples

### Example 1: Hub Explorer Geist

**Before** (no modifiers):
```yaml
origin:
  - "[[#hub#]] connects many ideas—what's the #unifying_theme#?"
  - "your hub note [[#hub#]] has grown—time to #action#?"
```

**Sample Output (Before):**
- "[[Project Planning]] connects many ideas—what's the common thread?"
- "your hub note [[Team Building]] has grown—time to review and refine?"

**After** (with modifiers):
```yaml
origin:
  - "[[#hub#]] #verb.s# many #noun.s#—what's the #unifying_theme#?"
  - "#sentence_start.capitalize# hub note [[#hub#]] has grown—time to #action#?"

sentence_start:
  - "your"
  - "this"

verb:
  - "connect"
  - "link"
  - "bridge"

noun:
  - "idea"
  - "concept"
  - "theme"
```

**Sample Output (After):**
- "[[Project Planning]] connects many ideas—what's the common thread?"
- "Your hub note [[Team Building]] has grown—time to review and refine?"

**Improvements:**
- Proper capitalization at sentence start
- Grammatically correct plurals ("idea" → "ideas")
- Consistent verb conjugation

---

### Example 2: Orphan Connector Geist

**Before** (no modifiers):
```yaml
origin:
  - "[[#orphan#]] has no connections yet—what if it relates to #topic#?"
  - "found an isolated note: [[#orphan#]]. could it be a #metaphor# for something?"
```

**Sample Output (Before):**
- "[[Brainstorming]] has no connections yet—what if it relates to your recent work?"
- "found an isolated note: [[Ideas]]. could it be a bridge for something?"

**After** (with modifiers):
```yaml
origin:
  - "[[#orphan#]] has no #connection.s# yet—what if it relates to #topic#?"
  - "#sentence_start.capitalize# isolated note: [[#orphan#]]. #suggestion.capitalize#"

sentence_start:
  - "found an"
  - "discovered an"

suggestion:
  - "could it be #metaphor.a# for something in your vault?"
  - "where does it fit in your thinking?"

connection:
  - "connection"
  - "link"

metaphor:
  - "bridge"
  - "seed"
  - "key"
```

**Sample Output (After):**
- "[[Brainstorming]] has no connections yet—what if it relates to your recent work?"
- "Found an isolated note: [[Ideas]]. Could it be a bridge for something in your vault?"

**Improvements:**
- Proper sentence capitalization
- Correct article usage ("a bridge" vs "an owl")
- Professional presentation

---

### Example 3: What If Geist

**Before** (no modifiers):
```yaml
origin:
  - "what if #subject# #verb# #object#?"

subject:
  - "you"
  - "your thinking"

verb:
  - "explored"
  - "questioned"

object:
  - "assumption"
  - "connection"
```

**Sample Output (Before):**
- "what if you explored assumption?"
- "what if your thinking questioned connection?"

**After** (with modifiers):
```yaml
origin:
  - "#question_start.capitalize# #subject# #verb.ed# the #object.s#?"
  - "#question_start.capitalize# #subject# #verb.ed# #object.a#?"

question_start:
  - "what if"

subject:
  - "you"
  - "your thinking"

verb:
  - "explore"
  - "question"
  - "invert"
  - "reframe"

object:
  - "assumption"
  - "connection"
  - "gap"
  - "pattern"
```

**Sample Output (After):**
- "What if you explored the assumptions?"
- "What if your thinking questioned an assumption?"
- "What if you inverted the patterns?"

**Improvements:**
- Proper capitalization for question starts
- Grammatically correct plurals
- Proper article usage ("an assumption" vs "a gap")
- Consistent past tense usage

---

### Example 4: Temporal Mirror Geist

**Before** (no modifiers):
```yaml
origin:
  - "#timeframe# you wrote [[#old_note#]]. today's [[#new_note#]] #relationship#"

timeframe:
  - "6 months ago"
  - "1 years ago"

relationship:
  - "might be the answer you were looking for"
```

**Sample Output (Before):**
- "6 months ago you wrote [[Early Ideas]]. today's [[Synthesis]] might be the answer you were looking for"
- "1 years ago you wrote [[Questions]]. today's [[Framework]] shows how far you've travelled"

**After** (with modifiers):
```yaml
origin:
  - "#time_amount# #time_unit.s# ago you #verb.ed# [[#old_note#]]. #today.capitalize# [[#new_note#]] #relationship#"

time_amount:
  - "6"
  - "12"

time_unit:
  - "month"

verb:
  - "write"
  - "create"
  - "draft"

today:
  - "today's"

relationship:
  - "might be the answer you were looking for"
  - "shows how far you've travelled"
```

**Sample Output (After):**
- "6 months ago you wrote [[Early Ideas]]. Today's [[Synthesis]] might be the answer you were looking for"
- "12 months ago you created [[Questions]]. Today's [[Framework]] shows how far you've travelled"

**Improvements:**
- Grammatically correct plurals ("months" not "month")
- Proper capitalization mid-sentence
- Consistent past tense ("wrote" not "write")

---

### Example 5: New Geist - Perspective Shifter

**With Modifiers (new capability):**
```yaml
type: geist-tracery
id: perspective_shifter
description: Suggests viewing notes through different lenses

tracery:
  origin:
    - "#action.capitalize# [[#note#]] #manner#"
    - "what if you #verb.ed# [[#note#]] as #metaphor.a#?"
    - "try #verb_ing# [[#note#]] like #comparison.a#"

  action:
    - "view"
    - "read"
    - "approach"

  manner:
    - "from #perspective.a# perspective"
    - "through the lens of #concept#"

  perspective:
    - "opposite"
    - "historical"
    - "future"

  concept:
    - "systems thinking"
    - "first principles"

  verb:
    - "treat"
    - "frame"
    - "understand"

  metaphor:
    - "experiment"
    - "organism"
    - "garden"

  comparison:
    - "conversation"
    - "journey"

  note:
    - "$vault.sample_notes(1)"
```

**Sample Output:**
- "View [[Project Planning]] from an opposite perspective"
- "What if you treated [[Ideas]] as an experiment?"
- "Try approaching [[Strategy]] like a conversation"

**Benefits:**
- Natural-sounding suggestions
- Grammatically correct articles
- Professional capitalization
- Flexible template patterns

---

## Summary of Improvements

### Grammar Correctness
- **Plurals**: "idea" → "ideas", "connection" → "connections"
- **Articles**: "owl" → "an owl", "bridge" → "a bridge"
- **Tense**: "explore" → "explored", "try" → "tried"

### Professional Presentation
- **Capitalization**: Sentences start with capital letters
- **Consistency**: Uniform style across all suggestions

### Creative Flexibility
- **Composability**: Mix and match modifiers (`.s.capitalize`)
- **Expressiveness**: More natural language patterns
- **Variety**: Same grammar generates more diverse outputs

### User Experience
- **Readability**: Suggestions read like natural language
- **Professionalism**: No awkward grammar mistakes
- **Trust**: Well-formed text increases credibility

---

## Technical Implementation

Location: `src/geistfabrik/tracery.py`

**Key Methods:**
- `_pluralize()`: Handles regular/irregular plurals (person→people, city→cities)
- `_past_tense()`: Converts verbs to past tense (walk→walked, go→went)
- `_article()`: Selects a/an based on vowel sounds
- `_capitalize()`: Capitalizes first letter
- `_capitalize_all()`: Capitalizes all words

**Modifier Syntax:**
```yaml
# Single modifier
text: "#word.capitalize#"

# Chained modifiers (left to right)
text: "#animal.s.capitalize#"  # plural then capitalize → "Cats"

# Multiple modifiers in template
text: "#subject.capitalize# #verb.ed# #object.a#"
```

**Test Coverage:**
- 10+ new tests in `tests/unit/test_tracery.py`
- Tests for each modifier type
- Tests for modifier chaining
- Tests for integration with geists

---

## Migration Guide for Existing Geists

### 1. Identify Grammar Issues
Look for:
- Hardcoded plurals in templates
- Missing capitalization at sentence starts
- Awkward article usage

### 2. Extract Base Forms
Convert:
```yaml
# Before
noun: ["ideas", "connections"]

# After
noun: ["idea", "connection"]
# Use: #noun.s#
```

### 3. Add Modifiers
```yaml
# Before
origin: "your hub connects many ideas"

# After
origin: "#possessive.capitalize# hub #verb.s# many #noun.s#"
possessive: ["your", "this"]
verb: ["connect", "link"]
noun: ["idea", "theme"]
```

### 4. Test Output
Use `uv run geistfabrik test <geist_id>` to verify natural output

---

## Conclusion

The implementation of Tracery modifiers (Tier 1: Foundational Geist Enablers from the research) unlocks:

1. **Natural Language**: Grammatically correct suggestions
2. **Flexibility**: Compose text dynamically with proper grammar
3. **Professionalism**: Well-formed output increases trust
4. **Creativity**: More expressive geist templates

This brings GeistFabrik's Tracery implementation to parity with pytracery's `base_english` modifiers, as identified in `specs/tracery_research.md`.
