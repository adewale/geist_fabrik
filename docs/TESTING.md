# Testing GeistFabrik

This document explains how to test GeistFabrik locally and replicate CI failures before pushing.

## Quick Start

To run the full fast CI pipeline locally before pushing:

```bash
./scripts/validate.sh
```

It syncs the locked `[vector-search]` extra, forces offline mode, runs Ruff,
strict Mypy plus warnings-as-errors Astral ty, database/security checks, split unit/integration coverage with a
measured 70% branch gate, the acceptance-criteria verifier, and the release
artifact real-model lane. For a focused artifact check, run:

```bash
./scripts/test_wheel.sh
```

## Replicating CI Environment

The CI runs tests with specific environment variables to limit threading in ML libraries. To replicate CI conditions exactly:

```bash
# Set CI environment variables
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export TOKENIZERS_PARALLELISM=false

export GEISTFABRIK_OFFLINE=1
MARKERS="not slow and not benchmark and not artifact and not production_model"
uv sync --frozen --extra vector-search
uv run pytest tests/unit -v -m "$MARKERS" --timeout=60
uv run pytest tests/integration -v -m "$MARKERS" --timeout=300
```

## Common Test Issues

### Non-Deterministic Tests

**Problem**: Tests pass locally but fail in CI with different output.

**Common Causes**:
1. **Shared RNG state**: Reusing a `VaultContext` between multiple operations advances its RNG state
2. **File ordering**: Files may be created/listed in different orders on different systems
3. **Timestamps**: Non-deterministic file modification times

**Solutions**:
```python
# ❌ BAD: Reuses same context
context = create_test_vault_context(tmp_path)
result1 = geist1.suggest(context)  # Advances RNG state
result2 = geist2.suggest(context)  # Different state!

# ✅ GOOD: Separate contexts with same seed
context1 = VaultContext(vault, session, seed=123)
context2 = VaultContext(vault, session, seed=123)
result1 = geist1.suggest(context1)
result2 = geist2.suggest(context2)

# ✅ GOOD: Deterministic file times
import os
base_time = 1640000000.0
for i, file_path in enumerate(files):
    os.utime(file_path, (base_time + i, base_time + i))
```

## Test Suite Structure

```
tests/
├── unit/                   # Fast unit tests (~3s)
│   ├── test_tracery_geists.py   # 50 tests for Tracery geists
│   ├── test_vault_context.py    # VaultContext functionality
│   └── ...
├── integration/            # Integration tests
│   ├── test_example_geists.py   # All example geists
│   ├── test_kepano_vault.py     # Real vault parsing
│   └── ...
├── artifact/               # Built wheel/sdist structure contracts
├── stubs.py                # External SentenceTransformer test double
└── conftest.py             # Marker-selected constructor fixture
```

## Running Tests

```bash
# Run the fast lane exactly as validation/CI selects it
uv run pytest -v -m "not slow and not benchmark and not artifact and not production_model"

# Run real source-checkout model integration tests
uv run pytest tests/integration/test_embeddings_integration.py -m production_model -v

# Build and test installed release artifacts (real offline model)
./scripts/test_wheel.sh

# Run specific test file
uv run pytest tests/unit/test_tracery_geists.py -v

# Run specific test
uv run pytest tests/unit/test_tracery_geists.py::TestContradictor::test_contradictor_is_deterministic -xvs

# Run an explicit one-process coverage report
uv run pytest tests/unit tests/integration --cov=geistfabrik --cov-branch --cov-report=term-missing

# Run tests multiple times to check for flakiness
for i in {1..10}; do
  echo "Run $i:"
  uv run pytest tests/unit/test_tracery_geists.py::TestContradictor::test_contradictor_is_deterministic -q || exit 1
done
```

## CI Pipeline

The CI runs these steps on every push to `main` and every pull request:

1. **Install dependencies**: `uv sync --frozen --extra vector-search`
2. **Fast tests**: split unit (`--timeout=60`) and integration
   (`--timeout=300`) runs excluding `slow`, `benchmark`, `artifact`, and
   `production_model`, with explicit appended branch coverage and a measured 70% gate
3. **Static checks**: Ruff, strict Mypy, ty warnings-as-errors, unused tables, Bandit, acceptance gate
4. **Package smoke**: LFS checkout, wheel+sdist and size/metadata/content checks,
   clean wheel install outside the checkout, both console scripts, and real
   384-dimensional inference with empty caches and offline flags

The fast CI matrix runs on:
- **Ubuntu**: Python 3.11 and 3.12
- **macOS**: Python 3.11 only (to save CI time)

The installed-wheel, real-model package smoke runs on Ubuntu with both Python
3.11 and 3.12.

## Debugging Test Failures

### 1. Check CI logs
```bash
# View failed run logs
gh run list --limit 5
gh run view <run-id> --log-failed
```

### 2. Replicate locally
```bash
# Run the canonical local CI validation
./scripts/validate.sh

# Or reproduce only the fast pytest selection
export GEISTFABRIK_OFFLINE=1
uv run pytest -v \
  -m "not slow and not benchmark and not artifact and not production_model"
```

### 3. Run test multiple times
```bash
# Check for flakiness
for i in {1..20}; do
  uv run pytest path/to/test.py::test_name -q || break
done
```

### 4. Add debug output
```python
# Temporary debug output in tests
print(f"Debug: vault notes = {[n.title for n in vault.all_notes()]}")
print(f"Debug: RNG seed = {context.rng.getstate()}")
```

## Test Performance

Target performance (on modern MacBook):
- Unit tests: < 5 seconds
- Integration tests: < 3 seconds
- Full suite: < 10 seconds

`slow` describes duration, `benchmark` performance-only work,
`production_model` real weights, and `artifact` release builds. The fast lane
excludes all four explicitly; `package-smoke` is required release evidence for
the latter two concerns.

## Writing New Tests

### Unit Tests

Use mocks and minimal fixtures:

```python
def test_my_feature(tmp_path: Path):
    """Test description."""
    # Create minimal vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    # Test with deterministic setup
    # ...
```

### Determinism

Always use seeds for reproducibility:

```python
context = VaultContext(vault, session, seed=42)
geist = TraceryGeist.from_yaml(path, seed=42)
```

### Test Organization

- One test class per geist/component
- Descriptive test names: `test_<component>_<behaviour>`
- Group related tests together
- Keep tests independent (no shared state)
