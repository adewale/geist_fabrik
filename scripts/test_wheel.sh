#!/usr/bin/env bash
# Build and verify release artifacts in isolation, including real offline inference.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
if [ -n "${PACKAGE_SMOKE_WORKDIR:-}" ]; then
    # Treat caller input as a parent directory; never recursively delete a
    # caller-selected path. CI can upload the retained run directory on failure.
    mkdir -p "$PACKAGE_SMOKE_WORKDIR"
    WORK_PARENT=$(cd "$PACKAGE_SMOKE_WORKDIR" && pwd -P)
    case "$WORK_PARENT" in
        /|"${HOME:-}"|"$ROOT")
            echo "Unsafe PACKAGE_SMOKE_WORKDIR: $WORK_PARENT" >&2
            exit 2
            ;;
    esac
    WORK=$(mktemp -d "$WORK_PARENT/run.XXXXXX")
else
    WORK=$(mktemp -d "${TMPDIR:-/tmp}/geistfabrik-package-smoke.XXXXXX")
    trap 'rm -rf "$WORK"' EXIT
fi

DIST="$WORK/dist"
mkdir -p "$DIST"
cd "$ROOT"
uv build --out-dir "$DIST"
WHEEL=$(find "$DIST" -maxdepth 1 -name '*.whl' -print -quit)
SDIST=$(find "$DIST" -maxdepth 1 -name '*.tar.gz' -print -quit)
export GEISTFABRIK_WHEEL="$WHEEL"
export GEISTFABRIK_SDIST="$SDIST"

uv run pytest tests/artifact/test_wheel_artifact.py -v --timeout=300
uv run twine check "$WHEEL" "$SDIST"

printf 'wheel: %s bytes (%s)\n' "$(stat -f%z "$WHEEL" 2>/dev/null || stat -c%s "$WHEEL")" "$WHEEL"
printf 'sdist: %s bytes (%s)\n' "$(stat -f%z "$SDIST" 2>/dev/null || stat -c%s "$SDIST")" "$SDIST"

# Prove the sdist can reproduce a wheel with the same resource contract.
mkdir -p "$WORK/sdist-source" "$WORK/rebuilt"
tar -xzf "$SDIST" -C "$WORK/sdist-source"
SOURCE_ROOT=$(find "$WORK/sdist-source" -mindepth 1 -maxdepth 1 -type d -print -quit)
uv build --wheel "$SOURCE_ROOT" --out-dir "$WORK/rebuilt"
export GEISTFABRIK_WHEEL
GEISTFABRIK_WHEEL=$(find "$WORK/rebuilt" -maxdepth 1 -name '*.whl' -print -quit)
uv run pytest tests/artifact/test_wheel_artifact.py -v --timeout=300

# Install only the built wheel into a fresh environment and run away from the checkout.
VENV="$WORK/wheel-venv"
SMOKE_PYTHON=${PACKAGE_SMOKE_PYTHON:-3.11}
uv venv --python "$SMOKE_PYTHON" "$VENV"
uv pip install --python "$VENV/bin/python" "$WHEEL"
SMOKE_HOME="$WORK/empty-home"
mkdir -p "$SMOKE_HOME/hf" "$WORK/outside-repository"
cd "$WORK/outside-repository"
env -u PYTHONPATH HOME="$SMOKE_HOME" HF_HOME="$SMOKE_HOME/hf" \
    GEISTFABRIK_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    "$VENV/bin/python" -I "$ROOT/scripts/installed_wheel_smoke.py"
env -u PYTHONPATH HOME="$SMOKE_HOME" GEISTFABRIK_OFFLINE=1 \
    "$VENV/bin/geistfabrik" --help >/dev/null
env -u PYTHONPATH HOME="$SMOKE_HOME" GEISTFABRIK_OFFLINE=1 \
    "$VENV/bin/gf" --help >/dev/null

echo "Package smoke passed."
