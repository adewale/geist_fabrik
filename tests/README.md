# GeistFabrik Test Suite

The suite is split into fast unit/integration lanes, explicit real-model tests,
and built-artifact checks.

## Canonical Fast Selection

Use the same four-marker exclusion as validation and CI:

```bash
MARKERS="not slow and not benchmark and not artifact and not production_model"
uv run pytest tests/unit -v -m "$MARKERS" --timeout=60 --require-geist-firing
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

- `tests/conftest.py`: shared fixtures, marker-driven external constructor stub,
  and registration of the `tests/plugins/` gate options
- `tests/stubs.py`: deterministic `SentenceTransformerStub`
- `tests/fixtures/helpers.py`: `VaultBuilder`, `assert_valid_suggestions`, `SESSION_DATE`, `SEED`
- `tests/fixtures/virtual_notes.py`: `create_journal_file` for date-collection journals
- `tests/unit/conftest.py`: unit-specific notes, embeddings, and injected models
- `tests/integration/conftest.py`: integration fixtures

### Designing fixtures that make a geist fire

The stub embedding is lexical (bag of words): each content word of three or
more characters (minus a few stopwords) adds to a hashed dimension, so notes that
share words are similar and notes with disjoint vocabulary are near-orthogonal.
Identical text gives similarity 1.0. Embeddings include the `# Title` line.
Control similarity by choosing shared or disjoint words, not by hoping.

`VaultBuilder(tmp_path)` writes real notes with pinned `created`/`modified`
times, then `.build(session_date=..., history=[...], seed=...)` returns a real
`VaultContext` on an in-memory database with the requested past sessions
already embedded. `.journal(...)` writes a `geist journal/` note that no geist
may suggest. Check output with `assert_valid_suggestions`, which fails on empty
output unless you pass `min_count=0` for a test about abstention.

Every test must be able to fail. Do not loop over output that may be empty or
bound it by a cap it can never exceed. A regression test for a bug must fail
on the pre-fix code (a control run: check the old code out from git and run
the test with `--timeout`) and pass after the fix. Do not use mutation testing,
automated or hand-made: mutants routinely produce runaway tests. Do not let a
mock or spy supply the value under test; a spy should delegate to the real
function.

## Quality Gates

Coverage shows that code ran, not that a test checked it. These gates check
the tests themselves. They are cheap and deterministic, and `validate.sh` and
CI run them identically.

| Gate | Where | Fails when |
|------|-------|------------|
| Geist firing | `--require-geist-firing` on the unit lane; `tests/plugins/geist_firing.py` | a bundled geist (code or Tracery) never built a `Suggestion` during the lane |
| Suite hygiene | `tests/unit/test_suite_hygiene.py`; `tests/plugins/hygiene_scan.py` | a test asserts nothing, asserts something always true, or checks output only where it may be empty: inside a loop over it, under `if output:`, as `not any(...)` over it, or behind a guard that does not prove it is non-empty (`isinstance(x, list)`, `len(x) <= N`) |
| Acceptance evidence | `scripts/check_phase_completion.py`; `tests/plugins/selection_report.py` | an AUTO pytest criterion selects no tests, or names a file the canonical marker filter only partly selects |

How the geist firing gate attributes output: it wraps `Suggestion.__init__`
for the session and credits the nearest calling frame that lives in
`default_geists/code/<geist>.py`, or `TraceryGeist.suggest` for a grammar
loaded from `default_geists/tracery/<geist>.yaml`. This works for direct
`module.suggest(vault)` calls and for `GeistExecutor`, which loads geists by
file path. `Suggestion(geist_id="x", ...)` written in a test is not credited.
Pass the flag only on the full unit lane; on a partial run it lists every
geist the selection did not exercise.

Each gate has an allowlist with exact ids and written reasons:
`ALLOWLIST` in `tests/plugins/geist_firing.py` (geist ids) and in
`tests/unit/test_suite_hygiene.py` (`(test id, rule)` pairs). A stale entry
fails: one whose geist now fires, or whose test was fixed or removed. To clear
an entry, fix the test and delete the entry.

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
