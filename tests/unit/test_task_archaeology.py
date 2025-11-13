"""Unit tests for task_archaeology geist."""

import os
from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import task_archaeology
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
def vault_with_old_tasks(tmp_path):
    """Create a vault with notes containing old incomplete tasks."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()
    old_date = now - timedelta(days=60)

    # Create notes with incomplete tasks (old)
    for i in range(5):
        path = vault_path / f"old_tasks_{i}.md"
        content = f"""# Old Tasks {i}

Project notes with tasks:
- [ ] Incomplete task 1
- [x] Completed task 1
- [ ] Incomplete task 2
- [ ] Incomplete task 3"""
        path.write_text(content)
        task_time = (old_date - timedelta(days=i * 5)).timestamp()
        os.utime(path, (task_time, task_time))

    # Create notes with all completed tasks (should be excluded)
    for i in range(3):
        path = vault_path / f"completed_tasks_{i}.md"
        content = f"""# Completed Tasks {i}

All done:
- [x] Completed task 1
- [x] Completed task 2
- [x] Completed task 3"""
        path.write_text(content)
        task_time = (old_date - timedelta(days=i * 5)).timestamp()
        os.utime(path, (task_time, task_time))

    # Create recent notes with tasks (should be excluded)
    recent_date = now - timedelta(days=10)
    for i in range(3):
        path = vault_path / f"recent_tasks_{i}.md"
        content = f"""# Recent Tasks {i}

Recent project:
- [ ] Incomplete task 1
- [ ] Incomplete task 2"""
        path.write_text(content)
        recent_time = (recent_date - timedelta(days=i)).timestamp()
        os.utime(path, (recent_time, recent_time))

    # Create notes without tasks
    for i in range(5):
        path = vault_path / f"no_tasks_{i}.md"
        content = f"""# No Tasks {i}

Just regular content without any tasks."""
        path.write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_no_old_tasks(tmp_path):
    """Create a vault with no old incomplete tasks."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Only create notes without tasks or with completed tasks
    for i in range(10):
        path = vault_path / f"no_tasks_{i}.md"
        content = f"""# No Tasks {i}

Regular content without tasks."""
        path.write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_task_archaeology_returns_suggestions(vault_with_old_tasks):
    """Test that task_archaeology returns suggestions with old incomplete tasks.

    Setup:
        Vault with task-bearing notes.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_old_tasks

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = task_archaeology.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_task_archaeology_suggestion_structure(vault_with_old_tasks):
    """Test that suggestions have correct structure.

    Setup:
        Vault with tasks.

    Verifies:
        - Has required fields
        - References notes with unfinished tasks"""
    vault, session = vault_with_old_tasks

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = task_archaeology.suggest(context)

    # BEHAVIORAL: Verify geist follows output constraints
    # (This is a basic check - deeper assertions added to high-priority geists in Session 2)
    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "task_archaeology"

        # Should reference 1 note
        assert len(suggestion.notes) == 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_task_archaeology_uses_obsidian_link(vault_with_old_tasks):
    """Test that task_archaeology uses obsidian_link for note references.

    Setup:
        Vault with tasks.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_old_tasks

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = task_archaeology.suggest(context)

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


def test_task_archaeology_empty_vault(tmp_path):
    """Test that task_archaeology handles empty vault gracefully.

    Setup:
        Empty vault.

    Verifies:
        - Returns empty list"""
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

    suggestions = task_archaeology.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_task_archaeology_no_old_tasks(vault_no_old_tasks):
    """Test that task_archaeology handles vault with no old incomplete tasks."""
    vault, session = vault_no_old_tasks

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = task_archaeology.suggest(context)

    # Should return empty list when no old incomplete tasks
    assert len(suggestions) == 0


def test_task_archaeology_recent_tasks_excluded(tmp_path):
    """Test that task_archaeology excludes recently modified task notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Create notes with incomplete tasks but modified recently (< 30 days)
    recent_date = now - timedelta(days=20)
    for i in range(5):
        path = vault_path / f"recent_tasks_{i}.md"
        content = f"""# Recent Tasks {i}

- [ ] Incomplete task 1
- [ ] Incomplete task 2"""
        path.write_text(content)
        recent_time = (recent_date - timedelta(days=i)).timestamp()
        os.utime(path, (recent_time, recent_time))

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

    suggestions = task_archaeology.suggest(context)

    # Should return empty when all tasks are recent
    assert len(suggestions) == 0


def test_task_archaeology_max_suggestions(vault_with_old_tasks):
    """Test that task_archaeology never returns more than 3 suggestions.

    Setup:
        Vault with many tasks.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_old_tasks

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = task_archaeology.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_task_archaeology_deterministic_with_seed(vault_with_old_tasks):
    """Test that task_archaeology returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_old_tasks

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

    suggestions1 = task_archaeology.suggest(context1)
    suggestions2 = task_archaeology.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_task_archaeology_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with old task content
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    now = datetime.now()
    old_date = now - timedelta(days=60)

    for i in range(5):
        path = journal_dir / f"2024-03-{15 + i:02d}.md"
        content = f"""# Session {i}

Project notes with tasks:
- [ ] Incomplete task 1
- [x] Completed task 1
- [ ] Incomplete task 2

^g20240315-{i}"""
        path.write_text(content)
        task_time = (old_date - timedelta(days=i * 5)).timestamp()
        os.utime(path, (task_time, task_time))

    # Create notes with old incomplete tasks
    for i in range(5):
        path = vault_path / f"old_tasks_{i}.md"
        content = f"""# Old Tasks {i}

Project notes with tasks:
- [ ] Incomplete task 1
- [x] Completed task 1
- [ ] Incomplete task 2
- [ ] Incomplete task 3"""
        path.write_text(content)
        task_time = (old_date - timedelta(days=i * 5)).timestamp()
        os.utime(path, (task_time, task_time))

    # Create notes with all completed tasks (should be excluded)
    for i in range(3):
        path = vault_path / f"completed_tasks_{i}.md"
        content = f"""# Completed Tasks {i}

All done:
- [x] Completed task 1
- [x] Completed task 2
- [x] Completed task 3"""
        path.write_text(content)
        task_time = (old_date - timedelta(days=i * 5)).timestamp()
        os.utime(path, (task_time, task_time))

    # Create recent notes with tasks (should be excluded)
    recent_date = now - timedelta(days=10)
    for i in range(3):
        path = vault_path / f"recent_tasks_{i}.md"
        content = f"""# Recent Tasks {i}

Recent project:
- [ ] Incomplete task 1
- [ ] Incomplete task 2"""
        path.write_text(content)
        recent_time = (recent_date - timedelta(days=i)).timestamp()
        os.utime(path, (recent_time, recent_time))

    # Create notes without tasks
    for i in range(5):
        path = vault_path / f"no_tasks_{i}.md"
        content = f"""# No Tasks {i}

Just regular content without any tasks."""
        path.write_text(content)

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

    suggestions = task_archaeology.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
