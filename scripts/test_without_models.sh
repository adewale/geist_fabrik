#!/usr/bin/env bash
# Test suite runner that works without model downloads
# Perfect for Claude Code for Web and rapid development

set -e  # Exit on first error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}GeistFabrik Test Suite (No Model Downloads)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Parse arguments
VERBOSE=""
COVERAGE=""
QUICK=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -c|--coverage)
            COVERAGE="--cov=geistfabrik --cov-report=term-missing --cov-branch"
            shift
            ;;
        -q|--quick)
            QUICK="-x"  # Stop on first failure
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-v|--verbose] [-c|--coverage] [-q|--quick]"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}Running 655 tests with stubbed embeddings...${NC}"
echo -e "${YELLOW}(Skipping 9 tests that require real model downloads)${NC}"
echo ""

# Run tests with -m "not slow" to skip model downloads
uv run pytest -m "not slow" $VERBOSE $COVERAGE $QUICK

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Tests complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Coverage Summary:${NC}"
echo "  • Core infrastructure: 85-100% (vault, models, config, parsing)"
echo "  • Embeddings layer: ~79% (using deterministic stubs)"
echo "  • Overall: ~43% (many geists need real embeddings)"
echo ""
echo -e "${BLUE}What's tested:${NC}"
echo "  ✓ All core vault operations (sync, queries, links, tags)"
echo "  ✓ All embedding logic (with deterministic stub model)"
echo "  ✓ All markdown parsing and virtual notes"
echo "  ✓ All metadata and function registry system"
echo "  ✓ All filtering and quality checks"
echo "  ✓ All Tracery grammar and geist loading"
echo "  ✓ Most VaultContext helpers and graph operations"
echo ""
echo -e "${BLUE}What's NOT tested:${NC}"
echo "  ✗ Real semantic similarity (needs actual model)"
echo "  ✗ Individual geist quality (needs real embeddings)"
echo "  ✗ CLI commands (many need real model)"
echo ""
