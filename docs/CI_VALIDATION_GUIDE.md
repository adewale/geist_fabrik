# CI Validation Guide: Preventing Failed Builds

> **Origin:** written after the PR #30 CI failures (2025-10). The step list and
> gate descriptions below follow the current `scripts/validate.sh` and
> `.github/workflows/test.yml`; [TESTING.md](TESTING.md) is the fuller testing
> contract. A local pass is strong evidence, not a promise that
> platform-specific or service-side CI failures are impossible.

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
6. `pytest tests/unit -v -m "not slow and not benchmark and not artifact and not production_model" --timeout=60 --require-geist-firing` - Unit coverage pass, geist firing gate, suite hygiene
7. `pytest tests/integration -v -m "not slow and not benchmark and not artifact and not production_model" --timeout=300` and `python scripts/check_branch_coverage.py --minimum 70` - Appended integration coverage and measured 70% branch gate
8. `python scripts/check_phase_completion.py` - Acceptance criteria, including the evidence gate
9. `./scripts/test_wheel.sh` - Wheel/sdist, installation, entry-point, and real-model smoke

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
| Unit tests | `pytest tests/unit ... --timeout=60 --require-geist-firing` | First branch-coverage pass; geist firing and suite hygiene gates |
| Integration tests | `pytest tests/integration ... --timeout=300`; `check_branch_coverage.py --minimum 70` | Appended coverage; measured 70% branch gate |
| Acceptance | `check_phase_completion.py` | Executable spec criteria; rejects partial or empty evidence |
| Package smoke | `./scripts/test_wheel.sh` | Wheel/sdist build, install, real-model offline inference |

### Gates That Check the Tests Themselves

Coverage measures execution, not verification. The suite once passed for
months while it could not fail, so three cheap, deterministic gates check
the tests:

- **Geist firing** (`--require-geist-firing`, `tests/plugins/geist_firing.py`):
  the unit lane fails unless every bundled geist built at least one
  `Suggestion` inside its own `suggest()` (or, for Tracery, a geist loaded
  from its bundled YAML under its own id). A test that constructs `Suggestion(geist_id=...)` itself does not
  count. The flag only makes sense on the full unit lane; on a partial run it
  lists every geist the selection did not exercise.
- **Suite hygiene** (`tests/unit/test_suite_hygiene.py`): an AST scan rejects
  tests with no assertion, always-true asserts (`len(x) >= 0`,
  `assertTrue(True)`), and tests whose checks of output only run where it may
  be empty: in a loop over it, under `if output:`, as `not any(...)`, or
  behind a guard that does not prove it non-empty (`isinstance(x, list)`,
  `len(x) <= N`).
- **Acceptance evidence** (`scripts/check_phase_completion.py`): every AUTO
  pytest criterion must select at least one test, and in CI (`CI` set) at
  least one that runs rather than skips (locally an all-skipped target, such
  as a permission test run as root, is a warning). A criterion that names a
  whole file while the canonical marker filter deselects part of it is
  rejected; name the node IDs instead.

The firing and hygiene gates each have an allowlist of exact ids with written
reasons (both are currently empty). Entries fail when stale, so the lists can
only shrink. The acceptance-evidence gate has no allowlist: fix the criterion.

## Common Type Errors with --strict

### Missing Type Parameters

❌ **WRONG** (fails with --strict):
```python
def from_dict(cls, data: dict) -> Config:
    pass
```

✅ **CORRECT** (PEP 585 builtins, as ruff's `UP` rules require):
```python
from typing import Any

def from_dict(cls, data: dict[str, Any]) -> Config:
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
def get_config() -> dict[str, str]:
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
def process(items: list[str]) -> None:
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

**Last Updated**: 2026-10-02
**Triggered By**: PR #30 CI failures due to mypy --strict type errors
