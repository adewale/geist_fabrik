# GeistFabrik Scripts

This directory contains validation and utility scripts for development.

## Validation Script

### `validate.sh` ⭐

**Run this before every push:**

```bash
./scripts/validate.sh
```

It is the authoritative local CI gate and runs:
- locked dependency sync
- Ruff and Mypy strict
- database and security checks
- split unit/integration coverage with the canonical fast marker selection
- acceptance-criteria verification
- `test_wheel.sh` for wheel/sdist inspection and isolated real-model inference

The fast selection is:

```bash
MARKERS="not slow and not benchmark and not artifact and not production_model"
```

The autouse pytest fixture uses the absence of the `production_model` marker to
stub only the external `SentenceTransformer` constructor. Stubbing is
marker-driven; it does not depend on the command text or replace
`EmbeddingComputer`.

**Requirements:** synced development dependencies and a materialised bundled
model snapshot (run `git lfs pull` in a source checkout).

**Runtime:** several minutes, depending on dependency caches and artifact build/install speed.

A green run is required before pushing. CI also tests additional Python versions
and operating systems, so local success cannot rule out platform-specific failures.

## Release Artifact Script

### `test_wheel.sh`

For a focused artifact/full-release check, run:

```bash
./scripts/test_wheel.sh
```

It builds the wheel and sdist, checks their contents and metadata, rebuilds a
wheel from the sdist, installs the wheel into a fresh environment outside the
checkout, and performs real offline semantic inference from the bundled model.
It is also invoked by `validate.sh`; it does not invoke `validate.sh` itself.

## Other Scripts

### `detect_unused_tables.py`

Analyzes the codebase to detect unused database tables.

```bash
uv run python scripts/detect_unused_tables.py
```

Exit codes:
- 0: All tables are used
- 1: Found unused tables

## CI/CD Integration

GitHub Actions uses the same canonical fast selection and runs a required
package-smoke lane. `validate.sh` covers both locally.

## See Also

- `docs/CI_VALIDATION_GUIDE.md` - CI/CD best practices
- `tests/conftest.py` - Marker-driven external constructor stub
