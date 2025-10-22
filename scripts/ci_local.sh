#!/bin/bash
# Local CI replication script - runs all CI steps
set -e  # Exit on first error

echo "======================================"
echo "Running GeistFabrik CI Pipeline Locally"
echo "======================================"
echo ""

# Set CI environment variables (to match CI threading limits)
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export TOKENIZERS_PARALLELISM=false

# Step 1: Install dependencies
echo "Step 1/6: Installing dependencies..."
uv sync
echo "✅ Dependencies installed"
echo ""

# Step 2: Run tests (excluding slow tests, like CI)
echo "Step 2/6: Running tests..."
uv run pytest -v -m "not slow"
echo "✅ Tests passed"
echo ""

# Step 3: Run linting
echo "Step 3/6: Running linting..."
uv run ruff check src/ tests/
echo "✅ Linting passed"
echo ""

# Step 4: Run type checking
echo "Step 4/6: Running type checking..."
uv run mypy src/ --strict
echo "✅ Type checking passed"
echo ""

# Step 5: Check for unused database tables
echo "Step 5/6: Checking for unused database tables..."
uv run python scripts/detect_unused_tables.py
echo "✅ No unused database tables"
echo ""

# Step 6: Check phase completion (continue on error like CI)
echo "Step 6/6: Checking phase completion..."
uv run python scripts/check_phase_completion.py || true
echo "✅ Phase completion check complete"
echo ""

echo "======================================"
echo "✅ All CI steps passed successfully!"
echo "======================================"
