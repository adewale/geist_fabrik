# Unit Testing Template for Geists

This document provides a template and guidelines for creating unit tests for GeistFabrik geists.

## Purpose

Unit tests for geists should verify:
1. **Core logic works correctly** - The geist produces suggestions in normal scenarios
2. **Edge cases are handled** - Empty vaults, insufficient data, etc.
3. **Exclusion rules work** - Geist journal filtering, vault-specific filters
4. **Helper functions work** - Any extracted utility functions
5. **Suggestion structure is valid** - Contains required fields (geist_id, notes, text)

## Test File Structure

```python
"""Unit tests for <geist_name> geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import <geist_name>
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry, _GLOBAL_REGISTRY


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_vault_basic(tmp_path):
    """Create a basic test vault for normal case testing.

    Customize this fixture based on what the geist needs:
    - Notes with specific content patterns
    - Notes with particular link structures
    - Notes with temporal properties
    - Virtual notes from journals
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create test notes
    (vault_path / "note1.md").write_text("# Note 1\\n\\nContent here.")
    (vault_path / "note2.md").write_text("# Note 2\\n\\nMore content.")

    # Initialize vault
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Compute embeddings if geist needs them
    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_geist_returns_suggestions(test_vault_basic):
    """Test that geist returns suggestions in normal case."""
    vault, session = test_vault_basic

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = <geist_name>.suggest(context)

    # Basic assertions
    assert isinstance(suggestions, list)
    assert len(suggestions) >= 0  # May return empty if no quality suggestions

    # If suggestions exist, verify structure
    if suggestions:
        suggestion = suggestions[0]
        assert suggestion.geist_id == "<geist_name>"
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)


def test_geist_suggestion_structure(test_vault_basic):
    """Test that suggestions have correct structure."""
    vault, session = test_vault_basic

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = <geist_name>.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, 'text')
        assert hasattr(suggestion, 'notes')
        assert hasattr(suggestion, 'geist_id')

        # Correct types
        assert isinstance(suggestion.text, str)
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "<geist_name>"

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_geist_empty_vault(tmp_path):
    """Test that geist handles empty vault gracefully."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = <geist_name>.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_geist_insufficient_data(tmp_path):
    """Test that geist handles insufficient data gracefully.

    Customize based on geist's minimum requirements:
    - Not enough notes
    - Not enough links
    - Not enough temporal data
    etc.
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create minimal vault (below threshold)
    (vault_path / "note.md").write_text("# Single Note\\n\\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = <geist_name>.suggest(context)

    # Should return empty list when insufficient data
    assert len(suggestions) == 0


# ============================================================================
# Exclusion Tests
# ============================================================================


def test_geist_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    # Create journal notes
    for i in range(5):
        note_path = journal_dir / f"2024-03-{15 + i:02d}.md"
        note_path.write_text(f"# Session {i}\\n\\nJournal entry.")

    # Create regular notes
    for i in range(3):
        note_path = vault_path / f"note_{i}.md"
        note_path.write_text(f"# Note {i}\\n\\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = <geist_name>.suggest(context)

    # Verify that journal notes don't appear in suggestions
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref


# ============================================================================
# Helper Function Tests (if applicable)
# ============================================================================


def test_helper_function_basic():
    """Test extracted helper functions.

    If the geist has helper functions that are exported,
    test them directly here.

    Example from test_harvester_geists.py:
        from geistfabrik.default_geists.code.question_harvester import (
            extract_questions,
            is_valid_question,
        )

        content = "What is this? How does it work?"
        questions = extract_questions(content)
        assert len(questions) == 2
    """
    pass


# ============================================================================
# Virtual Notes Tests (if applicable)
# ============================================================================


def test_geist_uses_obsidian_link_for_virtual_notes(tmp_path):
    """Test that geist uses obsidian_link for virtual notes.

    Only needed if geist queries notes by creation date or other
    properties that could include virtual notes.

    Use the vault_with_virtual_notes fixture from tests/fixtures/virtual_notes.py
    """
    from tests.fixtures.virtual_notes import create_journal_file

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create journal with virtual notes
    create_journal_file(
        vault_path / "Journal.md",
        dates=["2024-03-15", "2024-03-16"],
        content_template="Journal entry for {date}."
    )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2024, 3, 17), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240317,
        function_registry=FunctionRegistry(),
    )

    suggestions = <geist_name>.suggest(context)

    # Check that virtual notes use deeplinks (contain '#')
    virtual_refs = [n for n in suggestions[0].notes if "#" in n]

    # Should have deeplinks for virtual notes
    assert len(virtual_refs) >= 1

    # Check for no duplicate titles (abstraction layer bypass)
    all_refs = []
    for s in suggestions:
        all_refs.extend(s.notes)

    assert len(all_refs) == len(set(all_refs)), "Found duplicate references"


# ============================================================================
# Regression Tests (if applicable)
# ============================================================================


def test_geist_regression_<bug_name>():
    """Test specific bug fix or regression.

    When a bug is found and fixed, add a regression test
    to ensure it doesn't happen again.

    Example from test_creation_burst.py:
        def test_creation_burst_virtual_notes_use_deeplinks(tmp_path):
            # Regression test for duplicate title bug
    """
    pass
```

## Customization Guidelines

### 1. Choose Appropriate Fixtures

Based on what the geist needs:

**For temporal geists** (on_this_day, seasonal_revisit, temporal_drift):
- Set specific created/modified dates on notes
- Use Session with meaningful dates
- Test date boundaries and edge cases

**For graph-based geists** (bridge_builder, hidden_hub, island_hopper):
- Create notes with specific link patterns
- Test different graph structures (isolated, fully connected, hub-and-spoke)
- Verify graph traversal logic

**For semantic geists** (divergent_evolution, concept_cluster, scale_shifter):
- Create notes with varied content for different embeddings
- Test semantic similarity thresholds
- Verify clustering or grouping logic

**For harvester geists** (question_harvester, quote_harvester, todo_harvester):
- Test helper functions directly (extract_*, is_valid_*)
- Use the pattern from test_harvester_geists.py
- Test filtering, deduplication, and validation

**For virtual note geists** (creation_burst, burst_evolution):
- Use fixtures from tests/fixtures/virtual_notes.py
- Test obsidian_link usage
- Check for duplicate title bugs

### 2. Test What Matters

Focus tests on:
- **Core logic**: Does the geist work in typical scenarios?
- **Error handling**: Does it gracefully handle edge cases?
- **Data validation**: Are suggestions structured correctly?
- **Exclusions**: Are filtered items properly excluded?

Don't test:
- Framework internals (VaultContext, Session) - already tested elsewhere
- Generic Python behavior
- Things covered by integration tests

### 3. Use Descriptive Test Names

Good:
- `test_columbo_extracts_questions_from_notes()`
- `test_bridge_builder_finds_shortest_path()`
- `test_on_this_day_filters_by_month_day()`

Bad:
- `test_basic()`
- `test_works()`
- `test_1()`

### 4. Keep Tests Independent

Each test should:
- Create its own test vault (use tmp_path fixture)
- Not depend on other tests running first
- Clean up after itself (pytest handles this automatically)

### 5. Document Test Purpose

Add docstrings explaining:
- What scenario is being tested
- Why this test is important
- What regression it prevents (if applicable)

## Examples to Reference

- **test_creation_burst.py** - Virtual notes, date-based queries, obsidian_link usage
- **test_burst_evolution.py** - Session history, embeddings, temporal logic
- **test_harvester_geists.py** - Helper functions, content extraction, validation

## Running Tests

```bash
# Run unit tests for specific geist
uv run pytest tests/unit/test_<geist_name>.py -v

# Run all unit tests
uv run pytest tests/unit/ -v

# Run with coverage
uv run pytest tests/unit/test_<geist_name>.py --cov=geistfabrik.default_geists.code.<geist_name>
```

## Validation Workflow

Before committing:

```bash
# Run the validation script (includes unit tests)
./scripts/validate.sh
```

This ensures:
- All tests pass
- Code is properly formatted (ruff)
- Type hints are correct (mypy --strict)
- No database issues

## When to Create Unit Tests

Create unit tests for a geist when:

1. **The geist has complex logic** - Multiple branches, edge cases, thresholds
2. **The geist has helper functions** - Extracted utilities that can be tested in isolation
3. **The geist had a bug** - Regression tests prevent recurrence
4. **The geist queries by temporal/creation properties** - May interact with virtual notes
5. **You're developing a new geist** - TDD approach

You may skip unit tests if:
- The geist is trivial (simple query + format)
- It's already covered by integration tests
- It's purely declarative (Tracery geists)

## Notes

- **Integration tests** (`tests/integration/test_virtual_notes_regression.py`) already test all geists together
- **Unit tests** provide focused, fast feedback on specific functionality
- Both are valuable - integration tests catch systemic issues, unit tests catch logic bugs
