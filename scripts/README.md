# GeistFabrik Scripts

This directory contains validation and utility scripts for development.

## Validation Script

### `validate.sh` ⭐

**Run this before every push!**

```bash
./scripts/validate.sh
```

**What it does:**
- Ruff linting
- Mypy type checking (strict)
- Unused database tables check
- Unit tests (with mocked models)
- Integration tests (with mocked models, excludes 9 slow tests)

**Requirements:** None! Works in all environments including Claude Code for Web.

**Runtime:** ~20-40 seconds

**How it works:** The script uses `-m "not slow"` flag which triggers automatic model mocking via `SentenceTransformerStub` in `tests/conftest.py`. This allows tests to run without downloading the ~90MB sentence-transformers model. Only 9 tests marked as "slow" require the real model.

**If validate.sh passes, CI will pass.**

## Other Scripts

### `detect_unused_tables.py`

Analyzes the codebase to detect unused database tables.

**Usage:**
```bash
uv run python scripts/detect_unused_tables.py
```

**What it does:**
- Parses database schema from `src/geistfabrik/schema.py`
- Searches codebase for table references
- Reports tables that are never queried

**Exit codes:**
- 0: All tables are used
- 1: Found unused tables

## CI/CD Integration

GitHub Actions (`.github/workflows/test.yml`) runs the same checks as `validate.sh`:

```yaml
- name: Run tests
  run: uv run pytest -v -m "not slow and not benchmark"
```

This runs all tests except those marked `slow` or `benchmark`, using mocked models via the automatic stubbing system.

## See Also

- `docs/CI_VALIDATION_GUIDE.md` - CI/CD best practices
- `tests/conftest.py` - Automatic model mocking implementation
