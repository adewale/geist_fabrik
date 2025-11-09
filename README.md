# GeistFabrik

[![Test](https://github.com/adewale/geist_fabrik/actions/workflows/test.yml/badge.svg)](https://github.com/adewale/geist_fabrik/actions/workflows/test.yml)

**A Python-based divergence engine for Obsidian vaults**

GeistFabrik (German for "spirit factory") generates creative suggestions through both code and Tracery grammars. It's a tool for thought that acts as a muse, not an oracle - offering provocative "What if...?" questions rather than prescriptive answers.

Inspired by Gordon Brander's work on tools for thought.

## Status

**Version**: 0.9.0 (Beta)
**Default Geists**: Code + Tracery _[programmatically verified]_
**Tests**: 611 passing (100%)
**Progress**: ~99% (Feature-complete, approaching 1.0)

See [STATUS.md](STATUS.md) for detailed implementation status and test results, and [examples/README.md](examples/README.md) for comprehensive examples.

## Features

### Core Functionality
✅ **Vault Management**: Parse Obsidian vaults with incremental sync
✅ **Date-Collection Notes**: Automatically split journal files into virtual entries
✅ **Semantic Search**: 384-dim embeddings via sentence-transformers
✅ **Temporal Embeddings**: Track how understanding evolves over time
✅ **Graph Operations**: Orphans, hubs, backlinks, unlinked pairs
✅ **Geist Execution**: Safe Python and Tracery grammar execution
✅ **Filtering Pipeline**: Boundary, novelty, diversity, and quality checks
✅ **Session Notes**: Generates linkable journal entries with suggestions
✅ **Stats Command**: Comprehensive vault health diagnostics and metrics
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

# Install pre-commit hooks (for contributors)
uv run pre-commit install

# Run tests
uv run pytest

# Check that everything works
uv run geistfabrik --help
```

### First Run

```bash
# Initialize a vault (creates _geistfabrik directory structure)
uv run geistfabrik init /path/to/your/vault

# This automatically configures bundled default geists:
# • Code geists (blind_spot_detector, temporal_drift, columbo, creation_burst, etc.)
# • Tracery geists (contradictor, hub_explorer, transformation_suggester, etc.)

# Preview suggestions (read-only, no files created)
uv run geistfabrik invoke /path/to/your/vault

# Write suggestions to journal (creates session note)
uv run geistfabrik invoke /path/to/your/vault --write

# View your session note at:
# /path/to/your/vault/geist journal/YYYY-MM-DD.md

# Check vault health and statistics
uv run geistfabrik stats /path/to/your/vault

# Get detailed stats with verbose mode
uv run geistfabrik stats /path/to/your/vault --verbose

# Export stats as JSON for scripting
uv run geistfabrik stats /path/to/your/vault --json
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

**Note**: Default geists work immediately - no installation needed!

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

# Debug mode (performance profiling and diagnostics)
uv run geistfabrik invoke ~/my-vault --debug

# Test a geist during development
uv run geistfabrik test my_geist ~/my-vault --date 2025-01-15

# Debug geist timeouts with performance profiling
uv run geistfabrik test my_geist ~/my-vault --timeout 10 --debug

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

## Configuration

GeistFabrik's configuration file controls which geists run and in what order:

```
<vault>/_geistfabrik/config.yaml
```

### Key Configuration Features

**Execution Order**: Geists execute in the order they appear in `config.yaml`. This matters because:
- All geists share a random number generator seeded by the session date
- Execution order determines which geist gets which random numbers
- Same order + same date = same suggestions (reproducible sessions)

**Enable/Disable Geists**: Set any geist to `false` to disable it:
```yaml
default_geists:
  temporal_drift: true   # enabled
  creative_collision: false  # disabled
```

**Custom Geists**: When you create custom geists, they're automatically added to the config file (enabled by default). You can then reorder or disable them as needed.

**See [docs/example_config.yaml](docs/example_config.yaml) for a comprehensive example** showing all default geists with descriptions and configuration tips.

### Cluster Labeling

GeistFabrik uses semantic clustering to group related notes and generate descriptive labels. You can choose between two labeling methods:

```yaml
clustering:
  labeling_method: keybert  # or "tfidf"
  min_cluster_size: 5       # minimum notes per cluster
  n_label_terms: 4          # number of terms in label
```

**Labeling Methods**:
- **keybert** (default): Uses semantic similarity to cluster centroids for more coherent, conceptual labels. Supports 1-3 word phrases.
- **tfidf**: Frequency-based keyword extraction. Faster and more deterministic, focuses on term frequency within clusters.

**Note**: KeyBERT requires the sentence-transformers model (~90MB). If unavailable, it falls back to simple labels.

### Date-Collection Notes (Journal Files)

GeistFabrik automatically detects and splits journal files with multiple date-based entries into individual virtual notes:

```markdown
## 2025-01-15
Had an insight about [[PKM Systems]] today...

## 2025-01-16
Followed up on yesterday's thoughts. Created [[New Project Idea]].

## 2025-01-17
Implemented the first prototype...
```

This single file becomes three virtual entries that can be individually linked, searched, and referenced:
- `Daily Journal.md/2025-01-15`
- `Daily Journal.md/2025-01-16`
- `Daily Journal.md/2025-01-17`

**Supported Date Formats**: ISO (2025-01-15), US (01/15/2025), EU (15.01.2025), Long (January 15, 2025), Year-Month-Day (2025 January 15), and more.

**Configuration**:
```yaml
date_collection:
  enabled: true
  min_sections: 2        # Minimum H2 headings required
  date_threshold: 0.5    # Minimum fraction that must be dates
  exclude_files: []      # Patterns to exclude (e.g., 'Templates/*')
```

**See**: [docs/JOURNAL_FILES.md](docs/JOURNAL_FILES.md) for complete documentation, usage guide, and examples.

### Vector Search Backends

GeistFabrik supports pluggable vector search backends for semantic similarity:

**In-Memory Backend** (default):
- Fast for small-medium vaults (100-1000 notes)
- No additional dependencies beyond core requirements
- Loads all embeddings into RAM

**SQLite-Vec Backend** (optional):
- Better for large vaults (5000+ notes)
- Native SQL vector operations
- Requires: `uv pip install -e ".[vector-search]"`

**Configuration**:
```yaml
vector_search:
  backend: in-memory  # or "sqlite-vec"
```

**Both backends provide identical functionality** - they're tested for parity and return the same results. Choose based on your vault size and performance needs.

**See**:
- [specs/VECTOR_SEARCH_BACKENDS_SPEC.md](specs/VECTOR_SEARCH_BACKENDS_SPEC.md) - Technical specification
- [scripts/BENCHMARKS.md](scripts/BENCHMARKS.md) - Performance benchmarks and recommendations

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

### Technologies

**Core Dependencies**:
- `sentence-transformers` (≥2.2.0) - Local embedding computation with all-MiniLM-L6-v2 model
- `pyyaml` (≥6.0) - YAML parsing for configuration and Tracery geists
- Python 3.11+ standard library (SQLite, pathlib, etc.)

**Tracery Grammar**:
- Custom implementation included (no external dependency)
- Compatible with standard Tracery syntax
- Extended with `$vault.*` function calls for dynamic content

**Optional Dependencies**:
- `sqlite-vec` - For large vaults (5000+ notes) using SQLite-Vec backend
- `numpy`, `scipy`, `scikit-learn` - For advanced stats metrics (auto-detected)

## Example Geists

The examples/ directory includes 38 example geists demonstrating various patterns (for learning, not installation):

### Code Geists (29)
Including patterns for:
- **Temporal analysis** - temporal_drift, session_drift, hermeneutic_instability, temporal_clustering, seasonal_patterns, anachronism_detector, convergent_evolution, divergent_evolution, concept_drift
- **Creative connections** - creative_collision, bridge_builder, bridge_hunter, island_hopper, hidden_hub
- **Analysis & critique** - columbo, assumption_challenger, antithesis_generator, density_inversion, complexity_mismatch
- **Pattern discovery** - pattern_finder, concept_cluster, question_generator, method_scrambler, scale_shifter
- **Vault health** - link_density_analyser, task_archaeology, stub_expander, recent_focus, vocabulary_expansion

### Tracery Geists (9)
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
- **[docs/example_config.yaml](docs/example_config.yaml)** - Configuration reference with all default geists
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

### Recent Performance Improvements (2025-10-31)

**Session-level caching**: `vault.notes()` now caches results per session, eliminating redundant filesystem operations when geists query the note list multiple times.

**Vectorized similarity computations**: Embedding similarity calculations now use `sklearn.metrics.pairwise.cosine_similarity` with vectorized NumPy operations, replacing O(n²) nested loops. **Estimated 50-70% speedup** for stats commands and similarity-heavy geists.

**Optimized database queries**:
- Orphan queries now use `LEFT JOIN` instead of `NOT IN` subqueries
- New composite index `idx_links_target_source` for backlink operations
- Schema v5→v6 migration applies automatically

**Code quality improvements**: Updated 8 geist files to cache `vault.notes()` calls before loops, reducing API call overhead and improving maintainability.

See [CHANGELOG.md](CHANGELOG.md) for complete details.

### Debugging Performance Issues

When geists timeout or run slowly, use the `--debug` flag to enable detailed performance profiling:

```bash
# Debug a timeout during normal invocation
uv run geistfabrik invoke ~/my-vault --debug

# Debug a specific geist with extended timeout
uv run geistfabrik test cluster_mirror ~/my-vault --timeout 10 --debug
```

**Debug output includes**:
- Top 10 most expensive operations with timing breakdown
- Function call counts and per-call averages
- Percentage of total execution time
- Pattern-based suggestions for optimization

**Example diagnostic output**:
```
✗ cluster_mirror timed out after 5.000s

Top expensive operations:
  1. sklearn.cluster.HDBSCAN.fit     2.891s (57.8%)  1 calls
  2. stats.get_cluster_labels        0.401s ( 8.0%)  1 calls
  3. cosine_similarity               0.305s ( 6.1%)  3 calls

Total accounted: 4.123s (82.5%)

Suggestions:
  → HDBSCAN clustering took 2.9s - consider caching results or reducing min_size
  → get_clusters took 3.5s - clustering is expensive, consider caching
  → Test with longer timeout: geistfabrik test cluster_mirror <vault> --timeout 10 --debug
```

For more details, see [docs/GEIST_INSTRUMENTATION_DESIGN.md](docs/GEIST_INSTRUMENTATION_DESIGN.md).

## Development

### Setup for Development

```bash
# Install pre-commit hooks (prevents committing code that fails CI)
uv run pre-commit install

# This installs hooks that run before each commit:
# - Ruff linting (catches style issues like line length)
# - Ruff formatting (auto-formats code)
# - Trailing whitespace removal
# - YAML validation
# - Large file detection
# - Unused database table detection
```

**Important**: Pre-commit hooks will **block commits** that fail linting. For example:
```bash
$ git commit -m "Add feature"
ruff (legacy alias)......................................................Failed
- hook id: ruff
- exit code: 1

E501 Line too long (112 > 100)
```

This prevents CI failures by catching issues locally before you push.

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

# Run full validation (same checks as CI)
./scripts/validate.sh
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
- [x] Enhanced error messages and debugging
- [x] Performance profiling for 1000+ note vaults
- [ ] Migration system for schema changes
- [ ] Comprehensive user tutorials
- [ ] API documentation

## Contributing

Contributions welcome! Please:
1. Read [CLAUDE.md](CLAUDE.md) for development guidelines
2. Install pre-commit hooks: `uv run pre-commit install` (blocks bad commits)
3. Run tests: `uv run pytest`
4. Check types: `uv run mypy src/ --strict`
5. Validate before pushing: `./scripts/validate.sh`
6. Follow existing code style

## License

MIT License - See [LICENSE](LICENSE) for details

## Acknowledgments

Inspired by Gordon Brander's work on tools for thought and the philosophy of "muses, not oracles."

---

**Note**: This is beta software approaching 1.0. Core functionality is feature-complete and well-tested. The system is ready for adventurous users who want to extend their Obsidian vaults with creative suggestion engines.
