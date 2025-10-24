# Testing GeistFabrik

This document explains how to test GeistFabrik locally and replicate CI failures before pushing.

## Quick Start

To run the full CI pipeline locally before pushing:

```bash
./scripts/ci_local.sh
```

This script replicates the exact CI environment and runs all the same checks.

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

# Run tests excluding slow tests (like CI)
uv run pytest -v -m "not slow"
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
├── integration/            # Integration tests (~2s)
│   ├── test_example_geists.py   # All example geists
│   ├── test_kepano_vault.py     # Real vault parsing
│   └── ...
└── conftest.py            # Shared fixtures
```

## Running Tests

```bash
# Run all tests (excluding slow)
uv run pytest -v -m "not slow"

# Run all tests including slow ones
uv run pytest -v

# Run specific test file
uv run pytest tests/unit/test_tracery_geists.py -v

# Run specific test
uv run pytest tests/unit/test_tracery_geists.py::TestContradictor::test_contradictor_is_deterministic -xvs

# Run with coverage
uv run pytest --cov=src/geistfabrik --cov-report=html

# Run tests multiple times to check for flakiness
for i in {1..10}; do
  echo "Run $i:"
  uv run pytest tests/unit/test_tracery_geists.py::TestContradictor::test_contradictor_is_deterministic -q || exit 1
done
```

## CI Pipeline

The CI runs these steps on every push to `main` and every pull request:

1. **Install dependencies**: `uv sync`
2. **Run tests**: `uv run pytest -v -m "not slow"`
3. **Linting**: `uv run ruff check src/ tests/`
4. **Type checking**: `uv run mypy src/ --strict`
5. **Unused tables check**: `uv run python scripts/detect_unused_tables.py`

The CI runs on:
- **Ubuntu**: Python 3.11 and 3.12
- **macOS**: Python 3.11 only (to save CI time)

## Debugging Test Failures

### 1. Check CI logs
```bash
# View failed run logs
gh run list --limit 5
gh run view <run-id> --log-failed
```

### 2. Replicate locally
```bash
# Run with CI environment
./scripts/ci_local.sh

# Or manually set env vars
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
       OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 TOKENIZERS_PARALLELISM=false
uv run pytest -v -m "not slow"
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

Slow tests are marked with `@pytest.mark.slow` and excluded from CI via `-m "not slow"`.

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
- Descriptive test names: `test_<component>_<behavior>`
- Group related tests together
- Keep tests independent (no shared state)
