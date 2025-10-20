# GeistFabrik Test Suite

This directory contains the test suite for GeistFabrik, organized into unit tests and integration tests.

## Test Structure

### Unit Tests (`tests/unit/`)

Fast, isolated tests that use mocked dependencies. These tests:
- Use mocked SentenceTransformer models (no model downloads)
- Run in seconds
- Have 5-second timeout per test
- Are suitable for TDD and rapid development
- Run by default in CI/CD pipelines

**Run unit tests:**
```bash
pytest tests/unit/
```

### Integration Tests (`tests/integration/`)

Slower, end-to-end tests that use real dependencies. These tests:
- Use real SentenceTransformer models (downloads ~80-90MB on first run)
- Run in minutes
- Have 60-second timeout per test
- Marked with `@pytest.mark.slow` and `@pytest.mark.integration`
- Verify actual semantic similarity with real embeddings

**Run integration tests:**
```bash
pytest tests/integration/
```

**Skip integration tests (faster):**
```bash
pytest -m "not slow"
```

## Test Files

### Unit Tests
- `test_embeddings.py` - Unit tests for embeddings module with mocked models
  - Tests embedding computation logic
  - Tests session management
  - Tests caching behavior
  - Tests similarity calculations
  - All tests use deterministic mocked embeddings

### Integration Tests
- `test_embeddings_integration.py` - Integration tests with real SentenceTransformer model
  - Tests actual model loading
  - Tests semantic similarity quality
  - Tests batch computation
  - Tests edge cases (empty content, very long content)

## Fixtures

### Unit Test Fixtures (`tests/unit/conftest.py`)
- `sample_notes` - Sample Note objects for testing
- `mock_sentence_transformer` - Mocked model returning deterministic embeddings
- `mock_embedding_computer` - EmbeddingComputer with injected mock model
- `fixed_embeddings` - Pre-computed simple vectors for similarity testing

### Integration Test Fixtures (`tests/integration/conftest.py`)
- Registers pytest markers (`slow`, `integration`)

## Preventing Hangs

The original `test_embeddings.py` would hang due to:
1. Model download on first run without timeout
2. Module-scoped fixtures that blocked test startup
3. No separation between unit and integration tests

### Solutions Applied:

1. **Model Injection**: Updated `EmbeddingComputer` and `Session` to accept pre-initialized models
2. **Mocked Unit Tests**: Unit tests use deterministic mocked embeddings
3. **Timeout Decorators**: All tests have timeouts (5s for unit, 60s for integration)
4. **Fixture Scope**: Changed from module-scoped to function-scoped fixtures
5. **Clear Separation**: Unit tests never trigger model downloads

## Running Tests

**All tests:**
```bash
pytest
```

**Unit tests only (fast, default in CI):**
```bash
pytest tests/unit/ -v
```

**Integration tests only:**
```bash
pytest tests/integration/ -v
```

**Skip slow tests:**
```bash
pytest -m "not slow"
```

**With coverage:**
```bash
pytest --cov=geistfabrik --cov-report=html
```

## CI/CD Recommendations

For GitHub Actions or other CI:

```yaml
# Fast check (unit tests only)
- name: Run unit tests
  run: pytest tests/unit/ -v

# Comprehensive check (all tests, cache model)
- name: Cache sentence-transformers models
  uses: actions/cache@v3
  with:
    path: ~/.cache/huggingface
    key: ${{ runner.os }}-huggingface-models

- name: Run all tests
  run: pytest -v
```

## Adding New Tests

### For Unit Tests:
1. Add test to `tests/unit/test_*.py`
2. Use mocked fixtures from `conftest.py`
3. Verify test runs in <5 seconds
4. Don't trigger actual model loading

### For Integration Tests:
1. Add test to `tests/integration/test_*_integration.py`
2. Mark with `@pytest.mark.slow` and `@pytest.mark.integration`
3. Use real models and verify semantic quality
4. Set appropriate timeout (default 60s)

## Troubleshooting

### "Model download hangs"
- Integration tests download models on first run
- Ensure internet connection is available
- Check `~/.cache/huggingface/` for cached models
- Set `TRANSFORMERS_CACHE` environment variable if needed

### "Tests timeout"
- Unit tests should complete in <5 seconds
- Integration tests should complete in <60 seconds
- If timeouts occur, check for:
  - Accidental use of real model in unit tests
  - Network issues during model download
  - Large batch sizes in tests

### "Import errors"
- Ensure `pytest-timeout` is installed: `pip install pytest-timeout>=2.2.0`
- Update dev dependencies: `pip install -e ".[dev]"`
