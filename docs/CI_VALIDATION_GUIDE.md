# CI Validation Guide: Preventing Failed Builds

## The Problem

**Issue**: Code passes local checks but fails in CI with mypy errors.

**Root Cause**: Running different checks locally than what CI runs.

## What Went Wrong

### ❌ WRONG Approach
```bash
# Running custom mypy command
mypy src/geistfabrik --ignore-missing-imports

# This is NOT what CI runs!
```

**Why this fails:**
- CI runs `mypy src/ --strict` (see `.github/workflows/test.yml`)
- `--strict` requires explicit type parameters for generics
- `--ignore-missing-imports` masks issues
- Wrong directory (`src/geistfabrik/` vs `src/`)

### ✅ CORRECT Approach

```bash
# Use the existing validation script
./scripts/validate.sh
```

**This script runs EXACTLY what CI runs:**
1. `ruff check src/ tests/` - Linting
2. `mypy src/ --strict` - Type checking with strict mode
3. `python scripts/detect_unused_tables.py` - Database validation
4. `pytest tests/unit -v --timeout=60` - Unit tests
5. `pytest tests/integration -v -m "not slow" --timeout=300` - Integration tests

## The Systemic Fix

### 1. ALWAYS Run validate.sh Before Pushing

```bash
# Before every git push
./scripts/validate.sh
```

If this passes, CI will pass. **No exceptions.**

### 2. Never Run Custom CI Checks

Don't create your own variations of CI checks. Use the validated script.

❌ DON'T:
```bash
mypy src/geistfabrik --ignore-missing-imports
mypy src/ --config-file mypy.ini
pytest tests/ -k "not slow"
```

✅ DO:
```bash
./scripts/validate.sh
```

### 3. Trust the Documented Workflow

The project already has:
- ✅ Pre-commit hooks (run automatically on commit)
- ✅ `./scripts/validate.sh` (run manually before push)
- ✅ Clear documentation in `CONTRIBUTING.md`

**Follow them.**

## Quick Reference

### Daily Workflow

```bash
# 1. Make changes
vim src/geistfabrik/my_file.py

# 2. Pre-commit hooks run automatically on commit
git add .
git commit -m "fix: my change"
# → hooks run automatically

# 3. Before pushing, validate
./scripts/validate.sh

# 4. Only push if validation passes
git push
```

### What validate.sh Checks

| Check | Command | What It Does |
|-------|---------|--------------|
| Linting | `ruff check src/ tests/` | Code style, imports, line length |
| Type checking | `mypy src/ --strict` | Full type safety with strict mode |
| DB validation | `detect_unused_tables.py` | No orphaned database tables |
| Unit tests | `pytest tests/unit -v` | Fast isolated tests |
| Integration tests | `pytest tests/integration -v -m "not slow"` | Real component tests |

## Common Type Errors with --strict

### Missing Type Parameters

❌ **WRONG** (fails with --strict):
```python
from typing import Dict

def from_dict(cls, data: Dict) -> Config:
    pass
```

✅ **CORRECT**:
```python
from typing import Any, Dict

def from_dict(cls, data: Dict[str, Any]) -> Config:
    pass
```

### Missing Return Types

❌ **WRONG** (fails with --strict):
```python
def get_config():
    return {"key": "value"}
```

✅ **CORRECT**:
```python
def get_config() -> Dict[str, str]:
    return {"key": "value"}
```

### Implicit Any

❌ **WRONG** (fails with --strict):
```python
def process(items):  # Implicit Any
    pass
```

✅ **CORRECT**:
```python
def process(items: List[str]) -> None:
    pass
```

## Why --strict Matters

The `--strict` flag enables:
- `--disallow-untyped-defs` - All functions must have types
- `--disallow-any-generics` - Generic types need parameters
- `--warn-return-any` - Functions can't implicitly return Any
- `--no-implicit-optional` - Optional must be explicit
- `--warn-redundant-casts` - Catch unnecessary type casts

These catch real bugs before they reach production.

## Emergency: CI Failed

If CI fails after pushing:

1. **Check the CI logs** on GitHub Actions
2. **Find the exact failing command**
3. **Run that exact command locally**:
   ```bash
   # Example from CI logs
   mypy src/ --strict
   ```
4. **Fix the issue**
5. **Run validate.sh to confirm fix**
6. **Push the fix**

## Summary

### The One Rule

**Before every push, run:**
```bash
./scripts/validate.sh
```

If it passes, CI will pass. If it fails, don't push.

### Why This Failed Before

1. ❌ Ran custom mypy command instead of validate.sh
2. ❌ Didn't use --strict flag
3. ❌ Didn't follow documented workflow in CONTRIBUTING.md

### How to Never Fail Again

1. ✅ Always use `./scripts/validate.sh` before pushing
2. ✅ Never create custom CI check variations
3. ✅ Trust and follow the documented process
4. ✅ When in doubt, read CONTRIBUTING.md

---

**Last Updated**: 2025-10-23
**Triggered By**: PR #30 CI failures due to mypy --strict type errors
