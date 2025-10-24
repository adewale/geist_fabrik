# Tracery Feature Comparison: JS, PyTracery, and GeistFabrik

**Created**: 2025-01-24
**Purpose**: Side-by-side comparison of Tracery implementations to track feature support as GeistFabrik's engine evolves.

## Executive Summary

This document compares three Tracery implementations:

1. **Tracery.js** - Original JavaScript implementation by Kate Compton (galaxykate/tracery)
2. **PyTracery** - Python port by Allison Parrish (aparrish/pytracery)
3. **GeistFabrik Tracery** - Custom implementation for vault-aware text generation

**Key Finding**: GeistFabrik implements standard Tracery's core expansion and modifier features, but intentionally omits state management (push-pop stacks) in favor of a novel `$vault.*` function system for dynamic vault queries.

## Quick Reference: Feature Support Matrix

| Feature Category | Tracery.js | PyTracery | GeistFabrik |
|-----------------|------------|-----------|-------------|
| **Core Expansion** | ✅ Full | ✅ Full | ✅ Full |
| **English Modifiers** | ✅ 5+ modifiers | ✅ 5+ modifiers | ✅ 5 modifiers |
| **Custom Modifiers** | ✅ Yes | ✅ Yes | ✅ Yes |
| **State Management** | ✅ Push-pop stacks | ✅ Push-pop stacks | ❌ None |
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
| **Parameterized modifiers** | Modifiers with args | `.replace(a,b)` | - | ✅ | ✅ | ❌ Not implemented |

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
| **Push (labeled action)** | `[key:value]` | Store value on stack | ✅ | ✅ | ❌ |
| **Pop action** | `[key:POP]` | Remove top value from stack | ✅ | ✅ | ❌ |
| **Unlabeled actions** | `[#symbol#]` | Execute without storing | ✅ | ✅ | ❌ |
| **Variable consistency** | Reuse same random choice | ✅ Via push-pop | ✅ Via push-pop | ❌ Each expansion independent |
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

### Not Implemented (Intentional) ❌

- [ ] Push-pop stack memory (`[var:value]`)
- [ ] POP actions (`[var:POP]`)
- [ ] Unlabeled actions (`[#symbol#]`)
- [ ] JSON format support
- [ ] Variable consistency across expansions
- [ ] Parameterized modifiers (`.replace(a,b)`)

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
- Any use of push-pop syntax (`[var:value]`)
- Any use of `.a`, `.s`, `.ed` modifiers (UPDATE: Now works! ✅)
- Parameterized modifiers
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

## When to Use Each Implementation

### Use **Tracery.js** When:

- ✅ Building web-based generators (Twitter bots, websites)
- ✅ Need maximum ecosystem compatibility
- ✅ Want to use tracery.io visual editor
- ✅ Integrating with JavaScript projects
- ✅ Need established, battle-tested library

### Use **PyTracery** When:

- ✅ Building Python-based text generators
- ✅ Need general-purpose generative text
- ✅ Want standard Tracery compatibility in Python
- ✅ Prefer Python ecosystem integration
- ✅ Don't need external data integration

### Use **GeistFabrik Tracery** When:

- ✅ Building suggestions for Obsidian vaults
- ✅ Need dynamic queries of vault content
- ✅ Want deterministic session-based output
- ✅ Prefer YAML over JSON
- ✅ Need structured outputs with metadata
- ✅ Building creative "muses" not general generators
- ✅ Don't need variable state management

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

### 2025-01-24 - Initial Version
- Compiled comprehensive comparison of all three implementations
- Documented all core features, modifiers, and advanced capabilities
- Created side-by-side comparison tables
- Added evolution tracking section for GeistFabrik development
- Included code examples and API comparisons

---

**Maintained by**: GeistFabrik Project
**Last updated**: 2025-01-24
**Version**: 1.0
