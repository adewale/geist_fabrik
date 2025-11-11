# GeistFabrik Scripts

This directory contains validation and utility scripts for development.

## Validation Scripts

### `validate.sh` - Full Validation

**Use when:** Local development with models or matching CI exactly

**What it does:**
- Ruff linting
- Mypy type checking (strict)
- Unused database tables check
- Unit tests (mocked models)
- Integration tests (real models)

**Requirements:** sentence-transformers model (~90MB download on first run)

**Runtime:** ~30-60 seconds (with cached models)

### `validate_web.sh` - Web-Safe Validation

**Use when:** Claude Code for Web or environments without model access

**What it does:**
- Ruff linting
- Mypy type checking (strict)
- Unused database tables check
- Unit tests (mocked models)
- Integration tests (mocked models, excludes 9 slow tests)

**Requirements:** None! Runs entirely with mocked dependencies

**Runtime:** ~20-40 seconds

**Tests excluded:**
- `test_embeddings_integration.py` (8 tests) - Requires real model
- `test_phase3b_regression.py::TestPatternFinderPerformance` (1 test) - Requires real model

## Which Validation Script Should I Use?

| Environment | Script | Model Downloads | Tests Run |
|-------------|--------|-----------------|-----------|
| Claude Code for Web | `validate_web.sh` | ❌ None | 96% (excludes 9 slow tests) |
| Local development | `validate.sh` | ✅ One-time (~90MB) | 100% (all tests) |
| GitHub CI | Automatic | ✅ Cached | 100% (all tests) |

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

GitHub Actions (`.github/workflows/test.yml`) uses the equivalent of `validate.sh`:

```yaml
- name: Run tests
  run: uv run pytest -v -m "not slow and not benchmark"
```

This runs all tests except those marked `slow` or `benchmark`, but with real models pre-downloaded and cached.

## See Also

- `docs/VALIDATION_MODES.md` - Detailed explanation of validation approaches
- `docs/WEB_TESTING_SETUP.md` - Technical details about model mocking
- `docs/CI_VALIDATION_GUIDE.md` - CI/CD best practices
