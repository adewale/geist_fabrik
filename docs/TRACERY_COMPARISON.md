# Tracery Implementation Comparison

This document provides a detailed comparison between GeistFabrik's custom Tracery-like implementation and standard Tracery (original JavaScript version and pytracery Python port).

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Feature Comparison Matrix](#feature-comparison-matrix)
3. [Syntax Differences](#syntax-differences)
4. [Code Examples](#code-examples)
5. [Performance Considerations](#performance-considerations)
6. [Compatibility Analysis](#compatibility-analysis)
7. [When to Use Each Implementation](#when-to-use-each-implementation)
8. [Technical Deep Dive](#technical-deep-dive)

---

## Executive Summary

**GeistFabrik's Implementation** is a custom, lightweight Tracery-like engine (283 lines) built specifically for vault-aware text generation. It intentionally omits standard Tracery features (modifiers, stack memory) in favor of a novel `$vault.*` function call system that enables declarative grammars to query Obsidian vaults.

**Standard Tracery** is a mature, feature-rich generative grammar system with widespread adoption, supporting modifiers, push-pop stack memory, and extensive language ports.

**Key Difference**: GeistFabrik's implementation is **not** standard Tracery. It's a Tracery-*inspired* engine optimized for a specific use case (vault-aware suggestion generation) rather than general-purpose text generation.

---

## Feature Comparison Matrix

| Feature | GeistFabrik Tracery | Standard Tracery (pytracery) | Notes |
|---------|--------------------|-----------------------------|-------|
| **Basic Symbol Expansion** | ✅ `#symbol#` | ✅ `#symbol#` | Identical syntax |
| **Recursive Expansion** | ✅ Full support | ✅ Full support | Identical behavior |
| **Random Selection** | ✅ Deterministic seed | ✅ Optional seed | GF uses session-based seeding |
| **Grammar Format** | YAML | JSON | Different file formats |
| **Modifiers** | ❌ None | ✅ `.capitalize`, `.s`, `.ed`, `.a`, etc. | GF has no modifier support |
| **Custom Modifiers** | ❌ Not supported | ✅ `grammar.add_modifiers()` | GF cannot add modifiers |
| **Push-Pop Stack** | ❌ None | ✅ `[variable:value]` syntax | GF has no variable memory |
| **POP Action** | ❌ None | ✅ `[variable:POP]` | GF has no stack operations |
| **Vault Functions** | ✅ **`$vault.function()`** | ❌ Not available | GF's killer feature |
| **Integration** | Returns `Suggestion` objects | Returns strings | GF tightly coupled to domain |
| **Metadata** | ✅ `id`, `count`, `description` | ❌ Grammar only | GF supports geist metadata |
| **Execution Context** | ✅ `VaultContext` injection | ❌ Standalone | GF receives vault context |
| **Timeout Handling** | ✅ Via `TraceryGeistLoader` | ❌ No timeout | GF integrates with executor |
| **Recursion Limits** | ✅ `max_depth=50` | ✅ Configurable | Both prevent infinite loops |
| **List Formatting** | ✅ Smart `[[note]]` linking | ❌ Basic join | GF handles Note objects specially |

### Summary of Differences

**Unique to GeistFabrik:**
- `$vault.function_name(args)` calls for querying vault
- YAML format with metadata (`id`, `count`, `suggestions_per_invocation`)
- Returns `Suggestion` objects instead of raw strings
- Automatic Obsidian `[[wikilink]]` extraction
- Smart list formatting for Note objects

**Unique to Standard Tracery:**
- Text modifiers (`.capitalize`, `.s`, `.ed`, `.a`, `.capitalizeAll`)
- Push-pop stack memory for variable persistence `[var:value]`
- POP action for stack management `[var:POP]`
- Custom modifier registration
- JSON format (standard across all Tracery ports)

---

## Syntax Differences

### 1. File Format

**GeistFabrik (YAML):**
```yaml
type: geist-tracery
id: example_geist
description: A sample geist demonstrating GeistFabrik syntax
suggestions_per_invocation: 3

tracery:
  origin:
    - "What if you combined [[#note1#]] with [[#note2#]]?"
    - "Consider #action# [[#note#]]."

  note1:
    - "$vault.sample_notes(1)"

  note2:
    - "$vault.sample_notes(1)"

  note:
    - "$vault.recent_notes(7)"

  action:
    - "revisiting"
    - "expanding"
    - "linking"
```

**Standard Tracery (JSON):**
```json
{
  "origin": [
    "#greeting.capitalize#, #character.a#!",
    "#character.capitalize# said #greeting#."
  ],
  "greeting": ["hello", "greetings", "howdy"],
  "character": ["#adjective# #animal#"],
  "adjective": ["brave", "clever", "mysterious"],
  "animal": ["fox", "rabbit", "owl"]
}
```

### 2. Variable Assignment and Memory

**Standard Tracery** uses push-pop stack syntax for temporary variables:

```json
{
  "origin": "#[hero:#name#][heroPet:#animal#]story#",
  "story": "#hero# traveled with their pet #heroPet#. #hero# was brave.",
  "name": ["Arjun", "Lina", "Azra"],
  "animal": ["unicorn", "raven", "duck"]
}
```

This ensures "Arjun" is used consistently for `#hero#` throughout the expansion, then popped when complete.

**GeistFabrik** has **no variable memory**. Each symbol expansion is independent:

```yaml
tracery:
  origin: "#character# met #character#"  # Could produce "fox met owl" - different each time
  character: ["fox", "owl", "rabbit"]
```

If you need consistent values in GeistFabrik, you must use separate symbols:

```yaml
tracery:
  origin: "#char1# met #char2#"
  char1: ["fox", "owl", "rabbit"]
  char2: ["fox", "owl", "rabbit"]
```

### 3. Text Modifiers

**Standard Tracery** has rich modifier support:

```json
{
  "origin": "I saw #animal.a.capitalize# in the #place#.",
  "animal": ["unicorn", "owl", "elephant"],
  "place": ["forest", "library", "marketplace"]
}
```

Output: "I saw An Owl in the library."

**GeistFabrik** has **no modifiers**:

```yaml
tracery:
  origin: "What if you explored #concept#?"  # No .capitalize or .a
  concept: ["creativity", "emergence", "connection"]
```

If you need capitalization or formatting in GeistFabrik, you must provide it in the grammar rules themselves:

```yaml
tracery:
  origin: "#concept_capitalized# is important"
  concept_capitalized: ["Creativity", "Emergence", "Connection"]
```

### 4. Vault Function Calls

**GeistFabrik's Killer Feature** - not available in standard Tracery:

```yaml
tracery:
  origin:
    - "What if you combined [[#note1#]] with [[#note2#]]?"
    - "Revisit [[#old_note#]] in light of [[#recent_note#]]"

  note1:
    - "$vault.sample_notes(1)"  # Calls VaultContext.call_function("sample_notes", 1)

  note2:
    - "$vault.sample_notes(1)"

  old_note:
    - "$vault.oldest_notes(5)"

  recent_note:
    - "$vault.recent_notes(3)"
```

**Syntax**: `$vault.function_name(arg1, arg2, ...)`

Arguments are parsed as comma-separated values and passed to `VaultContext.call_function()`. The function must be registered via the `@vault_function` decorator.

**Standard Tracery** has no equivalent mechanism. All content must be pre-generated and included in the JSON grammar.

---

## Code Examples

### Example 1: Basic Text Generation

**Task**: Generate a greeting with a random animal

**Standard Tracery (pytracery):**
```python
import tracery
from tracery.modifiers import base_english

rules = {
    'origin': '#greeting.capitalize#, #animal.a#!',
    'greeting': ['hello', 'greetings', 'howdy'],
    'animal': ['unicorn', 'owl', 'elephant']
}

grammar = tracery.Grammar(rules)
grammar.add_modifiers(base_english)
print(grammar.flatten("#origin#"))
# Output: "Hello, an owl!"
```

**GeistFabrik Equivalent:**
```yaml
# greetings.yaml
type: geist-tracery
id: greetings
tracery:
  origin:
    - "#greeting#, a #animal#!"
  greeting:
    - "Hello"
    - "Greetings"
    - "Howdy"
  animal:
    - "unicorn"
    - "owl"
    - "elephant"
suggestions_per_invocation: 1
```

```python
from geistfabrik.tracery import TraceryGeist
from geistfabrik import VaultContext

geist = TraceryGeist.from_yaml("greetings.yaml", seed=42)
suggestions = geist.suggest(vault_context)
# Returns: [Suggestion(text="Hello, a unicorn!", notes=[], geist_id="greetings")]
```

**Key Differences:**
- GeistFabrik can't use `.capitalize` or `.a` modifiers
- GeistFabrik must manually capitalize in rules
- GeistFabrik returns `Suggestion` objects, not strings
- GeistFabrik uses YAML, standard uses JSON

### Example 2: Variable Consistency

**Task**: Generate a story with consistent character name

**Standard Tracery:**
```json
{
  "origin": "#[hero:#name#]story#",
  "story": "#hero# found a treasure. #hero# was happy.",
  "name": ["Alice", "Bob", "Charlie"]
}
```
Output: "Alice found a treasure. Alice was happy." (same name used twice)

**GeistFabrik - NOT POSSIBLE:**
GeistFabrik cannot maintain variable state across expansions. You would get:
```yaml
tracery:
  origin: "#hero# found a treasure. #hero# was happy."
  hero: ["Alice", "Bob", "Charlie"]
```
Output: "Alice found a treasure. Bob was happy." (potentially different names!)

**Workaround**: Keep sentences simple and single-expansion, or use vault functions to get consistent data.

### Example 3: Vault-Aware Generation (GeistFabrik Only)

**Task**: Generate suggestions that reference actual vault notes

**GeistFabrik:**
```yaml
# note_combinations.yaml
type: geist-tracery
id: note_combinations
description: Suggests combining random notes in creative ways

tracery:
  origin:
    - "What if you combined [[#note1#]] with [[#note2#]]? #reason#"
    - "Consider connecting [[#note1#]] and [[#note2#]]. #reason#"

  note1:
    - "$vault.sample_notes(1)"

  note2:
    - "$vault.sample_notes(1)"

  reason:
    - "They might reveal unexpected patterns."
    - "The contrast could clarify your thinking."
    - "A synthesis might emerge from the tension."

suggestions_per_invocation: 2
```

**How it works:**
1. `$vault.sample_notes(1)` calls `VaultContext.call_function("sample_notes", "1")`
2. The vault function returns a single random note
3. `TraceryEngine._format_list()` converts Note object to `[[Title]]` format
4. Final text includes proper Obsidian wikilinks: `[[Note A]]` and `[[Note B]]`
5. TraceryGeist extracts note references and includes them in Suggestion.notes

**Standard Tracery - Requires Preprocessing:**
```python
import tracery
from my_vault import get_all_note_titles

# Must precompute note titles before creating grammar
note_titles = get_all_note_titles()

rules = {
    'origin': 'What if you combined [[#note1#]] with [[#note2#]]?',
    'note1': note_titles,  # All titles pre-loaded
    'note2': note_titles   # Cannot be dynamic
}

grammar = tracery.Grammar(rules)
print(grammar.flatten("#origin#"))
```

**Key Advantage**: GeistFabrik's vault functions are called **at expansion time**, enabling dynamic queries like "notes modified in the last 7 days" or "notes semantically similar to X". Standard Tracery requires all possible values to be pre-computed.

### Example 4: Nested Grammars with POP (Standard Tracery Only)

**Task**: Generate nested stories with context-specific characters

**Standard Tracery:**
```json
{
  "origin": "The #pet# was reading a book about #story#.",
  "story": "[pet:#mood# #animal#]#pet.a#. #action#[pet:POP]",
  "action": "The #pet# did something interesting",
  "pet": ["friendly dog", "curious cat"],
  "mood": ["happy", "sad"],
  "animal": ["unicorn", "dragon"]
}
```

Output: "The friendly dog was reading a book about a sad unicorn. The sad unicorn did something interesting."

The inner story has a different pet than the outer story, then POPs back to the original pet.

**GeistFabrik - NOT SUPPORTED:**
No equivalent. GeistFabrik grammars should stay simple and flat.

---

## Performance Considerations

### Execution Speed

**GeistFabrik:**
- Lightweight (283 lines of code)
- No external dependencies beyond PyYAML
- Regex-based symbol expansion (`re.sub`)
- Adds overhead for vault function calls (SQL queries, semantic search)
- Typical expansion: <1ms for pure grammar, 10-100ms+ with vault functions

**Standard Tracery (pytracery):**
- Pure string generation (no I/O)
- No database queries or semantic search
- Similar regex-based expansion
- Typical expansion: <1ms
- Modifier application adds minimal overhead

**Verdict**: For pure text generation, standard Tracery is faster. For vault-aware generation, GeistFabrik's vault function overhead is unavoidable (and worth it).

### Memory Usage

**GeistFabrik:**
- Grammars loaded from YAML files
- VaultContext held in memory (includes vault, embeddings, function registry)
- Each `$vault.*` call may allocate Note objects
- Suggestion objects created for each expansion

**Standard Tracery:**
- Grammars held in memory as Python dicts
- No external context
- Returns strings (minimal allocation)
- Stack memory for push-pop (small overhead)

**Verdict**: Standard Tracery has lower memory footprint. GeistFabrik's context and Suggestion objects add overhead, but acceptable for 100+ geists.

### Recursion Limits

Both implementations protect against infinite recursion:

**GeistFabrik:**
```python
def expand(self, text: str, depth: int = 0) -> str:
    if depth > self.max_depth:  # max_depth=50
        raise RecursionError(f"Tracery expansion exceeded max depth ({self.max_depth})")
```

**Standard Tracery:**
Similar depth tracking (implementation-dependent)

### Deterministic Seeding

**GeistFabrik:**
```python
self.rng = random.Random(seed)  # Seed set at initialization
selected = self.rng.choice(rules)  # Same seed = same output
```

**Standard Tracery (pytracery):**
```python
# Optional - must manually set random seed
import random
random.seed(42)
grammar = tracery.Grammar(rules)
grammar.flatten("#origin#")
```

**Verdict**: GeistFabrik's session-based seeding is built-in and mandatory (same date = same suggestions). Standard Tracery requires manual seed management.

---

## Compatibility Analysis

### Can Standard Tracery Grammars Run on GeistFabrik's Engine?

**Short Answer**: No, not without conversion.

**Why Not:**

1. **Format Difference**: Standard Tracery uses JSON, GeistFabrik uses YAML with metadata
2. **Modifiers**: Standard grammars using `.capitalize`, `.s`, etc. will fail (symbols like `#animal.a#` will be treated as literal)
3. **Stack Memory**: Grammars using `[var:value]` will not work (syntax will be preserved as literal text)
4. **Origin Rules**: Standard Tracery allows single string origin, GeistFabrik expects list

**Example of Incompatibility:**

Standard Tracery grammar:
```json
{
  "origin": "#[hero:#name#]story#",
  "story": "#hero.capitalize# was brave.",
  "name": ["alice", "bob"]
}
```

If naively converted to GeistFabrik YAML:
```yaml
tracery:
  origin: "#[hero:#name#]story#"  # Literal text, not variable assignment
  story: "#hero.capitalize# was brave."  # .capitalize treated as literal
  name: ["alice", "bob"]
```

Output: "#[hero:#name#]story#" (no expansion because `[hero:#name#]story` isn't a known symbol)

**Conversion Requirements:**

To convert, you would need to:
1. Manually wrap in GeistFabrik YAML structure
2. Remove all modifiers and manually create capitalized variants
3. Remove all stack operations and simplify to single-expansion rules
4. Add `$vault.*` calls if you want vault awareness

### Can GeistFabrik Grammars Run on Standard Tracery?

**Short Answer**: Partially, if you remove vault functions.

**What Works:**
```yaml
# GeistFabrik
tracery:
  origin: "What if you explored #concept#?"
  concept: ["creativity", "emergence", "connection"]
```

Can be converted to:
```json
{
  "origin": "What if you explored #concept#?",
  "concept": ["creativity", "emergence", "connection"]
}
```

**What Doesn't Work:**
- `$vault.function()` calls have no equivalent
- Metadata (`id`, `count`, `suggestions_per_invocation`) would be ignored
- Return value is string, not `Suggestion` object

**Verdict**: Simple GeistFabrik grammars (no vault functions) can be manually converted to standard Tracery, but you lose the vault-aware features that make GeistFabrik useful.

### Cross-Compatibility Matrix

| Feature | Standard → GeistFabrik | GeistFabrik → Standard |
|---------|------------------------|------------------------|
| Basic symbols | ✅ Manual conversion | ✅ Manual conversion |
| Modifiers | ❌ Must remove | N/A (GF doesn't use) |
| Stack memory | ❌ Must remove | N/A (GF doesn't use) |
| Vault functions | N/A (not in standard) | ❌ No equivalent |
| JSON/YAML format | ✅ Easily converted | ✅ Easily converted |
| Metadata | ❌ Must add | ❌ Would be lost |

---

## When to Use Each Implementation

### Use GeistFabrik's Tracery Engine When:

✅ **You need vault-aware text generation**
- Generating suggestions that reference actual vault notes
- Dynamically querying notes by recency, semantic similarity, tags, etc.
- Building creative prompts that combine real user content

✅ **You want deterministic, session-based output**
- Same date + same vault = same suggestions
- Reproducible debugging and testing

✅ **You're building geists for Obsidian**
- Integration with VaultContext and function registry
- Automatic extraction of `[[wikilinks]]`
- Returns structured Suggestion objects

✅ **You prefer simple, flat grammars**
- No need for modifiers or state management
- Simple symbol expansion is sufficient
- YAML format is more readable for your use case

### Use Standard Tracery (pytracery) When:

✅ **You need text modifiers**
- Pluralization (`.s`), past tense (`.ed`), articles (`.a`)
- Capitalization variants without duplicating rules
- Custom modifiers for domain-specific transformations

✅ **You need variable consistency**
- Characters or entities that must be referenced multiple times
- Nested contexts with push-pop stack memory
- Complex narrative generation

✅ **You're building general-purpose text generators**
- Twitter bots, story generators, poetry engines
- No connection to external data sources
- Pure string output is sufficient

✅ **You want maximum compatibility**
- JSON format is standard across all Tracery ports
- Works with existing Tracery tooling (editors, visualizers)
- Large ecosystem of example grammars

✅ **You're using other Tracery features**
- POP actions for stack management
- Custom modifier registration
- Integration with existing Tracery workflows

### Hybrid Approach: Combine Both

You can use **both** implementations in the same project:

**Code Geists** (Python) for complex vault queries:
```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    # Complex logic with conditionals, loops, state
    notes = vault.semantic_search("quantum physics", top_k=3)
    suggestions = []
    for note in notes:
        suggestions.append(Suggestion(
            text=f"How does [[{note.title}]] relate to consciousness?",
            notes=[note.title],
            geist_id="quantum_consciousness"
        ))
    return suggestions
```

**GeistFabrik Tracery Geists** for simple templates with vault data:
```yaml
tracery:
  origin: "What if you combined [[#note1#]] with [[#note2#]]?"
  note1: "$vault.sample_notes(1)"
  note2: "$vault.sample_notes(1)"
```

**Standard Tracery** for pure text generation (no vault dependency):
```python
import tracery
from tracery.modifiers import base_english

# Used in geist for generating poetic prompts
poetry_rules = {
    'origin': '#line1.capitalize#\n#line2#\n#line3#',
    'line1': ['what if #concept#', 'imagine #concept#'],
    'concept': ['time', 'space', 'thought', 'dreams']
}
grammar = tracery.Grammar(poetry_rules)
grammar.add_modifiers(base_english)

def suggest(vault: VaultContext) -> List[Suggestion]:
    text = grammar.flatten("#origin#")
    return [Suggestion(text=text, notes=[], geist_id="poetry")]
```

---

## Technical Deep Dive

### GeistFabrik Implementation Details

**File**: `/home/user/geist_fabrik/src/geistfabrik/tracery.py` (283 lines)

**Architecture:**

1. **TraceryEngine**: Core expansion engine
   - `expand(text, depth)`: Recursively expands `#symbols#`
   - `_expand_symbol(symbol, depth)`: Randomly selects and expands a rule
   - `_expand_vault_functions(text)`: Replaces `$vault.*` calls with results
   - Uses `random.Random(seed)` for deterministic selection

2. **TraceryGeist**: Wrapper that loads YAML and returns Suggestions
   - `from_yaml(path, seed)`: Loads YAML file
   - `suggest(vault)`: Generates suggestions by expanding `#origin#`
   - Extracts `[[wikilinks]]` and populates `Suggestion.notes`

3. **TraceryGeistLoader**: Discovers and loads .yaml files from directory
   - `load_all()`: Glob for `*.yaml`, instantiate TraceryGeist for each

**Vault Function Expansion:**

```python
def _expand_vault_functions(self, text: str) -> str:
    pattern = r"\$vault\.([a-z_]+)\(([^)]*)\)"  # Matches $vault.func(args)

    def replace_function(match: re.Match[str]) -> str:
        func_name = match.group(1)
        args_str = match.group(2).strip()

        # Simple comma-separated parsing
        args = [arg.strip().strip("\"'") for arg in args_str.split(",")]

        result = self.vault_context.call_function(func_name, *args)

        # Format result (list of Notes → "[[A]], [[B]], and [[C]]")
        if isinstance(result, list):
            return self._format_list(result)
        else:
            return str(result)

    return re.sub(pattern, replace_function, text)
```

**List Formatting for Note Objects:**

```python
def _format_list(self, items: List[Any]) -> str:
    if hasattr(items[0], "title"):  # Note objects
        titles = [f"[[{item.title}]]" for item in items]
        if len(titles) == 1:
            return titles[0]
        elif len(titles) == 2:
            return f"{titles[0]} and {titles[1]}"
        else:
            return ", ".join(titles[:-1]) + f", and {titles[-1]}"
    else:
        return ", ".join(str(item) for item in items)
```

**Example Output:**
- `[Note("A"), Note("B"), Note("C")]` → `"[[A]], [[B]], and [[C]]"`
- `[Note("X")]` → `"[[X]]"`
- `[1, 2, 3]` → `"1, 2, 3"`

### Standard Tracery (pytracery) Implementation Details

**GitHub**: https://github.com/aparrish/pytracery

**Core API:**

```python
import tracery
from tracery.modifiers import base_english

# 1. Create grammar from dict
rules = {
    'origin': '#greeting.capitalize#, #animal.a#!',
    'greeting': ['hello', 'greetings'],
    'animal': ['unicorn', 'owl']
}
grammar = tracery.Grammar(rules)

# 2. Add modifiers (optional)
grammar.add_modifiers(base_english)

# 3. Flatten (expand) the grammar
output = grammar.flatten("#origin#")  # "Hello, an owl!"
```

**Built-in Modifiers (base_english):**

| Modifier | Example Input | Example Output | Description |
|----------|--------------|----------------|-------------|
| `.capitalize` | "hello" | "Hello" | Capitalize first letter |
| `.capitalizeAll` | "hello world" | "Hello World" | Capitalize all words |
| `.s` | "cat" | "cats" | Pluralize (simple heuristics) |
| `.ed` | "jump" | "jumped" | Past tense (simple heuristics) |
| `.a` | "unicorn" | "a unicorn" | Add article (a/an) |
| `.a` | "owl" | "an owl" | Detects vowel sounds |

**Custom Modifiers:**

```python
def reverse_modifier(text):
    return text[::-1]

my_modifiers = {'reverse': reverse_modifier}
grammar.add_modifiers(my_modifiers)

# Now you can use #word.reverse#
```

**Push-Pop Stack:**

```python
rules = {
    'origin': '#[name:Alice]greeting#',  # Push "Alice" onto "name" stack
    'greeting': 'Hello, #name#!',         # Reference "name"
    # After expansion completes, "name" is popped
}
```

For nested contexts:
```python
rules = {
    'origin': '#[pet:dog]story#',
    'story': 'My #pet# found a book about [pet:cat]#pet.a#. The #pet# meowed.[pet:POP] My #pet# barked.',
}
```
Output: "My dog found a book about a cat. The cat meowed. My dog barked."

### Execution Integration in GeistFabrik

Tracery geists are loaded separately from code geists:

**GeistExecutor** (handles code geists):
- Loads `*.py` files from `geists_dir`
- Imports modules, calls `suggest(vault)` function
- Timeout, error handling, failure tracking

**TraceryGeistLoader** (handles Tracery geists):
- Loads `*.yaml` files from `geists_dir / "tracery"`
- Instantiates `TraceryGeist` objects
- Called separately by session manager

**Example Integration:**

```python
from pathlib import Path
from geistfabrik import GeistExecutor, VaultContext
from geistfabrik.tracery import TraceryGeistLoader
from geistfabrik.embeddings import Session

# Setup
vault_dir = Path("~/vault")
geists_dir = vault_dir / "_geistfabrik" / "geists"

# Load code geists
code_executor = GeistExecutor(geists_dir / "code", timeout=5)
code_executor.load_geists()

# Load Tracery geists
session_date = datetime(2025, 1, 15)
seed = hash(session_date.isoformat())
tracery_loader = TraceryGeistLoader(geists_dir / "tracery", seed=seed)
tracery_geists = tracery_loader.load_all()

# Execute all
vault_context = VaultContext(vault, session)
code_suggestions = code_executor.execute_all(vault_context)
tracery_suggestions = {g.geist_id: g.suggest(vault_context) for g in tracery_geists}

# Combine results
all_suggestions = {**code_suggestions, **tracery_suggestions}
```

---

## Conclusion

GeistFabrik's Tracery implementation is **intentionally minimal and specialized**. It sacrifices standard Tracery features (modifiers, stack memory) for a novel `$vault.*` function call system that enables declarative grammars to query and reference actual vault content.

**Choose GeistFabrik Tracery** if:
- You need vault-aware text generation
- Simple symbol expansion is sufficient
- You want deterministic, session-based seeding

**Choose Standard Tracery** if:
- You need modifiers, stack memory, or other standard features
- You're building general-purpose text generators
- You want maximum compatibility with Tracery ecosystem

**Both are valid tools** - GeistFabrik's implementation is not "broken Tracery," it's a purpose-built variant optimized for a specific use case (muses for Obsidian vaults).

---

## References

### GeistFabrik
- Implementation: `/home/user/geist_fabrik/src/geistfabrik/tracery.py`
- Examples: `/home/user/geist_fabrik/examples/geists/tracery/`
- Research: `/home/user/geist_fabrik/specs/tracery_research.md`

### Standard Tracery
- Original (JavaScript): https://github.com/galaxykate/tracery
- Official Site: https://tracery.io
- Python Port (pytracery): https://github.com/aparrish/pytracery
- Academic Paper: "Tracery: An Author-Focused Generative Text Tool" (Compton et al., 2015)
- Tutorial: http://air.decontextualize.com/tracery/

### Installation

**pytracery:**
```bash
pip install pytracery
```

**GeistFabrik Tracery:**
```bash
# Built into GeistFabrik (no separate installation)
pip install geistfabrik  # Includes custom Tracery engine
```
