# CI Validation Guide: Preventing Failed Builds

> **Historical troubleshooting record.** Commands and guarantees below describe
> an earlier workflow. Use [TESTING.md](TESTING.md) and `scripts/validate.sh` as
> the maintained local contract. A local pass is strong evidence, not a promise
> that platform-specific or service-side CI failures are impossible.

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

**This script runs the same required checks as CI:**
1. `uv sync --frozen --extra vector-search` - Locked dependencies
2. `ruff check src/ tests/` - Linting
3. `mypy src/ --strict` - Production type checking with strict mode
4. `ty check src tests --error-on-warning` - Additive whole-project type checking
5. `python scripts/detect_unused_tables.py` and Bandit - Data/security checks
5. `pytest tests/unit -v -m "not slow and not benchmark and not artifact and not production_model" --timeout=60` - Unit coverage pass
6. `pytest tests/integration -v -m "not slow and not benchmark and not artifact and not production_model" --timeout=300` - Appended integration coverage and measured 70% branch gate
7. `python scripts/check_phase_completion.py` - Acceptance criteria
8. `./scripts/test_wheel.sh` - Wheel/sdist, installation, entry-point, and real-model smoke

Fast lanes set `GEISTFABRIK_OFFLINE=1`; their marker-selected fixture replaces
only the external SentenceTransformer constructor. The final validation step
matches the required `package-smoke` CI job by checking wheel and sdist
metadata/size/content, clean installation, console scripts, and real offline
inference. `./scripts/test_wheel.sh` remains available as a focused artifact check.

## The Systemic Fix

### 1. ALWAYS Run validate.sh Before Pushing

```bash
# Before every git push
./scripts/validate.sh
```

If this passes, the equivalent local checks have passed; CI may still expose a
platform-specific or service-side failure.

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
| Dependencies | `uv sync --frozen --extra vector-search` | Matches CI lock and extra |
| Linting | `ruff check src/ tests/` | Code style, imports, line length |
| Type checking | `mypy src/ --strict`; `ty check src tests --error-on-warning` | Strict production checking plus additive whole-project checking |
| DB/security | `detect_unused_tables.py`; Bandit | Data and security regressions |
| Unit tests | `pytest tests/unit ... --timeout=60` | First branch-coverage pass |
| Integration tests | `pytest tests/integration ... --timeout=300` | Appended coverage; measured 70% gate |
| Acceptance | `check_phase_completion.py` | Executable spec criteria |

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

If it passes, the equivalent local checks have passed. If it fails, don't push.

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
