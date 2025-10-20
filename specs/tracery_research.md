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

## Resources

- Official Tutorial: https://tracery.io
- GitHub Repository: https://github.com/galaxykate/tracery
- Academic Paper: "Tracery: An Author-Focused Generative Text Tool" (Compton et al., 2015)
- Visual Editor: https://tracery.io/editor
- Community Grammars: https://github.com/galaxykate/tracery/tree/tracery2/js/grammars
