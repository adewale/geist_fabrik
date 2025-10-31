# GeistFabrik Examples

This directory contains example implementations for extending GeistFabrik through metadata inference and vault functions.

## Important: Geists are Bundled, Not in Examples

**All default geists are now bundled with GeistFabrik** in `src/geistfabrik/default_geists/`. They work immediately on first run—no installation needed.

This `examples/` directory focuses on:
- **Metadata inference modules** - Adding custom properties to notes
- **Vault functions** - Creating reusable functions for Tracery geists

To create custom geists, refer to the bundled source code in `src/geistfabrik/default_geists/` as examples.

## Directory Structure

```
examples/
├── metadata_inference/     # Custom metadata modules
│   ├── complexity.py       # Text complexity metrics
│   ├── temporal.py         # Temporal/staleness metrics
│   └── structure.py        # Document structure analysis
│
└── vault_functions/        # Custom vault functions
    ├── contrarian.py       # Find semantically dissimilar notes
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

Or create symlinks for easier development:

```bash
ln -s $(pwd)/examples/metadata_inference /path/to/vault/_geistfabrik/metadata_inference
ln -s $(pwd)/examples/vault_functions /path/to/vault/_geistfabrik/vault_functions
```

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
    - graph_neighbors(note) - Get all connected notes (incoming + outgoing)
    """
    suggestions = []

    for note in vault.notes():
        # Get metadata
        metadata = vault.metadata(note)

        # Example: Find notes with few outgoing links but many backlinks
        outgoing = vault.outgoing_links(note)  # Notes this note links to
        incoming = vault.backlinks(note)        # Notes linking to this note

        if len(incoming) > 5 and len(outgoing) < 2:
            suggestions.append(
                Suggestion(
                    text=f"[[{note.title}]] is a hub (5+ incoming) but links out rarely. "
                         "What connections could it make?",
                    notes=[note.title],
                    geist_id="my_geist"
                )
            )

        # Example: Find semantically similar notes that aren't linked
        similar = vault.neighbours(note, k=5)
        for candidate in similar:
            if not vault.has_link(note, candidate):  # Check if linked (bidirectional)
                suggestions.append(
                    Suggestion(
                        text=f"[[{note.title}]] and [[{candidate.title}]] are semantically "
                             "similar but not linked. Missing connection?",
                        notes=[note.title, candidate.title],
                        geist_id="my_geist"
                    )
                )

        # Example: Analyze graph neighborhood density
        neighbors = vault.graph_neighbors(note)  # All connected notes (both directions)
        if len(neighbors) > 10:
            # Check how interconnected the neighbors are
            interconnections = sum(
                1 for i, n1 in enumerate(neighbors)
                for n2 in neighbors[i+1:]
                if vault.has_link(n1, n2)
            )

            if interconnections < len(neighbors):
                suggestions.append(
                    Suggestion(
                        text=f"[[{note.title}]] has {len(neighbors)} neighbors, "
                             "but they're not well connected to each other. "
                             "Is there a central theme?",
                        notes=[note.title],
                        geist_id="my_geist"
                    )
                )

    return vault.sample(suggestions, k=5)
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
- temporal_drift, creative_collision, bridge_builder, complexity_mismatch
- question_generator, link_density_analyser, task_archaeology, concept_cluster
- stub_expander, recent_focus, columbo, session_drift, hermeneutic_instability
- and 22 more...

**Tracery geists include:**
- contradictor, hub_explorer, note_combinations, orphan_connector
- perspective_shifter, random_prompts, semantic_neighbours, temporal_mirror
- transformation_suggester, what_if

View their source code in `src/geistfabrik/default_geists/` to learn patterns.

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
uv run geistfabrik test my_geist --vault ~/my-vault

# Test with specific date for reproducibility
uv run geistfabrik test my_geist --vault ~/my-vault --date 2025-01-15
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
