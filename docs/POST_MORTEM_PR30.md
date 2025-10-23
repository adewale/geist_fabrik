# Post-Mortem: PR #30 CI Failures

**Date**: 2025-10-23
**PR**: #30 - Implement default geists system
**Issue**: CI failed with mypy type errors despite passing local checks

## What Happened

PR #30 implemented the default geists system successfully, but CI builds failed with type errors:

```
src/geistfabrik/config_loader.py:53: error: Missing type parameters for generic type "Dict"
src/geistfabrik/config_loader.py:67: error: Missing type parameters for generic type "Dict"
```

These errors were **not caught locally** before pushing.

## Root Cause

### The Core Problem

**I ran the wrong checks locally before pushing.**

### What I Did Wrong

```bash
# ❌ WRONG - What I ran
mypy src/geistfabrik --ignore-missing-imports
```

### What CI Actually Runs

```bash
# ✅ CORRECT - What CI runs (from .github/workflows/test.yml:72)
mypy src/ --strict
```

### Key Differences

| Aspect | My Command | CI Command | Impact |
|--------|------------|------------|---------|
| **Strictness** | Default | `--strict` | Missed type parameter requirements |
| **Imports** | `--ignore-missing-imports` | None | Masked issues |
| **Directory** | `src/geistfabrik/` | `src/` | Different scope |

## Why This Is a Systemic Issue

This isn't just about one wrong command. The real problem is:

### 1. Didn't Follow Documented Workflow

The project **already had the solution**:

```bash
# From CONTRIBUTING.md line 302:
# "Before Pushing"
# ✅ Run ./scripts/validate.sh
```

**I didn't follow it.**

### 2. Created Custom Check Instead of Using Existing Tools

Instead of using `./scripts/validate.sh`, I improvised:
- Ran mypy manually
- Used different flags
- Tested different directory

This **guaranteed** my checks wouldn't match CI.

### 3. Didn't Verify Against CI Configuration

I should have:
1. Read `.github/workflows/test.yml`
2. Seen `mypy src/ --strict` on line 72
3. Run that exact command

Instead, I assumed my local checks were correct.

## The Fix

### Immediate Fix

```diff
# src/geistfabrik/config_loader.py
-from typing import Dict, List
+from typing import Any, Dict, List

-def from_dict(cls, data: Dict) -> "GeistFabrikConfig":
+def from_dict(cls, data: Dict[str, Any]) -> "GeistFabrikConfig":

-def to_dict(self) -> Dict:
+def to_dict(self) -> Dict[str, Any]:
```

**Commit**: `1270539` - fix: Add missing type parameters for mypy --strict compliance

### Systemic Fix

Created documentation to prevent recurrence:

1. **CI_VALIDATION_GUIDE.md** - Comprehensive guide on why this happened and how to prevent it
2. **scripts/README.md** - Makes validate.sh more discoverable
3. **Enhanced commit message** - Explains root cause, not just the fix

**Commits**:
- `d1b7142` - docs: Add CI validation guide to prevent build failures
- `c34d403` - docs: Add README to scripts directory

## Lessons Learned

### 1. Trust the Documented Workflow

If the project documents a validation script, **use it**.

```bash
# ALWAYS before pushing
./scripts/validate.sh
```

### 2. Never Create Custom Variations of CI Checks

Don't improvise. Don't "improve". Just run what CI runs.

❌ DON'T:
```bash
mypy src/geistfabrik --ignore-missing-imports  # Custom variation
mypy src/ --config-file my.ini                 # Custom config
pytest -k "unit"                               # Custom filter
```

✅ DO:
```bash
./scripts/validate.sh  # What the project provides
```

### 3. Read CI Configuration

Before pushing any code, understand what CI actually runs:
- `.github/workflows/test.yml` shows exact commands
- `scripts/validate.sh` mirrors those commands
- No guessing required

### 4. Document Root Causes, Not Just Fixes

The commit message for the fix explains:
- What was wrong (type parameters missing)
- Why it happened (wrong local checks)
- How to prevent it (use validate.sh)

This helps future developers understand the context.

## Prevention Checklist

Before every push:

- [ ] **Run pre-commit hooks** (automatic on commit)
- [ ] **Run `./scripts/validate.sh`** (manual before push)
- [ ] **Verify all checks passed** (don't ignore failures)
- [ ] **Push only after validation** (no exceptions)

## Impact

### Time Lost
- Initial implementation: Successful
- CI failure: Wasted 1-2 hours debugging
- Creating fixes: 30 minutes
- Creating documentation: 30 minutes

**Total**: ~2-3 hours that could have been avoided by running one script.

### What Was Gained

- Comprehensive documentation preventing future failures
- Clear understanding of the validation workflow
- Better commit messages explaining root causes
- Multiple reference documents for future developers

## Conclusion

**The Problem**: Not following the documented development workflow

**The Solution**: Always use `./scripts/validate.sh` before pushing

**The Lesson**: Good processes exist for a reason. Follow them.

---

## Quick Reference

### What to Run Before Pushing

```bash
# One command that runs all CI checks
./scripts/validate.sh
```

### If You Forget

CI will fail. Read the error, fix it, and remember:

**Use validate.sh next time.**

### Documentation

- [CI_VALIDATION_GUIDE.md](./CI_VALIDATION_GUIDE.md) - Detailed guide
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Full development workflow
- [scripts/README.md](../scripts/README.md) - Scripts documentation

---

**Author**: Claude Code
**Reviewer**: Human
**Status**: Resolved and Documented
