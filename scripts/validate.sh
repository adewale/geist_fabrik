#!/usr/bin/env bash
# Local validation script - runs all CI checks locally before pushing
# This helps catch issues before they reach GitHub CI

set -e  # Exit on first error

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

# 1. Linting with ruff
run_check "Ruff linting" uv run ruff check src/ tests/ || FAILED=1

# 2. Type checking with mypy
run_check "Mypy type checking" uv run mypy src/ --strict || FAILED=1

# 3. Unused database tables check
run_check "Unused database tables check" uv run python scripts/detect_unused_tables.py || FAILED=1

# 4. Unit tests (with mocked models)
run_check "Unit tests" uv run pytest tests/unit -v -m "not slow" --timeout=60 || FAILED=1

# 5. Integration tests (excluding slow tests)
run_check "Integration tests" uv run pytest tests/integration -v -m "not slow" --timeout=300 || FAILED=1

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
