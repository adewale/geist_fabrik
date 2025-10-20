# GeistFabrik Examples

This directory contains example implementations of the three-dimensional extensibility system in GeistFabrik.

## Directory Structure

```
examples/
├── metadata_inference/     # Metadata inference modules (Phase 8)
│   ├── complexity.py       # Text complexity metrics
│   ├── temporal.py         # Temporal/staleness metrics
│   └── structure.py        # Document structure analysis
│
├── vault_functions/        # Vault functions for geists (Phase 9)
│   ├── contrarian.py       # Find semantically dissimilar notes
│   └── questions.py        # Find question notes and metadata queries
│
└── geists/                 # Example geists
    ├── code/               # Python code geists
    │   ├── temporal_drift.py          # Find stale but important notes
    │   ├── creative_collision.py      # Suggest unexpected note combinations
    │   ├── bridge_builder.py          # Find notes that could bridge clusters
    │   ├── complexity_mismatch.py     # Find complexity/importance mismatches
    │   ├── question_generator.py      # Reframe statements as questions
    │   ├── link_density_analyzer.py   # Analyze link patterns
    │   ├── task_archaeology.py        # Find old incomplete tasks
    │   ├── concept_cluster.py         # Identify emergent concept clusters
    │   ├── stub_expander.py           # Find stubs worth expanding
    │   └── recent_focus.py            # Connect recent work to old notes
    │
    └── tracery/            # Tracery grammar geists
        ├── random_prompts.yaml        # Random creative prompts
        ├── note_combinations.yaml     # Combine random notes
        └── what_if.yaml               # "What if" question generator
```

## Installation

To use these examples with your vault, copy them to your vault's `_geistfabrik` directory:

```bash
# Copy metadata inference modules
cp -r examples/metadata_inference/* /path/to/vault/_geistfabrik/metadata_inference/

# Copy vault functions
cp -r examples/vault_functions/* /path/to/vault/_geistfabrik/vault_functions/

# Copy geists
cp -r examples/geists/* /path/to/vault/_geistfabrik/geists/
```

Or create symlinks for easier development:

```bash
ln -s $(pwd)/examples/metadata_inference /path/to/vault/_geistfabrik/metadata_inference
ln -s $(pwd)/examples/vault_functions /path/to/vault/_geistfabrik/vault_functions
ln -s $(pwd)/examples/geists /path/to/vault/_geistfabrik/geists
```

## Usage

### Metadata Inference Modules

Metadata modules automatically run when you invoke geists:

```python
# In your geists, metadata is automatically available
def suggest(vault):
    for note in vault.notes():
        metadata = vault.metadata(note)

        # From complexity.py
        reading_time = metadata['reading_time']
        lexical_diversity = metadata['lexical_diversity']

        # From temporal.py
        staleness = metadata['staleness']
        is_old = metadata['is_old']

        # From structure.py
        has_tasks = metadata['has_tasks']
        heading_count = metadata['heading_count']
```

### Vault Functions

Vault functions can be called from Python geists or Tracery geists:

```python
# From Python geists
def suggest(vault):
    # Call vault functions directly
    questions = vault.call_function('find_questions', k=5)
    contrarian = vault.call_function('contrarian_to', 'My Note', k=3)
```

```yaml
# From Tracery geists
tracery:
  origin:
    - "Consider these questions: #questions#"
    - "Contrarian view to #note#: #contrarian#"

  questions:
    - "$vault.find_questions(3)"

  contrarian:
    - "$vault.contrarian_to('My Note', 2)"
```

### Code Geists

Code geists are Python modules with a `suggest(vault)` function:

```bash
# Run all geists
uv run geistfabrik invoke

# Run specific geist
uv run geistfabrik invoke --geist temporal_drift

# Write suggestions to journal
uv run geistfabrik invoke --write
```

### Tracery Geists

Tracery geists use YAML grammar definitions and are automatically discovered:

```bash
# Tracery geists run alongside code geists
uv run geistfabrik invoke

# Control how many suggestions per geist
# (set in YAML: suggestions_per_invocation: 3)
```

## Creating Your Own Extensions

### 1. Metadata Inference Module

Create `_geistfabrik/metadata_inference/my_module.py`:

```python
def infer(note, vault):
    """Infer custom metadata about a note."""
    return {
        "my_metric": calculate_something(note),
        "my_flag": check_condition(note),
    }
```

### 2. Vault Function

Create `_geistfabrik/vault_functions/my_function.py`:

```python
from geistfabrik import vault_function

@vault_function("my_function")
def my_function(vault, arg1, k=5):
    """Do something with the vault."""
    results = []
    for note in vault.notes():
        if condition(note, arg1):
            results.append(note)
    return vault.sample(results, k)
```

### 3. Code Geist

Create `_geistfabrik/geists/code/my_geist.py`:

```python
from geistfabrik import Suggestion

def suggest(vault):
    """Generate suggestions based on vault analysis."""
    suggestions = []

    for note in vault.notes():
        metadata = vault.metadata(note)

        if interesting_condition(note, metadata):
            suggestions.append(
                Suggestion(
                    text="What if you ...",
                    notes=[note.title],
                    geist_id="my_geist"
                )
            )

    return vault.sample(suggestions, k=5)
```

### 4. Tracery Geist

Create `_geistfabrik/geists/tracery/my_geist.yaml`:

```yaml
type: geist-tracery
id: my_geist
description: My creative geist

tracery:
  origin:
    - "What if #subject# #verb#?"

  subject:
    - "you"
    - "your vault"

  verb:
    - "explored more"
    - "questioned assumptions"

suggestions_per_invocation: 2
```

## Example Geist Descriptions

### temporal_drift.py
Finds notes that haven't been modified in a long time but are well-connected in your vault. Suggests revisiting them to see if they still align with your current thinking.

### creative_collision.py
Randomly pairs notes from different domains to spark unexpected connections and creative insights.

### bridge_builder.py
Identifies notes that could serve as conceptual bridges between disconnected areas of your knowledge graph.

### complexity_mismatch.py
Finds notes where complexity doesn't match importance—either underdeveloped important notes or overcomplicated peripheral notes.

### question_generator.py
Suggests reframing declarative notes as questions to encourage deeper exploration and critical thinking.

### link_density_analyzer.py
Analyzes the ratio of links to content and suggests notes that might be over-linked (overwhelming) or under-linked (isolated).

### task_archaeology.py
Discovers old incomplete tasks in your notes and asks whether they're still relevant or should be archived.

### concept_cluster.py
Identifies emergent clusters of semantically related notes that might represent a theme worth naming and organizing.

### stub_expander.py
Finds very short notes with connections (stubs) that might be worth developing into more substantial notes.

### recent_focus.py
Analyzes your recently modified notes and connects them to older related notes, revealing how your thinking has evolved.

## Philosophy

These examples demonstrate GeistFabrik's core principle: **muses, not oracles**. Each geist asks "What if?" rather than declaring "Here's how." They're designed to:

- **Provoke** rather than prescribe
- **Question** rather than answer
- **Diverge** rather than converge
- **Sample** rather than rank

Geists should feel like opening a gift: surprising, delightful, and occasionally serendipitous.

## Contributing

To add your own example geists to this collection:

1. Create your geist following the patterns above
2. Test it with `geistfabrik test my_geist --vault testdata/kepano-obsidian-main`
3. Add documentation explaining what it does and why
4. Submit a pull request with your example

Great geists:
- Ask interesting questions
- Respect the user's attention
- Find surprising patterns
- Maintain appropriate randomness
- Fail gracefully

## License

[Same as GeistFabrik main project]
