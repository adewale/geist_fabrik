# GeistFabrik

**A Python-based divergence engine for Obsidian vaults**

GeistFabrik (German for "spirit factory") generates creative suggestions through both code and Tracery grammars. It's a tool for thought that acts as a muse, not an oracle - offering provocative "What if...?" questions rather than prescriptive answers.

Inspired by Gordon Brander's work on tools for thought.

## Status

**Version**: 0.1.0 (Alpha)
**Tests**: 108/108 passing ✅
**Progress**: ~40% (Core engine complete)

See [STATUS.md](STATUS.md) for detailed implementation status.

## Quick Start

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Check implementation status
uv run python scripts/check_phase_completion.py
```

## What Works Now

✅ **Vault Management**: Parse Obsidian vaults, incremental sync
✅ **Semantic Search**: 384-dim embeddings via sentence-transformers
✅ **Graph Operations**: Orphans, hubs, backlinks, unlinked pairs
✅ **Geist Execution**: Safe Python code execution with timeouts
✅ **Temporal Features**: Track note age and seasonal patterns

## What's Next

⏭️ **Filtering & Output**: Generate session notes with filtered suggestions
⏭️ **CLI**: Make it usable from command line
⏭️ **Tracery**: Declarative grammar-based geists

## Example

```python
from geistfabrik import Vault, VaultContext, GeistExecutor
from geistfabrik.embeddings import Session
from datetime import datetime

# Load vault
vault = Vault("/path/to/vault", "vault.db")
vault.sync()

# Create context
session = Session(datetime.now(), vault.db)
context = VaultContext(vault, session)

# Find similar notes
similar = context.neighbors(context.notes()[0], k=5)

# Execute geists
executor = GeistExecutor("/path/to/geists")
executor.load_geists()
results = executor.execute_all(context)
```

## Documentation

- **[STATUS.md](STATUS.md)** - Detailed implementation status
- **[specs/](specs/)** - Complete specification documents
- **[CLAUDE.md](CLAUDE.md)** - Development guidelines

## Architecture

The system has two main layers:

1. **Vault Layer** (`vault.py`, `embeddings.py`)
   Read-only access to notes, SQLite persistence, embeddings

2. **VaultContext Layer** (`vault_context.py`)
   Rich query API for geists: semantic search, graph operations, sampling

**Geists** are Python functions that receive VaultContext and return Suggestions:

```python
def suggest(vault):
    return [Suggestion(
        text="What if...",
        notes=["note1", "note2"],
        geist_id="my_geist"
    )]
```

## License

[Add license]

---

**Note**: This is alpha software. Core functionality works but the CLI is not yet implemented.
