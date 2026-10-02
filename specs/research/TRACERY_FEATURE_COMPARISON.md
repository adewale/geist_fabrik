# Tracery Feature Comparison: JS, PyTracery, and GeistFabrik

**Created**: 2025-01-24
**Purpose**: Side-by-side comparison of Tracery implementations to track feature support as GeistFabrik's engine evolves.

## Executive Summary

This document compares three Tracery implementations:

1. **Tracery.js** - Original JavaScript implementation by Kate Compton (galaxykate/tracery)
2. **PyTracery** - Python port by Allison Parrish (aparrish/pytracery)
3. **GeistFabrik Tracery** - Custom implementation for vault-aware text generation

**Key Finding**: GeistFabrik implements standard Tracery's core expansion and modifier features plus a novel `$vault.*` function system for dynamic vault queries.

> **Update (2026-10):** GeistFabrik now supports Tracery save actions: `[key:rule]`, `[key:POP]` and tag preactions (`#[key:rule]symbol#`). Differences from tracery.js: only `[identifier:` starts an action (so `[[wikilinks]]` stay literal), a save holds one value (no comma lists), saved text is reused without re-expansion, and `$vault` calls are rejected inside actions. Rows below marked ❌ for push-pop predate this; see `specs/tracery_research.md` (Save actions).

## Quick Reference: Feature Support Matrix

| Feature Category | Tracery.js | PyTracery | GeistFabrik |
|-----------------|------------|-----------|-------------|
| **Core Expansion** | ✅ Full | ✅ Full | ✅ Full |
| **English Modifiers** | ✅ 5+ modifiers | ✅ 5+ modifiers | ✅ 5 modifiers |
| **Custom Modifiers** | ✅ Yes | ✅ Yes | ✅ Yes |
| **State Management** | ✅ Push-pop stacks | ✅ Push-pop stacks | ✅ Save actions (one value per save) |
| **Dynamic Functions** | ❌ None | ❌ None | ✅ `$vault.*` |
| **Format** | JSON | JSON/Dict | YAML |

## Detailed Feature Comparison

### 1. Core Grammar Features

| Feature | Description | Tracery.js | PyTracery | GeistFabrik | Notes |
|---------|-------------|------------|-----------|-------------|-------|
| **Symbol expansion** | `#symbol#` syntax | ✅ | ✅ | ✅ | Identical syntax across all |
| **Recursive expansion** | Symbols can reference other symbols | ✅ | ✅ | ✅ | All support arbitrary depth |
| **Random selection** | Choose from multiple rules | ✅ | ✅ | ✅ | All implementations |
| **Deterministic seeding** | Same seed = same output | ✅ Manual | ✅ Manual | ✅ Built-in | GF uses session-based seed |
| **Recursion limiting** | Prevent infinite loops | ✅ | ✅ | ✅ Max 50 | GF: explicit `max_depth=50` |
| **Multiple rules per symbol** | Array of options | ✅ | ✅ | ✅ | All support lists |
| **Nested symbols** | Symbols within rules | ✅ | ✅ | ✅ | All support composition |
| **Empty rules** | Symbol with no expansion | ✅ | ✅ | ✅ | Returns empty string |

### 2. Modifiers

Modifiers transform expanded text using `.modifier` syntax (e.g., `#word.capitalize#`).

| Modifier | Function | Example Input | Example Output | Tracery.js | PyTracery | GeistFabrik |
|----------|----------|---------------|----------------|------------|-----------|-------------|
| **`.capitalize`** | Capitalize first letter | "hello" | "Hello" | ✅ | ✅ | ✅ |
| **`.capitalizeAll`** | Capitalize each word | "hello world" | "Hello World" | ✅ | ✅ | ✅ |
| **`.s`** | Pluralize noun | "cat" | "cats" | ✅ | ✅ | ✅ |
| **`.ed`** | Past tense verb | "walk" | "walked" | ✅ | ✅ | ✅ |
| **`.a`** | Add article (a/an) | "owl" | "an owl" | ✅ | ✅ | ✅ |
| **Modifier chaining** | Multiple modifiers | "#word.s.capitalize#" | "Cats" | ✅ | ✅ | ✅ |
| **Custom modifiers** | User-defined transforms | `.reverse`, `.shout` | Varies | ✅ | ✅ via `add_modifiers()` | ✅ via `add_modifier()` |
| **Parameterised modifiers** | Modifiers with args | `.replace(a,b)` | - | ✅ | ✅ | ❌ Not implemented |

**Modifier Implementation Details:**

All three implementations include these base English modifiers:
- **Pluralization** (`.s`): Handles regular plurals, some irregulars (person→people, child→children)
- **Past tense** (`.ed`): Handles regular verbs, common irregulars (go→went, see→saw)
- **Article selection** (`.a`): Detects vowel sounds, handles special cases (honest→an honest)

**GeistFabrik Specific**:
- Modifiers defined in `tracery.py` lines 37-49
- Includes 8 irregular plurals, 29 irregular verbs
- Custom modifiers added via `engine.add_modifier(name, func)`

### 3. State Management & Actions

State management allows storing and reusing generated values across an expansion.

| Feature | Syntax | Description | Tracery.js | PyTracery | GeistFabrik |
|---------|--------|-------------|------------|-----------|-------------|
| **Push (labelled action)** | `[key:value]` | Store value on stack | ✅ | ✅ | ✅ |
| **Pop action** | `[key:POP]` | Remove top value from stack | ✅ | ✅ | ✅ |
| **Unlabeled actions** | `[#symbol#]` | Execute without storing | ✅ | ✅ | ❌ |
| **Variable consistency** | Reuse same random choice | ✅ Via push-pop | ✅ Via push-pop | ✅ Via save actions |
| **Nested contexts** | Temporary variable override | ✅ | ✅ | ❌ |

**Example of Push-Pop**:

```json
{
  "origin": "#[hero:#name#]story#",
  "story": "#hero# found treasure. #hero# was happy.",
  "name": ["Alice", "Bob", "Charlie"]
}
```

Output: "Alice found treasure. Alice was happy." (same name used twice)

**GeistFabrik Limitation**: Cannot maintain variable consistency. Each `#hero#` expansion would be independent.

**Workaround in GeistFabrik**: Use separate symbols or vault functions.

### 4. Dynamic Content & Functions

| Feature | Syntax | Description | Tracery.js | PyTracery | GeistFabrik |
|---------|--------|-------------|------------|-----------|-------------|
| **Vault function calls** | `$vault.func(args)` | Call registered functions at expansion time | ❌ | ❌ | ✅ Unique feature |
| **Dynamic queries** | Query external data | Not in grammar | ❌ | ❌ | ✅ Via vault functions |
| **Integer arguments** | `func(5)` | Pass numbers | N/A | N/A | ✅ |
| **String arguments** | `func("tag", 2)` | Pass strings | N/A | N/A | ✅ |
| **List returns** | Function returns array | N/A | N/A | ✅ Formatted as "A, B, and C" |
| **Smart formatting** | Wikilink generation | N/A | N/A | ✅ `[[Note]]` format |

**GeistFabrik's Killer Feature**: The `$vault.*` system enables declarative grammars to query vault content dynamically:

```yaml
tracery:
  origin: "What if you combined [[#note1#]] with [[#note2#]]?"
  note1: ["$vault.sample_notes(1)"]
  note2: ["$vault.sample_notes(1)"]
```

Functions execute at expansion time, enabling queries like:
- `$vault.recent_notes(7)` - Notes modified in last 7 days
- `$vault.semantic_search("quantum", 3)` - Semantic similarity
- `$vault.hubs(5)` - Most connected notes
- `$vault.orphans(3)` - Notes with no links

### 5. File Format & Structure

| Feature | Tracery.js | PyTracery | GeistFabrik |
|---------|------------|-----------|-------------|
| **Format** | JSON | JSON / Python dict | YAML |
| **Metadata support** | ❌ Grammar only | ❌ Grammar only | ✅ `id`, `count`, `type`, `description` |
| **Multiple grammars per file** | ❌ | ❌ | ❌ One geist per file |
| **File extension** | `.json` | `.json` | `.yaml` |
| **Comments** | ❌ JSON no comments | ❌ | ✅ YAML supports comments |
| **Multiline strings** | ❌ Escaped | ❌ Escaped | ✅ YAML `\|` syntax |

**Example Format Comparison**:

**Tracery.js / PyTracery (JSON)**:
```json
{
  "origin": "#greeting.capitalize#, #animal.a#!",
  "greeting": ["hello", "greetings"],
  "animal": ["unicorn", "owl"]
}
```

**GeistFabrik (YAML with metadata)**:
```yaml
type: geist-tracery
id: example_geist
count: 3
description: "Example demonstrating GeistFabrik format"

tracery:
  origin:
    - "#greeting#, #animal.a#!"
  greeting:
    - "Hello"
    - "Greetings"
  animal:
    - "unicorn"
    - "owl"
```

### 6. Output & Integration

| Feature | Tracery.js | PyTracery | GeistFabrik |
|---------|------------|-----------|-------------|
| **Return type** | String | String | `Suggestion` object |
| **Note reference tracking** | ❌ | ❌ | ✅ Extracts `[[wikilinks]]` |
| **Multiple outputs** | Manual loop | Manual loop | ✅ `count` parameter |
| **Error handling** | Throws | Throws | ✅ Logs and continues |
| **Geist identification** | N/A | N/A | ✅ `geist_id` in output |
| **Timeout handling** | ❌ | ❌ | ✅ Via executor wrapper |
| **Failure tracking** | ❌ | ❌ | ✅ Auto-disable after 3 fails |

**GeistFabrik Integration**:

```python
# Returns structured suggestions with metadata
suggestions = geist.suggest(vault)
# [Suggestion(
#     text="What if you combined [[Note A]] with [[Note B]]?",
#     notes=["Note A", "Note B"],
#     geist_id="note_combinations"
# )]
```

### 7. Advanced Features

| Feature | Description | Tracery.js | PyTracery | GeistFabrik |
|---------|-------------|------------|-----------|-------------|
| **Weighted distributions** | Some rules more likely | ❌ Equal probability | ❌ Equal probability | ❌ Workaround: repeat options |
| **Conditional expansion** | If-then rules | ❌ | ❌ | ❌ Use code geists |
| **Grammar composition** | Import/share symbols | ❌ | ❌ | ❌ Workaround: vault functions |
| **Visual editor** | GUI for authoring | ✅ tracery.io | ❌ | ❌ |
| **Command-line tool** | Run from terminal | ✅ Node package | ✅ Module execution | ✅ Part of CLI |
| **Dry-run / testing** | Test grammar output | ✅ | ✅ | ✅ `test` command |
| **Embedding in other tools** | Use as library | ✅ | ✅ | ✅ Part of GeistFabrik |

## Implementation Comparison

### Code Size & Complexity

| Implementation | Core Code | Modifiers | Dependencies |
|----------------|-----------|-----------|--------------|
| **Tracery.js** | ~300 lines | Built-in | None (vanilla JS) |
| **PyTracery** | ~400 lines | Separate module | None (stdlib only) |
| **GeistFabrik** | 577 lines | Integrated | PyYAML |

### API Comparison

**Tracery.js**:
```javascript
const tracery = require('tracery-grammar');
const grammar = tracery.createGrammar(rules);
const output = grammar.flatten('#origin#');
```

**PyTracery**:
```python
import tracery
from tracery.modifiers import base_english

grammar = tracery.Grammar(rules)
grammar.add_modifiers(base_english)
output = grammar.flatten('#origin#')
```

**GeistFabrik**:
```python
from geistfabrik.tracery import TraceryGeist, TraceryEngine

# Option 1: Via geist (YAML + metadata)
geist = TraceryGeist.from_yaml("geist.yaml", seed=42)
suggestions = geist.suggest(vault_context)

# Option 2: Direct engine use
engine = TraceryEngine(grammar, seed=42)
engine.set_vault_context(vault)
text = engine.expand("#origin#")
```

## Feature Evolution Tracking

This section tracks features as they're added to GeistFabrik.

### Currently Implemented ✅

- [x] Basic symbol expansion (`#symbol#`)
- [x] Recursive expansion with depth limiting
- [x] Deterministic seeding (session-based)
- [x] 5 English modifiers (capitalize, capitalizeAll, s, ed, a)
- [x] Custom modifier support
- [x] Modifier chaining
- [x] Vault function calls (`$vault.*`)
- [x] Smart list formatting
- [x] Wikilink extraction
- [x] YAML format with metadata
- [x] Multiple suggestions per geist (`count` parameter)
- [x] Structured output (`Suggestion` objects)
- [x] Save actions (`[var:value]`, `[var:POP]`, preactions)

### Not Implemented (Intentional) ❌

- [ ] Unlabeled actions (`[#symbol#]`)
- [ ] JSON format support
- [ ] Variable consistency across expansions
- [ ] Parameterised modifiers (`.replace(a,b)`)

### Potential Future Additions 🔮

- [ ] Obsidian-specific modifiers (`.wikilink`, `.embed`, `.tag`)
- [ ] Weighted distributions (custom YAML syntax)
- [ ] Grammar composition / shared fragments
- [ ] Temporal modifiers (`.ago`, date formatting)
- [ ] Number formatting (`.spell`, `.ordinal`)
- [ ] External wordlist loading
- [ ] Visual emphasis helpers (unicode symbols)

## Compatibility Analysis

### Standard Tracery → GeistFabrik

**What Works**:
- Basic symbol expansion
- Simple grammars without modifiers
- Random selection

**What Breaks**:
- Push-pop values containing commas (one value per save in GeistFabrik)
- Any use of `.a`, `.s`, `.ed` modifiers (UPDATE: Now works! ✅)
- Parameterised modifiers
- JSON format (needs conversion to YAML + metadata)

**Conversion Difficulty**: Medium
- Must manually wrap in YAML structure
- Must remove/simplify state management
- Can use modifiers now (as of current implementation)

### GeistFabrik → Standard Tracery

**What Works**:
- Pure Tracery grammars (no vault functions)
- Simple symbol expansion
- Modifiers (now that GF implements them)

**What Breaks**:
- All `$vault.*` function calls (no equivalent)
- Metadata fields (`id`, `count`, etc.)
- `Suggestion` objects (standard Tracery returns strings)
- YAML format (needs conversion to JSON)

**Conversion Difficulty**: Easy for simple grammars, impossible for vault-aware ones.

## Deep Dive: Push-Pop Stacks and Grammar Complexity

The presence or absence of push-pop stacks fundamentally changes what kinds of grammars are expressible and how complex narratives can be constructed.

### What Push-Pop Stacks Enable

Push-pop stacks in Tracery.js and PyTracery allow **storing generated values for reuse within a single expansion**. This creates a form of temporary memory during text generation.

**Basic Syntax**:
- `[key:value]` - Push `value` onto the stack for `key`
- `[key:POP]` - Pop the top value off the stack for `key`
- `#key#` - Reference the current top value on the stack

### Grammar Complexity: With vs Without Stacks

#### Level 1: Simple Grammars (No State Needed)

**Both implementations can handle:**

```json
{
  "origin": "What if #concept# led to #outcome#?",
  "concept": ["curiosity", "fear", "ambition"],
  "outcome": ["clarity", "confusion", "transformation"]
}
```

Output examples:
- "What if curiosity led to clarity?"
- "What if fear led to transformation?"

**No difference** - each symbol expands independently, no memory required.

---

#### Level 2: Character Consistency (Requires State)

**Standard Tracery with push-pop:**

```json
{
  "origin": "#[character:#name#][trait:#personality#]story#",
  "story": "#character.capitalize# was known for being #trait#. Everyone loved #character# because #trait# people are trustworthy. When danger came, #character# stayed true to being #trait#.",
  "name": ["alice", "bob", "charlie"],
  "personality": ["brave", "clever", "kind"]
}
```

Output: "Alice was known for being brave. Everyone loved Alice because brave people are trustworthy. When danger came, Alice stayed true to being brave."

**Key feature**: Same character name and trait throughout the narrative.

**GeistFabrik without push-pop:**

```yaml
tracery:
  origin: "#character# was known for being #trait#. Everyone loved #character# because #trait# people are trustworthy."
  character: ["Alice", "Bob", "Charlie"]
  trait: ["brave", "clever", "kind"]
```

Output: "Alice was known for being brave. Everyone loved Bob because kind people are trustworthy."

**Breaks coherence** - different characters and traits in same sentence.

**GeistFabrik workaround (verbose):**

```yaml
tracery:
  origin: "#char1_brave#"
  char1_brave: ["Alice was known for being brave. Everyone loved Alice because brave people are trustworthy."]
  # Must pre-generate ALL combinations - explosion of symbols
```

This doesn't scale. For 3 names × 3 traits = 9 pre-written combinations. Add more variables and it becomes unmaintainable.

---

#### Level 3: Nested Contexts (Requires Stack Depth)

**Standard Tracery with push-pop:**

```json
{
  "origin": "[hero:Alice]In the outer story, #hero# met [hero:Bob]#hero#. The inner #hero# greeted the outer [hero:POP]#hero#.",
  "hero": ["someone"]
}
```

Output: "In the outer story, Alice met Bob. The inner Bob greeted the outer Alice."

**Stack operations**:
1. Push "Alice" onto hero stack → `hero = ["Alice"]`
2. Reference `#hero#` → "Alice"
3. Push "Bob" onto hero stack → `hero = ["Alice", "Bob"]`
4. Reference `#hero#` → "Bob" (top of stack)
5. Reference `#hero#` → "Bob"
6. Pop hero stack → `hero = ["Alice"]`
7. Reference `#hero#` → "Alice"

**This enables**:
- Stories within stories
- Temporary context switches
- Recursive narrative structures
- Frame stories

**GeistFabrik**: Cannot express this pattern. No way to maintain multiple context levels.

---

#### Level 4: Procedural Character Generation

**Standard Tracery with push-pop:**

```json
{
  "origin": "#[name:#names#][job:#jobs#][weapon:#weapons#]character# set off on a quest.",
  "character": "#name# the #job#, wielding #weapon#,",
  "names": ["Aria", "Finn", "Luna"],
  "jobs": ["blacksmith", "scholar", "ranger"],
  "weapons": ["a hammer", "a staff", "a bow"]
}
```

Output: "Aria the blacksmith, wielding a hammer, set off on a quest."

**Generate once, reference many times**. The character attributes are chosen randomly but remain consistent throughout.

**Extended example with relationships:**

```json
{
  "origin": "#[hero:#name#][companion:#name#]story#",
  "story": "#hero# and #companion# were unlikely allies. #hero# was bold while #companion# was cautious. Together, #hero# and #companion# faced the dragon.",
  "name": ["Aria", "Finn", "Luna", "Kael"]
}
```

Output: "Aria and Finn were unlikely allies. Aria was bold while Finn was cautious. Together, Aria and Finn faced the dragon."

**Without push-pop**: Cannot guarantee hero ≠ companion, or maintain consistency across multiple references.

---

#### Level 5: Complex Narrative with Multiple Characters

**Standard Tracery with push-pop:**

```json
{
  "origin": "#[hero:#name#][villain:#name#][mentor:#name#]act1# #act2# #act3#",
  "act1": "In a small village, #hero# dreamed of adventure. #hero#'s mentor, #mentor#, warned of the dark wizard #villain#.",
  "act2": "#hero# set out to confront #villain#, remembering #mentor#'s teachings.",
  "act3": "In the final battle, #hero# defeated #villain# and returned to thank #mentor#.",
  "name": ["Aria", "Finn", "Luna", "Kael", "Zara"]
}
```

Output: "In a small village, Aria dreamed of adventure. Aria's mentor, Kael, warned of the dark wizard Finn. Aria set out to confront Finn, remembering Kael's teachings. In the final battle, Aria defeated Finn and returned to thank Kael."

**This enables**:
- Multi-character narratives
- Relationship tracking (hero knows mentor, fights villain)
- Character continuity across acts
- Complex story structure

**GeistFabrik limitation**: Cannot maintain character identity across multiple references. Would need either:
1. Pre-written templates with baked-in names (no randomness)
2. One sentence maximum (no multi-act structure)
3. Accept incoherence (different name each time)

---

#### Level 6: Pronoun Agreement and Grammar Consistency

**Standard Tracery with push-pop:**

```json
{
  "origin": "#[hero:#character#]story#",
  "story": "#hero.name# picked up #hero.possessive# sword. #hero.pronoun.capitalize# was ready.",
  "character": [
    {"name": "Alice", "pronoun": "she", "possessive": "her"},
    {"name": "Bob", "pronoun": "he", "possessive": "his"}
  ]
}
```

With a modified Tracery that supports object properties, this could output:
- "Alice picked up her sword. She was ready."
- "Bob picked up his sword. He was ready."

**Even without object support**, can use parallel stacks:

```json
{
  "origin": "#[name:#names#][pronoun:#pronouns#][possessive:#possessives#]story#",
  "story": "#name# picked up #possessive# sword. #pronoun.capitalize# was ready.",
  "names": ["Alice", "Bob"],
  "pronouns": ["she", "he"],
  "possessives": ["her", "his"]
}
```

**Problem**: No guarantee of alignment (might get "Alice...his...he"). Need coordinated selection.

**Better pattern with Tracery's inline actions:**

```json
{
  "origin": "#[#setAlice#]story#",
  "setAlice": "[name:Alice][pronoun:she][possessive:her]",
  "story": "#name# picked up #possessive# sword. #pronoun.capitalize# was ready."
}
```

Now all pronouns align with the name.

**GeistFabrik**: Cannot implement this pattern. Would need vault functions to return coordinated bundles.

---

### Grammar Patterns Enabled by Push-Pop

| Pattern | Description | Possible without push-pop? |
|---------|-------------|---------------------------|
| **Identity continuity** | Same entity referenced multiple times | ❌ No |
| **Relationship networks** | Multiple distinct entities with relationships | ❌ No |
| **Recursive narratives** | Stories within stories | ❌ No |
| **Grammatical agreement** | Pronouns matching gender/number | ❌ Very difficult |
| **Attribute bundles** | Multiple correlated properties | ⚠️ Pre-generated only |
| **Scene setting** | Establish context, then build on it | ⚠️ Limited |
| **Dialogue** | Multiple speakers maintaining identity | ❌ No |
| **Character arcs** | Same character changing over time | ❌ No |

### Why GeistFabrik Omits Push-Pop

**Design trade-off**: GeistFabrik optimizes for **short, provocative questions** rather than **coherent narratives**.

**Typical GeistFabrik output**:
```
"What if you combined [[Note A]] with [[Note B]]?"
"Consider revisiting [[Old Note]] in light of [[Recent Note]]."
"Your most connected notes are [[Hub 1]], [[Hub 2]], and [[Hub 3]]."
```

These patterns **don't require** character consistency or narrative coherence:
- Single sentence or question
- Notes are distinct entities (not "characters" that reappear)
- Vault functions provide the coherence (semantic relationships, not grammatical)

**GeistFabrik's coherence comes from the vault, not the grammar**:
- Push-pop provides internal grammatical coherence
- `$vault.*` functions provide external semantic coherence

**Example**:
```yaml
origin: "What if [[#note1#]] and [[#note2#]] are both really about #theme#?"
note1: ["$vault.sample_notes(1)"]
note2: ["$vault.sample_notes(1)"]
theme: ["power", "transformation", "connection"]
```

The two notes are **meaningfully different** (selected separately by vault), but the theme **doesn't need** to be consistent with anything - it's just a provocative lens.

### Implications for Grammar Authors

**With push-pop (Standard Tracery)**:
- Can write grammars for stories, dialogue, characters
- Grammar itself maintains coherence
- More complex grammar structure
- Better for narrative generation

**Without push-pop (GeistFabrik)**:
- Keep templates short (one sentence)
- Let vault functions provide coherence
- Simpler grammar structure
- Better for provocative questions about real content

### Could GeistFabrik Add Push-Pop?

**Technically**: Yes, the implementation is well-understood.

**Philosophically**: Probably not. It would enable:
- ✅ More complex multi-sentence suggestions
- ✅ Character-like entity tracking
- ❌ But risk of "mini-stories" instead of provocations
- ❌ Drift toward narrative generation (not the goal)
- ❌ More complex grammars (higher barrier to authoring)

**Alternative**: If narrative coherence is needed, use **code geists** which have full Python state management, not limited to Tracery's stack model.

## Design Philosophy Differences

### Standard Tracery Philosophy

**Goal**: Simple, accessible generative text tool
**Audience**: Writers, artists, hobbyists
**Approach**: Maximum features for creative text generation
**Complexity**: Moderate (supports state, actions, complex grammars)

### GeistFabrik Philosophy

**Goal**: Provocative suggestions for personal knowledge management
**Audience**: Obsidian users, knowledge workers
**Approach**: Minimal grammar + rich vault integration
**Complexity**: Simpler grammars, richer context
**Unique Value**: Questions, not answers; muses, not oracles

## References & Resources

### Official Resources

**Tracery.js**:
- Repository: https://github.com/galaxykate/tracery
- Official site: https://tracery.io
- Visual editor: https://tracery.io/editor
- Academic paper: "Tracery: An Author-Focused Generative Text Tool" (Compton et al., 2015)

**PyTracery**:
- Repository: https://github.com/aparrish/pytracery
- PyPI: https://pypi.org/project/tracery/
- Tutorial: https://www.brettwitty.net/tracery-in-python.html
- Notebook tutorial: https://github.com/aparrish/rwet/blob/master/tracery-and-python.ipynb

**GeistFabrik**:
- Implementation: `src/geistfabrik/tracery.py`
- Documentation: `docs/TRACERY_COMPARISON.md`
- Research: `specs/tracery_research.md`
- Examples: `src/geistfabrik/default_geists/tracery/`

### Tutorials & Learning

- Tracery tutorial: http://air.decontextualize.com/tracery/
- Sculpting Generative Text: https://www.andrewzigler.com/blog/sculpting-generative-text-with-tracery/
- Learning Tracery series: https://videlais.com/2018/10/04/learning-tracery-part-1-example-and-definitions/

## Change Log

### 2025-01-24 - Version 1.1
- Removed "When to Use Each" decision guide section
- Added comprehensive "Deep Dive: Push-Pop Stacks and Grammar Complexity" section
- Documented 6 levels of grammar complexity with concrete examples
- Analyzed implications of push-pop absence for GeistFabrik
- Created pattern matrix showing what's possible with/without stacks
- Explained design trade-off: vault coherence vs grammatical coherence

### 2025-01-24 - Version 1.0 (Initial)
- Compiled comprehensive comparison of all three implementations
- Documented all core features, modifiers, and advanced capabilities
- Created side-by-side comparison tables
- Added evolution tracking section for GeistFabrik development
- Included code examples and API comparisons

---

**Maintained by**: GeistFabrik Project
**Last updated**: 2025-01-24
**Version**: 1.1
