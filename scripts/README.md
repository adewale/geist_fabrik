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
- Ruff, Mypy strict and ty
- database and security checks
- split unit/integration coverage with the canonical fast marker selection,
  then the 70% branch-coverage gate (`check_branch_coverage.py`)
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

## Release Process

The GitHub Actions tag path promotes the exact wheel and source distribution
that passed the Python 3.11 package-smoke lane; it does not rebuild them. To
prepare a release:

1. Move the relevant changelog entries out of `Unreleased` and update the
   version in both `pyproject.toml` and `src/geistfabrik/__init__.py`.
2. Run `./scripts/validate.sh` and merge the release commit to `main`.
3. Create and push an annotated `v<version>` tag at that commit.

The tag workflow checks that the tag, both source version declarations, wheel,
and sdist agree. After all test and package-smoke jobs pass, it generates
`SHA256SUMS` and creates a GitHub Release from those retained artifacts.

PyPI publication is not automated. Add it only after choosing the package
ownership, trusted-publishing environment, and release policy; the GitHub
Release remains the supported automated destination until then.

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
