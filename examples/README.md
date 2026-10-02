# GeistFabrik Examples

This directory contains example implementations for extending GeistFabrik through metadata inference and vault functions.

## Important: Geists are Bundled, Not in Examples

**All default geists are now bundled with GeistFabrik** in `src/geistfabrik/default_geists/`. They work immediately on first run—no installation needed.

This `examples/` directory focuses on:
- **Metadata inference modules** - Adding custom properties to notes
- **Vault functions** - Creating reusable functions for Tracery geists
- **Example geists** - Learning materials, not installed by default:
  - `geists/code/` - the GraphPatternFinder extension API
    (`geistfabrik.graph_analysis`), used by the graph-structural geists the
    reuse-abstractions spec proposed (structural holes, path-length
    anomalies, bridge redundancy), plus the `MetadataAnalyser` API
    (`metadata_outlier_detector.py`)
  - `geists/tracery/` - Tracery patterns retired from the bundled set
    (save actions, the cluster pattern, every modifier)

To create custom geists, refer to the bundled source code in `src/geistfabrik/default_geists/` and to `examples/geists/code/`.

## Directory Structure

```
examples/
├── geists/
│   ├── code/               # Example code geists (graph and metadata APIs)
│   └── tracery/            # Example Tracery geists (save actions, modifiers)
│
├── metadata_inference/     # Custom metadata modules
│   ├── complexity.py       # Text complexity metrics
│   ├── temporal.py         # Temporal/staleness metrics
│   └── structure.py        # Document structure analysis
│
└── vault_functions/        # Custom vault functions
    ├── contrarian.py       # Least-similar-in-topic query (distinct from the builtin)
    └── questions.py        # Find question notes
```

## Installation

Copy these examples to your vault's `_geistfabrik` directory:

```bash
# Copy metadata inference modules
cp -r examples/metadata_inference/* /path/to/vault/_geistfabrik/metadata_inference/

# Copy vault functions
cp -r examples/vault_functions/* /path/to/vault/_geistfabrik/vault_functions/
```

Managed plugin paths reject symlinks so a vault cannot escape its configured
root through path indirection. During development, repeat the copy after edits
or keep the plugin source directly in the vault.

## Usage

### Metadata Inference Modules

Metadata modules automatically run when you invoke geists:

```python
# In your custom geists, metadata is automatically available
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
    questions = vault.call_function('find_questions', count=5)
    # Least similar in topic (not opposing: embeddings measure topic, not stance)
    distant = vault.call_function('example_contrarian_to', 'My Note', count=3)
```

```yaml
# From Tracery geists
tracery:
  origin:
    - "Consider these questions: #questions#"
    - "Far from #note# in topic: #distant#"

  questions:
    - "$vault.find_questions(3)"

  note:
    - "[[My Note]]"

  # A literal note name only: a #symbol# argument is rejected, because vault
  # functions run before symbols expand
  distant:
    - "$vault.example_contrarian_to('My Note', 2)"
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
def my_function(vault, arg1, count=5):
    """Do something with the vault."""
    results = []
    for note in vault.notes():
        if condition(note, arg1):
            results.append(note)
    # Like every vault function, return bracketed [[links]]
    return [f"[[{note.link_text}]]" for note in vault.sample(results, count)]
```

### 3. Creating Custom Geists

To create custom geists, view the bundled source code in `src/geistfabrik/default_geists/` for examples, then create your own:

#### Code Geist

Create `_geistfabrik/geists/code/my_geist.py`:

```python
from geistfabrik import Suggestion
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import VaultContext

def suggest(vault: "VaultContext") -> list[Suggestion]:
    """Generate suggestions based on vault analysis.

    This example demonstrates VaultContext helper functions:
    - outgoing_links(note) - Get notes this note links to
    - has_link(a, b) - Check if two notes are linked
    - graph_neighbours(note) - Get all connected notes (incoming + outgoing)
    """
    suggestions = []

    for note in vault.notes():
        # Get metadata
        metadata = vault.metadata(note)

        # Example: Find notes with few outgoing links but many backlinks
        outgoing = vault.outgoing_links(note)  # Notes this note links to
        incoming = vault.backlinks(note)        # Notes linking to this note

        # Link with note.link_text (the file name, or "file|Title" when the
        # title differs), never note.title, which may not resolve
        if len(incoming) > 5 and len(outgoing) < 2:
            suggestions.append(
                Suggestion(
                    text=f"[[{note.link_text}]] is a hub (more than 5 incoming) but "
                         "links out rarely. What connections could it make?",
                    notes=[note.link_text],
                    geist_id="my_geist"
                )
            )

        # Example: Find semantically similar notes that aren't linked
        similar = vault.neighbours(note, count=5)
        for candidate in similar:
            if not vault.has_link(note, candidate):  # Check if linked (bidirectional)
                suggestions.append(
                    Suggestion(
                        text=f"[[{note.link_text}]] and [[{candidate.link_text}]] are "
                             "semantically similar but not linked. Missing connection?",
                        notes=[note.link_text, candidate.link_text],
                        geist_id="my_geist"
                    )
                )

        # Example: Analyze graph neighborhood density
        neighbours = vault.graph_neighbours(note)  # All connected notes (both directions)
        if len(neighbours) > 10:
            # Check how interconnected the neighbours are
            interconnections = sum(
                1 for i, n1 in enumerate(neighbours)
                for n2 in neighbours[i+1:]
                if vault.has_link(n1, n2)
            )

            if interconnections < len(neighbours):
                suggestions.append(
                    Suggestion(
                        text=f"[[{note.link_text}]] has {len(neighbours)} neighbours, "
                             "but they're not well connected to each other. "
                             "Is there a central theme?",
                        notes=[note.link_text],
                        geist_id="my_geist"
                    )
                )

    return vault.sample(suggestions, count=5)
```

#### Tracery Geist

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

count: 2
```

## Bundled Default Geists

GeistFabrik includes bundled default geists that work immediately:

**Code geists include:**
- temporal_drift, creative_collision, bridge_builder, orphan_connector
- question_generator, link_density_analyser, task_archaeology, concept_cluster
- stub_expander, recent_focus, surprisal, concept_drift
- and more (see `docs/GEIST_CATALOG.md`)

**Tracery geists:** contradictor, hub_explorer, what_if

**Extension examples in this directory** (not bundled; copy into
`_geistfabrik/geists/...` to try them):
- `geists/tracery/note_combinations.yaml` - `$vault.note_pairs()` with a
  `[picked:#pair#]` save action and `.split_seed` / `.split_neighbours`
- `geists/tracery/semantic_neighbours.yaml` - the cluster pattern
  (`$vault.semantic_clusters()` split from one saved expansion)
- `geists/tracery/transformation_suggester.yaml` - every Tracery modifier
- `geists/code/metadata_outlier_detector.py` - the `MetadataAnalyser` API

View the bundled geists' source code in `src/geistfabrik/default_geists/` to learn patterns.

Enable/disable defaults in `_geistfabrik/config.yaml`:

```yaml
default_geists:
  temporal_drift: true
  contradictor: false  # Disable this one
  # ... rest default to true
```

## Philosophy

These examples demonstrate GeistFabrik's core principle: **muses, not oracles**.

Extensions should:
- **Provoke** rather than prescribe
- **Question** rather than answer
- **Diverge** rather than converge
- **Sample** rather than rank

Geists should feel like opening a gift: surprising, delightful, and occasionally serendipitous.

## Testing Your Extensions

Test custom geists:

```bash
# Test a specific geist
uv run geistfabrik test my_geist ~/my-vault

# Test with specific date for reproducibility
uv run geistfabrik test my_geist ~/my-vault --date 2025-01-15
```

## Contributing

To contribute example extensions:

1. Create your module following the patterns above
2. Test it thoroughly
3. Add documentation explaining what it does and why
4. Submit a pull request

Great extensions:
- Ask interesting questions
- Respect the user's attention
- Find surprising patterns
- Maintain appropriate randomness
- Fail gracefully

## License

[Same as GeistFabrik main project]
