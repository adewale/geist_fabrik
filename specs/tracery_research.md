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

This section ranks Tracery features **by the creative geists they would unlock**, rather than just technical complexity. Each feature is evaluated by asking: "What kinds of provocations become possible?"

### Tier 1: Foundational Geist Enablers

These features unlock entire categories of geists and should be prioritized first.

#### 1. Text Modifiers (.s, .ed, .a, .capitalize)

**What It Unlocks**: Grammatically correct, natural-sounding suggestions

**Modifiers Available in pytracery's `base_english`**:
- `.capitalize` - "hello" → "Hello"
- `.capitalizeAll` - "hello world" → "Hello World"
- `.s` - "cat" → "cats" (pluralization)
- `.ed` - "walk" → "walked" (past tense)
- `.a` - "owl" → "an owl" (article selection)

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

**Implementation Status**: Pytracery includes this. **Action: Verify loaded in GeistFabrik**.

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

**Implementation**: Add custom modifiers to pytracery:

```python
def obsidian_modifiers():
    return {
        'wikilink': lambda s: f"[[{s}]]",
        'embed': lambda s: f"![[{s}]]",
        'tag': lambda s: f"#{s.replace(' ', '-').lower()}",
        'heading': lambda s: f"#{s}",  # For use inside wikilinks
    }
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

**Status**: **Needs testing** - verify YAML multiline works with pytracery.

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
@vault_function("power_verbs")
def power_verbs(vault: VaultContext) -> List[str]:
    """Load curated action verbs"""
    wordlist_path = vault.geistfabrik_dir / "wordlists" / "power_verbs.txt"
    with open(wordlist_path) as f:
        return [line.strip() for line in f if line.strip()]

@vault_function("evocative_adjectives")
def evocative_adjectives(vault: VaultContext) -> List[str]:
    """Load evocative descriptive words"""
    wordlist_path = vault.geistfabrik_dir / "wordlists" / "evocative_adjectives.txt"
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

**Geists Enabled**:

```yaml
# Memory Mirror Geist - surfaces old notes with readable timespans
type: geist-tracery
id: memory_mirror
tracery:
  origin: "#timespan.ago# you wrote [[#old_note#]]. Today's [[#new_note#]] #relationship#"
  old_note: ["$vault.old_notes(1)"]
  new_note: ["$vault.recent_notes(1)"]
  timespan: ["$vault.note_age_days(old_note)"]  # Returns "847"
  relationship: ["answers it", "contradicts it", "completes it", "has forgotten it"]
# With .ago modifier: "847" → "2 years ago"
# Output: "2 years ago you wrote [[Early Thoughts]]. Today's [[Synthesis]] answers it"
```

```yaml
# Seasonal Rhythm Geist - detects patterns across time
type: geist-tracery
id: seasonal_notes
tracery:
  origin: "Every #season.capitalize#, you return to [[#topic#]]"
  season: ["$vault.current_season()"]  # "spring", "fall", etc.
  topic: ["$vault.notes_from_season(season, 1)"]
```

**Implementation Options**:

1. **Vault function returns formatted string** (easier):
```python
@vault_function("note_age_formatted")
def note_age_formatted(vault: VaultContext, note_title: str) -> List[str]:
    days = vault.note_age_days(note_title)
    if days < 30:
        return [f"{days} days ago"]
    elif days < 365:
        return [f"{days // 30} months ago"]
    else:
        return [f"{days // 365} years ago"]
```

2. **Custom modifier** (more flexible):
```python
def temporal_modifier(days_str: str) -> str:
    days = int(days_str)
    if days < 30: return f"{days} days ago"
    elif days < 365: return f"{days // 30} months ago"
    else: return f"{days // 365} years ago"

grammar.add_modifiers({'ago': temporal_modifier})
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

**Already Supported by pytracery** - just need to document pattern:

```python
# <vault>/_geistfabrik/tracery_modifiers.py
def load_custom_modifiers():
    """Load user-defined Tracery modifiers"""
    return {
        # Text transformations
        'reverse': lambda s: s[::-1],
        'shout': lambda s: s.upper() + '!',
        'whisper': lambda s: s.lower() + '...',

        # Obsidian syntax
        'wikilink': lambda s: f"[[{s}]]",
        'embed': lambda s: f"![[{s}]]",
        'tag': lambda s: f"#{s.replace(' ', '-').lower()}",

        # Length control
        'truncate': lambda s: s[:50] + '...' if len(s) > 50 else s,
        'first_word': lambda s: s.split()[0] if s else s,

        # Custom formatting
        'ago': lambda days: format_timespan(int(days)),
        'spell': lambda n: num2words(int(n)),
    }
```

**Geists Enabled**: Any of the above examples using custom modifiers.

---

### Tier 5: Experimental / Niche

Features with limited use cases or design concerns.

#### 10. Visual/Diagram Generation

**What It Unlocks**: Mermaid diagram suggestions (niche but interesting)

**Geists Enabled**:

```yaml
# Diagram Suggester Geist - generates Mermaid syntax
type: geist-tracery
id: diagram_suggester
tracery:
  origin: |
    Try this diagram:
    ```mermaid
    graph LR
      #node1# --> #node2#
      #node2# --> #node3#
      #node3# -.-> #node1#
    ```
  node1: ["$vault.sample_notes(1)"]
  node2: ["$vault.sample_notes(1)"]
  node3: ["$vault.sample_notes(1)"]
```

**Status**: Possible but niche. Most users want text provocations.

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

#### 14. Recursive Depth Limiting

**What It Unlocks**: Protection against infinite recursion

**Status**: Pytracery likely has built-in limits. **Action: Verify and configure**.

---

## Feature Priority by Geist Impact

| Feature | Geist Categories Unlocked | Implementation | Status |
|---------|---------------------------|----------------|--------|
| **Text modifiers** (.s, .ed, .a) | Grammar-correct suggestions, natural language | Built-in pytracery | **Verify loaded** |
| **Obsidian modifiers** (.wikilink, .embed, .tag) | Syntax-aware geists, embed suggestions, tag bridges | Custom modifiers (easy) | **Implement** |
| **Weighted distributions** | Serendipity control, tonal variety, rare insights | Repeat options (workaround) or custom parser | **Workaround works** |
| **Multiline support** | Structured provocations, multi-perspective geists | YAML native | **Test with pytracery** |
| **External wordlists** | Domain-specific vocabulary, evocative language | Vault functions (easy) | **Implement pattern** |
| **Temporal modifiers** | Retrospective geists, anniversary awareness | Custom modifier or vault function | **Medium priority** |
| **Number formatting** | Statistical geists, count-based suggestions | Custom modifier | **Medium priority** |
| **Grammar composition** | DRY development, consistent voice | YAML anchors or custom loader | **Low priority** |
| **Custom modifier framework** | User extensibility, domain transformations | Built-in pytracery | **Document pattern** |
| **Visual generation** | Diagram suggestions (Mermaid) | Tracery native | **Niche use case** |
| **Conditional expansion** | Adaptive geists | Anti-pattern - use code geists | **Avoid** |
| **Semantic modifiers** | Embedding-aware text transforms | Very complex | **Use vault functions** |
| **State persistence** | Multi-turn geists | Not needed (single expansion) | **Not applicable** |
| **Recursion limits** | Safety | Pytracery built-in | **Verify config** |

## Recommended Implementation Order

1. **Verify text modifiers loaded** (`base_english` from pytracery)
2. **Implement Obsidian modifiers** (high impact, low complexity)
3. **Document external wordlist pattern** (enables rich vocabulary)
4. **Test multiline YAML support** (unlocks structured geists)
5. **Add temporal modifiers** (retrospective geists)
6. **Document custom modifier framework** (user extensibility)
7. Consider weighted distributions enhancement (quality of life)

## Resources

- Official Tutorial: https://tracery.io
- GitHub Repository: https://github.com/galaxykate/tracery
- Academic Paper: "Tracery: An Author-Focused Generative Text Tool" (Compton et al., 2015)
- Visual Editor: https://tracery.io/editor
- Community Grammars: https://github.com/galaxykate/tracery/tree/tracery2/js/grammars
- Pytracery Documentation: https://github.com/aparrish/pytracery
