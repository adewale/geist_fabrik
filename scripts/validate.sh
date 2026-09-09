#!/usr/bin/env bash
# Local validation script - runs all CI checks locally before pushing
# This helps catch issues before they reach GitHub CI

set -e  # Exit on first error
export GEISTFABRIK_OFFLINE=1

echo "=================================================="
echo "Running Local CI Validation"
echo "=================================================="
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Must be run from repository root"
    exit 1
fi

# Colour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Colour

run_check() {
    local name="$1"
    shift
    echo -e "${YELLOW}▶ $name${NC}"
    if "$@"; then
        echo -e "${GREEN}✓ $name passed${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ $name failed${NC}"
        echo ""
        return 1
    fi
}

# Track failures
FAILED=0

# 0. Resolve exactly the dependency set used by CI
run_check "Dependency sync" uv sync --frozen --extra vector-search || FAILED=1

# 1. Linting with ruff
run_check "Ruff linting" uv run ruff check src/ tests/ || FAILED=1

# 2. Type checking with mypy
run_check "Mypy type checking" uv run mypy src/ --strict || FAILED=1

# 2b. Additive whole-project type checking with Astral ty
run_check "ty type checking" uv run ty check src tests --error-on-warning || FAILED=1

# 3. Unused database tables check
run_check "Unused database tables check" uv run python scripts/detect_unused_tables.py || FAILED=1

# 3b. Security scan (bandit, medium+ severity)
run_check "Bandit security scan" uv run bandit -c pyproject.toml -r src/geistfabrik -ll -q || FAILED=1

# 4. Unit tests (external SentenceTransformer constructor stubbed)
MARKERS="not slow and not benchmark and not artifact and not production_model"
run_check "Unit tests" uv run pytest tests/unit -v -m "$MARKERS" --timeout=60 \
    --cov=geistfabrik --cov-branch --cov-report= || FAILED=1

# 5. Integration tests (same selection and coverage contract as CI)
run_check "Integration tests" uv run pytest tests/integration -v -m "$MARKERS" --timeout=300 \
    --cov=geistfabrik --cov-branch --cov-append --cov-report=term-missing \
    --cov-fail-under=70 || FAILED=1

# 6. Acceptance-criteria verification (spec <-> code drift gate)
# RUNS every machine-verifiable criterion in specs/acceptance_criteria.md
# (it does not trust the status column). Catches renamed/removed tests and
# unwired features that would otherwise let the spec drift from the code.
run_check "Acceptance criteria" uv run python scripts/check_phase_completion.py || FAILED=1

# 7. Build and test release artifacts, including isolated real-model inference.
# test_wheel.sh is standalone and never invokes validate.sh, avoiding recursion.
run_check "Package smoke" ./scripts/test_wheel.sh || FAILED=1

# Summary
echo "=================================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Safe to push.${NC}"
    echo "=================================================="
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Fix issues before pushing.${NC}"
    echo "=================================================="
    exit 1
fi
