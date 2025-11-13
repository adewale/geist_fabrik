"""Unit tests for metadata_driven_discovery geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import metadata_driven_discovery
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry


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
def vault_with_metadata_patterns(tmp_path):
    """Create a vault with diverse metadata patterns."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Pattern 1: Complex but isolated notes (high complexity, few connections)
    for i in range(5):
        path = vault_path / f"complex_isolated_{i}.md"
        # High lexical diversity - varied vocabulary
        content = f"""# Complex Isolated {i}

This note contains sophisticated terminology, elaborate explanations,
multifaceted perspectives, comprehensive analysis, nuanced distinctions,
paradigmatic frameworks, systematic methodologies, theoretical foundations,
empirical observations, and sophisticated argumentation. The vocabulary
demonstrates substantial lexical diversity.

Additional paragraphs to increase reading time and complexity."""
        path.write_text(content)

    # Pattern 2: Buried gems (high diversity, old)
    old_date = now - timedelta(days=120)
    for i in range(5):
        path = vault_path / f"buried_gem_{i}.md"
        content = f"""# Buried Gem {i}

Exceptional vocabulary, remarkable insights, extraordinary perspectives,
phenomenal analysis, outstanding clarity, magnificent structure,
superb articulation, brilliant synthesis, marvelous connections,
exemplary documentation."""
        path.write_text(content)
        import os

        old_time = (old_date - timedelta(days=i * 5)).timestamp()
        os.utime(path, (old_time, old_time))

    # Pattern 3: Abandoned task notes (tasks, old)
    task_date = now - timedelta(days=90)
    for i in range(5):
        path = vault_path / f"abandoned_project_{i}.md"
        content = f"""# Abandoned Project {i}

Project notes with tasks:
- [ ] Incomplete task 1
- [ ] Incomplete task 2
- [x] Completed task 1
- [ ] Incomplete task 3"""
        path.write_text(content)
        import os

        task_time = (task_date - timedelta(days=i * 10)).timestamp()
        os.utime(path, (task_time, task_time))

    # Add some regular notes to reach minimum
    for i in range(10):
        path = vault_path / f"regular_{i}.md"
        content = f"""# Regular {i}

Regular note with normal content and [[link_{i}]]."""
        path.write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with insufficient notes for pattern detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 5 notes (below minimum for patterns)
    for i in range(5):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_metadata_driven_discovery_returns_suggestions(vault_with_metadata_patterns):
    """Test that metadata_driven_discovery returns suggestions with metadata patterns."""
    vault, session = vault_with_metadata_patterns

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = metadata_driven_discovery.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_metadata_driven_discovery_suggestion_structure(vault_with_metadata_patterns):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_metadata_patterns

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = metadata_driven_discovery.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "metadata_driven_discovery"

        # Should reference at least 2 notes
        assert len(suggestion.notes) >= 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_metadata_driven_discovery_uses_obsidian_link(vault_with_metadata_patterns):
    """Test that metadata_driven_discovery uses obsidian_link for note references."""
    vault, session = vault_with_metadata_patterns

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = metadata_driven_discovery.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_metadata_driven_discovery_empty_vault(tmp_path):
    """Test that metadata_driven_discovery handles empty vault gracefully."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = metadata_driven_discovery.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_metadata_driven_discovery_insufficient_patterns(vault_insufficient_notes):
    """Test that metadata_driven_discovery handles insufficient patterns gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = metadata_driven_discovery.suggest(context)

    # Should return empty list or minimal suggestions
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_metadata_driven_discovery_max_suggestions(vault_with_metadata_patterns):
    """Test that metadata_driven_discovery never returns more than 2 suggestions."""
    vault, session = vault_with_metadata_patterns

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = metadata_driven_discovery.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_metadata_driven_discovery_deterministic_with_seed(vault_with_metadata_patterns):
    """Test that metadata_driven_discovery returns same results with same seed."""
    vault, session = vault_with_metadata_patterns

    # Reuse same FunctionRegistry to avoid duplicate registration
    registry = FunctionRegistry()

    context1 = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=registry,
    )

    context2 = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=registry,
    )

    suggestions1 = metadata_driven_discovery.suggest(context1)
    suggestions2 = metadata_driven_discovery.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_metadata_driven_discovery_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    now = datetime.now()
    old_date = now - timedelta(days=120)

    # Create journal notes with metadata patterns (complex, old, with tasks)
    for i in range(5):
        content = f"""# Session {i}

Exceptional vocabulary, remarkable insights, extraordinary perspectives,
phenomenal analysis, outstanding clarity, magnificent structure.

- [ ] Incomplete task 1
- [ ] Incomplete task 2
- [x] Completed task 1
"""
        path = journal_dir / f"2024-03-{15 + i:02d}.md"
        path.write_text(content)
        import os

        old_time = (old_date - timedelta(days=i * 10)).timestamp()
        os.utime(path, (old_time, old_time))

    # Create regular notes with metadata patterns
    # Complex but isolated notes
    for i in range(5):
        content = f"""# Complex Isolated {i}

This note contains sophisticated terminology, elaborate explanations,
multifaceted perspectives, comprehensive analysis, nuanced distinctions."""
        (vault_path / f"complex_{i}.md").write_text(content)

    # Buried gems (high diversity, old)
    for i in range(5):
        content = f"""# Buried Gem {i}

Exceptional vocabulary, remarkable insights, extraordinary perspectives."""
        path = vault_path / f"buried_{i}.md"
        path.write_text(content)
        import os

        old_time = (old_date - timedelta(days=i * 5)).timestamp()
        os.utime(path, (old_time, old_time))

    # Regular notes to reach minimum
    for i in range(10):
        (vault_path / f"regular_{i}.md").write_text(f"# Regular {i}\n\nRegular content.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault, session=session, seed=20240315, function_registry=FunctionRegistry()
    )

    suggestions = metadata_driven_discovery.suggest(context)

    # Verify no suggestions reference geist journal notes
    journal_notes = [note for note in vault.all_notes() if "geist journal" in note.path.lower()]
    journal_titles = {note.title.lower() for note in journal_notes}

    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert note_ref.lower() not in journal_titles, (
                f"Found journal note reference: {note_ref}"
            )
