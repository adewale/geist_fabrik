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

## Other Scripts

### detect_unused_tables.py
Checks for orphaned database tables that exist in schema but aren't used in code.

```bash
uv run python scripts/detect_unused_tables.py
```

### ci_replication.sh
Helps reproduce specific CI test failures locally.

```bash
./scripts/ci_replication.sh
```

## Quick Reference

```bash
# Before pushing (ALWAYS)
./scripts/validate.sh

# Check database tables only
uv run python scripts/detect_unused_tables.py

# Individual checks
uv run ruff check src/ tests/
uv run mypy src/ --strict
uv run pytest tests/unit -v
uv run pytest tests/integration -v -m "not slow"
```
