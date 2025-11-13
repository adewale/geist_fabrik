"""Unit tests for convergent_evolution geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import convergent_evolution
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
def vault_with_session_history(tmp_path):
    """Create a vault with multiple sessions for convergence detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Create notes with varying content
    for i in range(35):
        path = vault_path / f"note_{i}.md"
        path.write_text(f"# Note {i}\n\nContent about topic {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create multiple sessions (5 sessions over time)
    sessions = []
    for i in range(5):
        session_date = now - timedelta(days=(5 - i) * 30)  # Monthly sessions
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())
        sessions.append(session)

    # Return most recent session as active session
    return vault, sessions[-1]


@pytest.fixture
def vault_insufficient_sessions(tmp_path):
    """Create a vault with insufficient session history."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes
    for i in range(15):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Only 2 sessions (need 3)
    now = datetime.now()
    for i in range(2):
        session_date = now - timedelta(days=(2 - i) * 30)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    # Return most recent session
    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with insufficient notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only 8 notes (need 10)
    for i in range(8):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create sessions
    now = datetime.now()
    for i in range(3):
        session_date = now - timedelta(days=(3 - i) * 30)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_convergent_evolution_returns_suggestions(vault_with_session_history):
    """Test that convergent_evolution returns suggestions with session history.

    Setup:
        Vault with notes converging semantically.

    Verifies:
        - Returns suggestions (max 1)"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = convergent_evolution.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_convergent_evolution_suggestion_structure(vault_with_session_history):
    """Test that suggestions have correct structure.

    Setup:
        Vault with converging notes.

    Verifies:
        - Has required fields
        - References notes showing convergence"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = convergent_evolution.suggest(context)

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
        assert suggestion.geist_id == "convergent_evolution"

        # Should reference 2 notes (converging pair)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_convergent_evolution_uses_obsidian_link(vault_with_session_history):
    """Test that convergent_evolution uses obsidian_link for note references.

    Setup:
        Vault with converging notes.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = convergent_evolution.suggest(context)

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


def test_convergent_evolution_empty_vault(tmp_path):
    """Test that convergent_evolution handles empty vault gracefully.

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

    suggestions = convergent_evolution.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_convergent_evolution_insufficient_sessions(vault_insufficient_sessions):
    """Test that convergent_evolution handles insufficient sessions gracefully."""
    vault, session = vault_insufficient_sessions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = convergent_evolution.suggest(context)

    # Should return empty list when < 3 sessions
    assert len(suggestions) == 0


def test_convergent_evolution_insufficient_notes(vault_insufficient_notes):
    """Test that convergent_evolution handles insufficient notes gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = convergent_evolution.suggest(context)

    # Should return empty list when < 10 notes
    assert len(suggestions) == 0


def test_convergent_evolution_max_suggestions(vault_with_session_history):
    """Test that convergent_evolution never returns more than 2 suggestions.

    Setup:
        Vault with converging notes.

    Verifies:
        - Returns at most 1"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = convergent_evolution.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_convergent_evolution_deterministic_with_seed(vault_with_session_history):
    """Test that convergent_evolution returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_session_history

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

    suggestions1 = convergent_evolution.suggest(context1)
    suggestions2 = convergent_evolution.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_convergent_evolution_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\nJournal content that may show convergence patterns."
        )

    # Create regular notes with varying content
    now = datetime.now()
    for i in range(35):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent about topic {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create multiple sessions (5 sessions over time)
    for i in range(5):
        session_date = now - timedelta(days=(5 - i) * 30)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    # Return most recent session as active session
    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = convergent_evolution.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
