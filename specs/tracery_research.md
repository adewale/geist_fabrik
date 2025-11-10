# tracery_context.md

## Overview

Tracery is a lightweight generative text library created by Kate Compton (UC Santa Cruz) that uses context-free grammars with a beginner-friendly JSON syntax to generate varied text from simple rule sets. It became the standard for creative Twitter bots and procedural text generation in the mid-2010s through platforms like Cheap Bots, Done Quick.

## Core Technical Concepts

### Basic Grammar Structure

Tracery grammars are JSON objects where keys are symbols and values are arrays of expansion rules:

```json
{
  "origin": "#greeting#, #character#!",
  "greeting": ["Hello", "Greetings", "Howdy"],
  "character": ["#adjective# #animal#"],
  "adjective": ["brave", "clever", "mysterious"],
  "animal": ["fox", "rabbit", "owl"]
}
```

### Syntax Elements

- **Symbols**: Marked with `#symbolName#` for expansion
- **Rules**: Arrays of possible expansions for each symbol
- **Origin**: Default starting point for generation
- **Recursion**: Rules can reference other rules to arbitrary depth

### Advanced Features

#### Push-Pop Stack Memory
```json
{
  "origin": "#[hero:#name#][heroPet:#animal#]story#",
  "story": "#hero# travelled with their pet #heroPet#. #hero# was never #mood#.",
  "name": ["Arjun", "Lina", "Azra"],
  "animal": ["unicorn", "raven", "duck"],
  "mood": ["vexed", "indignant", "wistful"]
}
```
Syntax: `[variable:value]` saves generated text for reuse within the expansion.

#### Built-in Modifiers
- `.capitalize` - Capitalizes first letter
- `.s` - Pluralizes
- `.ed` - Past tense
- `.a` - Adds appropriate article (a/an)
- `.capitalizeAll` - Capitalizes all words
- Custom modifiers can be added programmatically

Example: `#animal.a.capitalize#` might produce "An Owl" or "A Fox"

## Available Implementations

### Primary Implementations
- **JavaScript** (original): `github.com/galaxykate/tracery`
- **Python**: `pip install tracery` or `github.com/aparrish/pytracery`
- **Ruby**: Available as gem
- **Rust**: `cargo add tracery`
- **Node.js**: `npm install tracery-grammar`
- **Java/JVM**: Grammy library `github.com/AlmasB/grammy`

### GeistFabrik Implementation

**GeistFabrik uses a custom TraceryEngine** (not pytracery) implemented in `src/geistfabrik/tracery.py`. This custom implementation provides:

- **Core features**: Symbol expansion, modifiers, deterministic randomness
- **Built-in modifiers**: `.capitalize`, `.capitalizeAll`, `.s` (pluralize), `.ed` (past tense), `.a` (article)
- **Custom modifiers**: `.split_seed`, `.split_neighbours` (for cluster functions)
- **Vault integration**: `$vault.*` function preprocessing
- **Safety features**: Anti-pattern validation, recursion limits (`max_depth = 50`)

The custom implementation was chosen over pytracery to:
- Integrate deeply with VaultContext and vault functions
- Support deterministic randomness via explicit seed parameter
- Add custom modifiers specific to GeistFabrik patterns
- Provide better error messages and validation

### Platform Integrations
- **Twine**: Twinecery for Twine 2 story format
- **Unity**: Multiple C# implementations available
- **Tracery.io**: Web-based editor and playground
- **Cheap Bots, Toot Sweet**: Mastodon bot platform (CBDQ successor)

### Usage Examples by Language

#### JavaScript
```javascript
const tracery = require('tracery-grammar');
const grammar = tracery.createGrammar({
  'origin': '#hello# #location#!',
  'hello': ['Hello', 'Greetings', 'Howdy'],
  'location': ['world', 'universe', 'cosmos']
});
const expansion = grammar.flatten('#origin#');
```

#### Python
```python
# GeistFabrik uses a custom TraceryEngine (not pytracery)
# See src/geistfabrik/tracery.py for implementation

from geistfabrik.tracery import TraceryEngine

grammar = {
    'origin': '#hello.capitalize#, #location#!',
    'hello': ['hello', 'greetings', 'howdy'],
    'location': ['world', 'universe', 'cosmos']
}

# Built-in modifiers are automatically available
engine = TraceryEngine(grammar, seed=42)
print(engine.expand("#origin#"))
```

## Geist-Style Implementations

### Connection Finder Geist
```json
{
  "origin": "What if #note1# and #note2# are #relationship#?",
  "note1": ["your oldest note", "yesterday's insight", "that abandoned idea", "the problem you're avoiding"],
  "note2": ["your newest thought", "a random Wikipedia article", "your childhood memory", "tomorrow's goal"],
  "relationship": ["two sides of the same coin", "in violent disagreement", "secret lovers", "the same thing at different scales", "speaking different languages about the same truth"]
}
```

### Assumption Challenger Geist
```json
{
  "origin": "#prompt# #assumption#",
  "prompt": ["What would break if", "Who benefits from believing", "When did you start assuming", "What evidence contradicts", "How would a child question"],
  "assumption": ["this must be finished before starting?", "expertise is required?", "the popular approach is correct?", "you understand the real problem?", "the constraint is real?"]
}
```

### Scale Shifter Geist
```json
{
  "origin": "Zoom #direction#: How would this #scale# #perspective#?",
  "direction": ["in", "out"],
  "scale": ["look to an ant", "work in a century", "feel to a civilization", "apply to a single atom", "manifest in a dream"],
  "perspective": ["change your approach", "reveal hidden patterns", "make the important trivial", "make the trivial important", "dissolve the boundaries"]
}
```

### SCAMPER Method Geist
```json
{
  "origin": "#action# #component# #modifier#",
  "action": ["Substitute", "Combine", "Adapt", "Magnify", "Minimize", "Put to other uses", "Eliminate", "Reverse", "Rearrange"],
  "component": ["the core assumption", "the desired outcome", "your role", "the timeline", "the success metrics", "the failure mode"],
  "modifier": ["and see what breaks.", "until it becomes absurd.", "with its opposite.", "recursively.", "but only on Tuesdays."]
}
```

### Temporal Mirror Geist
```json
{
  "origin": "#timeshift# #reflection#",
  "timeshift": ["Your past self from #timeline# would", "Future you in #timeline# will"],
  "timeline": ["10 years ago", "last month", "10 years", "next week"],
  "reflection": ["laugh at this problem", "already know the answer", "be asking different questions", "have different constraints"]
}
```

## Obsidian Integration Concepts

### Daily Prompt Generator
```javascript
// Pseudo-code for Obsidian plugin
class TraceryGeist {
  constructor(vault) {
    this.vault = vault;
    this.grammar = this.buildGrammarFromVault();
  }

  buildGrammarFromVault() {
    const recentNotes = this.vault.getRecentNotes(7);
    const randomNotes = this.vault.getRandomNotes(10);
    const tags = this.vault.getAllTags();

    return {
      origin: "[[Daily Prompt]]: #method# [[#recentNote#]] #connection# [[#randomNote#]]",
      method: ["What would happen if", "Draw a diagram showing how", "Write the opposite of"],
      connection: ["contradicts", "rhymes with", "could be caused by", "might prevent"],
      recentNote: recentNotes.map(n => n.title),
      randomNote: randomNotes.map(n => n.title)
    };
  }

  generatePrompt() {
    const grammar = tracery.createGrammar(this.grammar);
    return grammar.flatten('#origin#');
  }
}
```

### Inline Block Regeneration
```markdown
<!-- In an Obsidian note -->
```tracery
{
  "origin": "Consider: #provocation#",
  "provocation": ["What if the opposite were true?", "How would this look inverted?", "When does this break down?"]
}
```
<!-- Plugin would replace this block with generated text on each view -->
```

## Meaning Inversion Grammar

Complete grammar for inverting statements philosophically:

```json
{
  "origin": "#inversion_type#",
  "inversion_type": ["#logical_inverse#", "#temporal_inverse#", "#scale_inverse#", "#value_inverse#", "#perspective_inverse#"],

  "logical_inverse": "If '#statement#' is true, then #inverse_logic# must be false.",
  "inverse_logic": ["its opposite", "what everyone believes", "the obvious solution", "the comfortable path"],

  "temporal_inverse": "You believe '#statement#' today. #when# you believed #opposite#.",
  "when": ["Yesterday", "In a year", "As a child", "Before the crisis", "After the success"],
  "opposite": ["the exact opposite", "nothing mattered", "everything mattered", "it was impossible"],

  "scale_inverse": "'#statement#' is true at this scale. Zoom #direction# and #inversion#.",
  "direction": ["out far enough", "in close enough"],
  "inversion": ["it becomes meaningless", "its opposite becomes true", "the question dissolves"],

  "value_inverse": "You value '#statement#'. Someone who valued #antivalue# would #reaction#.",
  "antivalue": ["chaos over order", "questions over answers", "destruction over creation"],
  "reaction": ["laugh at your certainty", "see freedom where you see prison", "find wisdom in folly"],

  "perspective_inverse": "'#statement#' assumes #assumption#. Without that assumption, #result#.",
  "assumption": ["linear time", "individual identity", "cause and effect", "words mean things"],
  "result": ["the statement becomes meaningless", "its opposite is equally true", "silence is the only answer"],

  "statement": ["Productivity equals value", "Knowledge is power", "Time is money", "Growth is good"]
}
```

## Comparison with Alternative Tools

### Tracery vs Other Generative Text Tools

| Tool | Strengths | Weaknesses | Best For |
|------|-----------|------------|----------|
| **Tracery** | Simple JSON syntax, wide platform support, predictable output | Limited logic/state, no complex branching | Bots, creative prompts, simple generation |
| **Ink** | Powerful narrative logic, professional tool, state tracking | Steeper learning curve, narrative-focused | Interactive fiction, game dialogue |
| **Twine** | Visual authoring, self-contained HTML output | Less suited for pure generation | Choice-based stories, hypertext |
| **Markov Chains** | Natural-sounding output, learns from corpus | Less control, can be nonsensical | Mimicking style, creative writing |
| **L-Systems** | Mathematical rigor, good for recursive structures | Complex for text, better for graphics | Formal generation, plant/fractal modelling |
| **LLMs** | Contextual understanding, infinite variety | Unpredictable, requires API, expensive | Complex generation, conversational AI |

## Implementation Best Practices

### For Geist-like Systems
1. Keep grammars modular and composable
2. Use push-pop stacks sparingly to maintain coherence
3. Balance randomness with meaningful variation
4. Test outputs at scale to catch edge cases
5. Provide user control over generation frequency/type

### For Integration with Note-Taking Systems
1. Parse existing content to populate grammar variables
2. Use timestamps and metadata for temporal variations
3. Cache generated content to avoid regeneration spam
4. Allow user editing/saving of generated provocations
5. Track which provocations led to new insights

### Performance Considerations
- Grammars are fast but recursive depth affects performance
- Pre-compile grammars when possible
- Limit maximum expansion depth to prevent infinite loops
- Consider caching frequently-used sub-expansions

## Historical Context

Tracery emerged from Kate Compton's work at UC Santa Cruz's Centre for Games and Playable Media (2014-2015). It gained widespread adoption through:
- **Cheap Bots, Done Quick** (2015-2023): Zero-code Twitter bot platform
- **NaNoGenMo**: National Novel Generation Month projects
- **Game Industry**: Integration into narrative games
- **Academic Use**: Teaching computational creativity

The tool represents a design philosophy prioritizing accessibility and authorial control over technical sophistication, making it ideal for Gordon Brander's geists concept of "oracular provocations" for creative thinking.

## GeistFabrik Integration Specifics

### Architectural Overview

GeistFabrik uses Tracery geists as one of two geist types (alongside code geists). The key architectural challenge is **bridging Tracery's static grammar system with GeistFabrik's dynamic vault data**.

**Critical Design Principle**: Tracery grammars cannot directly access vault metadata or note content. Instead, **vault functions act as the bridge**, converting rich vault queries into simple string arrays that Tracery can use.

### YAML Format for Tracery Geists

Unlike standard Tracery (JSON), GeistFabrik uses YAML with specific structure:

```yaml
type: geist-tracery
id: unique_geist_identifier
tracery:
  origin: "Template with #symbols# and [[wikilinks]]"
  symbol_name: ["static option 1", "static option 2"]
  vault_symbol: ["$vault.function_name(args)"]
  nested_symbol: ["#other_symbol# with text"]
```

**Required Fields**:
- `type: geist-tracery` - Identifies this as a Tracery geist
- `id: <string>` - Unique identifier (becomes `geist_id` in Suggestions)
- `tracery:` - Contains the Tracery grammar itself
- `origin:` - Starting expansion rule (can be overridden)

**File Location**: `<vault>/_geistfabrik/geists/tracery/<geist_id>.yaml`

### Vault Function Integration

#### The `$vault.*` Syntax

Vault functions are called within YAML arrays using the syntax:
```yaml
symbol_name: ["$vault.function_name(arg1, arg2)"]
```

**Execution Flow**:
1. YAML parser loads geist file
2. System detects `$vault.*` patterns in symbol arrays
3. Before Tracery expansion, vault functions execute:
   - `$vault.sample_notes(3)` → `["Note A", "Note B", "Note C"]`
   - `$vault.orphans(2)` → `["Orphan 1", "Orphan 2"]`
4. Grammar symbols updated with results
5. Tracery expansion proceeds with populated arrays

**Important**: Vault functions return **bracketed wikilinks**. The Tracery template should use these directly without adding additional brackets.

#### Parameter Types

Vault functions support simple parameter types:
- **Integers**: `$vault.sample_notes(5)`
- **Strings** (quoted): `$vault.tagged('project', 2)`
- **Strings** (single-quoted): `$vault.notes_by_mood('positive', 1)`

**Limitation**: Complex objects or nested function calls not supported. Each function call must be self-contained.

#### Return Value Handling

Vault functions must return **lists of strings** containing bracketed wikilinks:

```python
@vault_function("sample_notes")
def sample_notes(vault: VaultContext, k: int) -> List[str]:
    """Sample k random notes, return as bracketed wikilinks"""
    notes = vault.sample(k)
    return [f"[[{note.obsidian_link}]]" for note in notes]  # Returns "[[Note Title]]"
```

**Edge Cases**:
- **Empty results**: Function returns `[]` → Symbol has empty array → Tracery fails gracefully
- **Fewer than requested**: `$vault.orphans(10)` with only 3 orphans → Returns `["[[Orphan 1]]", "[[Orphan 2]]", "[[Orphan 3]]"]`
- **Single result**: Still wrapped in list → `["[[Only Note]]"]`

**Note**: The `obsidian_link` property returns link text. Vault functions wrap this in brackets before returning:
```yaml
# Correct: Template uses function result as-is
origin: "Check out #note#"
note: ["$vault.sample_notes(1)"]

# Wrong: Double brackets (produces "Check out [[[[Note Title]]]]")
origin: "Check out [[#note#]]"
```

### Complete Integration Example

```yaml
# <vault>/_geistfabrik/geists/tracery/semantic_bridge.yaml
type: geist-tracery
id: semantic_bridge
tracery:
  origin: "#note1# and #note2# both seem to be about #theme#. #question#?"
  note1: ["$vault.sample_notes(1)"]
  note2: ["$vault.sample_notes(1)"]
  theme:
    - "the same underlying pattern"
    - "adjacent problems"
    - "opposite approaches to the same question"
    - "the tension between theory and practice"
  question:
    - "What if they're describing the same thing at different scales"
    - "What would combining them reveal"
    - "What assumption do they both share"
```

**Generated Output** (example):
```
[[Project Planning]] and [[Fermentation]] both seem to be about the tension between theory and practice. What if they're describing the same thing at different scales?
```

**Note**: The brackets appear in the output because `$vault.sample_notes(1)` returns `["[[Project Planning]]"]`, not `["Project Planning"]`.

### Note Reference Tracking

**Challenge**: Extract note titles from generated text to populate `Suggestion.notes` field.

**Solution**: Parse wikilink patterns `[[Note Title]]` from final expansion:

```python
def extract_note_references(text: str) -> List[str]:
    """Extract note titles from [[wikilinks]]"""
    import re
    pattern = r'\[\[([^\]]+)\]\]'
    return re.findall(pattern, text)
```

**Best Practice**: Always wrap vault function calls in wikilinks:
```yaml
# Good - trackable references
origin: "[[#note1#]] connects to [[#note2#]]"

# Bad - no way to track which notes were used
origin: "#note1# connects to #note2#"
```

### Deterministic Randomness

**Requirement**: Same vault state + date → identical output

**Implementation**: ✅ **IMPLEMENTED** in custom TraceryEngine

The TraceryEngine accepts a `seed` parameter that ensures deterministic behaviour:

```python
# TraceryEngine constructor
engine = TraceryEngine(grammar, seed=42)

# TraceryGeist passes session-based seed
geist = TraceryGeist.from_yaml(yaml_path, seed=int(date.strftime('%Y%m%d')))
```

**How it works**:
1. **Session-level seed**: Derived from date (e.g., `int(date.strftime('%Y%m%d'))`)
2. **VaultContext random state**: Seeded RNG passed to all vault functions
3. **Vault function sampling**: Use context's RNG, not Python's `random.choice()`
4. **Tracery rule selection**: Uses `random.Random(seed)` for reproducible choice

**Test Command**:
```bash
# Should produce identical output
geistfabrik invoke --date 2025-01-15
geistfabrik invoke --date 2025-01-15
```

### Error Handling

#### Vault Function Failures

```yaml
# What happens here if vault has no orphans?
note: ["$vault.orphans(1)"]
```

**Strategies**:
1. **Return empty list**: Tracery expansion fails silently → No suggestion generated
2. **Fallback values**: Function returns `["<no orphans>"]` → Geist generates but looks broken
3. **Log and continue**: Error logged, geist skipped for session

**Recommendation**: Return empty list + log warning. Better to skip a suggestion than generate nonsense.

#### Tracery Syntax Errors

```yaml
# Typo in symbol name
origin: "#greting#"  # Should be #greeting#
greeting: ["Hello"]
```

**Detection**: Pytracery raises `KeyError` or returns `#greting#` unexpanded.

**Handling**:
- Validate YAML structure on load
- Dry-run test expansion with dummy data
- Catch exceptions during execution
- After 3 failures, disable geist (per spec)

#### Debugging Workflow

```bash
# Test single geist with specific date
geistfabrik test semantic_bridge --vault ~/notes --date 2025-01-15

# Expected verbose output:
# ✓ Loaded geist: semantic_bridge
# ✓ Executed $vault.sample_notes(1) → ["Project Planning"]
# ✓ Executed $vault.sample_notes(1) → ["Fermentation"]
# ✓ Tracery expansion: "[[Project Planning]] and [[Fermentation]]..."
# ✓ Generated 1 suggestion
```

### Multiple Suggestions from One Geist

**Question**: Can a single Tracery geist generate multiple suggestions?

**Answer**: ✅ **YES** - Tracery geists support a `count` parameter.

Each Tracery geist can generate multiple suggestions per session:

```yaml
type: geist-tracery
id: example
count: 3  # Generate 3 suggestions
tracery:
  origin: "[[#note1#]] and [[#note2#]] might be #relationship#"
  note1: ["$vault.sample_notes(1)"]
  note2: ["$vault.sample_notes(1)"]
  relationship: ["connected", "contrasting", "complementary"]
```

**How it works**:
1. Grammar expands `count` times (line 638 in tracery.py)
2. Each expansion is independent with potentially different outputs
3. Randomness is deterministic (based on session seed)
4. Each expansion produces one `Suggestion` object
5. Returns list with `count` suggestions

**Example**: `semantic_neighbours.yaml` has `count: 2` and generates 2 suggestions per session.

### Python Implementation Reference

GeistFabrik's custom TraceryEngine implementation:

```python
from pathlib import Path
import yaml
from geistfabrik.tracery import TraceryEngine, TraceryGeist
from geistfabrik.models import Suggestion
from geistfabrik.vault_context import VaultContext

def load_tracery_geist(path: Path) -> tuple[str, dict, int]:
    """Load YAML geist file"""
    with open(path) as f:
        data = yaml.safe_load(f)

    assert data['type'] == 'geist-tracery'
    return data['id'], data['tracery'], data.get('count', 1)

def execute_tracery_geist(geist_id: str, grammar: dict, count: int,
                          vault: VaultContext, seed: int) -> list[Suggestion]:
    """Execute Tracery geist with vault integration"""

    # Create TraceryGeist instance
    geist = TraceryGeist(geist_id, grammar, count, seed)

    # Generate suggestions (handles vault function preprocessing internally)
    return geist.suggest(vault)
```

**Key differences from pytracery**:
- Uses custom `TraceryEngine` class, not `tracery.Grammar`
- Vault function preprocessing is built-in (no manual `$vault.*` parsing needed)
- Validation catches unsafe patterns at load time
- Deterministic randomness via `seed` parameter
- Custom modifiers (`.split_seed`, `.split_neighbours`) for cluster functions

### Metadata Bridge Pattern

**Problem**: Tracery cannot access note metadata directly.

**Example Failure**:
```yaml
# This CANNOT work - no metadata access
origin: "Notes with high complexity: #complex_notes#"
complex_notes: ["$note.complexity > 0.8"]  # ✗ Invalid
```

**Solution**: Create vault function that queries metadata:

```python
# <vault>/_geistfabrik/vault_functions/by_complexity.py
from geistfabrik.function_registry import vault_function

@vault_function("complex_notes")
def complex_notes(vault: VaultContext, k: int) -> List[str]:
    """Get k notes with highest complexity"""
    notes_with_meta = [
        (note, vault.metadata(note, 'complexity'))
        for note in vault.all_notes()
    ]
    # Sort by complexity, take top k
    sorted_notes = sorted(notes_with_meta,
                          key=lambda x: x[1] or 0,
                          reverse=True)
    return [note.obsidian_link for note, _ in sorted_notes[:k]]
```

```yaml
# Now Tracery can access it
origin: "Your most complex notes: [[#note#]]"
note: ["$vault.complex_notes(1)"]
```

**Pattern**: Metadata inference → Vault function → Tracery accessibility

### Advanced Patterns and Limitations

#### Symbol References

**Question**: Can vault symbols reference other vault symbols?

```yaml
origin: "[[#note1#]] vs [[#note2#]]"
note1: ["$vault.sample_notes(1)"]
note2: ["$vault.neighbours(#note1#, 1)"]  # Can we reference note1?
```

**Answer**: No direct support. Tracery expands symbols independently due to **preprocessing order**.

**Why This Fails**: Vault functions execute during preprocessing (before symbol expansion). When you write `$vault.neighbours(#note1#, 1)`, the literal string `"#note1#"` is passed to the function, not the expanded note title.

**Critical Anti-Pattern** (DO NOT USE):
```yaml
# ❌ BROKEN - Will produce empty results
origin: "[[#seed#]] shares space with #neighbours#"
seed: ["$vault.sample_notes(1)"]
neighbours: ["$vault.neighbours(#seed#, 3)"]  # Passes "#seed#" as string!
```

**Solution**: Use structured vault functions with custom Tracery modifiers.

#### Designing Tracery-Safe Vault Functions

**The Problem**: Functions that take note titles as parameters cannot work in Tracery because:
1. Preprocessing happens first → `$vault.*` functions execute
2. Symbol expansion happens second → `#symbols#` expand

**Unsafe Functions** (code-only, not for Tracery):
- `neighbours(note_title, k)` - Requires expanded note title
- `contrarian_to(note_title, k)` - Requires expanded note title
- Any function with string parameters expecting note references

**Safe Functions** (work in Tracery):
- `sample_notes(k)` - Only primitive parameters
- `orphans(k)` - Only primitive parameters
- `hubs(k)` - Only primitive parameters
- `semantic_clusters(count, k)` - Bundles seeds with neighbours using delimiters

**Workaround Pattern - The Cluster Function Pattern**:

The cluster pattern solves the "can't pass symbols to functions" problem by pre-bundling related data during preprocessing, then using custom modifiers to extract parts during expansion.

**Key Pattern**: Cluster functions bundle multiple notes using delimiters, with all note references already bracketed (consistent with all other vault functions).

```python
@vault_function("semantic_clusters")
def semantic_clusters(vault: VaultContext, count: int = 2, k: int = 3) -> List[str]:
    """Sample seeds and pair with neighbours using delimiter.

    Returns:
        List of strings with BRACKETED links:
        "[[SEED]]|||[[NEIGHBOUR1]], [[NEIGHBOUR2]], and [[NEIGHBOUR3]]"

    Note:
        Like all vault functions, this returns bracketed wikilinks.
        The delimiter pattern (|||) allows extracting parts via modifiers.
    """
    import random

    # Deterministic sampling
    session_seed = int(vault.session.date.strftime("%Y%m%d"))
    cluster_seed = hash(("cluster", session_seed)) % (2**31)
    cluster_rng = random.Random(cluster_seed)

    notes = vault.notes()
    if not notes:
        return []

    sampled_seeds = cluster_rng.sample(notes, min(count, len(notes)))

    results = []
    for seed_note in sampled_seeds:
        neighbor_notes = vault.neighbours(seed_note, k)

        if neighbor_notes:
            # Add brackets (consistent with all vault functions)
            neighbor_links = [f"[[{n.obsidian_link}]]" for n in neighbor_notes]

            # Format like Tracery does (with commas and "and")
            if len(neighbor_links) == 1:
                neighbors_str = neighbor_links[0]
            elif len(neighbor_links) == 2:
                neighbors_str = f"{neighbor_links[0]} and {neighbor_links[1]}"
            else:
                last = neighbor_links[-1]
                neighbors_str = ", ".join(neighbor_links[:-1]) + f", and {last}"
        else:
            neighbors_str = ""

        # Seed also gets brackets (consistent with all vault functions)
        formatted = f"[[{seed_note.obsidian_link}]]|||{neighbors_str}"
        results.append(formatted)

    return results
```

**Custom Tracery Modifiers** to extract parts:
```python
# Already implemented in TraceryEngine._default_modifiers()
# See src/geistfabrik/tracery.py lines 243-268

".split_seed": lambda text: text.split("|||")[0] if "|||" in text else text,
".split_neighbours": lambda text: text.split("|||")[1] if "|||" in text else "",
```

**Tracery Usage**:
```yaml
# ✓ WORKS - Bundles seed + neighbours in preprocessing
# Template uses extracted values as-is (already bracketed)
origin: "#seed# shares space with #neighbours#. What connects them?"
cluster: ["$vault.semantic_clusters(2, 3)"]
seed: ["#cluster.split_seed#"]           # Extracts "[[Seed Note]]"
neighbours: ["#cluster.split_neighbours#"]  # Extracts "[[N1]], [[N2]]"

# ❌ WRONG - Don't add brackets, they're already in the extracted values
# origin: "[[#seed#]] shares space with [[#neighbours#]]"
# This would produce: [[[[Seed Note]]]] (double brackets!)
```

**Consistent Bracket Handling**:

- **ALL vault functions** return bracketed wikilinks: `"[[Note Title]]"`
- **Templates** use function results as-is: `#symbol#` (not `[[#symbol#]]`)
- **Cluster functions** follow this same pattern, with the addition of delimiter-based extraction

This design provides:
- **Consistency**: Single pattern for all vault functions
- **Simplicity**: Templates don't need bracket logic
- **Correctness**: Eliminates bracket-related bugs

**Design Guidelines for Tracery Functions**:

1. **Return bracketed wikilinks** - ALL vault functions must wrap note titles in `[[...]]` brackets
2. **Parameters must be resolvable at preprocessing** - Only integers, strings (quoted literals), not symbols
3. **Return structured strings** (for cluster functions) - Use delimiters (|||, |, ::, etc.) to bundle related data
4. **Add matching modifiers** (for cluster functions) - Custom Tracery modifiers to extract parts
5. **Format like Tracery** - Use same comma/and patterns for lists
6. **Test the preprocessing** - Functions execute once before any symbol expansion

**Validation**: The system includes a validator to catch anti-patterns:
```bash
# This will fail validation:
$vault.neighbours(#note#, 3)  # ERROR: Cannot pass symbols to functions
```

**Implementation Guide for Future Cluster Functions**:

When implementing new cluster functions (see post-1.0 roadmap), follow this pattern:

```python
@vault_function("example_clusters")
def example_clusters(vault: VaultContext, count: int = 2, k: int = 3) -> List[str]:
    """Template for implementing cluster functions.

    Args:
        count: Number of seed items to sample
        k: Number of related items per seed

    Returns:
        List of delimiter-separated strings with PRE-BRACKETED links
    """
    import random

    # 1. Deterministic sampling using session date
    session_seed = int(vault.session.date.strftime("%Y%m%d"))
    func_seed = hash(("your_function_name", session_seed)) % (2**31)
    rng = random.Random(func_seed)

    # 2. Sample seeds
    candidate_seeds = get_candidates(vault)  # Your logic here
    sampled_seeds = rng.sample(candidate_seeds, min(count, len(candidate_seeds)))

    # 3. Build clusters
    results = []
    for seed_item in sampled_seeds:
        # Get related items (your clustering logic)
        related_items = get_related(vault, seed_item, k)

        if related_items:
            # Add [[...]] brackets (standard pattern for all vault functions)
            related_links = [f"[[{item.obsidian_link}]]" for item in related_items]

            # Format with commas and "and" (match Tracery style)
            if len(related_links) == 1:
                related_str = related_links[0]
            elif len(related_links) == 2:
                related_str = f"{related_links[0]} and {related_links[1]}"
            else:
                last = related_links[-1]
                related_str = ", ".join(related_links[:-1]) + f", and {last}"
        else:
            related_str = ""

        # Add [[...]] brackets to seed (standard pattern for all vault functions)
        formatted = f"[[{seed_item.obsidian_link}]]|||{related_str}"
        results.append(formatted)

    return results
```

**Testing Requirements for Cluster Functions**:

1. **Test delimiter extraction**:
   ```python
   def test_your_cluster_splits_correctly():
       result = "[[Seed]]|||[[Item1]], [[Item2]]"
       assert result.split("|||")[0] == "[[Seed]]"
       assert result.split("|||")[1] == "[[Item1]], [[Item2]]"
   ```

2. **Test bracket formatting**:
   ```python
   def test_your_cluster_has_brackets():
       results = vault.call_function("your_clusters", 1, 2)
       for result in results:
           # All note references should be bracketed
           assert "[[" in result and "]]" in result
           # Should not have nested brackets
           assert "[[[[" not in result
   ```

3. **Test deeplinks** (if handling virtual notes):
   ```python
   def test_your_cluster_handles_deeplinks():
       # Create virtual note
       # Test that deeplinks format as [[File#Heading]]
   ```

4. **Test special characters**:
   ```python
   def test_your_cluster_handles_special_chars():
       # Create notes with commas, brackets, etc.
       # Ensure formatting doesn't break
   ```

**Planned Cluster Functions** (post-1.0 roadmap):
- `contrarian_clusters(count, k)` - Seed + contrarian notes
- `temporal_clusters(count, k)` - Seed + temporally related notes
- `bridge_clusters(count)` - Two distant notes + their bridge
- `tag_clusters(count, k)` - Tag + notes with that tag

#### Push-Pop with Vault Data

**Status**: ❌ **NOT IMPLEMENTED**

Push-pop stack memory (`#[variable:value]#` syntax) is not currently supported in GeistFabrik's custom TraceryEngine. The original Tracery feature allowed saving generated text for reuse:

```yaml
# This syntax is NOT supported:
origin: "#[hero:#vault_note#]story#"
vault_note: ["$vault.sample_notes(1)"]
story: "[[#hero#]] was never mentioned in [[#other#]]"
other: ["$vault.sample_notes(1)"]
```

**Workaround**: Use vault functions to pre-generate related data, or use code geists for complex state management.

**Future consideration**: Could be added to custom TraceryEngine if needed, but current cluster function pattern handles most use cases.

## Potential Features for GeistFabrik

This section ranks Tracery features **by the creative geists they would unlock**, rather than just technical complexity. Each feature is evaluated by asking: "What kinds of provocations become possible?"

### Tier 1: Foundational Geist Enablers

These features unlock entire categories of geists and should be prioritised first.

#### 1. Text Modifiers (.s, .ed, .a, .capitalize)

**What It Unlocks**: Grammatically correct, natural-sounding suggestions

**Status**: ✅ **IMPLEMENTED** in custom TraceryEngine

**Modifiers Available**:
- `.capitalize` - "hello" → "Hello"
- `.capitalizeAll` - "hello world" → "Hello World"
- `.s` - "cat" → "cats" (pluralization with irregular support)
- `.ed` - "walk" → "walked" (past tense with irregular support)
- `.a` - "owl" → "an owl" (article selection)

**Implementation**: Built into `TraceryEngine._default_modifiers()` (lines 39-241 in tracery.py)

**Geists Enabled**:

```yaml
# Grammar Fixer Geist - ensures proper articles
type: geist-tracery
id: grammar_natural
tracery:
  origin: "What if [[#note#]] were #verb.ed# like #comparison.a#?"
  note: ["$vault.sample_notes(1)"]
  verb: ["treat", "approach", "frame", "question"]
  comparison: ["experiment", "garden", "conversation", "organism"]
# Output: "What if [[Project Planning]] were treated like an experiment?"
```

```yaml
# Plural Perspective Geist - handles singular/plural correctly
type: geist-tracery
id: perspective_shift
tracery:
  origin: "Your #count# #topic.s# might all be #relationship#"
  count: ["three", "five", "seven"]
  topic: ["assumption", "question", "project", "habit"]
  relationship: ["symptoms of the same problem", "asking the same question"]
# Output: "Your three assumptions might all be symptoms of the same problem"
```

**Status**: ✅ **IMPLEMENTED** - see `semantic_neighbours.yaml` for working example

---

#### 2. Obsidian-Specific Modifiers

**What It Unlocks**: Syntax-aware geists that generate valid Obsidian markup

**Custom Modifiers Needed**:
- `.wikilink` - "Note" → "[[Note]]"
- `.embed` - "Note" → "![[Note]]"
- `.tag` - "topic" → "#topic"
- `.heading` - "Section" → "[[Note#Section]]"
- `.block` - Generates block references

**Geists Enabled**:

```yaml
# Embed Suggester Geist - proposes visual inclusions
type: geist-tracery
id: embed_suggester
tracery:
  origin: "Try embedding #note.embed# in your #context# note"
  note: ["$vault.sample_notes(1)"]
  context: ["current", "most recent", "active project"]
# Output: "Try embedding ![[Diagram of Systems]] in your current note"
```

```yaml
# Tag Bridge Geist - suggests tag connections
type: geist-tracery
id: tag_bridge
tracery:
  origin: "Notes tagged #tag1.tag# and #tag2.tag# might be about #theme#"
  tag1: ["$vault.random_tag()"]
  tag2: ["$vault.random_tag()"]
  theme: ["the same pattern", "opposite approaches", "parallel evolution"]
# Output: "Notes tagged #project and #philosophy might be about the same pattern"
```

```yaml
# Section Linker Geist - creates heading links
type: geist-tracery
id: section_linker
tracery:
  origin: "The #section.heading# section might answer [[#question#]]"
  section: ["Assumptions", "Future Work", "Open Questions", "Contradictions"]
  question: ["$vault.find_questions(1)"]
# Output: "The [[Note#Assumptions]] section might answer [[How does this scale?]]"
```

**Implementation**: Add custom modifiers to TraceryEngine:

```python
# src/geistfabrik/tracery.py
def obsidian_modifiers():
    return {
        'wikilink': lambda s: f"[[{s}]]",
        'embed': lambda s: f"![[{s}]]",
        'tag': lambda s: f"#{s.replace(' ', '-').lower()}",
        'heading': lambda s: f"#{s}",  # For use inside wikilinks
    }

# Add to TraceryEngine._default_modifiers() or use add_modifier()
```

---

#### 3. Weighted Distributions

**What It Unlocks**: Geists with controlled serendipity (common patterns + rare surprises)

**Current Limitation**: All rule options equally likely.

**Geists Enabled**:

```yaml
# Tonal Surprise Geist - mostly gentle, occasionally bold
type: geist-tracery
id: tonal_variety
tracery:
  origin: "#prompt# [[#note1#]] and [[#note2#]]?"
  note1: ["$vault.sample_notes(1)"]
  note2: ["$vault.sample_notes(1)"]
  prompt:
    # Gentle options (weight: 5 each via repetition)
    - "What connects"
    - "What connects"
    - "What connects"
    - "What connects"
    - "What connects"
    - "How might"
    - "How might"
    - "How might"
    - "How might"
    - "How might"
    # Bold options (weight: 1 each)
    - "What violence unites"
    - "What cosmic joke connects"
# Mostly outputs gentle prompts, occasionally surprising ones
```

```yaml
# Rare Insight Geist - surfaces unusual connections
type: geist-tracery
id: rare_connections
tracery:
  origin: "[[#note1#]] and [[#note2#]] are #relationship#"
  note1: ["$vault.sample_notes(1)"]
  note2: ["$vault.sample_notes(1)"]
  relationship:
    # Common (repeat 10x)
    - "adjacent" - "adjacent" - "adjacent" - "adjacent" - "adjacent"
    - "adjacent" - "adjacent" - "adjacent" - "adjacent" - "adjacent"
    # Rare (1x each)
    - "the same thing at different scales"
    - "in violent disagreement yet necessary to each other"
    - "two masks worn by the same truth"
```

**Workaround**: Repeat options (works but verbose).

**Enhancement**: YAML syntax for weights:

```yaml
# Desired syntax (requires custom parser)
prompt:
  - "What connects" (weight: 10)
  - "What violence unites" (weight: 1)
```

---

#### 4. Multiline Support

**What It Unlocks**: Structured provocations with bullets, steps, or multiple perspectives

**YAML Native**: Should work with `|` or `>` syntax.

**Geists Enabled**:

```yaml
# Multi-Perspective Geist - offers multiple framings
type: geist-tracery
id: three_lenses
tracery:
  origin: "#multiline#"
  multiline:
    - |
      Three ways to read [[#note#]]:
      - As a question: #question#
      - As a warning: #warning#
      - As an invitation: #invitation#
  note: ["$vault.sample_notes(1)"]
  question: ["What if this is the wrong problem?", "Who benefits from this framing?"]
  warning: ["This path leads to infinite regress", "Certainty here is dangerous"]
  invitation: ["Start from the opposite assumption", "Zoom out three levels"]
```

```yaml
# Step-by-Step Provocation Geist
type: geist-tracery
id: process_inverter
tracery:
  origin: |
    Invert your approach to [[#note#]]:

    1. #step1#
    2. #step2#
    3. #step3#

    What breaks? What emerges?
  note: ["$vault.sample_notes(1)"]
  step1: ["Start from the end", "Assume the opposite", "Remove the constraint"]
  step2: ["Work backwards", "Embrace the contradiction", "Make it worse first"]
  step3: ["Notice what's missing", "Ask who this serves", "Celebrate the failure"]
```

**Status**: **Needs testing** - YAML multiline syntax should work, needs verification with TraceryEngine.

---

### Tier 2: Rich Vocabulary Geists

These features enable more evocative, domain-specific language.

#### 5. External Wordlist Loading

**What It Unlocks**: Geists with curated, domain-specific vocabularies

**Geists Enabled**:

```yaml
# Power Language Geist - uses curated verb list
type: geist-tracery
id: reframe_verb
tracery:
  origin: "#verb.capitalize# [[#note#]] instead of analyzing it"
  verb: ["$vault.power_verbs()"]  # Loads from wordlist
  note: ["$vault.sample_notes(1)"]
# Wordlist: dissolve, inhabit, interrogate, seduce, transmute, witness
# Output: "Inhabit [[Systems Thinking]] instead of analyzing it"
```

```yaml
# Evocative Adjectives Geist
type: geist-tracery
id: poetic_reframe
tracery:
  origin: "What if [[#note#]] is fundamentally #adjective#?"
  note: ["$vault.sample_notes(1)"]
  adjective: ["$vault.evocative_adjectives()"]
# Wordlist: liminal, recursive, emergent, fugitive, generative, oblique
```

**Implementation**:

```python
# <vault>/_geistfabrik/vault_functions/wordlists.py
from geistfabrik.function_registry import vault_function

@vault_function("power_verbs")
def power_verbs(vault: VaultContext) -> List[str]:
    """Load curated action verbs"""
    wordlist_path = vault.vault.vault_dir / "_geistfabrik" / "wordlists" / "power_verbs.txt"
    with open(wordlist_path) as f:
        return [line.strip() for line in f if line.strip()]

@vault_function("evocative_adjectives")
def evocative_adjectives(vault: VaultContext) -> List[str]:
    """Load evocative descriptive words"""
    wordlist_path = vault.vault.vault_dir / "_geistfabrik" / "wordlists" / "evocative_adjectives.txt"
    with open(wordlist_path) as f:
        return [line.strip() for line in f if line.strip()]
```

**File Structure**:
```
<vault>/_geistfabrik/
  wordlists/
    power_verbs.txt
    evocative_adjectives.txt
    philosophical_terms.txt
    scamper_prompts.txt
```

---

### Tier 3: Temporal & Quantitative Geists

These features enable time-aware and number-aware suggestions.

#### 6. Temporal Modifiers

**What It Unlocks**: Retrospective and anniversary-aware geists

**Status**: Partially possible via vault functions (cluster pattern required)

**Challenge**: Functions like `note_age_days(note_title)` that take note titles as parameters cannot work directly in Tracery due to preprocessing order.

**Solution**: Use cluster functions or pre-format in vault function:

```python
@vault_function("old_notes_with_age")
def old_notes_with_age(vault: VaultContext, k: int = 1) -> List[str]:
    """Return old notes with age pre-formatted"""
    old = vault.old_notes(k)
    results = []
    for note in old:
        days = (datetime.now() - note.modified).days
        if days < 30:
            age_str = f"{days} days ago"
        elif days < 365:
            age_str = f"{days // 30} months ago"
        else:
            age_str = f"{days // 365} years ago"
        # Bundle note and age using delimiter
        results.append(f"{note.obsidian_link}|||{age_str}")
    return results
```

```yaml
# Usage with custom modifiers
origin: "#timespan# you wrote [[#note#]]. #reflection#"
note_data: ["$vault.old_notes_with_age(1)"]
note: ["#note_data.split_seed#"]
timespan: ["#note_data.split_neighbours#"]  # Extract pre-formatted age
reflection: ["Today's work answers it", "Time changes perspective"]
```

---

#### 7. Number Formatting

**What It Unlocks**: Statistical and count-based geists

**Geists Enabled**:

```yaml
# Productivity Pattern Geist - uses counts
type: geist-tracery
id: writing_rhythm
tracery:
  origin: "You wrote #count# notes this week—#observation#"
  count: ["$vault.count_recent(7)"]  # Returns "17"
  observation:
    - "a creative burst"
    - "steady momentum"
    - "is that more or less than usual?"
# With .spell modifier: "17" → "seventeen"
# Output: "You wrote seventeen notes this week—a creative burst"
```

**Implementation**: Custom modifier for number spelling/formatting.

---

### Tier 4: Developer Experience

These features improve geist maintainability and extensibility.

#### 8. Grammar Composition / Shared Fragments

**What It Unlocks**: DRY geist development, consistent voice across geists

**Geists Enabled**:

```yaml
# _geistfabrik/geists/tracery/_shared/provocations.yaml
provocations:
  - "What if"
  - "Consider that"
  - "Imagine"
  - "What assumes"

tone_gentle:
  - "might be"
  - "could be"
  - "seems to be"

tone_bold:
  - "is definitely"
  - "must be"
  - "cannot be anything but"
```

```yaml
# Multiple geists can import shared fragments
type: geist-tracery
id: assumption_challenger
import: ["_shared/provocations", "_shared/tone_gentle"]
tracery:
  origin: "#provocations# [[#note#]] #tone_gentle# backwards?"
  note: ["$vault.sample_notes(1)"]
```

**Workaround**: Use vault functions to return shared arrays.

**Enhancement**: YAML anchors/aliases or custom `import:` directive.

---

#### 9. Custom Modifiers Framework

**What It Unlocks**: Domain-specific transformations, user extensibility

**Status**: ✅ **IMPLEMENTED** via `TraceryEngine.add_modifier()`

The custom TraceryEngine supports adding modifiers:

```python
# Built-in modifiers (always available)
engine.modifiers = {
    'capitalize': ...,
    'capitalizeAll': ...,
    's': ...,
    'ed': ...,
    'a': ...,
    'split_seed': ...,
    'split_neighbours': ...,
}

# Add custom modifier
engine.add_modifier('reverse', lambda s: s[::-1])
engine.add_modifier('shout', lambda s: s.upper() + '!')

# For Obsidian syntax
engine.add_modifier('wikilink', lambda s: f"[[{s}]]")
engine.add_modifier('embed', lambda s: f"![[{s}]]")
engine.add_modifier('tag', lambda s: f"#{s.replace(' ', '-').lower()}")
```

**User extensibility pattern** (future):
```python
# <vault>/_geistfabrik/tracery_modifiers.py
def load_custom_modifiers():
    """Load user-defined Tracery modifiers"""
    return {
        # Text transformations
        'reverse': lambda s: s[::-1],
        'whisper': lambda s: s.lower() + '...',

        # Custom formatting
        'truncate': lambda s: s[:50] + '...' if len(s) > 50 else s,
        'first_word': lambda s: s.split()[0] if s else s,
    }
```

**Geists Enabled**: Any of the above examples using custom modifiers.

---

### Tier 5: Experimental / Niche

Features with limited use cases or design concerns.

#### 10. Visual Emphasis with Formatting

**What It Unlocks**: Typographically interesting provocations that use spacing and symbols for emphasis

**Geists Enabled**:

```yaml
# Contrast Visualizer Geist - uses spacing to emphasize tension
type: geist-tracery
id: visual_contrast
tracery:
  origin: |
    [[#note1#]]
              ↕
    [[#note2#]]

    What sits in the space between?
  note1: ["$vault.sample_notes(1)"]
  note2: ["$vault.sample_notes(1)"]
```

```yaml
# Symbol Metaphor Geist - uses unicode for visual metaphors
type: geist-tracery
id: symbol_metaphor
tracery:
  origin: "[[#note1#]] #symbol# [[#note2#]] — #interpretation#"
  note1: ["$vault.sample_notes(1)"]
  note2: ["$vault.sample_notes(1)"]
  symbol: ["⇄", "⊗", "∞", "⊃", "≋", "⟷"]
  interpretation:
    - "what would this operation reveal?"
    - "a relationship that has no name"
    - "the same energy in different forms"
# Output: "[[Project Planning]] ⇄ [[Gardening]] — the same energy in different forms"
```

**Status**: Enhances visual interest without being prescriptive. Uses Tracery's text generation for creative formatting rather than technical diagrams.

---

#### 11. Conditional Expansion

**What It Unlocks**: Adaptive geists that respond to vault state

**Design Concern**: Against Tracery's simplicity philosophy. Better handled by code geists.

**Alternative Pattern**:

```python
# Code geist handles conditionals, delegates to Tracery
def suggest(vault: VaultContext) -> List[Suggestion]:
    if vault.count_orphans() > 0:
        # Use "has_orphans" Tracery geist
        return execute_tracery_geist('has_orphans', vault)
    else:
        # Use "no_orphans" Tracery geist
        return execute_tracery_geist('no_orphans', vault)
```

---

#### 12. Semantic Modifiers (Embedding-Aware)

**What It Unlocks**: Modifiers that use vault embeddings

**Complexity**: Very high - embeddings not accessible in modifier context.

**Better Pattern**: Vault functions handle semantic operations:

```python
@vault_function("semantic_opposite")
def semantic_opposite(vault: VaultContext, note_title: str, k: int) -> List[str]:
    """Find notes semantically opposite to given note"""
    embedding = vault.get_embedding(note_title)
    # Find notes with maximum cosine distance
    opposites = vault.semantic_search(-embedding, k=k)
    return [n.title for n in opposites]
```

```yaml
origin: "[[#note#]] vs [[#opposite#]]—same question, opposite answers?"
note: ["$vault.sample_notes(1)"]
opposite: ["$vault.semantic_opposite(note, 1)"]  # If symbol reference worked
```

---

#### 13. State Persistence Across Expansions

**What It Unlocks**: Multi-turn geists, memory across suggestions

**Current Status**: Not needed - each geist runs once per session.

**Future Use**: If geists generate multiple suggestions, could track which notes already used.

---

#### 14. Recursion Depth Limiting

**What It Unlocks**: Protection against infinite recursion

**Status**: ✅ **IMPLEMENTED** - `max_depth = 50`

The TraceryEngine has a built-in recursion limit:

```python
# src/geistfabrik/tracery.py
class TraceryEngine:
    def __init__(self, grammar, seed=None):
        self.max_depth = 50  # Maximum recursion depth

    def expand(self, text, depth=0):
        if depth > self.max_depth:
            raise RecursionError(f"Tracery expansion exceeded max depth ({self.max_depth})")
```

This prevents infinite loops from circular symbol references.

---

## Feature Priority by Geist Impact

| Feature | Geist Categories Unlocked | Implementation | Status |
|---------|---------------------------|----------------|--------|
| **Text modifiers** (.s, .ed, .a) | Grammar-correct suggestions, natural language | Built-in TraceryEngine | ✅ **Implemented** |
| **Custom cluster modifiers** (.split_seed, .split_neighbours) | Seed-neighbour pairing for Tracery | Built-in TraceryEngine | ✅ **Implemented** |
| **Obsidian modifiers** (.wikilink, .embed, .tag) | Syntax-aware geists, embed suggestions, tag bridges | Custom modifiers (easy) | 🔲 **Not implemented** |
| **Weighted distributions** | Serendipity control, tonal variety, rare insights | Repeat options (workaround) or custom parser | ⚠️ **Workaround works** |
| **Multiline support** | Structured provocations, multi-perspective geists | YAML native | 🔲 **Needs testing** |
| **External wordlists** | Domain-specific vocabulary, evocative language | Vault functions (easy) | 🔲 **Pattern documented** |
| **Temporal modifiers** | Retrospective geists, anniversary awareness | Cluster function pattern | ⚠️ **Partial via clusters** |
| **Number formatting** | Statistical geists, count-based suggestions | Custom modifier | 🔲 **Not implemented** |
| **Grammar composition** | DRY development, consistent voice | YAML anchors or custom loader | 🔲 **Low priority** |
| **Custom modifier framework** | User extensibility, domain transformations | Built-in add_modifier() | ✅ **Implemented** |
| **Deterministic randomness** | Same date → same output | Built-in seed parameter | ✅ **Implemented** |
| **Multiple suggestions** | Multiple outputs per geist | Built-in count parameter | ✅ **Implemented** |
| **Validation** | Catch anti-patterns at load time | Built-in _validate_grammar() | ✅ **Implemented** |
| **Recursion limits** | Safety | Built-in max_depth = 50 | ✅ **Implemented** |
| **Push-pop stack** | Variable reuse across expansion | Not implemented | ❌ **Not available** |
| **Visual formatting** | Typographic emphasis, unicode symbols | Tracery native | ⚠️ **Experimental** |
| **Conditional expansion** | Adaptive geists | Anti-pattern - use code geists | ❌ **Avoid** |
| **Semantic modifiers** | Embedding-aware text transforms | Very complex | ⚠️ **Use vault functions** |
| **State persistence** | Multi-turn geists | Not needed (count handles this) | ✅ **Not applicable** |

## Recommended Implementation Order

1. ✅ **Text modifiers** - Already implemented in TraceryEngine
2. ✅ **Cluster modifiers** (.split_seed/.split_neighbours) - Already implemented
3. ✅ **Deterministic randomness** - Already implemented via seed parameter
4. ✅ **Recursion limits** - Already implemented (max_depth = 50)
5. ✅ **Validation** - Already implemented (_validate_grammar)
6. 🔲 **Implement Obsidian modifiers** (high impact, low complexity)
7. 🔲 **Document external wordlist pattern** (enables rich vocabulary)
8. 🔲 **Test multiline YAML support** (unlocks structured geists)
9. 🔲 **Add number formatting modifiers** (statistical geists)
10. 🔲 Consider weighted distributions enhancement (quality of life)

## Resources

- Official Tutorial: https://tracery.io
- GitHub Repository: https://github.com/galaxykate/tracery
- Academic Paper: "Tracery: An Author-Focused Generative Text Tool" (Compton et al., 2015)
- Visual Editor: https://tracery.io/editor
- Community Grammars: https://github.com/galaxykate/tracery/tree/tracery2/js/grammars

**GeistFabrik Implementation**:
- Custom TraceryEngine: `src/geistfabrik/tracery.py`
- Vault function integration: `src/geistfabrik/function_registry.py`
- Example geists: `src/geistfabrik/default_geists/tracery/`
- Tests: `tests/unit/test_tracery.py`
