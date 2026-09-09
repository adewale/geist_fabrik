# GeistFabrik Test Suite

The suite is split into fast unit/integration lanes, explicit real-model tests,
and built-artifact checks.

## Canonical Fast Selection

Use the same four-marker exclusion as validation and CI:

```bash
MARKERS="not slow and not benchmark and not artifact and not production_model"
uv run pytest tests/unit -v -m "$MARKERS" --timeout=60
uv run pytest tests/integration -v -m "$MARKERS" --timeout=300
```

`tests/conftest.py` has an autouse fixture that stubs only the external
`SentenceTransformer` constructor for tests without the `production_model`
marker. This behavior is marker-driven: `-m` selects tests but does not itself
activate a stub, and `EmbeddingComputer` is not replaced. This keeps the fast
lanes offline while exercising GeistFabrik's loader and embedding code.

## Test Structure

### Unit Tests (`tests/unit/`)

Fast, isolated tests for individual modules. Prefer injected fakes or the shared
constructor stub, deterministic data, and focused assertions.

### Integration Tests (`tests/integration/`)

Tests interactions between real GeistFabrik components. Most run in the fast
stubbed lane. Tests explicitly marked `production_model` load bundled real
weights and are excluded from that lane.

To run the source-checkout real-model integration tests directly:

```bash
GEISTFABRIK_OFFLINE=1 uv run pytest \
  tests/integration/test_embeddings_integration.py -m production_model -v
```

A materialised model snapshot is required (`git lfs pull`).

### Artifact Tests (`tests/artifact/`)

Artifact tests require orchestrated wheel/sdist paths and should not be invoked
through bare `pytest`. Run the full artifact/release check instead:

```bash
./scripts/test_wheel.sh
```

This builds and inspects wheel/sdist artifacts, rebuilds from the sdist, installs
the wheel in an isolated environment, and performs real offline semantic
inference from the bundled model. The authoritative pre-push command
`./scripts/validate.sh` includes this package smoke.

## Fixtures

- `tests/conftest.py`: shared fixtures and marker-driven external constructor stub
- `tests/stubs.py`: deterministic `SentenceTransformerStub`
- `tests/unit/conftest.py`: unit-specific notes, embeddings, and injected models
- `tests/integration/conftest.py`: integration fixtures

## Focused Development Commands

Keep the canonical selection when running a fast file or directory:

```bash
MARKERS="not slow and not benchmark and not artifact and not production_model"
uv run pytest tests/unit/test_embeddings.py -v -m "$MARKERS"
uv run pytest tests/integration -v -m "$MARKERS"
```

For the complete mandatory local gate:

```bash
./scripts/validate.sh
```

## Adding Tests

### Fast tests
1. Add the test under `tests/unit/` or `tests/integration/`.
2. Prefer deterministic injected models or the shared constructor stub.
3. Do not mark it `production_model` unless real weights are essential to the oracle.
4. Keep it within the lane timeout.

### Real-model tests
1. Mark the test or module with `production_model`.
2. Force offline behavior and use the bundled snapshot.
3. Assert a semantic known answer, not only shape or finiteness.
4. Use `./scripts/test_wheel.sh` when the contract concerns installed artifacts.

## Troubleshooting

### Offline missing-model error

Fast tests that intentionally access the default loader must arrange a narrow
loader path so the external constructor stub can be reached. Production loader
tests should retain coverage of the error raised for an absent or Git LFS
pointer-only snapshot.

### Timeouts

Check for accidental `production_model` selection, network fallback, oversized
data, or missing fixture injection. Release-artifact checks are intentionally
slower than the fast lanes because they build, install, and load real weights.
