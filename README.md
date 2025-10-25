# GeistFabrik

[![Test](https://github.com/adewale/geist_fabrik/actions/workflows/test.yml/badge.svg)](https://github.com/adewale/geist_fabrik/actions/workflows/test.yml)

**A Python-based divergence engine for Obsidian vaults**

GeistFabrik (German for "spirit factory") generates creative suggestions through both code and Tracery grammars. It's a tool for thought that acts as a muse, not an oracle - offering provocative "What if...?" questions rather than prescriptive answers.

Inspired by Gordon Brander's work on tools for thought.

## Status

**Version**: 0.9.0 (Beta)
**Default Geists**: 45 (36 code + 9 Tracery)
**Progress**: ~98% (Feature-complete, approaching 1.0)

See [STATUS.md](STATUS.md) for detailed implementation status and test results, and [examples/README.md](examples/README.md) for comprehensive examples.

## Features

### Core Functionality
✅ **Vault Management**: Parse Obsidian vaults with incremental sync
✅ **Semantic Search**: 384-dim embeddings via sentence-transformers
✅ **Temporal Embeddings**: Track how understanding evolves over time
✅ **Graph Operations**: Orphans, hubs, backlinks, unlinked pairs
✅ **Geist Execution**: Safe Python and Tracery grammar execution
✅ **Filtering Pipeline**: Boundary, novelty, diversity, and quality checks
✅ **Session Notes**: Generates linkable journal entries with suggestions
✅ **CLI**: Full command-line interface with multiple invocation modes

### Three-Dimensional Extensibility
✅ **Metadata Inference**: Add custom note properties via Python modules
✅ **Vault Functions**: Create reusable query functions with `@vault_function`
✅ **Code Geists**: Full Python with VaultContext API
✅ **Tracery Geists**: Declarative YAML grammars with vault functions

### Performance
✅ **Batch Operations**: Optimized for vaults with 100+ notes
✅ **Incremental Sync**: Only reprocesses changed files
✅ **Query Optimization**: Sub-second semantic search
✅ **Batch Embeddings**: 15-20x faster than naive implementation

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/adewale/geist_fabrik.git
cd geist_fabrik

# Install dependencies (requires Python 3.11+)
uv sync

# Run tests
uv run pytest

# Check that everything works
uv run geistfabrik --help
```

### First Run

```bash
# Initialize a vault (creates _geistfabrik directory structure)
uv run geistfabrik init /path/to/your/vault

# This automatically configures 45 bundled default geists:
# • 36 code geists (blind_spot_detector, temporal_drift, columbo, etc.)
# • 9 Tracery geists (contradictor, hub_explorer, transformation_suggester, etc.)

# Preview suggestions (read-only, no files created)
uv run geistfabrik invoke /path/to/your/vault

# Write suggestions to journal (creates session note)
uv run geistfabrik invoke /path/to/your/vault --write

# View your session note at:
# /path/to/your/vault/geist journal/YYYY-MM-DD.md
```

### Try on Sample Vault (Risk-Free)

Test GeistFabrik on our sample vault before using your own:

```bash
# After installation, try on sample vault
uv run geistfabrik init testdata/kepano-obsidian-main
uv run geistfabrik invoke testdata/kepano-obsidian-main --write

# View results
cat "testdata/kepano-obsidian-main/geist journal/$(date +%Y-%m-%d).md"

# Clean up when done
rm -rf testdata/kepano-obsidian-main/_geistfabrik
rm -rf testdata/kepano-obsidian-main/"geist journal"
```

This is the **safest way** for early adopters to explore GeistFabrik without touching their personal vaults.

**Note**: 45 default geists work immediately - no installation needed!

## Privacy & Data Safety

**What GeistFabrik stores (all locally):**
- Note titles, content, links, and tags → SQLite database (`_geistfabrik/vault.db`)
- Semantic embeddings (384-dim vectors) → SQLite database
- Generated suggestions → Session notes in `geist journal/`

**What GeistFabrik NEVER does:**
- ❌ Modify your original notes (read-only access)
- ❌ Send data to external servers (100% local processing)
- ❌ Track usage or analytics
- ❌ Require internet connection (after installation)
- ❌ Delete any files

**Your vault remains yours.** All processing happens locally using sentence-transformers for embeddings.

## Uninstalling GeistFabrik

To completely remove GeistFabrik from your vault:

```bash
# Delete GeistFabrik data
rm -rf /path/to/vault/_geistfabrik

# Delete session notes (optional - you may want to keep these)
rm -rf /path/to/vault/"geist journal"
```

**That's it!** Your original notes are completely untouched.

**What gets removed:**
- `_geistfabrik/vault.db` - Embeddings and metadata
- `_geistfabrik/geists/` - Your geists (code and Tracery)
- `_geistfabrik/metadata_inference/` - Metadata modules
- `_geistfabrik/vault_functions/` - Vault functions
- `geist journal/` - Session notes (optional)

**What stays:**
- ✅ All your original notes (100% unchanged)

## Usage

### Basic Invocation

```bash
# Default: Preview suggestions (read-only, no files created)
uv run geistfabrik invoke ~/my-vault

# Write suggestions to journal
uv run geistfabrik invoke ~/my-vault --write

# Compare to recent sessions
uv run geistfabrik invoke ~/my-vault --diff

# Full mode: All filtered suggestions (no sampling)
uv run geistfabrik invoke ~/my-vault --full --write

# No filter: Raw output from all geists (no filtering or sampling)
uv run geistfabrik invoke ~/my-vault --no-filter --write

# Single geist only
uv run geistfabrik invoke ~/my-vault --geist temporal_drift

# Multiple geists
uv run geistfabrik invoke ~/my-vault --geists temporal_drift,creative_collision

# Replay specific date
uv run geistfabrik invoke ~/my-vault --date 2025-01-15

# Quiet mode (only show suggestions)
uv run geistfabrik invoke ~/my-vault --quiet

# Verbose mode (detailed output)
uv run geistfabrik invoke ~/my-vault --verbose

# Test a geist during development
uv run geistfabrik test my_geist ~/my-vault --date 2025-01-15

# Test all geists
uv run geistfabrik test-all ~/my-vault
```

### Understanding Filtering Modes

GeistFabrik has three invocation modes that control filtering and sampling:

**Default mode** (recommended for daily use):
- Applies 4-stage filtering (boundary, novelty, diversity, quality)
- Samples ~5 suggestions
- Balanced output

**Full mode** (`--full`):
- Applies 4-stage filtering (boundary, novelty, diversity, quality)
- Returns ALL filtered suggestions (no sampling)
- Good for seeing everything that passed quality checks
- Typical output: 10-50 suggestions depending on vault size

**No filter mode** (`--no-filter`):
- Skips filtering pipeline entirely
- Returns raw output from all geists
- Maximum output volume
- Typical output: 20-200+ suggestions depending on vault size and geist count
- ⚠️ May include low-quality or redundant suggestions

Example outputs for a 100-note vault:
- Default: ~5 suggestions
- `--full`: ~30 suggestions (after filtering)
- `--no-filter`: ~150 suggestions (raw, unfiltered)

### Working with Session Notes

When using `--write`, session notes are created at:
```
<vault>/geist journal/YYYY-MM-DD.md
```

Session notes:
- Contain filtered suggestions with block IDs (`^g20250120-001`)
- Are fully linkable and embeddable like any Obsidian note
- Include metadata about geists, vault state, and execution time
- Support deterministic replay (same date = same output)

## Extending GeistFabrik

GeistFabrik provides three ways to extend functionality. See [examples/README.md](examples/README.md) for detailed guides.

### 1. Metadata Inference

Add custom note properties by creating modules in `_geistfabrik/metadata_inference/`:

```python
# complexity.py
def infer(note, vault):
    """Add complexity metrics to notes."""
    words = note.content.split()
    unique_words = set(words)

    return {
        "reading_time_minutes": len(words) / 200,
        "lexical_diversity": len(unique_words) / len(words) if words else 0,
        "sentence_count": note.content.count('.') + note.content.count('!'),
    }
```

Access in code geists via `vault.metadata(note)`:
```python
def suggest(vault):
    complex_notes = [n for n in vault.notes()
                     if vault.metadata(n).get("lexical_diversity", 0) > 0.7]
    return [...]
```

### 2. Vault Functions

Create reusable query functions in `_geistfabrik/vault_functions/`:

```python
# questions.py
from geistfabrik import vault_function

@vault_function("find_questions")
def find_question_notes(vault, k=5):
    """Find notes with questions in title or content."""
    questions = [n for n in vault.notes() if '?' in n.title or '?' in n.content]
    return vault.sample(questions, k)

@vault_function("by_complexity")
def notes_by_complexity(vault, threshold=0.7):
    """Find notes above complexity threshold."""
    return [n for n in vault.notes()
            if vault.metadata(n).get("lexical_diversity", 0) > threshold]
```

Use in Tracery geists:
```yaml
type: geist-tracery
id: question_prompt
tracery:
  origin: "Consider: #question.title#"
  question: "$vault.find_questions(k=1)"
```

### 3. Geists

#### Code Geists
Create Python geists in `_geistfabrik/geists/code/`:

```python
# temporal_drift.py
"""Find stale but important notes."""

def suggest(vault):
    from geistfabrik import Suggestion

    old_notes = vault.old_notes(k=20)
    backlinks_map = {n: len(vault.backlinks(n)) for n in old_notes}
    important_old = sorted(backlinks_map.items(), key=lambda x: x[1], reverse=True)[:5]

    suggestions = []
    for note, backlink_count in important_old:
        metadata = vault.metadata(note)
        age_days = metadata.get("age_days", 0)

        suggestions.append(Suggestion(
            text=f"Consider revisiting [[{note.title}]] ({backlink_count} backlinks, {age_days} days old)",
            notes=[note.title],
            geist_id="temporal_drift"
        ))

    return suggestions
```

#### Tracery Geists
Create YAML geists in `_geistfabrik/geists/tracery/`:

```yaml
type: geist-tracery
id: creative_collision
description: Pair unrelated notes for creative collision

tracery:
  origin: "What if you combined [[#note1.title#]] with [[#note2.title#]]?"
  note1: "$vault.sample_notes(k=1)"
  note2: "$vault.sample_notes(k=1)"
```

## Architecture

### Two-Layer Design

**Layer 1: Vault** (`vault.py`, `embeddings.py`)
- Read-only access to Obsidian vault
- SQLite persistence for notes, links, tags
- Incremental sync (only processes changed files)
- Temporal embedding computation and storage

**Layer 2: VaultContext** (`vault_context.py`)
- Rich query API for geists
- Semantic search and graph operations
- Deterministic random sampling
- Metadata inference integration
- Vault function registry

### Data Flow

```
Vault Files → Vault.sync() → SQLite Database
                                    ↓
                            Session.compute_embeddings()
                                    ↓
                            VaultContext (with metadata & functions)
                                    ↓
                            Geists execute → Suggestions
                                    ↓
                            Filtering Pipeline
                                    ↓
                            Session Note Output
```

### Key Design Principles

1. **Muses, not oracles** - Provocative, not prescriptive
2. **Questions, not answers** - "What if...?" not "Here's how"
3. **Sample, don't rank** - Avoid preferential attachment
4. **Intermittent invocation** - User-initiated, not continuous
5. **Local-first** - No network required
6. **Deterministic randomness** - Same date + vault = same output
7. **Never destructive** - Read-only vault access
8. **Extensible at every layer** - Metadata, functions, geists

## Example Geists

GeistFabrik includes 39 example geists demonstrating various patterns:

### Code Geists (29)
Including patterns for:
- **Temporal analysis** - temporal_drift, session_drift, hermeneutic_instability, temporal_clustering, seasonal_patterns, anachronism_detector, convergent_evolution, divergent_evolution, concept_drift
- **Creative connections** - creative_collision, bridge_builder, bridge_hunter, island_hopper, hidden_hub
- **Analysis & critique** - columbo, assumption_challenger, antithesis_generator, density_inversion, complexity_mismatch
- **Pattern discovery** - pattern_finder, concept_cluster, question_generator, method_scrambler, scale_shifter
- **Vault health** - link_density_analyser, task_archaeology, stub_expander, recent_focus, vocabulary_expansion

### Tracery Geists (10)
- **random_prompts.yaml** - Creative writing prompts
- **note_combinations.yaml** - Random note pairings
- **what_if.yaml** - "What if" question generator
- **hub_explorer.yaml** - Explore highly connected notes
- **orphan_connector.yaml** - Connect isolated notes
- **semantic_neighbours.yaml** - Find semantically similar notes
- **temporal_mirror.yaml** - Compare notes across time periods
- **transformation_suggester.yaml** - Suggest note transformations
- **dialectic.yaml** - Find thesis-antithesis pairs
- **scale_shift.yaml** - Connect notes at different abstraction levels

See [examples/README.md](examples/README.md) for detailed documentation.

## Documentation

### Getting Started
- **[examples/README.md](examples/README.md)** - Comprehensive extension guide
- **[STATUS.md](STATUS.md)** - Detailed implementation status

### Deep Dives
- **[docs/TEMPORAL_EMBEDDINGS_EXAMPLES.md](docs/TEMPORAL_EMBEDDINGS_EXAMPLES.md)** - Temporal embeddings explained with examples
- **[docs/TRACERY_COMPARISON.md](docs/TRACERY_COMPARISON.md)** - Tracery engine technical analysis

### Development
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development setup and workflow
- **[CLAUDE.md](CLAUDE.md)** - AI development guidelines
- **[docs/CI_STRATEGY_ANALYSIS.md](docs/CI_STRATEGY_ANALYSIS.md)** - CI/CD troubleshooting

### Specifications
- **[specs/](specs/)** - Complete technical specification documents

## Performance

Optimized for vaults with 100+ notes and 100+ geists:

- **Vault loading**: ~3-5s for 1000 notes (vs 72s naive)
- **Embedding computation**: Batch processing with GPU support
- **Incremental sync**: Only reprocesses changed files
- **Query optimization**: Batch loading eliminates N+1 queries
- **Memory efficient**: Streaming where possible

## Development

### Running Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# Integration tests only
uv run pytest tests/integration/

# With coverage
uv run pytest --cov=src/geistfabrik

# Type checking
uv run mypy src/ --strict
```

### Project Structure

```
geist_fabrik/
├── src/geistfabrik/          # Core library (15 modules)
│   ├── models.py             # Data structures (Note, Suggestion, Link)
│   ├── schema.py             # SQLite database schema
│   ├── vault.py              # Vault management and sync
│   ├── markdown_parser.py    # Markdown parsing utilities
│   ├── embeddings.py         # Embedding computation
│   ├── vault_context.py      # Rich query API
│   ├── metadata_system.py    # Metadata inference
│   ├── function_registry.py  # Vault functions
│   ├── geist_executor.py     # Geist execution
│   ├── tracery.py            # Tracery grammar engine
│   ├── filtering.py          # Suggestion filtering
│   ├── journal_writer.py     # Session note generation
│   ├── config.py             # Configuration management
│   ├── cli.py                # Command-line interface
│   └── __init__.py           # Package exports
├── tests/                    # Test suite (see STATUS.md for details)
├── examples/                 # Example geists and extensions (39 geists)
├── testdata/                 # Sample vault for testing
└── specs/                    # Design specifications
```

## Roadmap to 1.0

Remaining work (5%):
- [ ] Enhanced error messages and debugging
- [ ] Performance profiling for 1000+ note vaults
- [ ] Migration system for schema changes
- [ ] Comprehensive user tutorials
- [ ] API documentation

## Contributing

Contributions welcome! Please:
1. Read [CLAUDE.md](CLAUDE.md) for development guidelines
2. Run tests: `uv run pytest`
3. Check types: `uv run mypy src/ --strict`
4. Follow existing code style

## License

MIT License - See [LICENSE](LICENSE) for details

## Acknowledgments

Inspired by Gordon Brander's work on tools for thought and the philosophy of "muses, not oracles."

---

**Note**: This is beta software approaching 1.0. Core functionality is feature-complete and well-tested. The system is ready for adventurous users who want to extend their Obsidian vaults with creative suggestion engines.
