#!/usr/bin/env bash
# One-time development environment setup script

set -e

echo "=================================================="
echo "GeistFabrik Development Environment Setup"
echo "=================================================="
echo ""

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv not found"
    echo ""
    echo "Install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "Or visit: https://docs.astral.sh/uv/"
    exit 1
fi

echo "✓ Found uv $(uv --version)"
echo ""

# Sync dependencies
echo "📦 Installing dependencies with uv sync..."
uv sync
echo "✓ Dependencies installed"
echo ""

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
uv run pre-commit install
echo "✓ Pre-commit hooks installed"
echo ""

# Run pre-commit once to cache tools
echo "🔧 Running pre-commit once to cache tools..."
uv run pre-commit run --all-files || true
echo "✓ Pre-commit cache initialized"
echo ""

# Verify setup
echo "=================================================="
echo "🎉 Development environment ready!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Run tests:  uv run pytest -v"
echo "  2. Before pushing:  ./scripts/validate.sh"
echo "  3. See CONTRIBUTING.md for full guide"
echo ""
echo "Pre-commit hooks will run automatically on git commit."
echo ""
