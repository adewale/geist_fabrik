# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GeistFabrik** is a Python-based divergence engine for Obsidian vaults that generates creative suggestions through both code and Tracery grammars. The name comes from German for "spirit factory" - the system is called GeistFabrik, and individual generative prompts are called "geists."

This is a specification-stage project inspired by Gordon Brander's work on tools for thought. It implements "muses, not oracles" - suggestions that are provocative rather than prescriptive, generating "What if...?" questions rather than answers.

## Current Project State

This repository currently contains:
- **specs/**: Comprehensive technical specifications and design documents
- **testdata/**: Sample Obsidian vault notes from kepano's vault for testing
- **No implementation yet**: This is purely specification phase

The specs define a complete architecture but no Python code has been written.

## Core Architecture (from specs)

GeistFabrik uses a two-layer architecture for understanding Obsidian vaults:

### Layer 1: Vault (Raw Data)
- Python class that provides read-only access to vault files
- Parses Markdown files, extracts links/tags/metadata
- Handles both atomic notes and date-collection notes
- Syncs filesystem changes to SQLite database incrementally
- Computes embeddings using sentence-transformers (all-MiniLM-L6-v2)
- Uses sqlite-vec extension for vector storage

### Layer 2: VaultContext (Rich Execution Context)
- Wraps the Vault with intelligence and utilities
- What geists actually receive when they execute
- Provides semantic search, graph operations, metadata access
- Includes deterministic randomness (same seed = same results)
- Manages function registry for extensibility

### Persistence: SQLite + sqlite-vec
- Single database at `<vault>/_geistfabrik/vault.db`
- Stores notes, links, embeddings, metadata, execution history
- Incremental updates (only reprocess changed files)
- Fast indexed queries for graph operations

### Geist Types
1. **Code geists**: Python functions in `<vault>/_geistfabrik/geists/code/` that receive VaultContext and return Suggestions
2. **Tracery geists**: YAML files in `<vault>/_geistfabrik/geists/tracery/` using Tracery grammar with `$vault.*` function calls

### Output: Session Notes
- Each session creates `<vault>/geist journal/YYYY-MM-DD.md`
- Contains suggestions with geist identifiers and block IDs (`^gYYYYMMDD-NNN`)
- Sessions are linkable and embeddable like any Obsidian note

## Key Design Principles

1. **Muses, not oracles** - Provocative, not prescriptive
2. **Questions, not answers** - "What if...?" not "Here's how"
3. **Sample, don't rank** - Random sampling to avoid preferential attachment
4. **Intermittent invocation** - User-initiated, not continuous background
5. **Local-first** - No network required, embeddings computed locally
6. **Deterministic randomness** - Same date + vault = same output
7. **Never destructive** - Read-only vault access, only writes session notes
8. **Extensible at every layer** - Metadata, functions, and geists are all user-extensible

## Three-Dimensional Extensibility

1. **Metadata Inference** (`<vault>/_geistfabrik/metadata_inference/`)
   - Modules export `infer(note, vault) -> Dict`
   - Add properties like complexity, sentiment, reading_time
   - Properties flow through VaultContext, not Note objects
   - Notes stay lightweight; intelligence lives in context

2. **Vault Functions** (`<vault>/_geistfabrik/vault_functions/`)
   - Decorated with `@vault_function("name")`
   - Bridge between metadata and Tracery
   - Automatically available as `$vault.function_name()` in Tracery
   - Critical: Each metadata type needs a function to be Tracery-accessible

3. **Geists** (`<vault>/_geistfabrik/geists/code/` and `<vault>/_geistfabrik/geists/tracery/`)
   - Code geists: Full Python with VaultContext access
   - Tracery geists: Declarative YAML using registered functions
   - All geists run every session; filtering prevents overwhelm

## Temporal Embeddings

A key architectural feature: GeistFabrik computes fresh embeddings for all notes at each session, enabling:
- Tracking how understanding of notes evolves over time
- Detecting interpretive drift even when content doesn't change
- Discovering temporal patterns and seasonal thinking rhythms
- Identifying notes developing toward or away from each other

Embeddings combine semantic (384 dims from sentence-transformers) with temporal features (3 dims: note age, creation season, session season).

## Data Structures

### Note (Immutable)
```python
@dataclass
class Note:
    path: str           # Relative path in vault
    title: str          # Note title
    content: str        # Full markdown content
    links: List[Link]   # Outgoing [[links]]
    tags: List[str]     # #tags found in note
    created: datetime   # File creation time
    modified: datetime  # Last modification time
```

### Suggestion
```python
@dataclass
class Suggestion:
    text: str           # 1-2 sentence suggestion (variable length)
    notes: List[str]    # Referenced note titles
    geist_id: str       # Identifier of creating geist
    title: str = None   # Optional suggested note title
```

## Invocation Modes

The CLI supports:

```bash
# Default: filtered + sampled (~5 suggestions)
uv run geistfabrik invoke

# Single geist mode
uv run geistfabrik invoke --geist columbo

# Full firehose (all filtered suggestions, 50-200+)
uv run geistfabrik invoke --full

# Replay specific session
uv run geistfabrik invoke --date 2025-01-15

# Test single geist during development
uv run geistfabrik test my_geist --vault ~/test-vault --date 2025-01-15
```

## Implementation Approach

When implementing GeistFabrik:

1. **Start with Vault layer**: File parsing, SQLite schema, incremental sync
2. **Add embeddings**: Integrate sentence-transformers and sqlite-vec
3. **Build VaultContext**: Semantic search, graph queries, sampling utilities
4. **Create core functions**: Built-in vault functions for common queries
5. **Implement geist execution**: Loading, timeout handling, error logging
6. **Add filtering pipeline**: Boundary, novelty, diversity, quality checks
7. **Build journal output**: Session note generation with block IDs
8. **Enable extensibility**: Module loading for metadata/functions/geists
9. **Add temporal embeddings**: Session-based embedding computation and storage
10. **Create CLI**: Argument parsing for different invocation modes

## Dependencies (when implementing)

Core dependencies will include:
- `sentence-transformers` - Local embedding computation (all-MiniLM-L6-v2 model)
- `sqlite-vec` - Vector similarity search in SQLite
- `tracery` (pytracery) - Tracery grammar support
- Python standard library for Markdown parsing, file watching

## Testing Strategy

The `testdata/kepano-obsidian-main/` directory contains real Obsidian notes for testing:
- Mix of daily notes (2023-09-12.md, 2023-09-30.md)
- Topic notes (Minimal Theme.md, Evergreen notes.md)
- Project notes (2023 Japan Trip.md)
- Provides realistic vault structure for development

## Key Files to Reference

- `specs/geistfabrik_spec.md` - Complete technical specification (~1500 lines)
- `specs/geistfabrik_vision.md` - Design philosophy and user experience goals
- `specs/tracery_research.md` - Background on Tracery grammar system
- `README.md` - High-level project description

## Common Development Patterns

### Adding a Metadata Module
1. Create `<vault>/_geistfabrik/metadata_inference/module_name.py`
2. Export `infer(note: Note, vault: VaultContext) -> Dict`
3. Add to `_geistfabrik/config.yaml` enabled_modules list
4. System auto-loads and detects key conflicts on startup

### Adding a Vault Function
1. Create `<vault>/_geistfabrik/vault_functions/function_name.py`
2. Use decorator: `@vault_function("function_name")`
3. Function automatically available in Tracery as `$vault.function_name()`
4. Add to config.yaml enabled_modules for verification

### Adding a Code Geist
1. Create `<vault>/_geistfabrik/geists/code/geist_name.py`
2. Export `suggest(vault: VaultContext) -> List[Suggestion]`
3. Include timeout handling (5 second default)
4. Return empty list if no quality suggestions found

### Adding a Tracery Geist
1. Create `<vault>/_geistfabrik/geists/tracery/geist_name.yaml`
2. Use format:
   ```yaml
   type: geist-tracery
   id: geist_name
   tracery:
     origin: "template with #symbols#"
     symbols: ["$vault.function_call(args)"]
   ```

## Error Handling Philosophy

From the spec:
- Geists execute with 5-second timeout (configurable)
- After 3 failures, geist automatically disabled
- Error logs include test command to reproduce: `geistfabrik test geist_id --date YYYY-MM-DD`
- System continues if individual geists fail
- Metadata conflicts detected at startup, not runtime

## Performance Targets

- Handle 100+ geists via execution and filtering
- Fast startup via incremental SQLite sync (only changed files)
- Sub-second semantic search queries
- 5-minute effort to add new capability at any extensibility layer
- 1000 notes × 20 sessions = ~30MB embedding storage

## Qualitative Success Metrics

GeistFabrik succeeds when suggestions generate:
- **Surprise** - Unexpected connections
- **Delight** - Reading journal feels like opening a gift
- **Serendipity** - Right suggestion at unexpected moment
- **Divergence** - Pull thinking in new directions
- **Questions** - "What if...?" not "Here's the answer"
- **Play** - Exploratory, not obligatory

The system should ask different questions than you would ask yourself.
