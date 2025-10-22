#!/bin/bash
# Local CI replication script - runs all CI steps
set -e  # Exit on first error

echo "======================================"
echo "Running GeistFabrik CI Pipeline Locally"
echo "======================================"
echo ""

# Step 1: Install dependencies
echo "Step 1/5: Installing dependencies..."
uv sync
echo "✅ Dependencies installed"
echo ""

# Step 2: Run tests
echo "Step 2/5: Running tests..."
uv run pytest -v
echo "✅ Tests passed"
echo ""

# Step 3: Run linting
echo "Step 3/5: Running linting..."
uv run ruff check src/ tests/
echo "✅ Linting passed"
echo ""

# Step 4: Run type checking
echo "Step 4/5: Running type checking..."
uv run mypy src/ --strict
echo "✅ Type checking passed"
echo ""

# Step 5: Check phase completion (continue on error like CI)
echo "Step 5/5: Checking phase completion..."
uv run python scripts/check_phase_completion.py || true
echo "✅ Phase completion check complete"
echo ""

echo "======================================"
echo "✅ All CI steps passed successfully!"
echo "======================================"
