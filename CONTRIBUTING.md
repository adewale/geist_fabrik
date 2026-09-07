# Contributing to GeistFabrik

Thank you for contributing! This guide will help you set up your development environment and ensure your contributions pass CI.

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/geist_fabrik.git
cd geist_fabrik

# 2. Install dependencies with uv
uv sync

# 3. Install pre-commit hooks (IMPORTANT!)
uv run pre-commit install

# 4. Run validation before pushing
./scripts/validate.sh
```

---

## Development Setup

### Prerequisites

- **Python 3.11 or 3.12**
- **uv** (package manager) - [Install uv](https://docs.astral.sh/uv/)

### Installation

```bash
# Install all dependencies (including dev dependencies)
uv sync

# Verify installation
uv run pytest --version
uv run ruff --version
uv run mypy --version
uv run ty --version
```

---

## Pre-commit Hooks (Critical!)

**Pre-commit hooks prevent linting failures from reaching CI.** They run automatically when you commit.

### Install Once

```bash
uv run pre-commit install
```

### What Gets Checked

On every commit, pre-commit will automatically run:

1. ✅ **Ruff linting** - Catches code style issues, unused imports, line length violations
2. ✅ **Ruff formatting** - Auto-formats code
3. ✅ **ty type checking** - Fast whole-project checking for `src/` and `tests/`
4. ✅ **Trailing whitespace** - Removes trailing spaces
5. ✅ **End-of-file fixer** - Ensures files end with newline
6. ✅ **YAML validation** - Checks YAML syntax
7. ✅ **Large file detection** - Prevents accidentally committing large files
8. ✅ **Merge conflict markers** - Detects unresolved merge conflicts
9. ✅ **Unused database tables** - Ensures no orphaned database tables

### If Pre-commit Finds Issues

```bash
# Pre-commit will auto-fix many issues (ruff --fix, trailing whitespace, etc.)
# Review the changes:
git diff

# Stage the auto-fixed files:
git add .

# Commit again (hooks will run again):
git commit -m "Your message"
```

### Bypass Pre-commit (Not Recommended)

```bash
# Only use in emergencies!
git commit --no-verify -m "Emergency fix"
```

---

## Local Validation

**Before pushing**, run the full CI validation locally:

```bash
./scripts/validate.sh
```

This script runs the same required checks as GitHub CI:

1. Dependency sync, Ruff, Mypy strict, ty, database, and security checks
2. Unit and integration tests with the canonical fast marker selection
3. Combined branch coverage and acceptance-criteria verification
4. Wheel/sdist build, artifact inspection, and isolated offline real-model inference

A green run is the mandatory local pre-push gate. CI also exercises additional
Python versions and operating systems, so platform-specific failures remain possible.

### Individual Checks

```bash
# Linting only
uv run ruff check src/ tests/

# Fix linting issues automatically
uv run ruff check src/ tests/ --fix

# Additive type checking (mypy remains the strict production-code gate)
uv run mypy src/ --strict
uv run ty check src tests --error-on-warning

# Fast test lanes (same canonical selection used by validation/CI)
MARKERS="not slow and not benchmark and not artifact and not production_model"
uv run pytest tests/unit -v -m "$MARKERS"
uv run pytest tests/integration -v -m "$MARKERS"

# Full release-artifact checks, including the real bundled model
./scripts/test_wheel.sh
```

---

## Common Issues and Fixes

### Issue: "Line too long (>100 characters)"

**Error:**
```
E501 Line too long (112 > 100)
```

**Fix:**
Break long lines into multiple lines:

```python
# Bad
geist_path = Path(__file__).parent.parent.parent / "examples" / "geists" / "tracery" / "random_prompts.yaml"

# Good
geist_path = (
    Path(__file__).parent.parent.parent
    / "examples"
    / "geists"
    / "tracery"
    / "random_prompts.yaml"
)
```

### Issue: "Imported but unused"

**Error:**
```
F401 [*] `geistfabrik.GeistMetadata` imported but unused
```

**Fix:**
Remove the unused import:

```python
# Bad
from geistfabrik import GeistExecutor, GeistMetadata, Vault

# Good (if GeistMetadata isn't used)
from geistfabrik import GeistExecutor, Vault
```

**Auto-fix:**
```bash
uv run ruff check src/ tests/ --fix
```

### Issue: Mypy type errors

**Error:**
```
error: Argument 1 to "foo" has incompatible type "str"; expected "int"
```

**Fix:**
Add proper type hints or fix type mismatches. See [mypy documentation](https://mypy.readthedocs.io/).

### Issue: Tests fail locally but pass in your IDE

This usually means:
1. You haven't synced dependencies: `uv sync`
2. You're using a different Python version
3. Your IDE is using a different virtual environment

**Fix:**
```bash
# Use uv's managed environment and the canonical fast lanes
uv sync
MARKERS="not slow and not benchmark and not artifact and not production_model"
uv run pytest tests/unit tests/integration -m "$MARKERS"
```

---

## Testing Guidelines

### Writing Tests

- **Unit tests**: `tests/unit/` - Fast, isolated, use mocks/stubs
- **Integration tests**: `tests/integration/` - Real components, real vault data
- **Use stubs, not mocks** when possible (see `tests/conftest.py`)
- The autouse fixture stubs only the external `SentenceTransformer` constructor
  unless a test has the `production_model` marker; command spelling does not
  activate stubbing.

### Running Tests

```bash
# Fast tests (recommended for local development)
MARKERS="not slow and not benchmark and not artifact and not production_model"
uv run pytest tests/unit -v -m "$MARKERS"
uv run pytest tests/integration -v -m "$MARKERS"

# Artifact/full-release lane (builds and installs the wheel, then uses real weights)
./scripts/test_wheel.sh

# Single test file
uv run pytest tests/unit/test_vault.py -v

# Single test function
uv run pytest tests/unit/test_vault.py::test_sync_notes -v
```

### Test Performance

- **Unit tests**: Should complete in <5 seconds
- **Integration tests**: Should complete in <30 seconds
- **CI impact**: New tests should add <1 second to CI time

---

## Code Style

### Formatting

- **Line length**: 100 characters max
- **Imports**: Sorted, grouped (stdlib, third-party, local)
- **Docstrings**: Google style
- **Type hints**: Required for all public APIs

### Ruff Rules

We use ruff's default rules plus:
- `E501`: Line too long (100 chars)
- `F401`: Imported but unused
- `F841`: Local variable assigned but unused

**Auto-format:**
```bash
uv run ruff format src/ tests/
uv run ruff check src/ tests/ --fix
```

### Type Checking

We use `mypy --strict` for `src/` and pinned Astral ty for the whole project.
ty is additive and still beta/pre-1.0; upgrade its exact pin deliberately and
run both checkers. The required ty command is
`uv run ty check src tests --error-on-warning`.

- All functions must have type hints
- No `Any` types without explanation
- No implicit `Optional`
- No global ty ignores or checked-in diagnostic baseline

### Type Hint Style

**GeistFabrik uses modern Python 3.9+ type hint syntax** (PEP 585):

```python
# ✅ CORRECT - Modern syntax (Python 3.9+)
def suggest(vault: "VaultContext") -> list["Suggestion"]:
    pass

def process_data(items: dict[str, Any]) -> tuple[int, str]:
    pass

# ❌ WRONG - Traditional syntax (requires imports)
from typing import List, Dict, Tuple

def suggest(vault: "VaultContext") -> List["Suggestion"]:
    pass

def process_data(items: Dict[str, Any]) -> Tuple[int, str]:
    pass
```

**Key differences:**

| Modern (✅ Use this) | Traditional (❌ Don't use) |
|---------------------|---------------------------|
| `list[Type]` | `List[Type]` from `typing` |
| `dict[K, V]` | `Dict[K, V]` from `typing` |
| `tuple[T, ...]` | `Tuple[T, ...]` from `typing` |
| `set[Type]` | `Set[Type]` from `typing` |

**Why modern syntax?**
- Simpler: No imports needed for built-in types
- Standard: Python 3.9+ best practice
- Consistent: One style across the entire codebase

**Note:** Both syntaxes are valid in Python 3.11+, but we standardise on modern for consistency.

---

## Git Workflow

### Branch Naming

```
feature/your-feature-name
bugfix/issue-description
docs/update-readme
```

### Commit Messages

Use conventional commits:

```
feat: Add temporal_mirror geist
fix: Resolve linting errors in test file
docs: Update contributing guide
test: Add integration tests for geists
refactor: Simplify vault sync logic
```

### Before Pushing

1. ✅ Pre-commit hooks passed (automatic)
2. ✅ Run `./scripts/validate.sh`
3. ✅ All tests pass locally
4. ✅ No linting or type errors

---

## Troubleshooting

### Pre-commit not running

```bash
# Reinstall hooks
uv run pre-commit install

# Verify installation
ls -la .git/hooks/pre-commit

# Run manually
uv run pre-commit run --all-files
```

### Dependencies out of sync

```bash
# Re-sync dependencies
uv sync

# Clear cache and re-sync
rm -rf .venv
uv sync
```

### CI passes locally but fails on GitHub

This shouldn't happen if you:
1. Installed pre-commit hooks
2. Ran `./scripts/validate.sh` before pushing

If it does happen:
1. Check the CI logs for the specific failure
2. Run the exact command from CI locally
3. Check for platform-specific issues (Ubuntu vs macOS)

---

## Getting Help

- **Issues**: Open a GitHub issue
- **Questions**: Start a discussion
- **Security**: See SECURITY.md (if it exists)

---

## Summary Checklist

Before your first commit:
- [ ] `uv sync` - Install dependencies
- [ ] `uv run pre-commit install` - Install hooks
- [ ] `./scripts/validate.sh` - Verify setup

Before every push:
- [ ] Pre-commit hooks ran automatically ✓
- [ ] `./scripts/validate.sh` passes ✓
- [ ] Commits follow conventional format ✓

**If both pre-commit and validate.sh pass, your PR will pass CI!** 🎉
