# Scripts Directory

Development and validation scripts for GeistFabrik.

## validate.sh ⭐

**Run this before every push!**

```bash
./scripts/validate.sh
```

This script runs all CI checks locally:
- ✅ Linting with ruff
- ✅ Type checking with mypy --strict
- ✅ Database table validation
- ✅ Unit tests
- ✅ Integration tests (excluding slow tests)

**If validate.sh passes, CI will pass.**

See [CI_VALIDATION_GUIDE.md](../docs/CI_VALIDATION_GUIDE.md) for details.

## test_without_models.sh 🚀

**Perfect for Claude Code for Web and rapid development!**

Runs the full test suite (655 tests) using stubbed embeddings, **without downloading models**.

```bash
# Basic run (quiet mode)
./scripts/test_without_models.sh

# Verbose mode
./scripts/test_without_models.sh -v

# With coverage report
./scripts/test_without_models.sh -c

# Quick mode (stop on first failure)
./scripts/test_without_models.sh -q
```

**Coverage achieved: ~43% overall**
- Core infrastructure: 85-100% (vault, models, config, parsing)
- Embeddings layer: ~79% (using deterministic stubs)
- Individual geists: 0% (need real embeddings to test properly)

**What's tested:**
- ✅ All core vault operations (sync, queries, links, tags)
- ✅ All embedding logic (with deterministic stub model)
- ✅ All markdown parsing and virtual notes
- ✅ All metadata and function registry system
- ✅ All filtering and quality checks
- ✅ All Tracery grammar and geist loading
- ✅ Most VaultContext helpers and graph operations

**What's NOT tested:**
- ❌ Real semantic similarity (needs actual model)
- ❌ Individual geist quality (needs real embeddings)
- ❌ CLI commands (many need real model)

## Other Scripts

### detect_unused_tables.py
Checks for orphaned database tables that exist in schema but aren't used in code.

```bash
uv run python scripts/detect_unused_tables.py
```

### ci_local.sh
Replicates the full CI pipeline locally (runs all tests without slow ones).

```bash
./scripts/ci_local.sh
```

## Quick Reference

```bash
# Run tests without models (perfect for Claude Code for Web)
./scripts/test_without_models.sh

# Before pushing (ALWAYS)
./scripts/validate.sh

# Run tests without models directly (no script)
uv run pytest -m "not slow"

# Check database tables only
uv run python scripts/detect_unused_tables.py

# Individual checks
uv run ruff check src/ tests/
uv run mypy src/ --strict
uv run pytest tests/unit -v
uv run pytest tests/integration -v -m "not slow"
```
