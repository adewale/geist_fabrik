# Validation Modes: Full vs Web-Safe

GeistFabrik has two validation scripts to accommodate different development environments:

## TL;DR

- **Local development with models**: Use `./scripts/validate.sh` (full validation)
- **Claude Code for Web** (no model downloads): Use `./scripts/validate_web.sh` (web-safe)
- **GitHub CI**: Always runs full validation with models

## Full Validation (`validate.sh`)

**Use when:**
- You have the sentence-transformers model available (via Git LFS or cache)
- You're running locally with network access
- You want to match exactly what CI will run

**What it runs:**
```bash
./scripts/validate.sh
```

1. Ruff linting
2. Mypy type checking (strict mode)
3. Unused database tables check
4. Unit tests (uses mocked models)
5. Integration tests including slow tests (uses real models)

**Requirements:**
- Git LFS for bundled model, OR
- Network access to download model (~90MB on first run)

**Runtime:** ~2-5 minutes (first run), ~30-60 seconds (cached)

## Web-Safe Validation (`validate_web.sh`)

**Use when:**
- You're in Claude Code for Web (no Git LFS, limited network)
- You want fast validation without model downloads
- You're iterating rapidly on code changes

**What it runs:**
```bash
./scripts/validate_web.sh
```

1. Ruff linting
2. Mypy type checking (strict mode)
3. Unused database tables check
4. Unit tests (uses mocked models)
5. Integration tests **excluding** slow tests (no model downloads)

**Requirements:**
- None! Runs entirely with mocked dependencies

**Runtime:** ~20-40 seconds

## What's the Difference?

The **only** difference is which tests are run:

### Full Validation
```bash
pytest tests/integration -v -m "not slow" --timeout=300
# Runs all integration tests including those marked slow
```

### Web-Safe Validation
```bash
pytest tests/integration -v -m "not slow" --timeout=300
# Excludes integration tests marked with @pytest.mark.slow
```

### Tests Excluded in Web-Safe Mode

Only 2 test files are excluded:

1. **`tests/integration/test_embeddings_integration.py`**
   - Tests real SentenceTransformer model loading
   - Verifies actual semantic similarity quality
   - Requires model download (~90MB)

2. **`tests/integration/test_phase3b_regression.py`**
   - Performance regression tests on large vaults
   - Uses real embeddings to verify geist quality
   - Marked `@pytest.mark.slow` and `@pytest.mark.benchmark`

All other tests (including most integration tests) use mocked models via `SentenceTransformerStub` defined in `tests/conftest.py`.

## How Model Mocking Works

The test suite uses an automatic model injection system in `tests/conftest.py:107-162`:

```python
def pytest_configure(config):
    markexpr = config.getoption("-m", default="")
    should_use_stub = "not slow" in markexpr

    if should_use_stub:
        # Inject SentenceTransformerStub that generates
        # deterministic embeddings without downloading models
        sys.modules["sentence_transformers"] = fake_module
```

**Key insight:** When you run tests with `-m "not slow"`, the test framework automatically replaces `sentence-transformers` with a stub that generates deterministic embeddings based on text hashes. This means:

- **Unit tests:** Always use stub (fast, no downloads)
- **Integration tests (not slow):** Use stub (most integration tests!)
- **Integration tests (slow):** Use real model (only 2 test files)

## CI Behavior

GitHub CI (`.github/workflows/test.yml`) always runs full validation:

```yaml
- name: Cache sentence-transformers models
  uses: actions/cache@v4
  with:
    path: ~/.cache/torch/sentence_transformers
    key: ${{ runner.os }}-sentence-transformers-${{ hashFiles('**/pyproject.toml') }}

- name: Pre-download sentence-transformers model
  run: |
    uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
  continue-on-error: true
  timeout-minutes: 5

- name: Run tests
  run: uv run pytest -v -m "not slow and not benchmark"
```

**Important:** CI runs all tests EXCEPT `slow` and `benchmark` marks, but it still downloads the real model. The model is cached between runs for performance.

## Recommendation for CLAUDE.md

Update the development workflow section to mention both scripts:

```markdown
### Before Pushing (MANDATORY)

**Choose your validation script based on environment:**

- **Local with models:** `./scripts/validate.sh` (recommended)
- **Claude Code for Web:** `./scripts/validate_web.sh`

Both scripts run the same linting and type checks. The web-safe version
skips 2 integration tests that require downloading the sentence-transformers
model (~90MB).

**If your chosen validation script passes, CI will pass.**
```

## Adding New Tests

**If your test needs the real model:**
```python
import pytest

@pytest.mark.slow
@pytest.mark.integration
def test_real_semantic_similarity():
    # Uses real SentenceTransformer model
    # Only runs with full validation
    pass
```

**If your test can use mocked models:**
```python
def test_embedding_computation(mock_embedding_computer):
    # Uses SentenceTransformerStub
    # Runs in both full and web-safe validation
    pass
```

## Troubleshooting

### "Tests are downloading models during validation"

This means you're running tests without `-m "not slow"`. The model stub only activates when slow tests are excluded.

**Fix:** Use the provided validation scripts instead of running pytest directly.

### "CI is passing but my local validation fails"

Check which validation script you're using:
- `validate.sh` should match CI exactly
- `validate_web.sh` may pass locally but CI could fail if you broke a slow test

**Fix:** Run `./scripts/validate.sh` to match CI behavior.

### "Model downloads fail in Claude Code for Web"

This is expected! Claude Code for Web doesn't have Git LFS or reliable model downloads.

**Fix:** Use `./scripts/validate_web.sh` instead of `./scripts/validate.sh`.
