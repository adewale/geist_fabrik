"""Unit tests for structure_diversity_checker geist."""

import os
from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import structure_diversity_checker
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
def vault_with_uniform_structure(tmp_path):
    """Create a vault with uniform recent structure (list-heavy)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Create 8 recent list-heavy notes (uniform structure)
    for i in range(8):
        path = vault_path / f"recent_list_{i}.md"
        content = f"""# Recent List Note {i}

- Item 1
- Item 2
- Item 3
- Item 4
- Item 5
- Item 6
- Item 7
- Item 8
- Item 9
- Item 10"""
        path.write_text(content)
        recent_time = (now - timedelta(days=i)).timestamp()
        os.utime(path, (recent_time, recent_time))

    # Create older notes with different structures (for contrast)
    old_time = (now - timedelta(days=100)).timestamp()

    # Prose-heavy note
    path = vault_path / "old_prose.md"
    content = """# Old Prose Note

This is a long-form prose note with extended paragraphs.
No lists or tasks, just flowing narrative text that explores
ideas in depth. Multiple paragraphs build on each other.

Another paragraph continues the thought."""
    path.write_text(content)
    os.utime(path, (old_time, old_time))

    # Task-oriented note
    path = vault_path / "old_tasks.md"
    content = """# Old Task Note

- [ ] Task 1
- [ ] Task 2
- [x] Task 3
- [ ] Task 4
- [ ] Task 5"""
    path.write_text(content)
    os.utime(path, (old_time, old_time))

    # Code-heavy note
    path = vault_path / "old_code.md"
    content = """# Old Code Note

```python
def example():
    pass
```

```python
def another():
    pass
```"""
    path.write_text(content)
    os.utime(path, (old_time, old_time))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_with_diverse_structure(tmp_path):
    """Create a vault with diverse recent structure."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Create 8 recent notes with varied structures
    structures = [
        ("list", "- Item 1\n- Item 2\n- Item 3\n- Item 4\n- Item 5\n- Item 6\n- Item 7\n- Item 8"),
        ("prose", "Long prose paragraph with extended narrative.\nAnother paragraph follows."),
        ("task", "- [ ] Task 1\n- [ ] Task 2\n- [x] Task 3\n- [ ] Task 4"),
        (
            "code",
            "```python\ndef example():\n    pass\n```\n\n```python\ndef another():\n    pass\n```",
        ),
        ("list", "- Item A\n- Item B\n- Item C\n- Item D\n- Item E\n- Item F\n- Item G\n- Item H"),
        ("prose", "Another prose note with flowing text.\nContinued thought development."),
        ("mixed", "# Mixed\n\n- Item 1\n- Item 2\n\nSome prose.\n\n- [ ] Task"),
        ("list", "- Item X\n- Item Y\n- Item Z\n- Item Q\n- Item R\n- Item S\n- Item T\n- Item U"),
    ]

    for i, (struct_type, content_snippet) in enumerate(structures):
        path = vault_path / f"recent_{struct_type}_{i}.md"
        content = f"""# Recent {struct_type.capitalize()} {i}

{content_snippet}"""
        path.write_text(content)
        recent_time = (now - timedelta(days=i)).timestamp()
        os.utime(path, (recent_time, recent_time))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_recent_notes(tmp_path):
    """Create a vault with insufficient recent notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 3 notes (below minimum of 5)
    for i in range(3):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_structure_diversity_checker_returns_suggestions(vault_with_uniform_structure):
    """Test that structure_diversity_checker returns suggestions with uniform structure."""
    vault, session = vault_with_uniform_structure

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = structure_diversity_checker.suggest(context)

    # Should return list (0-1 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 1


def test_structure_diversity_checker_suggestion_structure(vault_with_uniform_structure):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_uniform_structure

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = structure_diversity_checker.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "structure_diversity_checker"

        # Should reference 1 note (the different example)
        assert len(suggestion.notes) == 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_structure_diversity_checker_uses_obsidian_link(vault_with_uniform_structure):
    """Test that structure_diversity_checker uses obsidian_link for note references."""
    vault, session = vault_with_uniform_structure

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = structure_diversity_checker.suggest(context)

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


def test_structure_diversity_checker_empty_vault(tmp_path):
    """Test that structure_diversity_checker handles empty vault gracefully."""
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

    suggestions = structure_diversity_checker.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_structure_diversity_checker_insufficient_notes(vault_insufficient_recent_notes):
    """Test that structure_diversity_checker handles insufficient notes gracefully."""
    vault, session = vault_insufficient_recent_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = structure_diversity_checker.suggest(context)

    # Should return empty list when < 5 recent notes
    assert len(suggestions) == 0


def test_structure_diversity_checker_diverse_structure(vault_with_diverse_structure):
    """Test that structure_diversity_checker handles diverse structure gracefully."""
    vault, session = vault_with_diverse_structure

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = structure_diversity_checker.suggest(context)

    # Should return empty or no suggestions when structure is diverse
    assert len(suggestions) <= 1


def test_structure_diversity_checker_deterministic_with_seed(vault_with_uniform_structure):
    """Test that structure_diversity_checker returns same results with same seed."""
    vault, session = vault_with_uniform_structure

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

    suggestions1 = structure_diversity_checker.suggest(context1)
    suggestions2 = structure_diversity_checker.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_structure_diversity_checker_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Create geist journal directory with uniform structure
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        path = journal_dir / f"2024-03-{15 + i:02d}.md"
        content = f"""# Session {i}

- Item 1
- Item 2
- Item 3
- Item 4
- Item 5"""
        path.write_text(content)

    # Create 8 recent list-heavy notes (uniform structure)
    for i in range(8):
        path = vault_path / f"recent_list_{i}.md"
        content = f"""# Recent List Note {i}

- Item 1
- Item 2
- Item 3
- Item 4
- Item 5
- Item 6
- Item 7
- Item 8"""
        path.write_text(content)
        recent_time = (now - timedelta(days=i)).timestamp()
        os.utime(path, (recent_time, recent_time))

    # Create older note with different structure
    old_time = (now - timedelta(days=100)).timestamp()
    path = vault_path / "old_prose.md"
    content = """# Old Prose Note

This is a long-form prose note with extended paragraphs.
No lists or tasks, just flowing narrative text."""
    path.write_text(content)
    os.utime(path, (old_time, old_time))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = structure_diversity_checker.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
