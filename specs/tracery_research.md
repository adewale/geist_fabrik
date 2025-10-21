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
  "story": "#hero# traveled with their pet #heroPet#. #hero# was never #mood#.",
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
import tracery
from tracery.modifiers import base_english

rules = {
    'origin': '#hello.capitalize#, #location#!',
    'hello': ['hello', 'greetings', 'howdy'],
    'location': ['world', 'universe', 'cosmos']
}
grammar = tracery.Grammar(rules)
grammar.add_modifiers(base_english)
print(grammar.flatten("#origin#"))
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
| **L-Systems** | Mathematical rigor, good for recursive structures | Complex for text, better for graphics | Formal generation, plant/fractal modeling |
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

Tracery emerged from Kate Compton's work at UC Santa Cruz's Center for Games and Playable Media (2014-2015). It gained widespread adoption through:
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
   - `$vault.tagged('project', 2)` → `["Project X", "Project Y"]`
4. Grammar symbols updated with results
5. Tracery expansion proceeds with populated arrays

#### Parameter Types

Vault functions support simple parameter types:
- **Integers**: `$vault.sample_notes(5)`
- **Strings** (quoted): `$vault.tagged('project', 2)`
- **Strings** (single-quoted): `$vault.notes_by_mood('positive', 1)`

**Limitation**: Complex objects or nested function calls not supported. Each function call must be self-contained.

#### Return Value Handling

Vault functions must return **lists of strings** (typically note titles):

```python
@vault_function("sample_notes")
def sample_notes(vault: VaultContext, k: int) -> List[str]:
    """Sample k random notes, return their titles"""
    notes = vault.sample(k)
    return [note.title for note in notes]
```

**Edge Cases**:
- **Empty results**: Function returns `[]` → Symbol has empty array → Tracery fails gracefully
- **Fewer than requested**: `$vault.orphans(10)` with only 3 orphans → Returns `["Note 1", "Note 2", "Note 3"]`
- **Single result**: Still wrapped in list → `["Only Note"]`

### Complete Integration Example

```yaml
# <vault>/_geistfabrik/geists/tracery/semantic_bridge.yaml
type: geist-tracery
id: semantic_bridge
tracery:
  origin: "[[#note1#]] and [[#note2#]] both seem to be about #theme#. #question#?"
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

**Implementation Strategy**:
1. **Session-level seed**: Derive from date (e.g., `int(date.strftime('%Y%m%d'))`)
2. **VaultContext random state**: Pass seeded RNG to all vault functions
3. **Vault function sampling**: Use context's RNG, not Python's `random.choice()`
4. **Tracery internal randomness**:

**Open Question**: Does pytracery respect an external random seed? If not, may need to:
- Pre-expand all vault function calls deterministically
- Control Tracery's rule selection by manually choosing indices
- Wrap pytracery with seeded selection

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

**Answer**: No, based on spec architecture. Each Tracery geist:
1. Expands grammar once per session
2. Produces single text output
3. Wraps in `Suggestion(text=..., notes=..., geist_id=...)`
4. Returns list with one element

To generate multiple suggestions, create multiple Tracery geists or use a code geist.

### Python Implementation with pytracery

```python
import yaml
import tracery
from tracery.modifiers import base_english
import re

def load_tracery_geist(path: str):
    """Load YAML geist file"""
    with open(path) as f:
        data = yaml.safe_load(f)

    assert data['type'] == 'geist-tracery'
    return data['id'], data['tracery']

def execute_tracery_geist(geist_id: str, grammar_dict: dict,
                          vault: VaultContext) -> List[Suggestion]:
    """Execute Tracery geist with vault integration"""

    # 1. Execute all $vault.* function calls
    processed_grammar = {}
    for symbol, rules in grammar_dict.items():
        processed_rules = []
        for rule in rules:
            if rule.startswith('$vault.'):
                # Parse and execute vault function
                result = execute_vault_function(rule, vault)
                processed_rules.extend(result)  # Flatten results
            else:
                processed_rules.append(rule)
        processed_grammar[symbol] = processed_rules

    # 2. Create Tracery grammar
    grammar = tracery.Grammar(processed_grammar)
    grammar.add_modifiers(base_english)

    # 3. Generate text
    try:
        text = grammar.flatten('#origin#')
    except Exception as e:
        print(f"⚠️  Tracery expansion failed for {geist_id}: {e}")
        return []

    # 4. Extract note references
    notes = extract_note_references(text)

    # 5. Create suggestion
    return [Suggestion(text=text, notes=notes, geist_id=geist_id)]

def execute_vault_function(call_str: str, vault: VaultContext) -> List[str]:
    """Parse and execute $vault.function(args) calls"""
    import re
    pattern = r'\$vault\.(\w+)\(([^)]*)\)'
    match = re.match(pattern, call_str)

    if not match:
        raise ValueError(f"Invalid vault function syntax: {call_str}")

    func_name, args_str = match.groups()

    # Get registered function
    func = vault.functions.get(func_name)
    if not func:
        raise ValueError(f"Unknown vault function: {func_name}")

    # Parse arguments (simplified - needs proper parsing)
    args = eval(f"[{args_str}]")  # UNSAFE - use proper parser

    # Execute
    return func(vault, *args)
```

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
from geistfabrik.registry import vault_function

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
    return [note.title for note, _ in sorted_notes[:k]]
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

**Answer**: No direct support. Tracery expands symbols independently. Workaround:
- Generate all data in single vault function
- Return structured results
- Split in Tracery

```python
@vault_function("note_and_neighbour")
def note_and_neighbour(vault: VaultContext) -> List[str]:
    """Return 'NoteA|NoteB' format"""
    note = vault.sample(1)[0]
    neighbour = vault.semantic_search(note.title, k=1)[0]
    return [f"{note.title}|{neighbour.title}"]
```

```yaml
# Then parse in origin
origin: "Compare these: [[#pair#]]"
pair: ["$vault.note_and_neighbour()"]
# Not ideal but works around limitation
```

#### Push-Pop with Vault Data

```yaml
origin: "#[hero:#vault_note#]story#"
vault_note: ["$vault.sample_notes(1)"]
story: "[[#hero#]] was never mentioned in [[#other#]]"
other: ["$vault.sample_notes(1)"]
```

**Status**: Should work. Vault function executes first, result stored in push-pop stack.

**Uncertainty**: Needs testing with pytracery implementation.

## Potential Features for GeistFabrik

This section identifies Tracery features that could enhance GeistFabrik's Tracery geist capabilities.

### 1. Text Modifiers

**What Tracery Provides**:
- `.capitalize` - "hello" → "Hello"
- `.capitalizeAll` - "hello world" → "Hello World"
- `.s` - "cat" → "cats" (pluralization)
- `.ed` - "walk" → "walked" (past tense)
- `.a` - "owl" → "an owl" (article selection)

**GeistFabrik Status**: Unclear if implemented via pytracery's `base_english` modifiers.

**Use Case**:
```yaml
origin: "What if [[#note.capitalize#]] were #verb.ed# differently?"
note: ["$vault.sample_notes(1)"]
verb: ["approach", "frame", "question"]
```

**Implementation**: Pytracery includes `tracery.modifiers.base_english` - verify it's loaded.

### 2. Custom Modifiers

**What Tracery Provides**: Ability to add custom text transformations.

**JavaScript Example**:
```javascript
grammar.addModifiers({
  'allcaps': (s) => s.toUpperCase(),
  'reverse': (s) => s.split('').reverse().join('')
});
```

**GeistFabrik Use Cases**:
- `.backlink` - Convert "Note Title" → "[[Note Title]]"
- `.tag` - Convert "topic" → "#topic"
- `.truncate` - Limit length for long note titles
- `.basename` - Extract filename from path

**Example**:
```yaml
origin: "#note.backlink# relates to #tag.tag#"
note: ["$vault.sample_notes(1)"]  # Returns "Project Planning"
tag: ["project", "planning", "strategy"]
# Output: [[Project Planning]] relates to #project
```

**Implementation Complexity**: Medium. Requires extending pytracery's modifier system.

### 3. Conditional Expansion

**What Tracery Lacks**: Native if/else logic within grammar.

**Common Workaround**: Multiple origin rules with different patterns.

**GeistFabrik Enhancement**:
```yaml
# Current: Must duplicate logic
origin: ["#has_orphans#", "#no_orphans#"]
has_orphans: "Orphan note: [[#orphan#]]"
no_orphans: "No orphaned notes today"

# Desired: Conditional based on vault state
# (Not natively supported by Tracery)
```

**Alternative**: Code geist handles conditional logic; Tracery stays simple.

**Priority**: Low - against Tracery's design philosophy of simplicity.

### 4. Number Formatting

**What Tracery Lacks**: Numeric operations or formatting.

**Use Case**:
```yaml
origin: "You wrote #count# notes in #timeframe#"
count: ["$vault.count_recent(7)"]  # Returns "42"
timeframe: ["the last week"]
# Desired: "42" → "forty-two" or handle plurals
```

**Workaround**: Vault function returns formatted string.

**Enhancement**: Custom modifier for number formatting.

### 5. SVG/Visual Generation

**What Tracery Supports**: Can generate SVG markup for procedural graphics.

**Kate Compton's Examples**: Tracery generating shapes, patterns, colors.

**GeistFabrik Application**: Probably out of scope (text-focused suggestions).

**Possible Use**: Generate Mermaid diagram syntax?

```yaml
origin: "#mermaid_graph#"
mermaid_graph: "graph TD\n  #node1# --> #node2#"
node1: ["$vault.sample_notes(1)"]
node2: ["$vault.sample_notes(1)"]
```

**Priority**: Low - niche use case.

### 6. Distribution Control

**What Tracery Lacks**: Weighted random selection (all rules equally likely).

**Desired Feature**:
```yaml
# Want "rare" to appear less often
mood:
  - "the same journey" (weight: 5)
  - "necessary opposites" (weight: 5)
  - "false dichotomies" (weight: 2)
  - "a cosmic joke" (weight: 1)  # rare
```

**Workaround**: Repeat common options.

```yaml
mood:
  - "the same journey"
  - "the same journey"  # 2x as likely
  - "necessary opposites"
  - "necessary opposites"
  - "a cosmic joke"  # 1x
```

**Enhancement**: Custom grammar parser supporting weights.

### 7. State Persistence

**What Tracery Lacks**: State across multiple expansions.

**GeistFabrik Context**: Each geist runs once per session (single expansion).

**Potential Use**: If geist generated multiple suggestions:
```yaml
# Remember which notes already used
origin: "#[used:#note1#]first# | #[used:#note2#]second#"
# Ensure note2 ≠ note1
```

**Current Status**: Not needed (single expansion per geist).

### 8. Recursive Depth Limiting

**What Tracery Has**: Potential infinite recursion.

```yaml
origin: "#loop#"
loop: ["#loop# forever"]  # ∞
```

**GeistFabrik Need**: Timeout/depth protection.

**Implementation**: Pytracery likely has depth limits. Verify and configure.

### 9. Multiline Support

**What Tracery Supports**: Multiline strings in rules.

**GeistFabrik Use**:
```yaml
origin: "#multiline_suggestion#"
multiline_suggestion:
  - |
    What if [[#note1#]] and [[#note2#]] are:
    - Two sides of the same coin
    - Answering different versions of the same question
    - Describing the same pattern at different scales
```

**YAML Compatibility**: Should work with YAML's `|` or `>` multiline syntax.

**Status**: Test with pytracery to confirm.

### 10. External Data Loading

**What Tracery Supports** (in JavaScript): Loading external JSON files into grammars.

**GeistFabrik Equivalent**: Vault functions already provide this (loading vault data).

**Additional Feature**: Load static word lists?

```python
@vault_function("power_verbs")
def power_verbs(vault: VaultContext) -> List[str]:
    """Load curated verb list"""
    with open('_geistfabrik/wordlists/power_verbs.txt') as f:
        return [line.strip() for line in f]
```

```yaml
origin: "#verb.capitalize# the way you think about [[#note#]]"
verb: ["$vault.power_verbs()"]
```

**Priority**: Medium - enables richer vocabularies without hardcoding.

### 11. Grammar Composition

**Desired Feature**: Reusable grammar fragments across geists.

```yaml
# _geistfabrik/geists/tracery/_fragments/provocations.yaml
provocations:
  - "What if"
  - "Consider that"
  - "Imagine"

# Then import in geists:
# (Not currently supported)
import: ["_fragments/provocations"]
origin: "#provocations# [[#note#]] is backwards?"
```

**Workaround**: Duplicate common fragments or use vault functions.

**Enhancement**: YAML includes/anchors or custom loader.

### 12. Obsidian-Specific Modifiers

**Custom Modifiers for Obsidian Syntax**:

- `.wikilink` - "Note" → "[[Note]]"
- `.embed` - "Note" → "![[Note]]"
- `.heading` - "Note" → "[[Note#Heading]]"
- `.block` - "Note" → "[[Note^block123]]"
- `.tag` - "topic" → "#topic"
- `.nestedtag` - "project/active" → "#project/active"

**Example**:
```yaml
origin: "Embed this: #note.embed#"
note: ["$vault.sample_notes(1)"]
# Output: "Embed this: ![[Note Title]]"
```

**Implementation**: Add to pytracery modifiers dictionary.

```python
def obsidian_modifiers():
    return {
        'wikilink': lambda s: f"[[{s}]]",
        'embed': lambda s: f"![[{s}]]",
        'tag': lambda s: f"#{s.replace(' ', '-')}",
    }

grammar.add_modifiers(obsidian_modifiers())
```

**Priority**: High - directly useful for GeistFabrik output.

### 13. Temporal Modifiers

**Custom Date/Time Formatting**:

```yaml
origin: "#timepoint.ago# you wrote [[#note#]]"
timepoint: ["$vault.note_age_days(<note>)"]  # Returns "127"
# With .ago modifier: "127" → "127 days ago" or "4 months ago"
```

**Implementation**: Vault function returns formatted string instead.

**Alternative**: Custom modifier:
```python
'ago': lambda days: format_timespan(int(days))
```

### 14. Semantic Modifiers

**Using Embeddings in Modifiers**:

```yaml
origin: "[[#note#]] but #direction.semantic#"
note: ["$vault.sample_notes(1)"]
direction: ["opposite", "adjacent", "orthogonal"]
# .semantic modifier uses embeddings to find semantically related concepts
```

**Complexity**: Very high - would need embedding lookups in modifier.

**Alternative**: Vault functions handle semantic operations.

**Priority**: Low - vault functions already provide this capability.

### Feature Priority Summary

| Feature | Priority | Complexity | Tracery Native? |
|---------|----------|------------|-----------------|
| Text modifiers (.s, .ed, .a) | High | Low | Yes (via pytracery) |
| Obsidian-specific modifiers | High | Low | No (custom) |
| Custom modifiers framework | High | Medium | Yes (pytracery) |
| Weighted distributions | Medium | Medium | No (workaround: repeat) |
| External wordlist loading | Medium | Low | No (via vault functions) |
| Multiline YAML support | Medium | Low | Yes (YAML native) |
| Number formatting | Low | Low | No (custom modifier) |
| Grammar composition/imports | Low | Medium | No (custom loader) |
| Conditional expansion | Low | High | No (anti-pattern) |
| Visual/diagram generation | Low | Medium | Yes (but niche) |
| Semantic modifiers | Low | Very High | No (complex) |

## Resources

- Official Tutorial: https://tracery.io
- GitHub Repository: https://github.com/galaxykate/tracery
- Academic Paper: "Tracery: An Author-Focused Generative Text Tool" (Compton et al., 2015)
- Visual Editor: https://tracery.io/editor
- Community Grammars: https://github.com/galaxykate/tracery/tree/tracery2/js/grammars
- Pytracery Documentation: https://github.com/aparrish/pytracery
